#!/usr/bin/env python3
# efio_daemon/modbus_mqtt_bridge.py
# Modbus to MQTT Bridge Service - Polls Modbus registers and publishes to MQTT

import time
import threading
import json
import paho.mqtt.client as mqtt
from datetime import datetime

class ModbusMQTTBridge:
    """
    Background service that:
    1. Polls Modbus devices for configured registers (FC3, FC4)
    2. Publishes values to MQTT with custom topic names
    3. Handles multiple devices and registers simultaneously
    """
    
    def __init__(self, modbus_manager, mqtt_config):
        """
        Args:
            modbus_manager: Instance with active Modbus connections
            mqtt_config: MQTT broker configuration dict
        """
        self.modbus_manager = modbus_manager
        self.mqtt_config = mqtt_config
        self.mappings = []  # List of {device_id, register, fc, topic, name, unit}
        self.running = False
        self.thread = None
        self.mqtt_client = None
        self.mqtt_connected = False
        self.poll_interval = 1.0  # seconds (default)
        
    def load_mappings(self, mappings):
        """Load register-to-topic mappings"""
        self.mappings = mappings
        print(f"✅ Bridge: Loaded {len(mappings)} mappings")
    
    def set_poll_interval(self, interval):
        """Set polling interval in seconds"""
        self.poll_interval = max(0.5, interval)  # Minimum 500ms
    
    def _init_mqtt(self):
        """Initialize MQTT client"""
        try:
            if not self.mqtt_config.get('enabled', True):
                print("⚠️ Bridge MQTT: Disabled in configuration")
                return False
            
            client_id = f"{self.mqtt_config.get('client_id', 'efio')}-bridge"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Authentication
            username = self.mqtt_config.get('username', '')
            password = self.mqtt_config.get('password', '')
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
            
            # TLS
            if self.mqtt_config.get('use_tls', False):
                self.mqtt_client.tls_set()
            
            # Connect
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            keepalive = self.mqtt_config.get('keepalive', 60)
            
            self.mqtt_client.connect(broker, port, keepalive)
            self.mqtt_client.loop_start()
            
            print(f"✅ Bridge MQTT: Connected to {broker}:{port}")
            return True
            
        except Exception as e:
            print(f"❌ Bridge MQTT: Connection failed: {e}")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            print("✅ Bridge MQTT: Connected successfully")
        else:
            print(f"❌ Bridge MQTT: Connection failed (code {rc})")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.mqtt_connected = False
        if rc != 0:
            print(f"⚠️ Bridge MQTT: Disconnected unexpectedly (code {rc})")
    
    def _publish_to_mqtt(self, topic, value, unit=""):
        """Publish value to MQTT topic"""
        if not self.mqtt_client or not self.mqtt_connected:
            return False
        
        try:
            # Create JSON payload
            payload = {
                "value": value,
                "unit": unit,
                "timestamp": datetime.now().isoformat()
            }
            
            qos = self.mqtt_config.get('qos', 1)
            self.mqtt_client.publish(
                topic, 
                json.dumps(payload), 
                qos=qos, 
                retain=True
            )
            return True
            
        except Exception as e:
            print(f"❌ Bridge: MQTT publish error: {e}")
            return False
    
    def _poll_loop(self):
        """Main polling loop - runs in background thread"""
        print("🔄 Bridge: Polling started")
        
        while self.running:
            if not self.mappings:
                time.sleep(1)
                continue
            
            for mapping in self.mappings:
                if not self.running:
                    break
                
                try:
                    device_id = mapping['device_id']
                    register = mapping['register']
                    function_code = mapping['function_code']
                    topic = mapping['topic']
                    unit = mapping.get('unit', '')
                    
                    # Check if device is connected
                    if device_id not in self.modbus_manager:
                        continue
                    
                    instrument = self.modbus_manager[device_id]
                    
                    # Read register based on function code
                    if function_code == 3:
                        # FC3 - Read Holding Registers
                        value = instrument.read_register(register, functioncode=3)
                    elif function_code == 4:
                        # FC4 - Read Input Registers
                        value = instrument.read_register(register, functioncode=4)
                    else:
                        continue
                    
                    # Apply scaling if configured
                    scaling = mapping.get('scaling', {})
                    if scaling:
                        multiplier = scaling.get('multiplier', 1.0)
                        offset = scaling.get('offset', 0.0)
                        decimals = scaling.get('decimals', 0)
                        value = round((value * multiplier) + offset, decimals)
                    
                    # Publish to MQTT
                    self._publish_to_mqtt(topic, value, unit)
                    
                except Exception as e:
                    # Log error but continue polling other registers
                    error_msg = str(e)
                    if "No communication" not in error_msg:  # Suppress common errors
                        print(f"⚠️ Bridge: Error reading {mapping.get('name', 'unknown')}: {e}")
            
            # Wait before next poll cycle
            time.sleep(self.poll_interval)
    
    def start(self):
        """Start the bridge service"""
        if self.running:
            print("⚠️ Bridge: Already running")
            return False
        
        if not self.mappings:
            print("⚠️ Bridge: No mappings configured")
            return False
        
        # Initialize MQTT
        if not self._init_mqtt():
            print("❌ Bridge: Cannot start without MQTT connection")
            return False
        
        # Start polling thread
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        
        print(f"✅ Bridge: Started with {len(self.mappings)} mappings")
        return True
    
    def stop(self):
        """Stop the bridge service"""
        if not self.running:
            return
        
        print("🛑 Bridge: Stopping...")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2)
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        print("✅ Bridge: Stopped")
    
    def get_status(self):
        """Get bridge status"""
        return {
            "running": self.running,
            "mqtt_connected": self.mqtt_connected,
            "mappings_count": len(self.mappings),
            "poll_interval": self.poll_interval
        }