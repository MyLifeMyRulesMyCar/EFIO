#!/usr/bin/env python3
# test_device_loading.py
# Test if devices are properly loaded into can_manager

import sys
sys.path.insert(0, '/home/radxa/efio')

print("=" * 60)
print("Testing CAN Device Loading")
print("=" * 60)

from efio_daemon.can_manager import can_manager
import json

# Check manager state
print(f"\n1. CAN Manager State:")
print(f"   Connected: {can_manager.connected}")
print(f"   Bitrate: {can_manager.bitrate}")
print(f"   Devices dict: {can_manager.devices}")
print(f"   Number of devices in dict: {len(can_manager.devices)}")

# Check config file
print(f"\n2. Config File:")
with open('/home/radxa/efio/can_config.json', 'r') as f:
    config = json.load(f)
    devices_in_config = config.get('devices', [])
    print(f"   Devices in config file: {len(devices_in_config)}")

# Test add_device method
print(f"\n3. Testing add_device method:")
try:
    # Try adding a test device
    test_id = can_manager.add_device(
        'test_device_001',
        'Test Device',
        123,
        False,
        True
    )
    print(f"   ✅ add_device() returned: {test_id}")
    
    # Check if it's in devices dict
    if test_id in can_manager.devices:
        print(f"   ✅ Device found in devices dict")
        device = can_manager.devices[test_id]
        print(f"   Device name: {device.name}")
        print(f"   Device CAN ID: {device.can_id}")
    else:
        print(f"   ❌ Device NOT in devices dict!")
        print(f"   Current devices dict: {can_manager.devices}")
    
    # Clean up
    can_manager.remove_device(test_id)
    print(f"   🗑️  Test device removed")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Now test the actual loading logic from init_can_manager
print(f"\n4. Simulating init_can_manager() device loading:")
devices_loaded = 0
for device_data in devices_in_config[:3]:  # Test first 3
    try:
        print(f"\n   Loading: {device_data['name']} (ID: 0x{device_data['can_id']:02X})")
        
        device_id = can_manager.add_device(
            device_data['id'],
            device_data['name'],
            device_data['can_id'],
            device_data.get('extended', False),
            device_data.get('enabled', True)
        )
        
        print(f"   → Returned ID: {device_id}")
        
        device = can_manager.get_device(device_id)
        if device:
            device.messages = device_data.get('messages', [])
            devices_loaded += 1
            print(f"   ✅ Loaded successfully")
        else:
            print(f"   ❌ get_device() returned None")
            
    except Exception as e:
        print(f"   ❌ Failed: {e}")

print(f"\n5. Final State:")
print(f"   Devices loaded: {devices_loaded}")
print(f"   Devices in dict: {len(can_manager.devices)}")
print(f"   Device IDs: {list(can_manager.devices.keys())}")

# Check get_status()
print(f"\n6. get_status() Result:")
status = can_manager.get_status()
print(json.dumps(status, indent=2))

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)