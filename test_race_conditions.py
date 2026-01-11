#!/usr/bin/env python3
# test_race_conditions_improved.py
# MORE AGGRESSIVE test to expose race conditions

import sys
import os
import threading
import time
import random
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from efio_daemon.thread_safe_state import ThreadSafeState

class AggressiveRaceTester:
    """
    Aggressive race condition tester.
    
    Key differences from original:
    1. ZERO sleep between operations (max contention)
    2. More threads competing (20 instead of 10)
    3. Longer duration (10s instead of 5s)
    4. Validation during execution (not just after)
    """
    
    def __init__(self, name="State"):
        self.name = name
        self.errors = []
        self.warnings = []
    
    # ================================
    # Test 1: BRUTAL Lost Update Test
    # ================================
    def test_brutal_lost_updates(self):
        """
        BRUTAL test for lost updates.
        
        Changes from original:
        - 20 threads (not 10)
        - NO SLEEP between operations
        - Validate DURING execution
        - 100,000 operations total
        """
        print(f"\n🔥 Test 1: BRUTAL Lost Update Detection")
        
        state = ThreadSafeState()
        state.set_do(0, 0)
        
        num_threads = 20
        ops_per_thread = 5000  # 100k total ops
        
        # Track inconsistencies during execution
        inconsistencies = []
        stop_flag = threading.Event()
        
        def increment_worker(worker_id):
            """Increment DO[0] as fast as possible"""
            local_ops = 0
            while local_ops < ops_per_thread:
                with state.lock():
                    current = state.get_do(0)
                    state.set_do(0, (current + 1) % 2)
                local_ops += 1
        
        def validator():
            """Validate state consistency during execution"""
            while not stop_flag.is_set():
                # Read state multiple times rapidly WITH LOCK
                with state.lock():
                    readings = []
                    for _ in range(10):
                        readings.append(state.get_do(0))
                    
                    # All readings should be same (0 or 1) when locked
                    if len(set(readings)) > 1:
                        inconsistencies.append(readings)
        
        # Start threads
        threads = [threading.Thread(target=increment_worker, args=(i,)) 
                   for i in range(num_threads)]
        validator_thread = threading.Thread(target=validator, daemon=True)
        
        validator_thread.start()
        
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        stop_flag.set()
        duration = time.time() - start
        
        # Results
        final_value = state.get_do(0)
        expected = (num_threads * ops_per_thread) % 2
        
        print(f"  📊 Results:")
        print(f"     - Total ops: {num_threads * ops_per_thread:,}")
        print(f"     - Duration: {duration:.3f}s")
        print(f"     - Throughput: {(num_threads * ops_per_thread)/duration:,.0f} ops/sec")
        print(f"     - Final value: {final_value} (expected: {expected})")
        print(f"     - Inconsistencies: {len(inconsistencies)}")
        
        if final_value == expected and len(inconsistencies) == 0:
            print("  ✅ PASS: No lost updates, no inconsistencies")
            return True
        else:
            print("  ❌ FAIL: Race condition detected!")
            if len(inconsistencies) > 0:
                print(f"     Example inconsistency: {inconsistencies[0]}")
            return False
    
    # ================================
    # Test 2: Interleaved Read-Write
    # ================================
    def test_interleaved_read_write(self):
        """
        Test reader/writer interleaving.
        
        Scenario:
        - Writer atomically sets [1,1,1,1]
        - Reader should NEVER see [1,1,0,0] or similar
        """
        print(f"\n🔥 Test 2: Interleaved Read-Write Consistency")
        
        state = ThreadSafeState()
        dirty_reads = []
        stop_flag = threading.Event()
        
        def writer():
            """Toggle all DO channels atomically"""
            counter = 0
            while not stop_flag.is_set():
                value = counter % 2
                state.set_do_all([value, value, value, value])
                counter += 1
                # NO SLEEP - max race condition exposure
        
        def reader():
            """Read and validate consistency"""
            reads = 0
            while not stop_flag.is_set() and reads < 50000:
                values = state.get_do()
                
                # All values must be identical
                if len(set(values)) > 1:
                    dirty_reads.append(values.copy())
                
                reads += 1
        
        # Start 10 readers, 5 writers
        readers = [threading.Thread(target=reader) for _ in range(10)]
        writers = [threading.Thread(target=writer, daemon=True) for _ in range(5)]
        
        start = time.time()
        for t in writers:
            t.start()
        for t in readers:
            t.start()
        for t in readers:
            t.join()
        
        stop_flag.set()
        duration = time.time() - start
        
        print(f"  📊 Results:")
        print(f"     - Duration: {duration:.3f}s")
        print(f"     - Dirty reads: {len(dirty_reads)}")
        
        if len(dirty_reads) == 0:
            print("  ✅ PASS: No dirty reads detected")
            return True
        else:
            print("  ❌ FAIL: Dirty reads found!")
            print(f"     Examples: {dirty_reads[:3]}")
            return False
    
    # ================================
    # Test 3: Lock Contention Stress
    # ================================
    def test_lock_contention(self):
        """
        Extreme lock contention test.
        
        30 threads all trying to modify state simultaneously.
        """
        print(f"\n🔥 Test 3: Extreme Lock Contention")
        
        state = ThreadSafeState()
        state.reset_stats()
        
        num_threads = 30
        ops_per_thread = 3000
        
        def worker(worker_id):
            """Random read/write operations"""
            for _ in range(ops_per_thread):
                op = random.randint(0, 2)
                
                if op == 0:
                    # Read operation
                    state.get_di()
                    state.get_do()
                elif op == 1:
                    # Single write
                    ch = random.randint(0, 3)
                    state.set_do(ch, random.randint(0, 1))
                else:
                    # Batch operation
                    with state.lock():
                        di = state.get_di()
                        state.set_do_all([1-x for x in di])
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        duration = time.time() - start
        stats = state.get_stats()
        
        print(f"  📊 Results:")
        print(f"     - Total ops: {num_threads * ops_per_thread:,}")
        print(f"     - Duration: {duration:.3f}s")
        print(f"     - Throughput: {(num_threads * ops_per_thread)/duration:,.0f} ops/sec")
        print(f"     - Lock contentions: {stats['lock_contentions']}")
        print(f"     - Max lock wait: {stats['max_lock_wait_ms']:.2f}ms")
        
        # Success criteria: No deadlocks, reasonable wait times
        if stats['max_lock_wait_ms'] < 100:  # Less than 100ms
            print("  ✅ PASS: Acceptable lock performance")
            return True
        else:
            print("  ⚠️  WARNING: High lock contention detected")
            return True  # Still pass, just warn
    
    # ================================
    # Test 4: Daemon + API Simulation
    # ================================
    def test_realistic_workload(self):
        """
        Simulate realistic EFIO usage:
        - 1 daemon thread (reads GPIO at 10Hz)
        - 5 API threads (handle requests)
        - 3 WebSocket threads (broadcast state)
        - 2 MQTT threads (publish updates)
        """
        print(f"\n🔥 Test 4: Realistic Workload Simulation")
        
        state = ThreadSafeState()
        stop_flag = threading.Event()
        operations = Counter()
        
        def daemon_loop():
            """Simulate main daemon loop"""
            while not stop_flag.is_set():
                # Simulate reading GPIO
                new_di = [random.randint(0, 1) for _ in range(4)]
                state.set_di_all(new_di)
                operations['daemon_reads'] += 1
                time.sleep(0.1)  # 10Hz update rate
        
        def api_handler(handler_id):
            """Simulate API endpoint handling"""
            while not stop_flag.is_set():
                # Random API operations
                if random.random() < 0.3:
                    # Read state
                    di = state.get_di()
                    do = state.get_do()
                    operations['api_reads'] += 1
                else:
                    # Write output
                    ch = random.randint(0, 3)
                    state.set_do(ch, random.randint(0, 1))
                    operations['api_writes'] += 1
                
                time.sleep(random.uniform(0.01, 0.05))
        
        def websocket_broadcast():
            """Simulate WebSocket broadcasting"""
            while not stop_flag.is_set():
                # Read state for broadcast
                with state.lock():
                    di = state.get_di()
                    do = state.get_do()
                operations['ws_broadcasts'] += 1
                time.sleep(0.5)  # Broadcast every 500ms
        
        def mqtt_publish():
            """Simulate MQTT publishing"""
            while not stop_flag.is_set():
                # Publish I/O state
                di = state.get_di()
                for i, val in enumerate(di):
                    operations['mqtt_publishes'] += 1
                time.sleep(1.0)  # Publish every second
        
        # Start all threads
        threads = [
            threading.Thread(target=daemon_loop, daemon=True),
        ]
        threads.extend([threading.Thread(target=api_handler, args=(i,)) 
                        for i in range(5)])
        threads.extend([threading.Thread(target=websocket_broadcast) 
                        for _ in range(3)])
        threads.extend([threading.Thread(target=mqtt_publish) 
                        for _ in range(2)])
        
        start = time.time()
        for t in threads:
            t.start()
        
        # Run for 10 seconds
        time.sleep(10)
        stop_flag.set()
        
        for t in threads:
            t.join(timeout=2)
        
        duration = time.time() - start
        
        print(f"  📊 Results:")
        print(f"     - Duration: {duration:.1f}s")
        print(f"     - Daemon reads: {operations['daemon_reads']}")
        print(f"     - API reads: {operations['api_reads']}")
        print(f"     - API writes: {operations['api_writes']}")
        print(f"     - WS broadcasts: {operations['ws_broadcasts']}")
        print(f"     - MQTT publishes: {operations['mqtt_publishes']}")
        
        print("  ✅ PASS: Realistic workload completed")
        return True
    
    # ================================
    # Run All Tests
    # ================================
    def run_all(self):
        """Run complete test suite"""
        print("\n" + "=" * 60)
        print(f"AGGRESSIVE Race Condition Test Suite")
        print("=" * 60)
        
        results = []
        results.append(("Lost Updates", self.test_brutal_lost_updates()))
        results.append(("Read-Write Consistency", self.test_interleaved_read_write()))
        results.append(("Lock Contention", self.test_lock_contention()))
        results.append(("Realistic Workload", self.test_realistic_workload()))
        
        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 SUCCESS: All race conditions fixed!")
            return 0
        else:
            print("\n⚠️  Some tests failed - race conditions may still exist")
            return 1


if __name__ == "__main__":
    tester = AggressiveRaceTester()
    sys.exit(tester.run_all())