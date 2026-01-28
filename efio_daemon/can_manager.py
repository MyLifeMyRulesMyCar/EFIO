#!/usr/bin/env python3
# efio_daemon/can_manager.py
# CAN Bus Manager with MCP2515 integration

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
            'last_seen': self.last_seen
        }


class CANManager:
    """
    Thread-safe CAN bus manager with:
    - MCP2515 controller management
    - Message queue and routing
    - Device registry
    - Message logging
    - Circuit breaker for error handling
    """
    
    def __init__(self, spi_bus=2, spi_device=0, bitrate=125000, crystal=8000000):
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.bitrate = bitrate
        self.crystal = crystal  # Add crystal frequency support
        
        # Controller
        self.controller: Optional[MCP2515] = None
        self.connected = False
        
        # Device registry
        self.devices: Dict[str, CANDevice] = {}
        self._lock = threading.RLock()
        
        # Message handling
        self.rx_queue = queue.Queue(maxsize=1000)
        self.message_log = deque(maxlen=1000)  # Keep last 1000 messages
        self.subscribers: List[Callable] = []
        
        # Threads
        self.rx_thread = None
        self.running = False
        
        # Statistics
        self.stats = {
            'rx_total': 0,
            'tx_total': 0,
            'errors': 0,
            'overruns': 0,
            'start_time': None
        }
        
        # Circuit breaker for SPI failures
        self.breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30,
            expected_exception=Exception,
            name="CAN-SPI"
        )
        
        print("✅ CANManager initialized")
    
    # ================================
    # Connection Management
    # ================================
    
    @retry_with_backoff(max_retries=3, initial_delay=1)
    def connect(self):
        """Connect to MCP2515 controller"""
        with self._lock:
            if self.connected:
                print("⚠️ CAN already connected")
                return True
            
            try:
                print(f"🔌 Connecting to MCP2515 (SPI{self.spi_bus}.{self.spi_device}, {self.bitrate} bps)...")
                
                # Create controller instance
                self.controller = MCP2515(
                    spi_bus=self.spi_bus,
                    spi_device=self.spi_device,
                    speed=1000000,  # 1 MHz SPI speed
                    crystal=self.crystal
                )
                
                # Initialize with bitrate
                if not self.controller.init(bitrate=self.bitrate):
                    raise RuntimeError("MCP2515 initialization failed")
                
                self.connected = True
                self.stats['start_time'] = datetime.now()
                
                # Start receive thread
                self._start_rx_thread()
                
                # Update health status
                health_status.update('can', 'healthy', f'Connected at {self.bitrate} bps')
                
                print(f"✅ CAN connected successfully")
                return True
                
            except Exception as e:
                self.connected = False
                health_status.update('can', 'unhealthy', f'Connection failed: {str(e)}')
                print(f"❌ CAN connection failed: {e}")
                raise
    
    def disconnect(self):
        """Disconnect from controller"""
        with self._lock:
            if not self.connected:
                return
            
            print("🔌 Disconnecting CAN...")
            
            # Stop threads
            self.running = False
            if self.rx_thread:
                self.rx_thread.join(timeout=2)
            
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
    # Message Reception (Background Thread)
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
                
                # Check for available messages
                if self.controller.available():
                    msg = self.controller.read_message()
                    
                    if msg:
                        # Reset error counter
                        consecutive_errors = 0
                        
                        # Process message
                        self._handle_rx_message(msg)
                    
                else:
                    time.sleep(0.001)  # Small delay when no messages
                
            except Exception as e:
                consecutive_errors += 1
                self.stats['errors'] += 1
                
                if consecutive_errors >= max_errors:
                    print(f"❌ Too many CAN RX errors ({consecutive_errors})")
                    health_status.update('can', 'unhealthy', 'Too many RX errors')
                    self.disconnect()
                    break
                
                print(f"⚠️ CAN RX error: {e}")
                time.sleep(0.1)
        
        print("🛑 CAN RX loop stopped")
    
    def _handle_rx_message(self, msg: CANMessage):
        """Process received CAN message"""
        try:
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
            
            # Update device statistics
            with self._lock:
                for device in self.devices.values():
                    if device.can_id == msg.can_id and device.enabled:
                        device.rx_count += 1
                        device.last_seen = datetime.now().isoformat()
            
            # Notify subscribers (WebSocket, MQTT, etc.)
            for subscriber in self.subscribers:
                try:
                    subscriber(log_entry)
                except Exception as e:
                    print(f"⚠️ Subscriber error: {e}")
            
            # Add to queue for polling
            try:
                self.rx_queue.put_nowait(log_entry)
            except queue.Full:
                self.stats['overruns'] += 1
        
        except Exception as e:
            print(f"❌ Error handling RX message: {e}")
    
    # ================================
    # Message Transmission
    # ================================
    
    def send_message(self, can_id: int, data: List[int], extended: bool = False):
        """
        Send CAN message
        
        Args:
            can_id: CAN identifier
            data: List of up to 8 bytes
            extended: Extended frame format
            
        Returns:
            bool: Success status
        """
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
            @self.breaker.call
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
                print(f"🗑️ Removed CAN device: {device.name}")
                return True
            return False
    
    def get_device(self, device_id: str) -> Optional[CANDevice]:
        """Get device by ID"""
        with self._lock:
            return self.devices.get(device_id)
    
    def get_all_devices(self) -> List[Dict]:
        """Get all devices as dict list"""
        with self._lock:
            return [dev.to_dict() for dev in self.devices.values()]
    
    # ================================
    # Message Retrieval
    # ================================
    
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
    
    # ================================
    # Status & Statistics
    # ================================
    
    def get_status(self) -> Dict:
        """Get current status"""
        with self._lock:
            uptime = None
            if self.stats['start_time']:
                uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            
            return {
                'connected': self.connected,
                'bitrate': self.bitrate,
                'devices_count': len(self.devices),
                'rx_total': self.stats['rx_total'],
                'tx_total': self.stats['tx_total'],
                'errors': self.stats['errors'],
                'overruns': self.stats['overruns'],
                'uptime': uptime,
                'circuit_breaker': self.breaker.get_state()
            }
    
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
                'start_time': datetime.now() if self.connected else None
            }
            
            # Reset device counters
            for device in self.devices.values():
                device.rx_count = 0
                device.tx_count = 0
        
        print("🔄 CAN statistics reset")


# ================================
# Global Instance
# ================================
can_manager = CANManager()


if __name__ == "__main__":
    # Test code
    print("=" * 60)
    print("CAN Manager Test")
    print("=" * 60)
    
    try:
        # Connect
        can_manager.connect()
        
        # Add test device
        device = CANDevice(
            device_id="test_001",
            name="Test ECU",
            can_id=0x0F6
        )
        can_manager.add_device(device)
        
        # Send test message
        can_manager.send_message(
            can_id=0x0F6,
            data=[0x8E, 0x87, 0x32, 0xFA, 0x26, 0x8E, 0xBE, 0x86]
        )
        
        # Wait and receive
        time.sleep(2)
        
        # Get status
        status = can_manager.get_status()
        print(f"\nStatus: {status}")
        
        # Get recent messages
        messages = can_manager.get_recent_messages(10)
        print(f"\nRecent messages: {len(messages)}")
        for msg in messages:
            print(f"  {msg}")
        
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        can_manager.disconnect()
        print("Test complete")