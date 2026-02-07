#!/usr/bin/env python3
# efio_daemon/can_manager.py - OPTIMIZED VERSION
# CAN Bus Manager with single-count timeout detection

import threading
import time
import queue
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional, Callable
import sys
import os

# Import your existing MCP2515 driver
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp2515_driver import MCP2515, CANMessage

from efio_daemon.resilience import CircuitBreaker, retry_with_backoff, health_status


class CANDevice:
    """Represents a CAN device configuration"""
    def __init__(self, device_id: str, name: str, can_id: int, 
                 extended: bool = False, enabled: bool = True):
        self.id = device_id
        self.name = name
        self.can_id = can_id
        self.extended = extended
        self.enabled = enabled
        self.messages = []  # Message definitions
        self.rx_count = 0
        self.tx_count = 0
        self.last_seen = None
        self.last_rx_time = None
        self.timeout_threshold = 30
        self._timeout_logged = False  # Track if timeout already logged
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'can_id': self.can_id,
            'extended': self.extended,
            'enabled': self.enabled,
            'messages': self.messages,
            'rx_count': self.rx_count,
            'tx_count': self.tx_count,
            'last_seen': self.last_seen,
            'last_rx_time': self.last_rx_time,
            'timeout_threshold': self.timeout_threshold
        }
    
    def is_alive(self) -> bool:
        """Check if device is considered alive based on recent activity"""
        if self.last_rx_time is None:
            return False
        
        time_since_rx = time.time() - self.last_rx_time
        return time_since_rx < self.timeout_threshold


