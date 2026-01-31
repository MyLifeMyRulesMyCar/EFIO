#!/usr/bin/env python3
# efio_daemon/can_mqtt_bridge.py
# CAN Bus to MQTT Bridge - Simple ID-to-Topic Mapping
# Phase 1: Direct CAN message forwarding (no byte parsing yet)

import time
import threading
import json
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Dict, List, Optional

class CANMQTTBridge:
    """
    Background service that:
    1. Subscribes to CAN messages from specific CAN IDs
    2. Publishes entire messages to corresponding MQTT topics
    3. Tracks message rates and statistics
    
    Phase 1: Simple ID-to-Topic mapping
    Future: Add byte extraction, data parsing, scaling
    """
    
    def __init__(self, can_manager, mqtt_config):
        """
        Args:
            can_manager: CANManager instance with active CAN bus connection
            mqtt_config: MQTT broker configuration dict
        """
        self.can_manager = can_manager
        self.mqtt_config = mqtt_config
        self.mappings = []  # List of {id, can_id, topic, name, enabled, format}
        self.running = False
        self.thread = None
        self.mqtt_client = None
        self.mqtt_connected = False
        
        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_published': 0,
            'messages_dropped': 0,
            'errors': 0,
            'start_time': None
        }
        
        # Rate limiting per mapping
        self.last_publish = {}  # {mapping_id: timestamp}
        self.message_counts = {}  # {mapping_id: count}
        
        print("✅ CAN-MQTT Bridge initialized")
    
    # ================================
    # Configuration Management
    # ================================
    
    def load_mappings(self, mappings: List[Dict]):
        """
        Load CAN ID to MQTT topic mappings
        
        Mapping structure:
        {
            "id": "map_001",
            "name": "Engine ECU",
            "can_id": 246,  # 0x0F6
            "topic": "vehicle/engine/ecu",
            "format": "json",  # "json" or "raw"
            "enabled": True,
            "rate_limit_ms": 100,  # Optional: minimum time between publishes
            "qos": 1  # MQTT QoS (0, 1, or 2)
        }
        """
        self.mappings = mappings
        
        # Initialize tracking
        for mapping in mappings:
            mapping_id = mapping['id']
            self.last_publish[mapping_id] = 0
            self.message_counts[mapping_id] = 0
        
        enabled_count = sum(1 for m in mappings if m.get('enabled', True))
        print(f"✅ Bridge: Loaded {len(mappings)} mappings ({enabled_count} enabled)")
    
    def add_mapping(self, mapping: Dict):
        """Add a single mapping"""
        self.mappings.append(mapping)
        mapping_id = mapping['id']
        self.last_publish[mapping_id] = 0
        self.message_counts[mapping_id] = 0
        print(f"✅ Bridge: Added mapping '{mapping['name']}'")
    
    def remove_mapping(self, mapping_id: str):
        """Remove a mapping by ID"""
        self.mappings = [m for m in self.mappings if m['id'] != mapping_id]
        if mapping_id in self.last_publish:
            del self.last_publish[mapping_id]
        if mapping_id in self.message_counts:
            del self.message_counts[mapping_id]
        print(f"🗑️ Bridge: Removed mapping '{mapping_id}'")
    
    # ================================
    # MQTT Connection Management
    # ================================
    
    def _init_mqtt(self):
        """Initialize MQTT client"""
        try:
            if not self.mqtt_config.get('enabled', True):
                print("⚠️ Bridge MQTT: Disabled in configuration")
                return False
            
            client_id = f"{self.mqtt_config.get('client_id', 'efio')}-can-bridge"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Authentication
            username = self.mqtt_config.get('username', '')
            password = self.mqtt_config.get('password', '')
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
                print(f"🔐 CAN Bridge MQTT: Using authentication")
            
            # TLS
            if self.mqtt_config.get('use_tls', False):
                self.mqtt_client.tls_set()
                print("🔒 CAN Bridge MQTT: TLS/SSL enabled")
            
            # Connect
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            keepalive = self.mqtt_config.get('keepalive', 60)
            
            self.mqtt_client.connect(broker, port, keepalive)
            self.mqtt_client.loop_start()
            
            print(f"✅ CAN Bridge MQTT: Connected to {broker}:{port}")
            return True
            
        except Exception as e:
            print(f"❌ CAN Bridge MQTT: Connection failed: {e}")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            print("✅ CAN Bridge MQTT: Connected successfully")
        else:
            print(f"❌ CAN Bridge MQTT: Connection failed (code {rc})")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.mqtt_connected = False
        if rc != 0:
            print(f"⚠️ CAN Bridge MQTT: Disconnected unexpectedly (code {rc})")
    
    # ================================
    # CAN Message Processing
    # ================================
    
    def _on_can_message(self, message: Dict):
        """
        Callback for CAN messages (called by CANManager)
        
        Message structure from CANManager:
        {
            'timestamp': '2025-01-28T12:34:56.789',
            'direction': 'RX',
            'can_id': 246,
            'dlc': 8,
            'data': [0x8E, 0x87, 0x32, 0xFA, 0x26, 0x8E, 0xBE, 0x86],
            'extended': False
        }
        """
        try:
            self.stats['messages_received'] += 1
            
            # Find matching mappings for this CAN ID
            can_id = message['can_id']
            
            for mapping in self.mappings:
                if not mapping.get('enabled', True):
                    continue
                
                if mapping['can_id'] == can_id:
                    self._process_mapping(mapping, message)
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"❌ CAN Bridge: Error processing message: {e}")
    
    def _process_mapping(self, mapping: Dict, message: Dict):
        """Process a CAN message for a specific mapping"""
        try:
            mapping_id = mapping['id']
            
            # Rate limiting check
            if not self._should_publish(mapping, mapping_id):
                self.stats['messages_dropped'] += 1
                return
            
            # Format message based on configuration
            payload = self._format_message(mapping, message)
            
            # Publish to MQTT
            if self._publish_to_mqtt(mapping, payload):
                self.stats['messages_published'] += 1
                self.message_counts[mapping_id] += 1
                self.last_publish[mapping_id] = time.time()
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"⚠️ CAN Bridge: Error processing mapping '{mapping['name']}': {e}")
    
    def _should_publish(self, mapping: Dict, mapping_id: str) -> bool:
        """Check if message should be published (rate limiting)"""
        rate_limit = mapping.get('rate_limit_ms', 0)
        
        if rate_limit <= 0:
            return True
        
        last_time = self.last_publish.get(mapping_id, 0)
        elapsed_ms = (time.time() - last_time) * 1000
        
        return elapsed_ms >= rate_limit
    
    def _format_message(self, mapping: Dict, message: Dict) -> str:
        """
        Format CAN message for MQTT publishing
        
        Format options:
        - "json": Full JSON object with all fields
        - "raw": Hex string of data bytes only
        - "data_array": JSON array of data bytes
        """
        format_type = mapping.get('format', 'json')
        
        if format_type == 'json':
            # Full structured JSON
            payload = {
                "can_id": f"0x{message['can_id']:03X}",
                "can_id_decimal": message['can_id'],
                "dlc": message['dlc'],
                "data": [f"0x{b:02X}" for b in message['data']],
                "data_decimal": message['data'],
                "extended": message['extended'],
                "timestamp": message['timestamp'],
                "device_name": mapping.get('name', 'Unknown')
            }
            return json.dumps(payload)
        
        elif format_type == 'raw':
            # Hex string: "8E8732FA268EBE86"
            return ''.join([f"{b:02X}" for b in message['data'][:message['dlc']]])
        
        elif format_type == 'data_array':
            # JSON array: [142, 135, 50, 250, 38, 142, 190, 134]
            return json.dumps(message['data'][:message['dlc']])
        
        else:
            # Default to JSON
            return json.dumps(message)
    
    def _publish_to_mqtt(self, mapping: Dict, payload: str) -> bool:
        """Publish formatted message to MQTT topic"""
        if not self.mqtt_client or not self.mqtt_connected:
            return False
        
        try:
            topic = mapping['topic']
            qos = mapping.get('qos', 1)
            
            self.mqtt_client.publish(topic, payload, qos=qos, retain=False)
            return True
            
        except Exception as e:
            print(f"❌ CAN Bridge: MQTT publish error: {e}")
            return False
    
    # ================================
    # Bridge Lifecycle
    # ================================
    
    def _is_can_connected(self):
        """
        Check if CAN manager has devices available
        Checks both runtime devices and config file
        """
        # First, try to get runtime status
        if hasattr(self.can_manager, 'get_status'):
            try:
                status = self.can_manager.get_status()
                if isinstance(status, dict):
                    # Check if actively connected
                    if status.get('connected', False):
                        return True
                    
                    # Check runtime devices
                    devices_count = status.get('devices_count', 0)
                    if devices_count > 0:
                        print(f"ℹ️  CAN Bridge: {devices_count} device(s) in CAN manager")
                        return True
            except Exception as e:
                print(f"⚠️ CAN Bridge: Error getting CAN status: {e}")
        
        # Check if devices dict exists in manager
        if hasattr(self.can_manager, 'devices'):
            devices = self.can_manager.devices
            if devices and len(devices) > 0:
                print(f"ℹ️  CAN Bridge: {len(devices)} device(s) registered")
                return True
        
        # Check config file for device configurations
        import os
        import json
        config_file = "/home/radxa/efio/can_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    devices = config.get('devices', [])
                    enabled_devices = [d for d in devices if d.get('enabled', True)]
                    if enabled_devices:
                        print(f"ℹ️  CAN Bridge: {len(enabled_devices)} device(s) in config file")
                        print(f"   Note: Devices configured but CAN manager not connected")
                        print(f"   Bridge will subscribe to manager and wait for messages")
                        return True  # Allow bridge to start with config file devices
            except Exception as e:
                print(f"⚠️ Error reading CAN config: {e}")
        
        # Check standard connection attributes
        if hasattr(self.can_manager, 'connected'):
            if self.can_manager.connected:
                return True
        
        return False
    
    def start(self):
        """Start the bridge service"""
        if self.running:
            print("⚠️ CAN Bridge: Already running")
            return False
        
        if not self.mappings:
            print("⚠️ CAN Bridge: No mappings configured")
            return False
        
        # Check if CAN manager has devices (configured or connected)
        can_available = self._is_can_connected()
        
        print(f"🔍 CAN Bridge: Checking CAN availability...")
        
        # Get detailed status for debugging
        if hasattr(self.can_manager, 'get_status'):
            try:
                status = self.can_manager.get_status()
                print(f"   Connected: {status.get('connected', False)}")
                print(f"   Devices: {status.get('devices_count', 0)}")
                print(f"   Bitrate: {status.get('bitrate', 'unknown')}")
            except Exception as e:
                print(f"   Could not get detailed status: {e}")
        
        if not can_available:
            print("⚠️  CAN Bridge: No CAN devices detected")
            print("   Bridge will start, but may not receive messages until device is connected")
            print("   Tip: Start your CAN device in CAN Manager for full functionality")
        
        # Initialize MQTT
        if not self._init_mqtt():
            print("❌ CAN Bridge: Cannot start without MQTT connection")
            return False
        
        # Subscribe to CAN messages
        self.can_manager.subscribe(self._on_can_message)
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        enabled_count = sum(1 for m in self.mappings if m.get('enabled', True))
        print(f"✅ CAN-MQTT Bridge: Started with {enabled_count} mappings")
        print(f"   Subscribed to CAN messages")
        print(f"   Publishing to MQTT broker")
        
        return True
    
    def stop(self):
        """Stop the bridge service"""
        if not self.running:
            return
        
        print("🛑 CAN Bridge: Stopping...")
        self.running = False
        
        # Unsubscribe from CAN messages
        try:
            self.can_manager.unsubscribe(self._on_can_message)
        except Exception as e:
            print(f"⚠️ Error unsubscribing from CAN: {e}")
        
        # Stop MQTT
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        print("✅ CAN Bridge: Stopped")
    
    # ================================
    # Status & Statistics
    # ================================
    
    def get_status(self) -> Dict:
        """Get bridge status and statistics"""
        uptime = None
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        # Get CAN connection status using helper method
        can_connected = self._is_can_connected()
        
        # Per-mapping statistics
        mapping_stats = []
        for mapping in self.mappings:
            if mapping.get('enabled', True):
                mapping_id = mapping['id']
                mapping_stats.append({
                    'id': mapping_id,
                    'name': mapping['name'],
                    'can_id': f"0x{mapping['can_id']:03X}",
                    'topic': mapping['topic'],
                    'message_count': self.message_counts.get(mapping_id, 0),
                    'last_publish': self.last_publish.get(mapping_id, 0)
                })
        
        return {
            "running": self.running,
            "can_connected": can_connected,  # Use helper method instead of direct attribute
            "mqtt_connected": self.mqtt_connected,
            "mappings_count": len(self.mappings),
            "enabled_mappings": sum(1 for m in self.mappings if m.get('enabled', True)),
            "uptime_seconds": uptime,
            "statistics": {
                "messages_received": self.stats['messages_received'],
                "messages_published": self.stats['messages_published'],
                "messages_dropped": self.stats['messages_dropped'],
                "errors": self.stats['errors'],
                "publish_rate": self._calculate_rate() if uptime else 0
            },
            "mapping_details": mapping_stats
        }
    
    def _calculate_rate(self) -> float:
        """Calculate messages per second"""
        if not self.stats['start_time']:
            return 0.0
        
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        if uptime == 0:
            return 0.0
        
        return round(self.stats['messages_published'] / uptime, 2)
    
    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'messages_received': 0,
            'messages_published': 0,
            'messages_dropped': 0,
            'errors': 0,
            'start_time': datetime.now() if self.running else None
        }
        
        for mapping_id in self.message_counts:
            self.message_counts[mapping_id] = 0
        
        print("🔄 CAN Bridge: Statistics reset")


