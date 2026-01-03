#!/usr/bin/env python3
# efio_daemon/resilience.py
# Circuit Breakers, Retry Logic, and Resilience Utilities

import time
import threading
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum

# ============================================
# Circuit Breaker States
# ============================================
class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, block calls
    HALF_OPEN = "half_open"  # Testing recovery

# ============================================
# Circuit Breaker Implementation
# ============================================
class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, block all requests
    - HALF_OPEN: Testing if service recovered
    
    Usage:
        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            expected_exception=Exception
        )
        
        @breaker.call
        def risky_operation():
            # Your code here
            pass
    """
    
    def __init__(
        self, 
        failure_threshold=5, 
        timeout=60, 
        expected_exception=Exception,
        name="unnamed"
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = threading.RLock()
    
    def call(self, func):
        """Decorator to wrap functions with circuit breaker"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                if self.state == CircuitState.OPEN:
                    if self._should_attempt_reset():
                        print(f"🔄 [{self.name}] Circuit breaker: HALF_OPEN (testing recovery)")
                        self.state = CircuitState.HALF_OPEN
                    else:
                        time_remaining = self.timeout - (time.time() - self.last_failure_time)
                        print(f"🚫 [{self.name}] Circuit breaker: OPEN (retry in {int(time_remaining)}s)")
                        raise Exception(f"Circuit breaker open for {self.name}")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self):
        """Check if enough time has passed to test recovery"""
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.timeout
    
    def _on_success(self):
        """Handle successful call"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                print(f"✅ [{self.name}] Circuit breaker: CLOSED (service recovered)")
            self.failure_count = 0
            self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    print(f"⚠️ [{self.name}] Circuit breaker: OPEN ({self.failure_count} failures)")
                self.state = CircuitState.OPEN
            else:
                print(f"⚠️ [{self.name}] Failure {self.failure_count}/{self.failure_threshold}")
    
    def reset(self):
        """Manually reset circuit breaker"""
        with self.lock:
            print(f"🔄 [{self.name}] Circuit breaker: Manual reset")
            self.failure_count = 0
            self.state = CircuitState.CLOSED
            self.last_failure_time = None
    
    def get_state(self):
        """Get current state as dict"""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "last_failure": datetime.fromtimestamp(self.last_failure_time).isoformat() 
                    if self.last_failure_time else None
            }

# ============================================
# Retry Decorator with Exponential Backoff
# ============================================
def retry_with_backoff(
    max_retries=3, 
    initial_delay=1, 
    max_delay=30, 
    exponential_base=2,
    expected_exception=Exception
):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        expected_exception: Exception type to catch and retry
    
    Usage:
        @retry_with_backoff(max_retries=3, initial_delay=1)
        def flaky_operation():
            # Your code here
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except expected_exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        print(f"❌ {func.__name__}: All {max_retries} retries failed")
                        raise
                    
                    wait_time = min(delay, max_delay)
                    print(f"⚠️ {func.__name__}: Retry {attempt + 1}/{max_retries} in {wait_time}s (error: {str(e)[:50]})")
                    time.sleep(wait_time)
                    delay *= exponential_base
            
            raise last_exception
        
        return wrapper
    return decorator

# ============================================
# Timeout Decorator
# ============================================
def timeout(seconds=10):
    """
    Timeout decorator using threading.
    
    WARNING: This creates a new thread for each call.
    Use sparingly for critical operations only.
    
    Usage:
        @timeout(seconds=5)
        def slow_operation():
            time.sleep(10)  # Will raise TimeoutError after 5s
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=seconds)
            
            if thread.is_alive():
                print(f"⏱️ {func.__name__}: Timeout after {seconds}s")
                raise TimeoutError(f"{func.__name__} timeout after {seconds}s")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        
        return wrapper
    return decorator

# ============================================
# Health Check Status
# ============================================
class HealthStatus:
    """Track health status of system components"""
    
    def __init__(self):
        self.components = {}
        self.lock = threading.RLock()
    
    def update(self, component, status, message="", details=None):
        """
        Update health status for a component.
        
        Args:
            component: Component name (e.g., "mqtt", "modbus", "gpio")
            status: "healthy" | "degraded" | "unhealthy"
            message: Human-readable status message
            details: Optional dict with additional info
        """
        with self.lock:
            self.components[component] = {
                "status": status,
                "message": message,
                "last_update": datetime.now().isoformat(),
                "details": details or {}
            }
    
    def get_status(self, component=None):
        """Get health status for component or all components"""
        with self.lock:
            if component:
                return self.components.get(component, {
                    "status": "unknown",
                    "message": "Component not registered"
                })
            return dict(self.components)
    
    def is_healthy(self, component=None):
        """Check if component (or entire system) is healthy"""
        with self.lock:
            if component:
                comp = self.components.get(component, {})
                return comp.get("status") == "healthy"
            
            # Check all components
            return all(
                c.get("status") == "healthy" 
                for c in self.components.values()
            )
    
    def get_overall_status(self):
        """Get overall system health status"""
        with self.lock:
            if not self.components:
                return "unknown"
            
            statuses = [c.get("status") for c in self.components.values()]
            
            if all(s == "healthy" for s in statuses):
                return "healthy"
            elif any(s == "unhealthy" for s in statuses):
                return "unhealthy"
            else:
                return "degraded"

# ============================================
# Global Health Status Instance
# ============================================
health_status = HealthStatus()

# ============================================
# Example Usage
# ============================================
if __name__ == "__main__":
    # Example 1: Circuit Breaker
    print("\n=== Circuit Breaker Example ===")
    
    mqtt_breaker = CircuitBreaker(
        failure_threshold=3,
        timeout=10,
        name="MQTT"
    )
    
    @mqtt_breaker.call
    def connect_mqtt():
        import random
        if random.random() < 0.7:  # 70% failure rate
            raise ConnectionError("MQTT connection failed")
        return "Connected"
    
    for i in range(10):
        try:
            result = connect_mqtt()
            print(f"✅ Attempt {i+1}: {result}")
        except Exception as e:
            print(f"❌ Attempt {i+1}: {e}")
        time.sleep(1)
    
    # Example 2: Retry with Backoff
    print("\n=== Retry with Backoff Example ===")
    
    @retry_with_backoff(max_retries=3, initial_delay=1)
    def flaky_operation():
        import random
        if random.random() < 0.7:
            raise ValueError("Random failure")
        return "Success"
    
    try:
        result = flaky_operation()
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Final error: {e}")
    
    # Example 3: Health Status
    print("\n=== Health Status Example ===")
    
    health_status.update("mqtt", "healthy", "Connected to broker")
    health_status.update("modbus", "degraded", "1 device offline")
    health_status.update("gpio", "healthy", "All I/O operational")
    
    print(f"Overall: {health_status.get_overall_status()}")
    print(f"MQTT: {health_status.is_healthy('mqtt')}")
    print(f"Status: {health_status.get_status()}")