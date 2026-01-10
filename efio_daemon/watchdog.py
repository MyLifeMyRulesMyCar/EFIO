#!/usr/bin/env python3
# efio_daemon/watchdog.py
# Software Watchdog Timer for system monitoring and auto-recovery

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)

class WatchdogTimer:
    """
    Software watchdog timer that monitors system health.
    
    Features:
    - Configurable timeout period
    - Automatic thread monitoring
    - Graceful degradation on failures
    - Health check integration
    
    Usage:
        watchdog = WatchdogTimer(timeout=60)
        watchdog.start()
        
        # In your main loop:
        watchdog.feed()  # Reset watchdog
        
        # Register subsystems:
        watchdog.register_component("mqtt", check_mqtt_health)
    """
    
    def __init__(self, timeout: int = 60, on_timeout: Optional[Callable] = None):
        """
        Args:
            timeout: Timeout in seconds before triggering action
            on_timeout: Callback function when timeout occurs
        """
        self.timeout = timeout
        self.on_timeout = on_timeout or self._default_timeout_handler
        
        self.last_feed = time.time()
        self.running = False
        self.thread = None
        self._lock = threading.RLock()
        
        # Component health tracking
        self.components: Dict[str, Dict] = {}
        self.timeout_count = 0
        
        logger.info(f"Watchdog initialized (timeout: {timeout}s)")
    
    def feed(self):
        """Feed the watchdog (reset timer)"""
        with self._lock:
            self.last_feed = time.time()
    
    def register_component(self, name: str, health_check: Callable) -> None:
        """
        Register a system component for health monitoring.
        
        Args:
            name: Component identifier (e.g., "mqtt", "gpio", "modbus")
            health_check: Function that returns True if healthy
        """
        with self._lock:
            self.components[name] = {
                "check": health_check,
                "last_check": None,
                "status": "unknown",
                "failures": 0
            }
        logger.info(f"Watchdog: Registered component '{name}'")
    
    def check_component_health(self, name: str) -> bool:
        """
        Check health of a specific component.
        
        Returns:
            True if healthy, False otherwise
        """
        with self._lock:
            if name not in self.components:
                logger.warning(f"Unknown component: {name}")
                return False
            
            component = self.components[name]
            
            try:
                is_healthy = component["check"]()
                component["status"] = "healthy" if is_healthy else "unhealthy"
                component["last_check"] = datetime.now().isoformat()
                
                if is_healthy:
                    component["failures"] = 0
                else:
                    component["failures"] += 1
                    logger.warning(
                        f"Component '{name}' unhealthy "
                        f"(failures: {component['failures']})"
                    )
                
                return is_healthy
                
            except Exception as e:
                component["status"] = "error"
                component["failures"] += 1
                logger.error(f"Health check failed for '{name}': {e}")
                return False
    
    def check_all_components(self) -> Dict[str, bool]:
        """
        Check health of all registered components.
        
        Returns:
            Dict of component_name: is_healthy
        """
        results = {}
        for name in self.components.keys():
            results[name] = self.check_component_health(name)
        return results
    
    def get_health_report(self) -> Dict:
        """
        Get comprehensive health report.
        
        Returns:
            Dict with watchdog and component status
        """
        with self._lock:
            time_since_feed = time.time() - self.last_feed
            
            return {
                "watchdog": {
                    "running": self.running,
                    "timeout": self.timeout,
                    "last_feed": datetime.fromtimestamp(self.last_feed).isoformat(),
                    "time_since_feed": round(time_since_feed, 2),
                    "timeout_count": self.timeout_count,
                    "status": "healthy" if time_since_feed < self.timeout else "timeout"
                },
                "components": {
                    name: {
                        "status": comp["status"],
                        "last_check": comp["last_check"],
                        "failures": comp["failures"]
                    }
                    for name, comp in self.components.items()
                }
            }
    
    def _default_timeout_handler(self):
        """Default action when watchdog timeout occurs"""
        logger.critical("⚠️ WATCHDOG TIMEOUT! System may be hung.")
        logger.critical(f"   Last feed: {datetime.fromtimestamp(self.last_feed)}")
        logger.critical(f"   Timeout count: {self.timeout_count}")
        
        # Get health status of all components
        health = self.check_all_components()
        unhealthy = [name for name, status in health.items() if not status]
        
        if unhealthy:
            logger.critical(f"   Unhealthy components: {', '.join(unhealthy)}")
        
        # In production, this could trigger:
        # - System restart
        # - Alert to monitoring system
        # - Graceful shutdown and recovery
        
        logger.critical("   Recommended action: Restart system")
    
    def _watchdog_loop(self):
        """Background monitoring loop"""
        logger.info("Watchdog monitoring started")
        
        while self.running:
            try:
                with self._lock:
                    time_since_feed = time.time() - self.last_feed
                    
                    if time_since_feed >= self.timeout:
                        self.timeout_count += 1
                        logger.warning(
                            f"Watchdog timeout! "
                            f"({time_since_feed:.1f}s > {self.timeout}s)"
                        )
                        
                        # Trigger timeout handler
                        self.on_timeout()
                        
                        # Reset timer to prevent continuous triggering
                        self.last_feed = time.time()
                
                # Check component health every 10 seconds
                if int(time.time()) % 10 == 0:
                    self.check_all_components()
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Watchdog loop error: {e}")
                time.sleep(5)  # Back off on errors
    
    def start(self):
        """Start watchdog monitoring"""
        if self.running:
            logger.warning("Watchdog already running")
            return
        
        logger.info("Starting watchdog timer")
        self.running = True
        self.last_feed = time.time()
        
        self.thread = threading.Thread(
            target=self._watchdog_loop,
            name="WatchdogTimer",
            daemon=True
        )
        self.thread.start()
        
        logger.info("✅ Watchdog timer started")
    
    def stop(self):
        """Stop watchdog monitoring"""
        logger.info("Stopping watchdog timer")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("✅ Watchdog timer stopped")


# ============================================
# Example Health Check Functions
# ============================================

def check_gpio_health() -> bool:
    """Example GPIO health check"""
    try:
        from efio_daemon.state import state
        # Check if GPIO is in simulation mode
        if state["simulation"]:
            return False  # Not ideal, but not critical
        return True
    except Exception:
        return False


def check_mqtt_health() -> bool:
    """Example MQTT health check"""
    try:
        # Check if MQTT client is connected
        # This would integrate with your actual MQTT client
        return True  # Placeholder
    except Exception:
        return False


def check_modbus_health() -> bool:
    """Example Modbus health check"""
    try:
        # Check if any Modbus devices are connected
        from api.modbus_device_routes import active_connections
        return len(active_connections) > 0
    except Exception:
        return False


# ============================================
# Integration Example
# ============================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create watchdog with 10 second timeout (for testing)
    watchdog = WatchdogTimer(timeout=10)
    
    # Register components
    watchdog.register_component("gpio", check_gpio_health)
    watchdog.register_component("mqtt", check_mqtt_health)
    watchdog.register_component("modbus", check_modbus_health)
    
    # Start monitoring
    watchdog.start()
    
    try:
        # Simulate main loop
        for i in range(30):
            print(f"Loop iteration {i}")
            
            # Feed watchdog every iteration
            watchdog.feed()
            
            # Simulate work
            time.sleep(1)
            
            # Get health report every 5 seconds
            if i % 5 == 0:
                report = watchdog.get_health_report()
                print(f"\nHealth Report: {report}\n")
        
        # Simulate watchdog timeout by not feeding
        print("\n⚠️ Simulating timeout (not feeding watchdog)...")
        time.sleep(15)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        watchdog.stop()
        print("Test complete")