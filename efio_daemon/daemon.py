#!/usr/bin/env python3
# efio_daemon/daemon.py
# UPDATED: With MQTT retry logic and circuit breaker

import time
import threading
import paho.mqtt.client as mqtt
import json
import os
from efio_daemon.io_manager import IOManager
from efio_daemon.state import state
from api.mqtt_config import load_mqtt_config
from efio_daemon.resilience import (
    CircuitBreaker, 
    retry_with_backoff, 
    health_status
)

class EFIODeviceDaemon:
    def __init__(self, debug_mqtt=False):
        self.manager = IOManager()
        self.running = True
        self.last_di = [0, 0, 0, 0]
        self.mqtt_client = None
        self.mqtt_connected = False
        self.debug_mqtt = debug_mqtt
        self.loop_count = 0
        
        # Load MQTT configuration
        self.mqtt_config = load_mqtt_config()
        
        # Circuit breaker for MQTT (5 failures, 60s timeout)
        self.mqtt_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            expected_exception=Exception,
            name="MQTT"
        )
        
        # Initialize MQTT with retry
        self._init_mqtt_with_retry()
        
    def _init_mqtt_with_retry(self, max_retries=3):
        """Initialize MQTT with retry logic and circuit breaker"""
        
        if not self.mqtt_config.get('enabled', True):
            print("⚠️ Daemon MQTT: Disabled in configuration")
            health_status.update("mqtt", "degraded", "MQTT disabled in config")
            return False
        
        for attempt in range(max_retries):
            try:
                success = self._init_mqtt()
                if success:
                    health_status.update("mqtt", "healthy", "Connected to broker")
                    return True
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"⚠️ Daemon MQTT: Connection attempt {attempt + 1}/{max_retries} failed")
                print(f"   Error: {e}")
                print(f"   Retrying in {wait_time}s...")
                
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
        
        print("❌ Daemon MQTT: All connection attempts failed")
        print("⚠️ Daemon: Running in DEGRADED mode (MQTT disabled)")
        health_status.update("mqtt", "unhealthy", "All connection attempts failed")
        
        # System continues without MQTT (graceful degradation)
        return False
    
    def _init_mqtt(self):
        """Initialize MQTT client (wrapped by retry logic)"""
        try:
            client_id = self.mqtt_config.get('client_id', 'efio-daemon')
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Authentication
            username = self.mqtt_config.get('username', '')
            password = self.mqtt_config.get('password', '')
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
                print(f"🔐 Daemon MQTT: Using authentication (user: {username})")
            
            # TLS
            if self.mqtt_config.get('use_tls', False):
                self.mqtt_client.tls_set()
                print("🔒 Daemon MQTT: TLS/SSL enabled")
            
            # Connect with timeout
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            keepalive = self.mqtt_config.get('keepalive', 60)
            
            print(f"🔌 Daemon: Connecting to MQTT broker {broker}:{port}...")
            
            # Set connect timeout
            self.mqtt_client.connect(broker, port, keepalive)
            self.mqtt_client.loop_start()
            
            # Wait for connection confirmation (with timeout)
            timeout = 10  # seconds
            start_time = time.time()
            while not self.mqtt_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.mqtt_connected:
                raise TimeoutError(f"MQTT connection timeout after {timeout}s")
            
            print("✅ Daemon: MQTT client initialized")
            return True
            
        except Exception as e:
            print(f"❌ Daemon: MQTT initialization error: {e}")
            if self.mqtt_client:
                try:
                    self.mqtt_client.loop_stop()
                    self.mqtt_client.disconnect()
                except:
                    pass
            raise  # Re-raise for retry logic
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when MQTT connects"""
        if rc == 0:
            self.mqtt_connected = True
            broker = self.mqtt_config.get('broker', 'localhost')
            port = self.mqtt_config.get('port', 1883)
            print(f"✅ Daemon: Connected to MQTT broker {broker}:{port}")
            
            # Reset circuit breaker on successful connection
            self.mqtt_breaker.reset()
            
            # Publish initial I/O state
            for i, val in enumerate(state["di"]):
                self._publish_di(i, val)
            for i, val in enumerate(state["do"]):
                self._publish_do(i, val)
            
            health_status.update("mqtt", "healthy", "Connected and publishing")
        else:
            self.mqtt_connected = False
            error_msgs = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            error = error_msgs.get(rc, f"Unknown error (code {rc})")
            print(f"❌ Daemon: MQTT connection failed: {error}")
            health_status.update("mqtt", "unhealthy", f"Connection failed: {error}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when MQTT disconnects"""
        self.mqtt_connected = False
        
        if rc != 0:
            print(f"⚠️ Daemon: MQTT disconnected unexpectedly (code {rc})")
            print("🔄 Daemon: Will attempt reconnection...")
            health_status.update("mqtt", "degraded", "Disconnected, reconnecting...")
            
            # Attempt reconnection in background
            def reconnect():
                time.sleep(5)  # Wait before reconnecting
                self._init_mqtt_with_retry()
            
            threading.Thread(target=reconnect, daemon=True).start()
    
    def _publish_di(self, channel, value):
        """Publish digital input with error handling"""
        if not self.mqtt_client or not self.mqtt_connected:
            return False
        
        try:
            # Wrap publish in circuit breaker
            @self.mqtt_breaker.call
            def publish():
                topic = f"edgeforce/io/di/{channel + 1}"
                qos = self.mqtt_config.get('qos', 1)
                self.mqtt_client.publish(topic, value, qos=qos, retain=True)
            
            publish()
            return True
            
        except Exception as e:
            # Circuit breaker will log the error
            return False
    
    def _publish_do(self, channel, value):
        """Publish digital output with error handling"""
        if not self.mqtt_client or not self.mqtt_connected:
            return False
        
        try:
            @self.mqtt_breaker.call
            def publish():
                topic = f"edgeforce/io/do/{channel + 1}"
                qos = self.mqtt_config.get('qos', 1)
                self.mqtt_client.publish(topic, value, qos=qos, retain=True)
            
            publish()
            return True
            
        except Exception as e:
            return False

    def loop(self):
        """Main daemon loop with error handling"""
        print("🔄 Daemon: Main loop started")
        
        # Update health status
        health_status.update("daemon", "healthy", "Main loop running")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.running:
            try:
                self.loop_count += 1
                
                # Read DI from hardware (with error handling)
                try:
                    di_values = self.manager.read_all_inputs()
                except Exception as e:
                    print(f"⚠️ Daemon: GPIO read error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"❌ Daemon: Too many consecutive GPIO errors ({consecutive_errors})")
                        health_status.update("gpio", "unhealthy", f"Read failures: {consecutive_errors}")
                    time.sleep(1)
                    continue
                
                # Reset error counter on success
                consecutive_errors = 0
                health_status.update("gpio", "healthy", "I/O operational")
                
                # Check for changes and publish
                for i, val in enumerate(di_values):
                    if val != self.last_di[i]:
                        print(f"🔄 Daemon: DI{i+1} changed: {self.last_di[i]} → {val}")
                        self._publish_di(i, val)
                        self.last_di[i] = val
                    elif self.debug_mqtt and self.loop_count % 50 == 0:
                        self._publish_di(i, val)
                
                # Update state
                state["di"] = di_values
                
                time.sleep(0.1)  # 100ms polling rate
                
            except Exception as e:
                print(f"❌ Daemon: Unexpected error in main loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)  # Prevent tight error loop

    def start(self):
        """Start the daemon thread"""
        t = threading.Thread(target=self.loop, daemon=True)
        t.start()
        
        broker = self.mqtt_config.get('broker', 'localhost')
        port = self.mqtt_config.get('port', 1883)
        mqtt_status = "enabled" if self.mqtt_connected else "disabled (degraded mode)"
        print(f"✅ efio-daemon running (MQTT: {mqtt_status})...")
    
    def stop(self):
        """Stop the daemon"""
        print("🛑 Stopping efio-daemon...")
        self.running = False
        
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        
        health_status.update("daemon", "unhealthy", "Daemon stopped")
        print("✅ efio-daemon stopped")
    
    def reload_mqtt_config(self):
        """Reload MQTT configuration and reconnect"""
        print("🔄 Daemon: Reloading MQTT configuration...")
        
        # Stop old connection
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except:
                pass
        
        self.mqtt_connected = False
        
        # Load new config
        self.mqtt_config = load_mqtt_config()
        
        # Reset circuit breaker
        self.mqtt_breaker.reset()
        
        # Reinitialize with retry
        self._init_mqtt_with_retry()
        
        print("✅ Daemon: MQTT configuration reloaded")
    
    def get_health_status(self):
        """Get daemon health status"""
        return {
            "running": self.running,
            "mqtt_connected": self.mqtt_connected,
            "mqtt_circuit_breaker": self.mqtt_breaker.get_state(),
            "loop_count": self.loop_count
        }