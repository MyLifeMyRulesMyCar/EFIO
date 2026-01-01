#!/usr/bin/env python3
# api/mqtt_config.py
# Shared MQTT configuration loader (prevents circular imports)

import json
import os

MQTT_CONFIG_FILE = "/home/radxa/efio/mqtt_config.json"

DEFAULT_MQTT_CONFIG = {
    "enabled": True,
    "broker": "localhost",
    "port": 1883,
    "username": "",
    "password": "",
    "client_id": "efio-daemon",
    "use_tls": False,
    "keepalive": 60,
    "qos": 1
}

def load_mqtt_config():
    """Load MQTT configuration from file"""
    if not os.path.exists(MQTT_CONFIG_FILE):
        return DEFAULT_MQTT_CONFIG
    
    try:
        with open(MQTT_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            print(f"✅ Loaded MQTT config: {config['broker']}:{config['port']}")
            return config
    except Exception as e:
        print(f"❌ Error loading MQTT config: {e}")
        return DEFAULT_MQTT_CONFIG