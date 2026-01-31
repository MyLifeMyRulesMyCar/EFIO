#!/usr/bin/env python3
# comprehensive_can_diagnostic.py
# Detailed check of CAN manager and devices

import sys
sys.path.insert(0, '/home/radxa/efio')

from efio_daemon.can_manager import can_manager
import json

print("=" * 60)
print("Comprehensive CAN Diagnostic")
print("=" * 60)

# 1. CAN Manager instance
print(f"\n1. CAN Manager Instance:")
print(f"   Object: {can_manager}")
print(f"   Type: {type(can_manager)}")

# 2. Status
print(f"\n2. Status (from get_status()):")
try:
    status = can_manager.get_status()
    print(json.dumps(status, indent=2))
except Exception as e:
    print(f"   Error: {e}")

# 3. All attributes
print(f"\n3. All Attributes:")
attrs = [attr for attr in dir(can_manager) if not attr.startswith('_')]
for attr in sorted(attrs):
    try:
        value = getattr(can_manager, attr)
        if not callable(value):
            print(f"   {attr}: {value}")
    except Exception as e:
        print(f"   {attr}: <error: {e}>")

# 4. Check for devices
print(f"\n4. Device Information:")

if hasattr(can_manager, 'devices'):
    print(f"   devices attribute exists: {can_manager.devices}")
    if can_manager.devices:
        print(f"   Number of devices: {len(can_manager.devices)}")
        for i, device in enumerate(can_manager.devices):
            print(f"   Device {i}: {device}")

if hasattr(can_manager, 'device'):
    print(f"   device attribute: {can_manager.device}")

if hasattr(can_manager, 'device_configs'):
    print(f"   device_configs: {can_manager.device_configs}")

if hasattr(can_manager, 'registered_devices'):
    print(f"   registered_devices: {can_manager.registered_devices}")

# 5. Check configuration file
print(f"\n5. Configuration Files:")
import os
config_paths = [
    "/home/radxa/efio/can_config.json",
    "/home/radxa/efio/can_devices.json",
    "/home/radxa/efio/config/can.json",
    "/home/radxa/efio/config/can_devices.json"
]

for path in config_paths:
    if os.path.exists(path):
        print(f"   Found: {path}")
        try:
            with open(path, 'r') as f:
                config = json.load(f)
                print(f"   Content: {json.dumps(config, indent=2)}")
        except Exception as e:
            print(f"   Error reading: {e}")
    else:
        print(f"   Not found: {path}")

# 6. Check if we can access the bus
print(f"\n6. Bus Access Test:")
if hasattr(can_manager, 'bus'):
    print(f"   bus attribute: {can_manager.bus}")
    if can_manager.bus:
        print(f"   Bus type: {type(can_manager.bus)}")

# 7. Check message queue/buffer
print(f"\n7. Message Queue:")
if hasattr(can_manager, 'message_queue'):
    print(f"   message_queue: {can_manager.message_queue}")
if hasattr(can_manager, 'rx_buffer'):
    print(f"   rx_buffer: {can_manager.rx_buffer}")

# 8. Check subscribers
print(f"\n8. Subscribers:")
if hasattr(can_manager, 'subscribers'):
    print(f"   subscribers: {can_manager.subscribers}")
    print(f"   Count: {len(can_manager.subscribers) if can_manager.subscribers else 0}")

# 9. Methods available
print(f"\n9. Available Methods:")
methods = [attr for attr in dir(can_manager) if callable(getattr(can_manager, attr)) and not attr.startswith('_')]
for method in sorted(methods)[:20]:  # Show first 20 methods
    print(f"   - {method}")

print("\n" + "=" * 60)
print("Diagnostic Complete")
print("=" * 60)

# 10. Recommendation
print("\n10. Recommendations:")
if status.get('devices_count', 0) == 0:
    print("   ⚠️  No devices registered with CAN manager")
    print("   ")
    print("   Possible reasons:")
    print("   1. Device configured but not registered/started")
    print("   2. Device config stored separately from CAN manager")
    print("   3. Need to call connect() or start() on device")
    print("   ")
    print("   Try:")
    print("   - Check CAN Manager UI - is device showing as 'Started'?")
    print("   - Restart efio-api: sudo systemctl restart efio-api")
    print("   - Check API logs: journalctl -u efio-api -n 50")