#!/usr/bin/env python3
"""
CAN-MQTT Bridge Setup Script
Creates all required configuration files with sensible defaults
"""

import json
import os

CONFIG_DIR = "/home/radxa/efio"

# Ensure config directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)

print("="*60)
print("CAN-MQTT Bridge Setup")
print("="*60)

# 1. Create MQTT Config (if missing)
mqtt_config_file = f"{CONFIG_DIR}/mqtt_config.json"
if not os.path.exists(mqtt_config_file):
    print(f"\n📝 Creating {mqtt_config_file}")
    mqtt_config = {
        "enabled": True,
        "broker": "localhost",
        "port": 1883,
        "username": "testuser",
        "password": "testpass",
        "client_id": "efio-daemon",
        "use_tls": False,
        "keepalive": 60,
        "qos": 1
    }
    with open(mqtt_config_file, 'w') as f:
        json.dump(mqtt_config, f, indent=2)
    print(f"   ✅ Created with default settings")
    print(f"   Broker: {mqtt_config['broker']}:{mqtt_config['port']}")
else:
    print(f"\n✅ {mqtt_config_file} already exists")

# 2. Create CAN-MQTT Bridge Config (if missing)
bridge_config_file = f"{CONFIG_DIR}/can_mqtt_bridge.json"
if not os.path.exists(bridge_config_file):
    print(f"\n📝 Creating {bridge_config_file}")
    bridge_config = {
        "enabled": False,
        "mappings": []
    }
    with open(bridge_config_file, 'w') as f:
        json.dump(bridge_config, f, indent=2)
    print(f"   ✅ Created (empty, ready for mappings)")
else:
    print(f"\n✅ {bridge_config_file} already exists")

# 3. Create CAN Config (if missing)
can_config_file = f"{CONFIG_DIR}/can_config.json"
if not os.path.exists(can_config_file):
    print(f"\n📝 Creating {can_config_file}")
    can_config = {
        "controller": {
            "spi_bus": 2,
            "spi_device": 0,
            "spi_speed": 1000000,
            "bitrate": 125000,
            "mode": "normal",
            "crystal": 8000000
        },
        "devices": [],
        "filters": [],
        "auto_connect": False
    }
    with open(can_config_file, 'w') as f:
        json.dump(can_config, f, indent=2)
    print(f"   ✅ Created with default settings")
    print(f"   Bitrate: {can_config['controller']['bitrate']} bps")
    print(f"   Auto-connect: {can_config['auto_connect']}")
else:
    print(f"\n✅ {can_config_file} already exists")

# 4. Set proper permissions
print(f"\n🔐 Setting file permissions...")
for config_file in [mqtt_config_file, bridge_config_file, can_config_file]:
    try:
        os.chmod(config_file, 0o644)
        print(f"   ✅ {os.path.basename(config_file)}")
    except Exception as e:
        print(f"   ⚠️  {os.path.basename(config_file)}: {e}")

print("\n" + "="*60)
print("Setup Complete!")
print("="*60)

print("\n📋 Next Steps:")
print("1. Verify MQTT broker is running:")
print("   sudo systemctl status mosquitto")
print("")
print("2. Restart EFIO service:")
print("   sudo systemctl restart efio")
print("")
print("3. Check EFIO logs:")
print("   sudo journalctl -u efio -f")
print("")
print("4. Test CAN-MQTT API:")
print("   curl http://192.168.1.30:5000/api/can-mqtt/config")
print("")
print("5. Access Web UI:")
print("   http://192.168.1.30:3000/can-mqtt-bridge")