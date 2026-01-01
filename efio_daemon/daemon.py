# efio_daemon/daemon.py
# Device daemon with MQTT publishing and configurable broker

import time
import threading
import paho.mqtt.client as mqtt
import json
import os
from efio_daemon.io_manager import IOManager
from efio_daemon.state import state
from api.mqtt_config import load_mqtt_config, DEFAULT_MQTT_CONFIG

# MQTT Configuration file path
MQTT_CONFIG_FILE = "/home/radxa/efio/mqtt_config.json"

DEFAULT_MQTT_CONFIG = {
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
        print(f"⚠️ MQTT config not found, using defaults: {DEFAULT_MQTT_CONFIG['broker']}:{DEFAULT_MQTT_CONFIG['port']}")
        return DEFAULT_MQTT_CONFIG
    
    try:
        with open(MQTT_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            print(f"✅ Loaded MQTT config: {config['broker']}:{config['port']}")
            return config
    except Exception as e:
        print(f"❌ Error loading MQTT config: {e}")
        print(f"   Using defaults: {DEFAULT_MQTT_CONFIG['broker']}:{DEFAULT_MQTT_CONFIG['port']}")
        return DEFAULT_MQTT_CONFIG

class EFIODeviceDaemon:
    def __init__(self, debug_mqtt=False):
        self.manager = IOManager()
        self.running = True
        self.last_di = [0, 0, 0, 0]
        self.mqtt_client = None
        self.mqtt_connected = False
        self.debug_mqtt = debug_mqtt  # If True, publish every cycle
        self.loop_count = 0
        
        # Load MQTT configuration
        self.mqtt_config = load_mqtt_config()
        
        # Initialize MQTT client
        self._init_mqtt()
        
    def _init_mqtt(self):
        """Initialize MQTT client for publishing I/O changes"""

        if not self.mqtt_config.get('enabled', True):
            print("⚠️ MQTT: Disabled in configuration")
            return False
        try:
            # Create client with configured client ID
            client_id = self.mqtt_config.get('client_id', 'efio-daemon')
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Configure authentication if provided
            username = self.mqtt_config.get('username', '')
            password = self.mqtt_config.get('password', '')
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
                print(f"🔐 MQTT: Using authentication (user: {username})")
            
            # Configure TLS if enabled
            if self.mqtt_config.get('use_tls', False):
                self.mqtt_client.tls_set()
                print("🔒 MQTT: TLS/SSL enabled")
            
            # Connect to broker
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            keepalive = self.mqtt_config.get('keepalive', 60)
            
            print(f"🔌 Daemon: Connecting to MQTT broker {broker}:{port}...")
            self.mqtt_client.connect(broker, port, keepalive)
            self.mqtt_client.loop_start()
            
            print("✅ Daemon: MQTT client initialized")
            return True
            
        except Exception as e:
            print(f"❌ Daemon: MQTT initialization failed: {e}")
            print("⚠️ Daemon: System will continue without MQTT publishing")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when MQTT connects"""
        if rc == 0:
            self.mqtt_connected = True
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            print(f"✅ Daemon: Connected to MQTT broker {broker}:{port}")
            
            # Publish initial I/O state
            for i, val in enumerate(state["di"]):
                self._publish_di(i, val)
            for i, val in enumerate(state["do"]):
                self._publish_do(i, val)
        else:
            print(f"❌ Daemon: MQTT connection failed (code {rc})")
            if rc == 4:
                print("   Bad username or password")
            elif rc == 5:
                print("   Not authorized")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when MQTT disconnects"""
        self.mqtt_connected = False
        if rc != 0:
            print(f"⚠️ Daemon: MQTT disconnected unexpectedly (code {rc})")
    
    def _publish_di(self, channel, value):
        """Publish digital input change to MQTT"""
        if self.mqtt_client and self.mqtt_connected:
            try:
                topic = f"edgeforce/io/di/{channel + 1}"
                qos = self.mqtt_config.get('qos', 1)
                self.mqtt_client.publish(topic, value, qos=qos, retain=True)
                print(f"📤 Daemon: Published {topic} = {value}")
            except Exception as e:
                print(f"❌ Daemon: MQTT publish error: {e}")
    
    def _publish_do(self, channel, value):
        """Publish digital output state to MQTT"""
        if self.mqtt_client and self.mqtt_connected:
            try:
                topic = f"edgeforce/io/do/{channel + 1}"
                qos = self.mqtt_config.get('qos', 1)
                self.mqtt_client.publish(topic, value, qos=qos, retain=True)
            except Exception as e:
                print(f"❌ Daemon: MQTT publish error: {e}")

    def loop(self):
        """Main daemon loop - poll inputs and publish changes"""
        while self.running:
            self.loop_count += 1
            
            # Read DI from hardware
            di_values = self.manager.read_all_inputs()
            
            # Check for changes and publish to MQTT
            for i, val in enumerate(di_values):
                # Publish if changed OR if in debug mode every 50 loops (5 seconds)
                should_publish = (val != self.last_di[i]) or \
                                (self.debug_mqtt and self.loop_count % 50 == 0)
                
                if val != self.last_di[i]:
                    print(f"🔄 Daemon: DI{i+1} changed: {self.last_di[i]} → {val}")
                    self._publish_di(i, val)
                    self.last_di[i] = val
                elif should_publish:
                    # Debug: Publish even if unchanged
                    self._publish_di(i, val)
            
            # Update global state
            state["di"] = di_values
            
            # DO state is already set by API writes
            # Hardware sync happens in write_output()
            
            time.sleep(0.1)  # 100ms polling rate

    def start(self):
        """Start the daemon thread"""
        t = threading.Thread(target=self.loop, daemon=True)
        t.start()
        broker = self.mqtt_config.get('broker', 'localhost')
        port = self.mqtt_config.get('port', 1883)
        print(f"✅ efio-daemon running (MQTT: {broker}:{port})...")
    
    def stop(self):
        """Stop the daemon"""
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        print("🛑 efio-daemon stopped")
    
    def reload_mqtt_config(self):
        """Reload MQTT configuration and reconnect"""
        print("🔄 Reloading MQTT configuration...")
        
        # Stop old connection
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        # Load new config
        self.mqtt_config = load_mqtt_config()
        
        # Reinitialize MQTT
        self._init_mqtt()
        
        print("✅ MQTT configuration reloaded")