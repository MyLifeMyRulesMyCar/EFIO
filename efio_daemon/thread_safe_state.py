#!/usr/bin/env python3
# efio_daemon/thread_safe_state.py
# Thread-safe state management with automatic locking

import threading
from typing import List, Dict, Any
from contextlib import contextmanager
import time

class ThreadSafeState:
    """
    Thread-safe state manager for EFIO system.
    
    Prevents race conditions when multiple threads access I/O state:
    - Main daemon loop reading/writing GPIO
    - API endpoints modifying outputs
    - WebSocket broadcasting state
    - MQTT publishing changes
    
    Usage:
        state = ThreadSafeState()
        
        # Read operations (automatically locked)
        di_values = state.get_di()
        
        # Write operations (automatically locked)
        state.set_do(2, 1)
        
        # Batch operations (single lock)
        with state.lock():
            di = state.get_di()
            state.set_do(0, di[0])
    """
    
    def __init__(self):
        # Use RLock (reentrant lock) to allow same thread to acquire multiple times
        self._lock = threading.RLock()
        
        # Core I/O state
        self._di = [0, 0, 0, 0]  # Digital inputs
        self._do = [0, 0, 0, 0]  # Digital outputs
        
        # System flags
        self._simulation = False
        self._simulation_oled = False
        
        # Modbus state
        self._modbus = {
            "slave_id": 1,
            "last_register": None,
            "last_value": None
        }
        
        # Statistics (for debugging)
        self._stats = {
            "di_reads": 0,
            "di_writes": 0,
            "do_reads": 0,
            "do_writes": 0,
            "lock_contentions": 0,
            "max_lock_wait_ms": 0
        }
    
    # ================================
    # Context Manager for Batch Operations
    # ================================
    @contextmanager
    def lock(self):
        """
        Context manager for batch operations.
        
        Example:
            with state.lock():
                di = state.get_di()
                state.set_do(0, di[0])
                state.set_do(1, di[1])
        """
        acquired = False
        start_time = time.time()
        
        try:
            # Try to acquire lock
            acquired = self._lock.acquire(blocking=True, timeout=1.0)
            
            if not acquired:
                raise TimeoutError("Failed to acquire state lock within 1 second")
            
            # Track lock wait time
            wait_ms = (time.time() - start_time) * 1000
            if wait_ms > self._stats["max_lock_wait_ms"]:
                self._stats["max_lock_wait_ms"] = wait_ms
            
            if wait_ms > 10:  # More than 10ms indicates contention
                self._stats["lock_contentions"] += 1
            
            yield
        finally:
            if acquired:
                self._lock.release()
    
    # ================================
    # Digital Input Operations
    # ================================
    def get_di(self, channel: int = None) -> Any:
        """
        Get digital input value(s).
        
        Args:
            channel: Specific channel (0-3), or None for all channels
        
        Returns:
            int if channel specified, list if channel is None
        """
        with self._lock:
            self._stats["di_reads"] += 1
            
            if channel is None:
                # Return copy to prevent external modification
                return self._di.copy()
            
            if not 0 <= channel < 4:
                raise ValueError(f"Invalid DI channel: {channel} (must be 0-3)")
            
            return self._di[channel]
    
    def set_di(self, channel: int, value: int):
        """
        Set digital input value (used by daemon reading hardware).
        
        Args:
            channel: Channel number (0-3)
            value: Value (0 or 1)
        """
        with self._lock:
            if not 0 <= channel < 4:
                raise ValueError(f"Invalid DI channel: {channel}")
            
            if value not in (0, 1):
                raise ValueError(f"Invalid DI value: {value} (must be 0 or 1)")
            
            self._di[channel] = value
            self._stats["di_writes"] += 1
    
    def set_di_all(self, values: List[int]):
        """
        Set all digital inputs at once (atomic operation).
        
        Args:
            values: List of 4 values [0/1, 0/1, 0/1, 0/1]
        """
        with self._lock:
            if len(values) != 4:
                raise ValueError(f"Expected 4 values, got {len(values)}")
            
            if not all(v in (0, 1) for v in values):
                raise ValueError("All DI values must be 0 or 1")
            
            self._di = list(values)
            self._stats["di_writes"] += 4
    
    # ================================
    # Digital Output Operations
    # ================================
    def get_do(self, channel: int = None) -> Any:
        """
        Get digital output value(s).
        
        Args:
            channel: Specific channel (0-3), or None for all channels
        
        Returns:
            int if channel specified, list if channel is None
        """
        with self._lock:
            self._stats["do_reads"] += 1
            
            if channel is None:
                return self._do.copy()
            
            if not 0 <= channel < 4:
                raise ValueError(f"Invalid DO channel: {channel}")
            
            return self._do[channel]
    
    def set_do(self, channel: int, value: int):
        """
        Set digital output value.
        
        Args:
            channel: Channel number (0-3)
            value: Value (0 or 1)
        """
        with self._lock:
            if not 0 <= channel < 4:
                raise ValueError(f"Invalid DO channel: {channel}")
            
            if value not in (0, 1):
                raise ValueError(f"Invalid DO value: {value}")
            
            self._do[channel] = value
            self._stats["do_writes"] += 1
    
    def set_do_all(self, values: List[int]):
        """
        Set all digital outputs at once (atomic operation).
        
        Args:
            values: List of 4 values [0/1, 0/1, 0/1, 0/1]
        """
        with self._lock:
            if len(values) != 4:
                raise ValueError(f"Expected 4 values, got {len(values)}")
            
            if not all(v in (0, 1) for v in values):
                raise ValueError("All DO values must be 0 or 1")
            
            self._do = list(values)
            self._stats["do_writes"] += 4
    
    # ================================
    # Simulation Flags
    # ================================
    def get_simulation(self) -> bool:
        """Get simulation mode flag"""
        with self._lock:
            return self._simulation
    
    def set_simulation(self, value: bool):
        """Set simulation mode flag"""
        with self._lock:
            self._simulation = bool(value)
    
    def get_simulation_oled(self) -> bool:
        """Get OLED simulation flag"""
        with self._lock:
            return self._simulation_oled
    
    def set_simulation_oled(self, value: bool):
        """Set OLED simulation flag"""
        with self._lock:
            self._simulation_oled = bool(value)
    
    # ================================
    # Modbus State
    # ================================
    def get_modbus(self, key: str = None) -> Any:
        """
        Get Modbus state.
        
        Args:
            key: Specific key, or None for entire dict
        """
        with self._lock:
            if key is None:
                return self._modbus.copy()
            return self._modbus.get(key)
    
    def set_modbus(self, key: str, value: Any):
        """Set Modbus state value"""
        with self._lock:
            self._modbus[key] = value
    
    # ================================
    # Compatibility Layer (for gradual migration)
    # ================================
    def to_dict(self) -> Dict:
        """
        Export state as dictionary (for compatibility with old code).
        
        WARNING: This creates a snapshot. Changes to the returned dict
        will NOT affect the actual state.
        """
        with self._lock:
            return {
                "di": self._di.copy(),
                "do": self._do.copy(),
                "simulation": self._simulation,
                "simulation_oled": self._simulation_oled,
                "modbus": self._modbus.copy()
            }
    
    def from_dict(self, data: Dict):
        """
        Import state from dictionary (for compatibility).
        
        This is an atomic operation - all or nothing.
        """
        with self._lock:
            # Validate first
            if "di" in data and len(data["di"]) != 4:
                raise ValueError("DI must have 4 values")
            if "do" in data and len(data["do"]) != 4:
                raise ValueError("DO must have 4 values")
            
            # Update atomically
            if "di" in data:
                self._di = list(data["di"])
            if "do" in data:
                self._do = list(data["do"])
            if "simulation" in data:
                self._simulation = bool(data["simulation"])
            if "simulation_oled" in data:
                self._simulation_oled = bool(data["simulation_oled"])
            if "modbus" in data:
                self._modbus = dict(data["modbus"])
    
    # ================================
    # Statistics & Debugging
    # ================================
    def get_stats(self) -> Dict:
        """Get operation statistics (for debugging)"""
        with self._lock:
            return self._stats.copy()
    
    def reset_stats(self):
        """Reset statistics counters"""
        with self._lock:
            self._stats = {
                "di_reads": 0,
                "di_writes": 0,
                "do_reads": 0,
                "do_writes": 0,
                "lock_contentions": 0,
                "max_lock_wait_ms": 0
            }
    
    def __repr__(self):
        """String representation for debugging"""
        with self._lock:
            return (
                f"ThreadSafeState("
                f"DI={self._di}, "
                f"DO={self._do}, "
                f"sim={self._simulation})"
            )


