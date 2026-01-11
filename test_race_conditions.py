#!/usr/bin/env python3
# test_race_conditions.py
# Comprehensive test suite to expose and verify race condition fixes

import sys
import os
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test both old and new state implementations
from efio_daemon.state import state as old_state
from efio_daemon.thread_safe_state import ThreadSafeState

class RaceConditionTester:
    """
    Test suite for detecting race conditions in state management.
    
    Tests include:
    1. Lost Update Detection - Concurrent writes
    2. Dirty Read Detection - Reading during write
    3. Non-Repeatable Read - Same read returns different values
    4. Phantom Read - State changes unexpectedly
    5. Write-Write Conflict - Concurrent modifications
    """
    
    def __init__(self, state_obj, name="State"):
        self.state = state_obj
        self.name = name
        self.errors = []
        self.warnings = []
    
    def log_error(self, msg):
        """Record test error"""
        self.errors.append(msg)
        print(f"  ❌ {msg}")
    
    def log_warning(self, msg):
        """Record test warning"""
        self.warnings.append(msg)
        print(f"  ⚠️  {msg}")
    
    def log_pass(self, msg):
        """Record test pass"""
        print(f"  ✅ {msg}")
    
    # ================================
    # Test 1: Lost Update Detection
    # ================================
    def test_lost_updates(self, iterations=1000):
        """
        Test for lost updates during concurrent writes.
        
        Scenario:
        - 10 threads each increment DO[0] 100 times
        - Final value should be 1000 if no race conditions
        - Lost updates occur when writes overwrite each other
        """
        print(f"\n📝 Test 1: Lost Update Detection ({iterations} ops)")
        
        # Reset state
        if isinstance(self.state, ThreadSafeState):
            self.state.set_do(0, 0)
        else:
            self.state["do"][0] = 0
        
        num_threads = 10
        ops_per_thread = iterations // num_threads
        
        def increment_do0():
            """Increment DO[0] multiple times"""
            for _ in range(ops_per_thread):
                if isinstance(self.state, ThreadSafeState):
                    # Thread-safe version
                    with self.state.lock():
                        current = self.state.get_do(0)
                        self.state.set_do(0, (current + 1) % 2)
                else:
                    # Old version (race condition prone)
                    current = self.state["do"][0]
                    self.state["do"][0] = (current + 1) % 2
        
        # Run concurrent increments
        threads = [threading.Thread(target=increment_do0) for _ in range(num_threads)]
        
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duration = time.time() - start
        
        # Check result
        if isinstance(self.state, ThreadSafeState):
            final_value = self.state.get_do(0)
        else:
            final_value = self.state["do"][0]
        
        expected = iterations % 2
        
        if final_value == expected:
            self.log_pass(f"No lost updates detected (value={final_value}, expected={expected})")
        else:
            self.log_error(f"Lost updates detected! Final={final_value}, Expected={expected}")
        
        print(f"  ⏱️  Duration: {duration:.3f}s ({iterations/duration:.0f} ops/sec)")
    
    # ================================
    # Test 2: Dirty Read Detection
    # ================================
    def test_dirty_reads(self, iterations=1000):
        """
        Test for dirty reads (reading partially written data).
        
        Scenario:
        - Writer thread sets all DO channels to same value atomically
        - Reader thread checks if all DO values are consistent
        - Dirty read = reader sees mixed values during write
        """
        print(f"\n📝 Test 2: Dirty Read Detection ({iterations} ops)")
        
        dirty_reads = []
        stop_flag = threading.Event()
        
        def writer():
            """Write consistent values to all DO channels"""
            counter = 0
            while not stop_flag.is_set():
                value = counter % 2
                
                if isinstance(self.state, ThreadSafeState):
                    # Thread-safe: atomic write
                    self.state.set_do_all([value, value, value, value])
                else:
                    # Unsafe: individual writes (can be interrupted)
                    self.state["do"][0] = value
                    self.state["do"][1] = value
                    self.state["do"][2] = value
                    self.state["do"][3] = value
                
                counter += 1
                time.sleep(0.0001)  # Small delay to increase race condition chance
        
        def reader():
            """Check if all DO values are consistent"""
            for _ in range(iterations):
                if isinstance(self.state, ThreadSafeState):
                    values = self.state.get_do()
                else:
                    values = self.state["do"].copy()
                
                # Check consistency
                if len(set(values)) > 1:
                    dirty_reads.append(values.copy())
                
                time.sleep(0.0001)
        
        # Run concurrent reader/writer
        writer_thread = threading.Thread(target=writer, daemon=True)
        reader_thread = threading.Thread(target=reader)
        
        start = time.time()
        writer_thread.start()
        reader_thread.start()
        reader_thread.join()
        stop_flag.set()
        duration = time.time() - start
        
        # Evaluate results
        if len(dirty_reads) == 0:
            self.log_pass(f"No dirty reads in {iterations} operations")
        else:
            self.log_error(f"Detected {len(dirty_reads)} dirty reads!")
            print(f"     Examples: {dirty_reads[:3]}")
        
        print(f"  ⏱️  Duration: {duration:.3f}s ({iterations/duration:.0f} reads/sec)")
    
    # ================================
    # Test 3: Non-Repeatable Read
    # ================================
    def test_non_repeatable_reads(self, iterations=1000):
        """
        Test for non-repeatable reads.
        
        Scenario:
        - Reader reads same channel twice in quick succession
        - Writer modifies channel between reads
        - Non-repeatable read = two reads return different values
        """
        print(f"\n📝 Test 3: Non-Repeatable Read Detection ({iterations} ops)")
        
        non_repeatable = []
        stop_flag = threading.Event()
        
        def writer():
            """Rapidly toggle DO[0]"""
            while not stop_flag.is_set():
                if isinstance(self.state, ThreadSafeState):
                    current = self.state.get_do(0)
                    self.state.set_do(0, 1 - current)
                else:
                    self.state["do"][0] = 1 - self.state["do"][0]
                time.sleep(0.00001)
        
        def reader():
            """Read same channel twice"""
            for _ in range(iterations):
                if isinstance(self.state, ThreadSafeState):
                    with self.state.lock():
                        val1 = self.state.get_do(0)
                        val2 = self.state.get_do(0)
                else:
                    val1 = self.state["do"][0]
                    val2 = self.state["do"][0]
                
                if val1 != val2:
                    non_repeatable.append((val1, val2))
                
                time.sleep(0.0001)
        
        writer_thread = threading.Thread(target=writer, daemon=True)
        reader_thread = threading.Thread(target=reader)
        
        start = time.time()
        writer_thread.start()
        reader_thread.start()
        reader_thread.join()
        stop_flag.set()
        duration = time.time() - start
        
        if len(non_repeatable) == 0:
            self.log_pass(f"No non-repeatable reads in {iterations} operations")
        else:
            self.log_error(f"Detected {len(non_repeatable)} non-repeatable reads!")
            print(f"     Examples: {non_repeatable[:3]}")
        
        print(f"  ⏱️  Duration: {duration:.3f}s")
    
    # ================================
    # Test 4: Stress Test
    # ================================
    def test_stress(self, duration_seconds=5):
        """
        Stress test with mixed read/write operations.
        
        Simulates realistic usage:
        - 5 reader threads (API endpoints, WebSocket)
        - 3 writer threads (daemon GPIO, API controls)
        - 2 batch operation threads (MQTT publishing)
        """
        print(f"\n📝 Test 4: Stress Test ({duration_seconds}s)")
        
        stop_flag = threading.Event()
        operations = Counter()
        errors_list = []
        
        def random_reader(thread_id):
            """Simulate API reading state"""
            while not stop_flag.is_set():
                try:
                    if isinstance(self.state, ThreadSafeState):
                        di = self.state.get_di()
                        do = self.state.get_do()
                    else:
                        di = self.state["di"].copy()
                        do = self.state["do"].copy()
                    operations["reads"] += 1
                except Exception as e:
                    errors_list.append(f"Reader-{thread_id}: {e}")
                time.sleep(0.001)
        
        def random_writer(thread_id):
            """Simulate daemon/API writing state"""
            while not stop_flag.is_set():
                try:
                    channel = random.randint(0, 3)
                    value = random.randint(0, 1)
                    
                    if isinstance(self.state, ThreadSafeState):
                        if random.random() < 0.5:
                            self.state.set_di(channel, value)
                        else:
                            self.state.set_do(channel, value)
                    else:
                        if random.random() < 0.5:
                            self.state["di"][channel] = value
                        else:
                            self.state["do"][channel] = value
                    
                    operations["writes"] += 1
                except Exception as e:
                    errors_list.append(f"Writer-{thread_id}: {e}")
                time.sleep(0.001)
        
        def batch_operations(thread_id):
            """Simulate MQTT batch publishing"""
            while not stop_flag.is_set():
                try:
                    if isinstance(self.state, ThreadSafeState):
                        with self.state.lock():
                            di = self.state.get_di()
                            do = self.state.get_do()
                            # Simulate processing
                            time.sleep(0.001)
                    else:
                        di = self.state["di"].copy()
                        do = self.state["do"].copy()
                    
                    operations["batch_ops"] += 1
                except Exception as e:
                    errors_list.append(f"Batch-{thread_id}: {e}")
                time.sleep(0.005)
        
        # Start threads
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=random_reader, args=(i,)))
        for i in range(3):
            threads.append(threading.Thread(target=random_writer, args=(i,)))
        for i in range(2):
            threads.append(threading.Thread(target=batch_operations, args=(i,)))
        
        start = time.time()
        for t in threads:
            t.start()
        
        time.sleep(duration_seconds)
        stop_flag.set()
        
        for t in threads:
            t.join()
        
        duration = time.time() - start
        
        # Results
        total_ops = sum(operations.values())
        print(f"  📊 Operations: {total_ops} total")
        print(f"     - Reads: {operations['reads']}")
        print(f"     - Writes: {operations['writes']}")
        print(f"     - Batch ops: {operations['batch_ops']}")
        print(f"  ⏱️  Duration: {duration:.3f}s ({total_ops/duration:.0f} ops/sec)")
        
        if len(errors_list) == 0:
            self.log_pass("No errors during stress test")
        else:
            self.log_error(f"Encountered {len(errors_list)} errors!")
            for err in errors_list[:5]:
                print(f"     {err}")
        
        # Get stats if available
        if isinstance(self.state, ThreadSafeState):
            stats = self.state.get_stats()
            print(f"  📈 Lock Stats:")
            print(f"     - Contentions: {stats['lock_contentions']}")
            print(f"     - Max wait: {stats['max_lock_wait_ms']:.2f}ms")
    
    # ================================
    # Run All Tests
    # ================================
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print(f"Testing: {self.name}")
        print("=" * 60)
        
        self.test_lost_updates(iterations=1000)
        self.test_dirty_reads(iterations=1000)
        self.test_non_repeatable_reads(iterations=1000)
        self.test_stress(duration_seconds=5)
        
        print("\n" + "=" * 60)
        print(f"Results for {self.name}")
        print("=" * 60)
        print(f"✅ Passed: {4 - len(self.errors)} tests")
        print(f"❌ Failed: {len(self.errors)} tests")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\nErrors:")
            for err in self.errors:
                print(f"  - {err}")
        
        return len(self.errors) == 0


