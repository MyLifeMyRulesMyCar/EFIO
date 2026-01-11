#!/usr/bin/env python3
# validate_race_fixes.py
# Final validation script to verify all race condition fixes

import sys
import os
import time
import threading
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("\n" + "=" * 70)
print("EFIO Race Condition Fix Validation")
print("=" * 70)

# ================================
# Step 1: Verify ThreadSafeState
# ================================
print("\n📋 Step 1: Verifying ThreadSafeState implementation...")

try:
    from efio_daemon.thread_safe_state import ThreadSafeState
    state = ThreadSafeState()
    
    # Test basic operations
    state.set_di(0, 1)
    assert state.get_di(0) == 1, "Basic DI operation failed"
    
    state.set_do(0, 1)
    assert state.get_do(0) == 1, "Basic DO operation failed"
    
    # Test batch operations
    state.set_di_all([1, 0, 1, 0])
    assert state.get_di() == [1, 0, 1, 0], "Batch DI operation failed"
    
    # Test lock context manager
    with state.lock():
        di = state.get_di()
        state.set_do_all(di)
    assert state.get_do() == [1, 0, 1, 0], "Context manager failed"
    
    print("✅ ThreadSafeState: All basic tests passed")
    
except Exception as e:
    print(f"❌ ThreadSafeState: Failed - {e}")
    sys.exit(1)

# ================================
# Step 2: Verify Compatibility Wrapper
# ================================
print("\n📋 Step 2: Verifying compatibility wrapper...")

try:
    from efio_daemon.state import state as wrapped_state
    
    # Test new API (recommended way)
    wrapped_state.set_di(0, 1)
    assert wrapped_state.get_di(0) == 1, "Wrapper DI access failed"
    
    wrapped_state.set_do(0, 1)
    assert wrapped_state.get_do(0) == 1, "Wrapper DO access failed"
    
    # Test dict-style read (deprecated but should work)
    di_values = wrapped_state["di"]
    assert di_values[0] == 1, "Dict-style read failed"
    
    # Test batch operations
    wrapped_state.set_di_all([1, 0, 1, 0])
    assert wrapped_state.get_di() == [1, 0, 1, 0], "Batch operation failed"
    
    print("✅ Compatibility Wrapper: Working correctly")
    print("   Note: Use new API (set_di/get_di) instead of dict access")
    
except Exception as e:
    print(f"❌ Compatibility Wrapper: Failed - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ================================
# Step 3: Verify IOManager Locking
# ================================
print("\n📋 Step 3: Verifying IOManager thread safety...")

try:
    from efio_daemon.io_manager import IOManager
    
    # Create manager in simulation mode
    from efio_daemon.state import state
    state.set_simulation(True)
    
    manager = IOManager()
    
    # Test concurrent reads
    def read_worker():
        for _ in range(100):
            manager.read_all_inputs()
    
    # Test concurrent writes
    def write_worker():
        for _ in range(100):
            ch = 0
            val = 1
            manager.write_output(ch, val)
    
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=read_worker))
        threads.append(threading.Thread(target=write_worker))
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    print("✅ IOManager: Concurrent access successful")
    
except Exception as e:
    print(f"❌ IOManager: Failed - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ================================
# Step 4: Verify Daemon Integration
# ================================
print("\n📋 Step 4: Verifying daemon integration...")

try:
    from efio_daemon.daemon import EFIODeviceDaemon
    from efio_daemon.state import state
    
    # Set simulation mode
    state.set_simulation(True)
    state.set_simulation_oled(True)
    
    # Create daemon
    daemon = EFIODeviceDaemon(debug_mqtt=False)
    daemon.start()
    
    # Let it run for 2 seconds
    time.sleep(2)
    
    # Verify it's running
    assert daemon.running, "Daemon not running"
    assert daemon.loop_count > 0, "Daemon loop not executing"
    
    # Stop daemon
    daemon.stop()
    
    print("✅ Daemon: Integration successful")
    
except Exception as e:
    print(f"❌ Daemon: Failed - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ================================
# Step 5: Quick Race Condition Test
# ================================
print("\n📋 Step 5: Running quick race condition test...")

try:
    from efio_daemon.thread_safe_state import ThreadSafeState
    
    test_state = ThreadSafeState()
    test_state.set_do(0, 0)
    
    # 10 threads, 1000 ops each
    def increment():
        for _ in range(1000):
            with test_state.lock():
                val = test_state.get_do(0)
                test_state.set_do(0, (val + 1) % 2)
    
    threads = [threading.Thread(target=increment) for _ in range(10)]
    
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    duration = time.time() - start
    
    final = test_state.get_do(0)
    expected = (10 * 1000) % 2
    
    if final == expected:
        print(f"✅ Race Test: Passed ({10000/duration:.0f} ops/sec)")
    else:
        print(f"❌ Race Test: Failed (got {final}, expected {expected})")
        sys.exit(1)
    
except Exception as e:
    print(f"❌ Race Test: Failed - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ================================
# Final Summary
# ================================
print("\n" + "=" * 70)
print("🎉 VALIDATION COMPLETE: All checks passed!")
print("=" * 70)
print("\nYour race condition fixes are working correctly.")
print("\nNext steps:")
print("  1. Run full test suite: python3 test_race_conditions_improved.py")
print("  2. Deploy to production")
print("  3. Monitor with: curl http://localhost:5000/api/health/watchdog")
print("\n" + "=" * 70)