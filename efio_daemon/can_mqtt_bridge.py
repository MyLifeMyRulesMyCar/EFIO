#!/usr/bin/env python3
# efio_daemon/can_mqtt_bridge.py - CORRECTED VERSION
# CAN Bus to MQTT Bridge with proper statistics tracking for UI

import time
import threading
import json
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Dict, List, Optional

class CANMQTTBridge:
    """
    CAN to MQTT Bridge with UI-compatible statistics
    Maps CAN IDs to MQTT topics with proper per-mapping tracking
    """
    
    def __init__(self, can_manager, mqtt_config):
        self.can_manager = can_manager
        self.mqtt_config = mqtt_config
        self.mappings = []
        self.running = False
        self.mqtt_client = None
        self.mqtt_connected = False
        
        # Global statistics (matches UI expectations)
        self.stats = {
            'messages_received': 0,
            'messages_published': 0,
            'messages_dropped': 0,
            'errors': 0,
            'start_time': None
        }
        
        # Per-mapping tracking (for UI table display)
        self.last_publish = {}  # {mapping_id: timestamp}
        self.message_counts = {}  # {mapping_id: count}
        self.last_values = {}  # {mapping_id: data_hex} for change detection
        
        self._lock = threading.RLock()
        
        print("✅ CAN-MQTT Bridge initialized")
    
    def load_mappings(self, mappings: List[Dict]):
        """Load CAN ID to MQTT topic mappings"""
        with self._lock:
            self.mappings = mappings
            
            # Initialize tracking for each mapping
            for mapping in mappings:
                mapping_id = mapping['id']
                self.last_publish[mapping_id] = 0
                self.message_counts[mapping_id] = 0
                self.last_values[mapping_id] = None
            
            enabled_count = sum(1 for m in mappings if m.get('enabled', True))
            print(f"✅ Bridge: Loaded {len(mappings)} mappings ({enabled_count} enabled)")
    
    def _init_mqtt(self) -> bool:
        """Initialize MQTT client"""
        try:
            if not self.mqtt_config.get('enabled', True):
                print("⚠️ Bridge MQTT: Disabled in configuration")
                return False
            
            client_id = f"{self.mqtt_config.get('client_id', 'efio')}-can-bridge"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            username = self.mqtt_config.get('username', '')
            password = self.mqtt_config.get('password', '')
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
            
            if self.mqtt_config.get('use_tls', False):
                self.mqtt_client.tls_set()
            
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            keepalive = self.mqtt_config.get('keepalive', 60)
            
            self.mqtt_client.connect(broker, port, keepalive)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.mqtt_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.mqtt_connected:
                raise TimeoutError(f"MQTT connection timeout after {timeout}s")
            
            print(f"✅ CAN Bridge MQTT: Connected to {broker}:{port}")
            return True
            
        except Exception as e:
            print(f"❌ CAN Bridge MQTT: Connection failed: {e}")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.mqtt_connected = True
            print("✅ CAN Bridge MQTT: Connected successfully")
        else:
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False
        if rc != 0:
            print(f"⚠️ CAN Bridge MQTT: Disconnected unexpectedly (code {rc})")
    
    def _on_can_message(self, message: Dict):
        """Handle incoming CAN message"""
        if not self.running or not self.mqtt_connected:
            return
        
        try:
            self.stats['messages_received'] += 1
            can_id = message['can_id']
            
            with self._lock:
                for mapping in self.mappings:
                    if mapping['can_id'] == can_id and mapping.get('enabled', True):
                        self._process_mapping(mapping, message)
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"❌ CAN Bridge: Error processing message: {e}")
    
    def _process_mapping(self, mapping: Dict, message: Dict):
        """Process CAN message for a specific mapping"""
        mapping_id = mapping['id']
        
        try:
            # Convert data to hex string
            data_hex = ' '.join([f'{b:02X}' for b in message['data'][:message['dlc']]])
            
            # Check if should publish (change detection + rate limiting)
            if not self._should_publish(mapping, mapping_id, data_hex):
                self.stats['messages_dropped'] += 1
                return
            
            # Format and publish
            payload = self._format_message(mapping, message)
            
            if self._publish_to_mqtt(mapping, payload):
                # ✅ Update statistics (THIS IS KEY FOR UI)
                self.stats['messages_published'] += 1
                self.message_counts[mapping_id] = self.message_counts.get(mapping_id, 0) + 1
                self.last_publish[mapping_id] = time.time()
                self.last_values[mapping_id] = data_hex
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"⚠️ CAN Bridge: Error processing mapping '{mapping['name']}': {e}")
    
    def _should_publish(self, mapping: Dict, mapping_id: str, data_hex: str) -> bool:
        """Check if message should be published"""
        # Change detection
        if mapping.get('publish_on_change', True):
            if self.last_values.get(mapping_id) == data_hex:
                return False
        
        # Rate limiting
        min_interval = mapping.get('min_interval_ms', 0) / 1000.0
        if min_interval > 0:
            last_time = self.last_publish.get(mapping_id, 0)
            if (time.time() - last_time) < min_interval:
                return False
        
        return True
    
    def _format_message(self, mapping: Dict, message: Dict) -> str:
        """Format CAN message for MQTT"""
        payload = {
            "can_id": f"0x{message['can_id']:03X}",
            "can_id_decimal": message['can_id'],
            "dlc": message['dlc'],
            "data_hex": [f"0x{b:02X}" for b in message['data'][:message['dlc']]],
            "data_decimal": message['data'][:message['dlc']],
            "extended": message.get('extended', False),
            "timestamp": message['timestamp'],
            "timestamp_unix": time.time(),
            "device_name": mapping.get('name', 'Unknown')
        }
        return json.dumps(payload)
    
    def _publish_to_mqtt(self, mapping: Dict, payload: str) -> bool:
        """Publish to MQTT topic"""
        if not self.mqtt_client or not self.mqtt_connected:
            return False
        
        try:
            qos = mapping.get('qos', 1)
            self.mqtt_client.publish(mapping['topic'], payload, qos=qos, retain=False)
            return True
        except Exception as e:
            print(f"❌ CAN Bridge: MQTT publish error: {e}")
            return False
    
    def _is_can_connected(self):
        """Check if CAN manager has devices available"""
        # Check runtime status
        if hasattr(self.can_manager, 'get_status'):
            try:
                status = self.can_manager.get_status()
                if isinstance(status, dict) and status.get('connected', False):
                    return True
                if status.get('devices_count', 0) > 0:
                    return True
            except:
                pass
        
        # Check devices dict
        if hasattr(self.can_manager, 'devices') and self.can_manager.devices:
            return len(self.can_manager.devices) > 0
        
        # Check config file
        import os
        config_file = "/home/radxa/efio/can_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    devices = config.get('devices', [])
                    if any(d.get('enabled', True) for d in devices):
                        return True
            except:
                pass
        
        return False
    
    def start(self) -> bool:
        """Start the bridge service"""
        if self.running:
            print("⚠️ CAN Bridge: Already running")
            return False
        
        if not self.mappings:
            print("⚠️ CAN Bridge: No mappings configured")
            return False
        
        # Check CAN availability (but don't block startup)
        can_available = self._is_can_connected()
        if not can_available:
            print("⚠️  CAN Bridge: No CAN devices detected")
            print("   Bridge will start, but may not receive messages until device is connected")
        
        # Initialize MQTT (this IS required)
        if not self._init_mqtt():
            print("❌ CAN Bridge: Cannot start without MQTT connection")
            return False
        
        # Subscribe to CAN messages
        self.can_manager.subscribe(self._on_can_message)
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        enabled_count = sum(1 for m in self.mappings if m.get('enabled', True))
        print(f"✅ CAN-MQTT Bridge: Started with {enabled_count} mappings")
        
        return True
    
    def stop(self):
        """Stop the bridge service"""
        if not self.running:
            return
        
        print("🛑 CAN Bridge: Stopping...")
        self.running = False
        
        try:
            self.can_manager.unsubscribe(self._on_can_message)
        except:
            pass
        
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        
        print("✅ CAN Bridge: Stopped")
    
    def get_status(self) -> Dict:
        """Get bridge status - UI COMPATIBLE FORMAT"""
        with self._lock:
            uptime = None
            publish_rate = 0.0
            
            if self.stats['start_time']:
                uptime = (datetime.now() - self.stats['start_time']).total_seconds()
                if uptime > 0:
                    publish_rate = round(self.stats['messages_published'] / uptime, 2)
            
            # Build per-mapping details for UI table
            mapping_details = []
            for mapping in self.mappings:
                if mapping.get('enabled', True):
                    mapping_id = mapping['id']
                    last_pub = self.last_publish.get(mapping_id, 0)
                    
                    mapping_details.append({
                        'id': mapping_id,
                        'name': mapping['name'],
                        'can_id': f"0x{mapping['can_id']:03X}",
                        'topic': mapping['topic'],
                        'messages_received': self.message_counts.get(mapping_id, 0),
                        'messages_published': self.message_counts.get(mapping_id, 0),
                        'message_count': self.message_counts.get(mapping_id, 0),
                        'last_publish': last_pub,
                        'last_seen': datetime.fromtimestamp(last_pub).isoformat() if last_pub > 0 else None
                    })
            
            # Return UI-compatible format
            return {
                "running": self.running,
                "can_connected": self._is_can_connected(),
                "mqtt_connected": self.mqtt_connected,
                "mappings_count": len(self.mappings),
                "enabled_mappings": sum(1 for m in self.mappings if m.get('enabled', True)),
                "uptime_seconds": uptime,
                "statistics": {
                    "messages_received": self.stats['messages_received'],
                    "messages_published": self.stats['messages_published'],
                    "messages_dropped": self.stats['messages_dropped'],
                    "errors": self.stats['errors'],
                    "publish_rate": publish_rate
                },
                "mapping_details": mapping_details
            }
    
    def reset_statistics(self):
        """Reset statistics counters"""
        with self._lock:
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