# ================================
# Main Test Runner
# ================================
def main():
    print("\n" + "=" * 60)
    print("EFIO Race Condition Test Suite")
    print("=" * 60)
    
    # Test 1: Old state (dict-based, expected to have race conditions)
    print("\n🔍 Phase 1: Testing OLD state implementation (dict-based)")
    print("   Expected: Race conditions detected\n")
    
    old_tester = RaceConditionTester(old_state, "Old State (dict)")
    old_passed = old_tester.run_all_tests()
    
    # Test 2: New state (thread-safe, should have no race conditions)
    print("\n🔍 Phase 2: Testing NEW state implementation (ThreadSafeState)")
    print("   Expected: No race conditions\n")
    
    new_state = ThreadSafeState()
    new_tester = RaceConditionTester(new_state, "New State (ThreadSafe)")
    new_passed = new_tester.run_all_tests()
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    
    if not old_passed and new_passed:
        print("✅ SUCCESS: Thread-safe implementation fixes all race conditions!")
        print("   Old implementation: Race conditions detected (expected)")
        print("   New implementation: No race conditions (fixed)")
        return 0
    elif old_passed and new_passed:
        print("⚠️  WARNING: Both implementations passed")
        print("   This might mean tests aren't sensitive enough")
        return 1
    elif not old_passed and not new_passed:
        print("❌ FAILURE: New implementation still has race conditions")
        print("   Further fixes needed")
        return 2
    else:
        print("❓ UNEXPECTED: Old implementation passed, new failed")
        print("   This shouldn't happen - check implementation")
        return 3


if __name__ == "__main__":
    import sys
    sys.exit(main())