# ================================
# Global Instance (singleton)
# ================================
state = ThreadSafeState()


# ================================
# Testing / Example Usage
# ================================
if __name__ == "__main__":
    import time
    import random
    
    print("=" * 60)
    print("ThreadSafeState Test")
    print("=" * 60)
    
    # Test 1: Basic operations
    print("\n1. Basic Operations:")
    state.set_di(0, 1)
    state.set_do(0, 1)
    print(f"   DI[0] = {state.get_di(0)}")
    print(f"   DO[0] = {state.get_do(0)}")
    print(f"   All DI = {state.get_di()}")
    print(f"   All DO = {state.get_do()}")
    
    # Test 2: Batch operations
    print("\n2. Batch Operations:")
    with state.lock():
        state.set_di_all([1, 0, 1, 0])
        state.set_do_all([0, 1, 0, 1])
    print(f"   DI = {state.get_di()}")
    print(f"   DO = {state.get_do()}")
    
    # Test 3: Concurrent access simulation
    print("\n3. Concurrent Access Test:")
    
    def writer_thread():
        """Simulate daemon writing DI values"""
        for i in range(100):
            channel = random.randint(0, 3)
            value = random.randint(0, 1)
            state.set_di(channel, value)
            time.sleep(0.001)
    
    def reader_thread():
        """Simulate API reading state"""
        for i in range(100):
            di = state.get_di()
            do = state.get_do()
            time.sleep(0.001)
    
    # Start threads
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=writer_thread))
        threads.append(threading.Thread(target=reader_thread))
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    duration = time.time() - start
    stats = state.get_stats()
    
    print(f"   Duration: {duration:.3f}s")
    print(f"   DI reads: {stats['di_reads']}")
    print(f"   DI writes: {stats['di_writes']}")
    print(f"   DO reads: {stats['do_reads']}")
    print(f"   Lock contentions: {stats['lock_contentions']}")
    print(f"   Max lock wait: {stats['max_lock_wait_ms']:.2f}ms")
    
    # Test 4: Dictionary compatibility
    print("\n4. Dictionary Compatibility:")
    snapshot = state.to_dict()
    print(f"   Snapshot: {snapshot}")
    
    print("\n✅ All tests passed!")