# ================================
# Testing
# ================================
if __name__ == "__main__":
    print("=" * 60)
    print("CAN-MQTT Bridge - Phase 1 Test")
    print("=" * 60)
    
    # Mock CAN manager
    class MockCANManager:
        def __init__(self):
            self.connected = True
            self.subscribers = []
        
        def subscribe(self, callback):
            self.subscribers.append(callback)
        
        def unsubscribe(self, callback):
            if callback in self.subscribers:
                self.subscribers.remove(callback)
        
        def simulate_message(self, can_id, data):
            """Simulate receiving a CAN message"""
            message = {
                'timestamp': datetime.now().isoformat(),
                'direction': 'RX',
                'can_id': can_id,
                'dlc': len(data),
                'data': data,
                'extended': False
            }
            
            for subscriber in self.subscribers:
                subscriber(message)
    
    # Test configuration
    mqtt_config = {
        'enabled': True,
        'broker': 'localhost',
        'port': 1883,
        'client_id': 'efio-test'
    }
    
    mappings = [
        {
            'id': 'map_001',
            'name': 'Engine ECU',
            'can_id': 0x0F6,
            'topic': 'test/vehicle/engine',
            'format': 'json',
            'enabled': True,
            'rate_limit_ms': 100
        },
        {
            'id': 'map_002',
            'name': 'Transmission',
            'can_id': 0x123,
            'topic': 'test/vehicle/transmission',
            'format': 'raw',
            'enabled': True
        }
    ]
    
    # Create bridge
    can_mgr = MockCANManager()
    bridge = CANMQTTBridge(can_mgr, mqtt_config)
    bridge.load_mappings(mappings)
    
    print("\n📊 Status before start:")
    print(json.dumps(bridge.get_status(), indent=2))
    
    # Note: Full test requires actual MQTT broker
    print("\n✅ Bridge created successfully")
    print("   To fully test: Connect to actual CAN bus and MQTT broker")