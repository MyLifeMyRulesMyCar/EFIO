#!/usr/bin/env python3
# efio_daemon/can_mqtt_bridge.py
# CAN to MQTT Bridge Service - Simple CAN ID → Topic Mapping

import time
import threading
import json
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Dict, List, Optional

class CANMQTTBridge:
    """
    Simple CAN to MQTT Bridge
    
    Maps CAN IDs directly to MQTT topics:
    - CAN ID 0x0F6 → mqtt/topic/engine
    - Publishes entire data payload as hex string
    - Change detection to avoid spam
    - Rate limiting per mapping
    
    Later: Add byte parsing, scaling, data types
    """
    
    def __init__(self, can_manager, mqtt_config):
        """
        Args:
            can_manager: CANManager instance
            mqtt_config: MQTT broker configuration dict
        """
        self.can_manager = can_manager
        self.mqtt_config = mqtt_config
        self.mappings = []  # List of {id, name, can_id, topic, enabled, publish_on_change, min_interval_ms}
        self.running = False
        self.mqtt_client = None
        self.mqtt_connected = False
        
        # State tracking
        self.last_values = {}  # {mapping_id: last_data_hex}
        self.last_publish_times = {}  # {mapping_id: timestamp}
        self.statistics = {}  # {mapping_id: {messages_received, messages_published, last_seen}}
        
        self._lock = threading.RLock()
        
        print("✅ CAN-MQTT Bridge initialized")
    
    # ================================
    # Configuration
    # ================================
    
    def load_mappings(self, mappings: List[Dict]):
        """
        Load CAN ID to MQTT topic mappings
        
        Args:
            mappings: List of mapping configs
            [
                {
                    "id": "map_001",
                    "name": "Engine ECU",
                    "can_id": 246,  # 0x0F6
                    "topic": "vehicle/engine/data",
                    "enabled": True,
                    "publish_on_change": True,
                    "min_interval_ms": 100,
                    "qos": 1
                }
            ]
        """
        with self._lock:
            self.mappings = mappings
            
            # Initialize statistics
            for mapping in mappings:
                mapping_id = mapping['id']
                self.statistics[mapping_id] = {
                    'messages_received': 0,
                    'messages_published': 0,
                    'last_seen': None
                }
            
            print(f"✅ CAN-MQTT Bridge: Loaded {len(mappings)} mappings")
    
    # ================================
    # MQTT Connection
    # ================================
    
    def _init_mqtt(self) -> bool:
        """Initialize MQTT client"""
        try:
            # Check if MQTT is enabled
            if not self.mqtt_config.get('enabled', True):
                print("⚠️ CAN-MQTT Bridge: MQTT disabled in configuration")
                return False
            
            # Create client
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
                print(f"🔐 CAN-MQTT Bridge: Using authentication (user: {username})")
            
            # TLS
            if self.mqtt_config.get('use_tls', False):
                self.mqtt_client.tls_set()
                print("🔒 CAN-MQTT Bridge: TLS/SSL enabled")
            
            # Connect
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            keepalive = self.mqtt_config.get('keepalive', 60)
            
            print(f"🔌 CAN-MQTT Bridge: Connecting to {broker}:{port}...")
            self.mqtt_client.connect(broker, port, keepalive)
            self.mqtt_client.loop_start()
            
            # Wait for connection (with timeout)
            timeout = 10
            start_time = time.time()
            while not self.mqtt_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.mqtt_connected:
                raise TimeoutError(f"MQTT connection timeout after {timeout}s")
            
            print(f"✅ CAN-MQTT Bridge: Connected to {broker}:{port}")
            return True
            
        except Exception as e:
            print(f"❌ CAN-MQTT Bridge: MQTT initialization failed: {e}")
            if self.mqtt_client:
                try:
                    self.mqtt_client.loop_stop()
                    self.mqtt_client.disconnect()
                except:
                    pass
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            print("✅ CAN-MQTT Bridge: MQTT connected successfully")
        else:
            print(f"❌ CAN-MQTT Bridge: MQTT connection failed (code {rc})")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.mqtt_connected = False
        if rc != 0:
            print(f"⚠️ CAN-MQTT Bridge: MQTT disconnected unexpectedly (code {rc})")
    
    # ================================
    # Message Processing
    # ================================
    
    def _on_can_message(self, message: Dict):
        """
        Handle incoming CAN message from can_manager
        
        Args:
            message: {
                'timestamp': '2024-01-28T...',
                'direction': 'RX',
                'can_id': 246,
                'dlc': 8,
                'data': [0x8E, 0x87, 0x32, 0xFA, 0x26, 0x8E, 0xBE, 0x86],
                'extended': False
            }
        """
        if not self.running or not self.mqtt_connected:
            return
        
        can_id = message['can_id']
        
        # Find matching mappings for this CAN ID
        with self._lock:
            for mapping in self.mappings:
                if mapping['can_id'] == can_id and mapping.get('enabled', True):
                    self._process_mapping(mapping, message)
    
    def _process_mapping(self, mapping: Dict, message: Dict):
        """
        Process CAN message for a specific mapping
        
        Args:
            mapping: Mapping configuration
            message: CAN message dict
        """
        mapping_id = mapping['id']
        
        try:
            # Update statistics
            stats = self.statistics[mapping_id]
            stats['messages_received'] += 1
            stats['last_seen'] = message['timestamp']
            
            # Convert data to hex string for simple publishing
            data_hex = ' '.join([f'{b:02X}' for b in message['data'][:message['dlc']]])
            
            # Check if should publish
            if not self._should_publish(mapping, data_hex):
                return
            
            # Publish to MQTT
            success = self._publish_to_mqtt(
                topic=mapping['topic'],
                data_hex=data_hex,
                message=message,
                mapping=mapping
            )
            
            if success:
                stats['messages_published'] += 1
                self.last_values[mapping_id] = data_hex
                self.last_publish_times[mapping_id] = time.time()
                
        except Exception as e:
            print(f"⚠️ CAN-MQTT Bridge: Error processing mapping '{mapping.get('name', mapping_id)}': {e}")
    
    def _should_publish(self, mapping: Dict, data_hex: str) -> bool:
        """
        Determine if message should be published based on:
        - Change detection (publish_on_change)
        - Rate limiting (min_interval_ms)
        
        Args:
            mapping: Mapping configuration
            data_hex: Current data as hex string
        
        Returns:
            True if should publish, False otherwise
        """
        mapping_id = mapping['id']
        
        # Check change detection
        if mapping.get('publish_on_change', True):
            last_value = self.last_values.get(mapping_id)
            if last_value == data_hex:
                return False  # No change, don't publish
        
        # Check rate limiting
        min_interval = mapping.get('min_interval_ms', 0) / 1000.0  # Convert to seconds
        if min_interval > 0:
            last_publish = self.last_publish_times.get(mapping_id, 0)
            time_since_publish = time.time() - last_publish
            
            if time_since_publish < min_interval:
                return False  # Too soon, skip
        
        return True
    
    def _publish_to_mqtt(self, topic: str, data_hex: str, message: Dict, mapping: Dict) -> bool:
        """
        Publish CAN message to MQTT
        
        Args:
            topic: MQTT topic
            data_hex: Data as hex string
            message: Original CAN message
            mapping: Mapping configuration
        
        Returns:
            True if published successfully
        """
        if not self.mqtt_client or not self.mqtt_connected:
            return False
        
        try:
            # Create JSON payload
            payload = {
                "can_id": f"0x{message['can_id']:03X}",
                "data": data_hex,
                "dlc": message['dlc'],
                "timestamp": message['timestamp'],
                "extended": message.get('extended', False),
                "mapping": mapping.get('name', mapping['id'])
            }
            
            # Publish
            qos = mapping.get('qos', self.mqtt_config.get('qos', 1))
            self.mqtt_client.publish(
                topic,
                json.dumps(payload),
                qos=qos,
                retain=False
            )
            
            return True
            
        except Exception as e:
            print(f"❌ CAN-MQTT Bridge: MQTT publish error: {e}")
            return False
    
    # ================================
    # Service Control
    # ================================
    
    def start(self) -> bool:
        """Start the bridge service"""
        if self.running:
            print("⚠️ CAN-MQTT Bridge: Already running")
            return False
        
        if not self.mappings:
            print("⚠️ CAN-MQTT Bridge: No mappings configured")
            return False
        
        if not self.can_manager.connected:
            print("⚠️ CAN-MQTT Bridge: CAN bus not connected")
            return False
        
        # Initialize MQTT
        if not self._init_mqtt():
            print("❌ CAN-MQTT Bridge: Cannot start without MQTT connection")
            return False
        
        # Subscribe to CAN messages
        self.can_manager.subscribe(self._on_can_message)
        
        self.running = True
        print(f"✅ CAN-MQTT Bridge: Started with {len(self.mappings)} mappings")
        
        return True
    
    def stop(self):
        """Stop the bridge service"""
        if not self.running:
            return
        
        print("🛑 CAN-MQTT Bridge: Stopping...")
        self.running = False
        
        # Unsubscribe from CAN messages
        try:
            self.can_manager.unsubscribe(self._on_can_message)
        except:
            pass
        
        # Disconnect MQTT
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        
        print("✅ CAN-MQTT Bridge: Stopped")
    
    # ================================
    # Status & Statistics
    # ================================
    
    def get_status(self) -> Dict:
        """Get bridge status"""
        with self._lock:
            return {
                "running": self.running,
                "mqtt_connected": self.mqtt_connected,
                "can_connected": self.can_manager.connected,
                "mappings_count": len(self.mappings),
                "enabled_mappings": len([m for m in self.mappings if m.get('enabled', True)]),
                "statistics": self.statistics.copy()
            }
    
    def get_mapping_stats(self, mapping_id: str) -> Optional[Dict]:
        """Get statistics for specific mapping"""
        return self.statistics.get(mapping_id)
    
    def reset_statistics(self):
        """Reset all statistics"""
        with self._lock:
            for mapping_id in self.statistics:
                self.statistics[mapping_id] = {
                    'messages_received': 0,
                    'messages_published': 0,
                    'last_seen': None
                }
            print("🔄 CAN-MQTT Bridge: Statistics reset")


# ================================
# Testing
# ================================
if __name__ == "__main__":
    print("=" * 60)
    print("CAN-MQTT Bridge Test")
    print("=" * 60)
    
    # This would normally come from can_manager and mqtt_config
    print("\nUsage:")
    print("  from efio_daemon.can_mqtt_bridge import CANMQTTBridge")
    print("  from efio_daemon.can_manager import can_manager")
    print("  from api.mqtt_config import load_mqtt_config")
    print("")
    print("  bridge = CANMQTTBridge(can_manager, load_mqtt_config())")
    print("  bridge.load_mappings([...])")
    print("  bridge.start()")
    print("")
    print("=" * 60)