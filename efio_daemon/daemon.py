# efio_daemon/daemon.py
# Device daemon with MQTT publishing

import time
import threading
import paho.mqtt.client as mqtt
from efio_daemon.io_manager import IOManager
from efio_daemon.state import state

class EFIODeviceDaemon:
    def __init__(self, debug_mqtt=False):
        self.manager = IOManager()
        self.running = True
        self.last_di = [0, 0, 0, 0]
        self.mqtt_client = None
        self.mqtt_connected = False
        self.debug_mqtt = debug_mqtt  # If True, publish every cycle
        self.loop_count = 0
        
        # Initialize MQTT client
        self._init_mqtt()
        
    def _init_mqtt(self):
        """Initialize MQTT client for publishing I/O changes"""
        try:
            self.mqtt_client = mqtt.Client(client_id="efio_daemon")
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start()
            print("🔌 Daemon: MQTT client initialized")
        except Exception as e:
            print(f"⚠️ Daemon: MQTT initialization failed: {e}")
            print("   Daemon will continue without MQTT publishing")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when MQTT connects"""
        if rc == 0:
            self.mqtt_connected = True
            print("✅ Daemon: Connected to MQTT broker")
            
            # Publish initial I/O state
            for i, val in enumerate(state["di"]):
                self._publish_di(i, val)
            for i, val in enumerate(state["do"]):
                self._publish_do(i, val)
        else:
            print(f"❌ Daemon: MQTT connection failed (code {rc})")
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
                self.mqtt_client.publish(topic, value, retain=True)
                print(f"📤 Daemon: Published {topic} = {value}")
            except Exception as e:
                print(f"❌ Daemon: MQTT publish error: {e}")
    
    def _publish_do(self, channel, value):
        """Publish digital output state to MQTT"""
        if self.mqtt_client and self.mqtt_connected:
            try:
                topic = f"edgeforce/io/do/{channel + 1}"
                self.mqtt_client.publish(topic, value, retain=True)
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
        print("✅ efio-daemon running (with MQTT publishing)...")
    
    def stop(self):
        """Stop the daemon"""
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        print("🛑 efio-daemon stopped")