class CANManager:
    """
    Enhanced CAN bus manager with optimized disconnection detection
    """
    
    def __init__(self, spi_bus=2, spi_device=0, bitrate=125000, crystal=8000000):
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.bitrate = bitrate
        self.crystal = crystal
        
        # Controller
        self.controller: Optional[MCP2515] = None
        self.connected = False
        
        # Device registry
        self.devices: Dict[str, CANDevice] = {}
        self._lock = threading.RLock()
        
        # Message handling
        self.rx_queue = queue.Queue(maxsize=1000)
        self.message_log = deque(maxlen=1000)
        self.subscribers: List[Callable] = []
        
        # Threads
        self.rx_thread = None
        self.liveness_thread = None
        self.running = False
        
        # Statistics
        self.stats = {
            'rx_total': 0,
            'tx_total': 0,
            'errors': 0,
            'overruns': 0,
            'start_time': None,
            'hardware_failures': 0,
            'device_timeouts': 0,  # Counts unique timeout events only
            'auto_cleanups': 0
        }
        
        # Circuit breaker for SPI/hardware failures
        self.hw_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30,
            expected_exception=Exception,
            name="CAN-Hardware"
        )
        
        # Per-device circuit breakers
        self.device_breakers: Dict[str, CircuitBreaker] = {}
        
        print("✅ CANManager initialized (with optimized disconnection detection)")
    
    # ================================
    # Connection Management
    # ================================
    
    @retry_with_backoff(max_retries=3, initial_delay=1)
    def connect(self):
        """Connect to MCP2515 controller with retry and circuit breaker"""
        with self._lock:
            if self.connected:
                print("⚠️ CAN already connected")
                return True
            
            try:
                print(f"🔌 Connecting to MCP2515 (SPI{self.spi_bus}.{self.spi_device}, {self.bitrate} bps)...")
                
                # Wrap hardware access in circuit breaker
                @self.hw_breaker.call
                def _hw_connect():
                    controller = MCP2515(
                        spi_bus=self.spi_bus,
                        spi_device=self.spi_device,
                        speed=1000000,
                        crystal=self.crystal
                    )
                    
                    if not controller.init(bitrate=self.bitrate):
                        raise RuntimeError("MCP2515 initialization failed")
                    
                    return controller
                
                self.controller = _hw_connect()
                self.connected = True
                self.stats['start_time'] = datetime.now()
                
                # Start threads
                self._start_rx_thread()
                self._start_liveness_thread()
                
                health_status.update('can', 'healthy', f'Connected at {self.bitrate} bps')
                
                print(f"✅ CAN connected successfully")
                return True
                
            except Exception as e:
                self.connected = False
                self.stats['hardware_failures'] += 1
                health_status.update('can', 'unhealthy', f'Connection failed: {str(e)}')
                print(f"❌ CAN connection failed: {e}")
                raise
    
    def disconnect(self):
        """Disconnect from controller and cleanup"""
        with self._lock:
            if not self.connected:
                return
            
            print("🔌 Disconnecting CAN...")
            
            # Stop threads
            self.running = False
            
            if self.rx_thread:
                self.rx_thread.join(timeout=2)
            
            if self.liveness_thread:
                self.liveness_thread.join(timeout=2)
            
            # Close controller
            if self.controller:
                try:
                    self.controller.close()
                except:
                    pass
                self.controller = None
            
            self.connected = False
            health_status.update('can', 'degraded', 'Disconnected')
            print("✅ CAN disconnected")
    
    # ================================
    # Hardware Health Monitoring
    # ================================
    
    def _check_hardware_health(self) -> bool:
        """Check if MCP2515 hardware is still responsive"""
        if not self.controller:
            return False
        
        try:
            @self.hw_breaker.call
            def _read_status():
                return self.controller.read_register(0x0E)  # CANSTAT
            
            status = _read_status()
            return True
            
        except Exception as e:
            print(f"⚠️ Hardware health check failed: {e}")
            self.stats['hardware_failures'] += 1
            return False
    
    def _cleanup_on_hardware_failure(self, reason: str):
        """Cleanup when hardware is disconnected"""
        print(f"🔧 CAN hardware cleanup triggered: {reason}")
        
        try:
            # Mark all devices as disconnected
            with self._lock:
                for device in self.devices.values():
                    device.last_rx_time = None
                    device.last_seen = None
            
            # Disconnect gracefully
            self.disconnect()
            
            # Update stats
            self.stats['auto_cleanups'] += 1
            
            # Update health status
            health_status.update(
                'can', 
                'unhealthy', 
                f'Hardware disconnected: {reason}'
            )
            
            print(f"✅ Cleanup complete (reason: {reason})")
            
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
    
    # ================================
    # OPTIMIZED: Device Liveness Monitoring
    # ================================
    
    def _start_liveness_thread(self):
        """Start background thread to monitor device timeouts"""
        if self.liveness_thread and self.liveness_thread.is_alive():
            return
        
        self.liveness_thread = threading.Thread(
            target=self._liveness_loop,
            name="CAN-Liveness",
            daemon=True
        )
        self.liveness_thread.start()
        print("🔄 CAN liveness monitoring started")
    
    def _liveness_loop(self):
        """
        Background loop to detect device disconnections.
        OPTIMIZED: Prevents repeated timeout logging
        """
        print("📡 CAN liveness loop started")
        check_interval = 5  # Check every 5 seconds
        
        while self.running:
            try:
                # Check hardware health first
                if not self._check_hardware_health():
                    print("❌ Hardware health check failed!")
                    self._cleanup_on_hardware_failure("Hardware unresponsive")
                    break
                
                # Check each device for timeouts
                with self._lock:
                    current_time = time.time()
                    
                    for device in self.devices.values():
                        if not device.enabled:
                            continue
                        
                        # Skip if never seen
                        if device.last_rx_time is None:
                            continue
                        
                        # Check for timeout
                        time_since_rx = current_time - device.last_rx_time
                        
                        if time_since_rx > device.timeout_threshold:
                            # Device is timed out
                            self._handle_device_timeout(device)
                        else:
                            # Device is alive - reset timeout flag
                            if device._timeout_logged:
                                device._timeout_logged = False
                                print(f"✅ Device {device.name} recovered (receiving messages)")
                
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"❌ Liveness loop error: {e}")
                time.sleep(check_interval)
        
        print("🛑 CAN liveness loop stopped")
    
    # ================================
    # OPTIMIZED: Timeout Handler
    # ================================
    
    def _handle_device_timeout(self, device: CANDevice):
        """
        Handle device timeout - OPTIMIZED VERSION
        Only counts unique timeout events (not repeated checks)
        """
        try:
            # Only increment counter and log on FIRST detection
            if not device._timeout_logged:
                self.stats['device_timeouts'] += 1  # Count once per timeout event
                device._timeout_logged = True
                
                time_since = time.time() - device.last_rx_time
                print(f"🔧 Device {device.name} timeout ({time_since:.1f}s since last RX)")
                print(f"   Threshold: {device.timeout_threshold}s | Total timeout events: {self.stats['device_timeouts']}")
            
            # Still update circuit breaker on each check (for failure tracking)
            if device.id not in self.device_breakers:
                self.device_breakers[device.id] = CircuitBreaker(
                    failure_threshold=3,
                    timeout=60,
                    name=f"CAN-{device.name}"
                )
            
            breaker = self.device_breakers[device.id]
            breaker._on_failure()
            
            # Update health status
            health_status.update(
                'can',
                'degraded',
                f'Device {device.name} timeout',
                details={'device_id': device.id, 'can_id': device.can_id}
            )
            
        except Exception as e:
            print(f"❌ Error handling device timeout: {e}")
    
    # ================================
    # Message Reception (Enhanced)
    # ================================
    
    def _start_rx_thread(self):
        """Start background thread for receiving messages"""
        if self.rx_thread and self.rx_thread.is_alive():
            return
        
        self.running = True
        self.rx_thread = threading.Thread(
            target=self._rx_loop,
            name="CAN-RX",
            daemon=True
        )
        self.rx_thread.start()
        print("🔄 CAN RX thread started")
    
    def _rx_loop(self):
        """Background loop to receive CAN messages"""
        print("📡 CAN RX loop started")
        consecutive_errors = 0
        max_errors = 10
        
        while self.running:
            try:
                if not self.connected or not self.controller:
                    time.sleep(0.1)
                    continue
                
                # Check for available messages (wrapped in circuit breaker)
                @self.hw_breaker.call
                def _check_and_read():
                    if self.controller.available():
                        return self.controller.read_message()
                    return None
                
                msg = _check_and_read()
                
                if msg:
                    # Reset error counter on successful read
                    consecutive_errors = 0
                    
                    # Process message
                    self._handle_rx_message(msg)
                else:
                    time.sleep(0.001)
                
            except Exception as e:
                consecutive_errors += 1
                self.stats['errors'] += 1
                
                if consecutive_errors >= max_errors:
                    print(f"❌ Too many CAN RX errors ({consecutive_errors})")
                    self._cleanup_on_hardware_failure(f"RX errors: {consecutive_errors}")
                    break
                
                print(f"⚠️ CAN RX error: {e}")
                time.sleep(0.1)
        
        print("🛑 CAN RX loop stopped")
    
    def _handle_rx_message(self, msg: CANMessage):
        """Process received CAN message (enhanced with device tracking)"""
        try:
            current_time = time.time()
            
            # Update statistics
            self.stats['rx_total'] += 1
            
            # Create log entry
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'direction': 'RX',
                'can_id': msg.can_id,
                'dlc': msg.dlc,
                'data': list(msg.data[:msg.dlc]),
                'extended': msg.extended
            }
            
            # Add to log
            self.message_log.append(log_entry)
            
            # Update device statistics and liveness
            with self._lock:
                for device in self.devices.values():
                    if device.can_id == msg.can_id and device.enabled:
                        device.rx_count += 1
                        device.last_seen = datetime.now().isoformat()
                        device.last_rx_time = current_time
                        
                        # Reset circuit breaker on successful RX
                        if device.id in self.device_breakers:
                            self.device_breakers[device.id]._on_success()
            
            # Notify subscribers
            for subscriber in self.subscribers:
                try:
                    subscriber(log_entry)
                except Exception as e:
                    print(f"⚠️ Subscriber error: {e}")
            
            # Add to queue
            try:
                self.rx_queue.put_nowait(log_entry)
            except queue.Full:
                self.stats['overruns'] += 1
        
        except Exception as e:
            print(f"❌ Error handling RX message: {e}")
    
    # ================================
    # Message Transmission (Enhanced)
    # ================================
    
    def send_message(self, can_id: int, data: List[int], extended: bool = False):
        """Send CAN message with circuit breaker protection"""
        if not self.connected or not self.controller:
            raise RuntimeError("CAN not connected")
        
        if len(data) > 8:
            raise ValueError("CAN data must be ≤ 8 bytes")
        
        try:
            # Create message
            msg = CANMessage(
                can_id=can_id,
                data=data,
                dlc=len(data),
                extended=extended
            )
            
            # Send with circuit breaker protection
            @self.hw_breaker.call
            def _send():
                return self.controller.send_message(msg)
            
            success = _send()
            
            if success:
                # Update statistics
                self.stats['tx_total'] += 1
                
                # Log message
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'direction': 'TX',
                    'can_id': can_id,
                    'dlc': len(data),
                    'data': data,
                    'extended': extended
                }
                self.message_log.append(log_entry)
                
                # Update device TX counter
                with self._lock:
                    for device in self.devices.values():
                        if device.can_id == can_id:
                            device.tx_count += 1
                
                print(f"✅ CAN TX: ID=0x{can_id:03X}, Data={[f'{b:02X}' for b in data]}")
                return True
            else:
                print(f"❌ CAN TX failed")
                return False
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"❌ CAN send error: {e}")
            
            # Check if this is a hardware failure
            if not self._check_hardware_health():
                self._cleanup_on_hardware_failure(f"TX error: {str(e)}")
            
            raise
    
    # ================================
    # Device Management
    # ================================
    
    def add_device(self, device: CANDevice):
        """Register a CAN device"""
        with self._lock:
            self.devices[device.id] = device
            print(f"✅ Added CAN device: {device.name} (ID=0x{device.can_id:03X})")
    
    def remove_device(self, device_id: str):
        """Remove a CAN device"""
        with self._lock:
            if device_id in self.devices:
                device = self.devices.pop(device_id)
                
                # Clean up circuit breaker
                if device_id in self.device_breakers:
                    del self.device_breakers[device_id]
                
                print(f"🗑️ Removed CAN device: {device.name}")
                return True
            return False
    
    def get_device(self, device_id: str) -> Optional[CANDevice]:
        """Get device by ID"""
        with self._lock:
            return self.devices.get(device_id)
    
    def get_all_devices(self) -> List[Dict]:
        """Get all devices as dict list (with liveness status)"""
        with self._lock:
            devices = []
            for dev in self.devices.values():
                dev_dict = dev.to_dict()
                dev_dict['alive'] = dev.is_alive()
                devices.append(dev_dict)
            return devices
    
    # ================================
    # Status & Statistics (Enhanced)
    # ================================
    
    def get_status(self) -> Dict:
        """Get current status with enhanced metrics"""
        with self._lock:
            uptime = None
            if self.stats['start_time']:
                uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            
            # Count alive devices
            alive_devices = sum(1 for d in self.devices.values() if d.is_alive())
            
            return {
                'connected': self.connected,
                'bitrate': self.bitrate,
                'devices_count': len(self.devices),
                'alive_devices': alive_devices,
                'rx_total': self.stats['rx_total'],
                'tx_total': self.stats['tx_total'],
                'errors': self.stats['errors'],
                'overruns': self.stats['overruns'],
                'hardware_failures': self.stats['hardware_failures'],
                'device_timeouts': self.stats['device_timeouts'],  # Unique events only
                'auto_cleanups': self.stats['auto_cleanups'],
                'uptime': uptime,
                'hardware_circuit_breaker': self.hw_breaker.get_state()
            }
    
    def get_recent_messages(self, count: int = 100) -> List[Dict]:
        """Get recent messages from log"""
        return list(self.message_log)[-count:]
    
    def subscribe(self, callback: Callable):
        """Subscribe to message notifications"""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from notifications"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def clear_logs(self):
        """Clear message log"""
        self.message_log.clear()
        print("🗑️ CAN message log cleared")
    
    def reset_statistics(self):
        """Reset statistics counters"""
        with self._lock:
            self.stats = {
                'rx_total': 0,
                'tx_total': 0,
                'errors': 0,
                'overruns': 0,
                'hardware_failures': 0,
                'device_timeouts': 0,
                'auto_cleanups': 0,
                'start_time': datetime.now() if self.connected else None
            }
            
            # Reset device counters
            for device in self.devices.values():
                device.rx_count = 0
                device.tx_count = 0
                device._timeout_logged = False  # Reset timeout flag
        
        print("🔄 CAN statistics reset")


# Global instance
can_manager = CANManager()