#!/usr/bin/env python3
# api/app.py - Flask API with WebSocket + MQTT Integration

from flask import Flask, jsonify, request, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import paho.mqtt.client as mqtt
import psutil
import threading
import time
import os
import sys
import json
import signal
import systemd.daemon
from datetime import datetime
#!/usr/bin/env python3
# api/app.py - Add this import at the top with other imports


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from efio_daemon.daemon import EFIODeviceDaemon
from efio_daemon.state import state
from utils.pairing import create_pairing, validate_pairing
from oled_manager.oled_service import show_qr, show_status, show_boot
from api.modbus_routes import modbus_api
from api.auth_routes import auth_api
from api.config_routes import config_api
from api.modbus_device_routes import modbus_device_api,active_connections  
from api.oled_routes import oled_api, init_oled_display, stop_oled_display
from api.backup_routes import backup_api 
from api.mqtt_routes import mqtt_config_api
from api.modbus_mqtt_bridge_routes import modbus_mqtt_api, set_bridge_instance
from efio_daemon.modbus_mqtt_bridge import ModbusMQTTBridge
from api.mqtt_config import load_mqtt_config
from api.health_routes import health_api
from api.can_routes import can_api
from efio_daemon.can_manager import can_manager
from api.can_mqtt_routes import can_mqtt_api, set_bridge_instance as set_can_bridge_instance
from efio_daemon.can_mqtt_bridge import CANMQTTBridge

# Local package imports that rely on project root in sys.path
from efio_daemon.watchdog import WatchdogTimer
# ============================================
# Initialize Flask app
# ============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = Config.JWT_ACCESS_TOKEN_EXPIRES # 8 hours
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = Config.JWT_REFRESH_TOKEN_EXPIRES  # 30 days

# ============================================
# Enable CORS with Dynamic Origins
# ============================================
print(f"🌐 CORS: Allowing origins from config ({len(Config.CORS_ORIGINS)} total)")
for origin in Config.CORS_ORIGINS[:5]:  # Show first 5
    print(f"   - {origin}")

CORS(app, resources={
    r"/*": {
        "origins": Config.CORS_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})



# Initialize JWT
jwt = JWTManager(app)

# Initialize SocketIO with CORS
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",  # Or use Config.CORS_ORIGINS
    async_mode='threading',
    logger=Config.FLASK_DEBUG,
    engineio_logger=Config.FLASK_DEBUG,
    ping_timeout=60,
    ping_interval=25
)

daemon = EFIODeviceDaemon(debug_mqtt=Config.DEBUG_MQTT)
daemon.start()
app.daemon = daemon

# Register blueprints
app.register_blueprint(modbus_api)
app.register_blueprint(auth_api)
app.register_blueprint(config_api)
app.register_blueprint(modbus_device_api)
app.register_blueprint(oled_api)
app.register_blueprint(backup_api)
app.register_blueprint(mqtt_config_api)
app.register_blueprint(modbus_mqtt_api)
app.register_blueprint(health_api)
app.register_blueprint(can_api)
app.register_blueprint(can_mqtt_api)

print("=" * 60)
print("EFIO API Server Starting...")
print(f"API Base URL: {Config.API_BASE_URL}")
print(f"Local IP: {Config.LOCAL_IP}")
print(f"Debug Mode: {Config.FLASK_DEBUG}")
print("=" * 60)

# ============================================
# MQTT Integration
# ============================================



mqtt_client = None
modbus_bridge = None
can_mqtt_bridge = None

_mqtt_callbacks = {
    'on_connect': None,
    'on_disconnect': None,
    'on_message': None
}


MQTT_CONFIG_FILE = "/home/radxa/efio/mqtt_config.json"

mqtt_system = {}

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
# Create watchdog (60 second timeout)
watchdog = WatchdogTimer(
    timeout=60,
    on_timeout=lambda: print("⚠️ WATCHDOG TIMEOUT - System may need restart")
)

# Watchdog feed thread control
_watchdog_feed_thread = None
_watchdog_feed_running = False


'''
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

'''
def on_mqtt_connect(client, userdata, flags, rc):
    """Callback when MQTT client connects"""
    if rc == 0:
        print("✅ MQTT: Connected to broker")
        # Subscribe to all EFIO topics
        client.subscribe("edgeforce/#")
        print("📡 MQTT: Subscribed to edgeforce/#")
        
        # Publish initial state
        for i, val in enumerate(state.get_di()):
            client.publish(f"edgeforce/io/di/{i+1}", val, retain=True)
        for i, val in enumerate(state.get_do()):
            client.publish(f"edgeforce/io/do/{i+1}", val, retain=True)
    else:
        print(f"❌ MQTT: Connection failed with code {rc}")

def on_mqtt_disconnect(client, userdata, rc):
    """Callback when MQTT client disconnects"""
    if rc != 0:
        print(f"⚠️ MQTT: Unexpected disconnection (code {rc})")

def on_mqtt_message(client, userdata, msg):
    """Forward MQTT messages to WebSocket clients"""
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        
        print(f"📥 MQTT: {topic} = {payload}")
        
        # Parse topic: edgeforce/io/di/1 → channel 0
        parts = topic.split('/')
        
        if len(parts) >= 3 and parts[0] == 'edgeforce':
            category = parts[1]  # 'io' or 'system'
            
            # Handle I/O updates
            if category == 'io' and len(parts) == 4:
                io_type = parts[2]  # 'di' or 'do'
                channel = int(parts[3]) - 1  # Convert to 0-indexed
                
                try:
                    value = int(payload)
                    
                    if io_type == 'di' and 0 <= channel < 4:
                        # Update digital input state
                        state.set_di(channel, value)
                        # Broadcast to WebSocket clients
                        socketio.emit('io_update', {
                            'di': state.get_di(), 'do': state.get_do()
                        }, namespace='/')
                        
                    elif io_type == 'do' and 0 <= channel < 4:
                        # Update digital output state (read-back)
                        state.set_do(channel, value)
                        socketio.emit('io_update', {
                            'di': state.get_di(), 'do': state.get_do()
                        }, namespace='/')
                        
                except ValueError:
                    print(f"⚠️ MQTT: Invalid value '{payload}' for {topic}")
            
            # Handle system metrics updates
            elif category == 'system':
                metric_name = parts[2] if len(parts) > 2 else None
                if metric_name:
                    # Store system metrics in state (optional)
                    if 'mqtt_system' not in state:
                        mqtt_system.clear()
                    mqtt_system[metric_name] = payload
                    
    except Exception as e:
        print(f"❌ MQTT message handler error: {e}")
        import traceback
        traceback.print_exc()

_mqtt_callbacks['on_connect'] = on_mqtt_connect
_mqtt_callbacks['on_disconnect'] = on_mqtt_disconnect
_mqtt_callbacks['on_message'] = on_mqtt_message

def init_mqtt():
    """Initialize MQTT client"""
    global mqtt_client
    
    try:
        # Stop existing client if running
        if mqtt_client:
            try:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
                print("🔄 Stopped existing MQTT client")
            except Exception as e:
                print(f"⚠️ Error stopping old client: {e}")
        
        # Load MQTT configuration
        mqtt_config = load_mqtt_config()
        
        # Check if MQTT is enabled
        if not mqtt_config.get('enabled', True):
            print("⚠️ API MQTT: Disabled in configuration")
            mqtt_client = None  # Set to None when disabled
            return False
        
        # Create client with configured ID
        client_id = mqtt_config.get('client_id', 'efio-api')
        mqtt_client = mqtt.Client(client_id=client_id + "-api")
        
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect
        mqtt_client.on_message = on_mqtt_message
        
        # Configure authentication if provided
        username = mqtt_config.get('username', '')
        password = mqtt_config.get('password', '')
        if username and password:
            mqtt_client.username_pw_set(username, password)
            print(f"🔐 API MQTT: Using authentication (user: {username})")
        
        # Configure TLS if enabled
        if mqtt_config.get('use_tls', False):
            mqtt_client.tls_set()
            print("🔒 API MQTT: TLS/SSL enabled")
        
        # Connect to broker
        broker = mqtt_config.get('broker', 'localhost')
        port = mqtt_config.get('port', 1883)
        keepalive = mqtt_config.get('keepalive', 60)
        
        mqtt_client.connect(broker, port, keepalive)
        mqtt_client.loop_start()
        
        print("🔌 API MQTT: Client initialized and connected")
        return True
        
    except Exception as e:
        print(f"❌ MQTT: Initialization failed: {e}")
        mqtt_client = None
        return False

def init_modbus_mqtt_bridge():
    """Initialize Modbus-MQTT Bridge"""
    global modbus_bridge
    
    try:
        # Load MQTT configuration
        mqtt_config = load_mqtt_config()
        
        # Create bridge instance with active Modbus connections
        modbus_bridge = ModbusMQTTBridge(active_connections, mqtt_config)
        
        # Set bridge instance in routes module
        set_bridge_instance(modbus_bridge)
        
        # Load saved configuration
        from api.modbus_mqtt_bridge_routes import load_bridge_config
        bridge_config = load_bridge_config()
        
        # Auto-start if enabled
        if bridge_config.get('enabled', False):
            mappings = bridge_config.get('mappings', [])
            enabled_mappings = [m for m in mappings if m.get('enabled', True)]
            
            if enabled_mappings:
                modbus_bridge.load_mappings(enabled_mappings)
                poll_interval = bridge_config.get('poll_interval', 1.0)
                modbus_bridge.set_poll_interval(poll_interval)
                modbus_bridge.start()
                print(f"✅ Modbus-MQTT Bridge: Auto-started with {len(enabled_mappings)} mappings")
        
        print("✅ Modbus-MQTT Bridge: Initialized")
        return True
        
    except Exception as e:
        print(f"❌ Modbus-MQTT Bridge: Initialization failed: {e}")
        return False

def init_can_mqtt_bridge():
    """Initialize CAN-MQTT Bridge"""
    global can_mqtt_bridge
    
    try:
        # Load MQTT configuration
        mqtt_config = load_mqtt_config()
        
        # Create bridge instance with CAN manager
        can_mqtt_bridge = CANMQTTBridge(can_manager, mqtt_config)
        
        # Set bridge instance in routes module
        set_can_bridge_instance(can_mqtt_bridge)
        
        # Load saved configuration
        from api.can_mqtt_routes import load_bridge_config
        bridge_config = load_bridge_config()
        
        # Auto-start if enabled
        if bridge_config.get('enabled', False):
            mappings = bridge_config.get('mappings', [])
            enabled_mappings = [m for m in mappings if m.get('enabled', True)]
            
            if enabled_mappings:
                can_mqtt_bridge.load_mappings(enabled_mappings)
                can_mqtt_bridge.start()
                print(f"✅ CAN-MQTT Bridge: Auto-started with {len(enabled_mappings)} mappings")
        
        print("✅ CAN-MQTT Bridge: Initialized")
        return True
        
    except Exception as e:
        print(f"❌ CAN-MQTT Bridge: Initialization failed: {e}")
        return False

def init_can_manager():
    """Initialize CAN manager and auto-connect if configured"""
    try:
        from api.can_routes import load_can_config
        from efio_daemon.can_manager import CANDevice  # IMPORTANT: Import CANDevice
        
        config = load_can_config()
        if not config:
            print("⚠️ CAN: No configuration found, using defaults")
            return False
        
        # Check if auto-connect is enabled
        if config.get('auto_connect', False):
            controller_config = config.get('controller', {})
            
            # Configure manager
            can_manager.spi_bus = controller_config.get('spi_bus', 2)
            can_manager.spi_device = controller_config.get('spi_device', 0)
            can_manager.bitrate = controller_config.get('bitrate', 125000)
            can_manager.crystal = controller_config.get('crystal', 8000000)
            
            # Load devices from config - CORRECTED VERSION
            devices_loaded = 0
            for device_data in config.get('devices', []):
                try:
                    # Create CANDevice object
                    device = CANDevice(
                        device_id=device_data['id'],
                        name=device_data['name'],
                        can_id=device_data['can_id'],
                        extended=device_data.get('extended', False),
                        enabled=device_data.get('enabled', True)
                    )
                    
                    # Set messages
                    device.messages = device_data.get('messages', [])
                    
                    # Add to manager (pass the device object)
                    can_manager.add_device(device)
                    
                    devices_loaded += 1
                    print(f"   ✓ Loaded: {device_data['name']} (ID: 0x{device_data['can_id']:02X})")
                        
                except Exception as e:
                    print(f"   ✗ Failed to load device {device_data.get('name', 'unknown')}: {e}")

            print(f"   Total devices loaded: {devices_loaded}/{len(config.get('devices', []))}")
            
            # Connect to bus
            can_manager.connect()
            print(f"✅ CAN: Auto-connected at {can_manager.bitrate} bps")
            print(f"   Devices in manager: {len(can_manager.devices)}")
            return True
        else:
            print("ℹ️ CAN: Auto-connect disabled in configuration")
            return False
        
    except Exception as e:
        print(f"❌ CAN: Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False



# Helper function to publish to MQTT
def mqtt_publish(topic, payload, retain=False):
    """Publish message to MQTT broker"""
    # Check if MQTT is enabled
    mqtt_config = load_mqtt_config()
    if not mqtt_config.get('enabled', True):
        return False  # Skip publishing if disabled
    
    if mqtt_client and mqtt_client.is_connected():
        try:
            mqtt_client.publish(topic, payload, retain=retain)
            return True
        except Exception as e:
            print(f"❌ MQTT publish error: {e}")
            return False
    return False

# Register health check functions
def check_daemon_health():
    """Check if main daemon is running"""
    try:
        return daemon.running and daemon.loop_count > 0
    except:
        return False

def check_mqtt_health():
    """Check MQTT connection"""
    try:
        mqtt_config = load_mqtt_config()
        if not mqtt_config.get('enabled', True):
            return True  # Not required when disabled
        return mqtt_client and mqtt_client.is_connected()
    except:
        return False

def check_gpio_health():
    """Check GPIO status"""
    try:
        from efio_daemon.state import state
        # In simulation mode, we're still operational
        return True
    except:
        return False

# Register components with watchdog
watchdog.register_component("daemon", check_daemon_health)
watchdog.register_component("mqtt", check_mqtt_health)
watchdog.register_component("gpio", check_gpio_health)


# ============================================
# REST API Endpoints
# ============================================

@app.get("/api/status")
def status():
    """Health check endpoint"""
    mqtt_status = "connected" if (mqtt_client and mqtt_client.is_connected()) else "disconnected"
    return jsonify({
        "status": "ok",
        "message": "EFIO API online",
        "version": "1.0.0",
        "websocket": "enabled",
        "mqtt": mqtt_status,
        "api_url": Config.API_BASE_URL,
        "local_ip": Config.LOCAL_IP
    })

@app.get("/api/io")
def get_io():
    """Get current I/O state"""
    return jsonify({
        "di": state.get_di(),
        "do": state.get_do(),
        "timestamp": time.time()
    })

@app.post("/api/io/do/<int:ch>")
def set_do(ch):
    """Set digital output state"""
    if ch < 0 or ch >= 4:
        return jsonify({"error": "Invalid channel"}), 400
    
    data = request.get_json()
    new_val = 1 if data.get("state") else 0
    
    # Update local state
    state.set_do(ch, new_val)
    
    # Write to hardware
    daemon.manager.write_output(ch, new_val)
    
    # Publish to MQTT (command topic)
    mqtt_publish(f"edgeforce/io/do/{ch+1}/set", new_val, retain=False)
    
    # Publish actual state (feedback topic)
    mqtt_publish(f"edgeforce/io/do/{ch+1}", new_val, retain=True)
    
    # Broadcast change to WebSocket clients
    socketio.emit('io_update', {
        'di': state.get_di(), 'do': state.get_do()
    }, namespace='/')
    
    return jsonify({
        "channel": ch,
        "new_value": new_val
    })

@app.get("/api/system")
def get_system_metrics():
    """Get system metrics (CPU, RAM, Temperature)"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Temperature (RK3588 specific)
        temp = 45.0  # Default
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000.0
        except Exception as e:
            pass
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Uptime
        uptime = time.time() - psutil.boot_time()
        
        metrics = {
            "cpu": {
                "percent": round(cpu_percent, 1),
                "cores": psutil.cpu_count()
            },
            "memory": {
                "percent": memory.percent,
                "used_gb": round(memory.used / (1024**3), 2),
                "total_gb": round(memory.total / (1024**3), 2)
            },
            "temperature": {
                "celsius": round(temp, 1),
                "fahrenheit": round(temp * 9/5 + 32, 1)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": round(disk.used / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2)
            },
            "uptime_seconds": int(uptime)
        }
        
        # Publish to MQTT
        mqtt_publish("edgeforce/system/cpu", cpu_percent)
        mqtt_publish("edgeforce/system/ram", memory.percent)
        mqtt_publish("edgeforce/system/temp", temp)
        mqtt_publish("edgeforce/system/uptime", uptime)
        
        return jsonify(metrics)
        
    except Exception as e:
        print(f"Error getting system metrics: {e}")
        return jsonify({"error": str(e)}), 500

@app.post("/api/pair/create")
def create_pair():
    data = request.get_json()
    sn = data.get("sn")
    if not sn:
        return jsonify({"error": "SN required"}), 400
    
    token, qr_path, url = create_pairing(sn)
    return jsonify({
        "sn": sn,
        "token": token,
        "qr_path": qr_path,
        "pair_url": url
    })

@app.get("/api/pair/qr")
def get_qr():
    return send_file("/tmp/oled.png", mimetype="image/png")

@app.get("/pair")
def pair_check():
    sn = request.args.get("sn")
    tok = request.args.get("tok")
    if not sn or not tok:
        return jsonify({"error": "Missing parameters"}), 400
    
    if validate_pairing(sn, tok):
        return jsonify({"status": "success", "message": "Pairing OK"})
    return jsonify({"status": "fail", "message": "Invalid token"}), 403

@app.get("/api/oled/splash")
def oled_splash():
    show_boot()
    return jsonify({"status": "ok", "msg": "splash shown"})

@app.post("/api/oled/status")
def oled_status():
    data = request.get_json()
    ip = data.get("ip", "0.0.0.0")
    status_msg = data.get("status", "OK")
    show_status(ip, status_msg)
    return jsonify({"status": "ok"})

@app.post("/api/oled/qr")
def oled_qr():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "url required"}), 400
    show_qr(url)
    return jsonify({"status": "ok"})

# ============================================
# MQTT Testing Endpoints (for debugging)
# ============================================

@app.get("/api/mqtt/status")
def mqtt_status():
    """Get MQTT connection status"""
    if mqtt_client:
        return jsonify({
            "connected": mqtt_client.is_connected(),
            "broker": "localhost:1883"
        })
    return jsonify({
        "connected": False,
        "error": "MQTT client not initialized"
    })

@app.post("/api/mqtt/publish")
def mqtt_publish_test():
    """Test MQTT publish (for debugging)"""
    data = request.get_json()
    topic = data.get("topic")
    payload = data.get("payload")
    
    if not topic or payload is None:
        return jsonify({"error": "topic and payload required"}), 400
    
    success = mqtt_publish(topic, payload)
    return jsonify({
        "success": success,
        "topic": topic,
        "payload": payload
    })

# ============================================
# ADD NEW HEALTH ENDPOINT
# ============================================

@app.route('/api/health/watchdog', methods=['GET'])
def watchdog_health():
    """
    Comprehensive health check for systemd watchdog.
    Returns 200 only if all critical systems are healthy.
    """
    try:
        report = watchdog.get_health_report()
        
        # Determine overall health
        watchdog_ok = report['watchdog']['status'] == 'healthy'
        
        # Check critical components
        critical_components = ['daemon', 'mqtt']
        components_ok = all(
            report['components'].get(comp, {}).get('status') == 'healthy'
            for comp in critical_components
        )
        
        overall_healthy = watchdog_ok and components_ok
        
        response = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "watchdog": report['watchdog'],
            "components": report['components']
        }
        
        status_code = 200 if overall_healthy else 503
        return jsonify(response), status_code
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ============================================
# WATCHDOG TESTING ENDPOINTS (Development Only)
# ============================================

@app.route('/api/test/watchdog/stop', methods=['POST'])
def test_watchdog_stop():
    """
    Test endpoint: Stop feeding the watchdog.
    This should cause systemd to restart the service in ~60-90 seconds.
    """
    try:
        # Stop both the software watchdog and the systemd feed thread
        stop_watchdog_feed()
        return jsonify({
            "status": "watchdog_stopped",
            "message": "Watchdog feeding stopped. Service should restart in 60-90 seconds if systemd watchdog is enabled.",
            "warning": "This is a destructive test!"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/test/watchdog/status', methods=['GET'])
def test_watchdog_status():
    """
    Get detailed watchdog status for testing.
    """
    try:
        report = watchdog.get_health_report()
        return jsonify({
            "watchdog_thread_running": watchdog.running,
            "watchdog_feed_running": _watchdog_feed_running,
            "last_feed": report['watchdog'].get('last_feed'),
            "time_since_feed": report['watchdog'].get('time_since_feed'),
            "timeout": report['watchdog'].get('timeout'),
            "components": report['components']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/test/crash', methods=['POST'])
def test_crash():
    """
    Test endpoint: Crash the application immediately.
    This should trigger an immediate systemd restart.
    """
    import os
    print("⚠️ TEST: Crashing application NOW!")
    os._exit(1)  # Hard crash


@app.route('/api/test/segfault', methods=['POST'])
def test_segfault():
    """
    Test endpoint: Simulate a Python segfault.
    This should trigger an immediate systemd restart.
    """
    import ctypes
    print("⚠️ TEST: Triggering segfault!")
    ctypes.string_at(0)  # This will cause a segfault
    return jsonify({"status": "this won't be reached"})


@app.route('/api/test/daemon/break', methods=['POST'])
def test_daemon_break():
    """
    Test endpoint: Break the daemon component.
    This should cause component health check to fail.
    """
    try:
        daemon.stop()
        return jsonify({
            "status": "daemon_stopped",
            "message": "Daemon stopped. Health checks should now fail."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# MONITORING ENDPOINT
# ============================================

@app.route('/api/test/watchdog/feed-manual', methods=['POST'])
def test_watchdog_feed_manual():
    """
    Manually feed the watchdog once (for testing).
    """
    try:
        watchdog.feed()
        return jsonify({
            "status": "fed",
            "message": "Watchdog manually fed"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# WebSocket Events
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('✅ WebSocket: Client connected')
    # Send initial state
    emit('io_update', {
        'di': state.get_di(), 'do': state.get_do()
    })
    
    # Get and send system metrics
    try:
        metrics = get_system_metrics().get_json()
        emit('system_update', metrics)
    except Exception as e:
        print(f"Error sending initial system metrics: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('❌ WebSocket: Client disconnected')

@socketio.on('request_io')
def handle_request_io():
    """Client requests current I/O state"""
    print('📥 WebSocket: I/O state requested')
    emit('io_update', {
        'di': state.get_di(), 'do': state.get_do()
    })

@socketio.on('request_system')
def handle_request_system():
    """Client requests system metrics"""
    print('📊 WebSocket: System metrics requested')
    try:
        metrics = get_system_metrics().get_json()
        emit('system_update', metrics)
    except Exception as e:
        print(f"Error sending system metrics: {e}")

@socketio.on('set_do')
def handle_set_do(data):
    """Handle digital output control from WebSocket"""
    print(f'⚡ WebSocket: Set DO command received: {data}')
    
    ch = data.get('channel')
    value = data.get('value')
    
    if ch is None or value is None:
        emit('error', {'message': 'Missing channel or value'})
        return
    
    if ch < 0 or ch >= 4:
        emit('error', {'message': 'Invalid channel'})
        return
    
    # Update state
    state.set_do(ch, value)
    
    # Write to hardware
    daemon.manager.write_output(ch, value)
    
    # Publish to MQTT
    mqtt_publish(f"edgeforce/io/do/{ch+1}/set", value)
    mqtt_publish(f"edgeforce/io/do/{ch+1}", value, retain=True)
    
    # Broadcast to all clients
    socketio.emit('io_update', {
        'di': state.get_di(), 'do': state.get_do()
    }, namespace='/')
    
    print(f'✅ DO{ch} set to {value}')

# ============================================
# Background Tasks
# ============================================

def background_broadcast():
    """Background thread to broadcast I/O and system updates"""
    print("🔄 Background broadcast thread started")
    last_io_state = {"di": [], "do": []}
    broadcast_count = 0
    
    while True:
        try:
            with app.app_context():
                broadcast_count += 1
                
                # Always broadcast I/O state
                current_io = {"di": state.get_di(), "do": state.get_do()}
                socketio.emit('io_update', current_io, namespace='/')
                
                if current_io != last_io_state:
                    print(f"📡 I/O state changed: {current_io}")
                    last_io_state = current_io
                
                # Broadcast system metrics
                try:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    memory = psutil.virtual_memory()
                    
                    # Temperature
                    temp = 45.0
                    try:
                        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                            temp = int(f.read().strip()) / 1000.0
                    except:
                        pass
                    
                    disk = psutil.disk_usage('/')
                    uptime = time.time() - psutil.boot_time()
                    
                    metrics = {
                        "cpu": {
                            "percent": round(cpu_percent, 1),
                            "cores": psutil.cpu_count()
                        },
                        "memory": {
                            "percent": memory.percent,
                            "used_gb": round(memory.used / (1024**3), 2),
                            "total_gb": round(memory.total / (1024**3), 2)
                        },
                        "temperature": {
                            "celsius": round(temp, 1),
                            "fahrenheit": round(temp * 9/5 + 32, 1)
                        },
                        "disk": {
                            "percent": disk.percent,
                            "used_gb": round(disk.used / (1024**3), 2),
                            "total_gb": round(disk.total / (1024**3), 2)
                        },
                        "uptime_seconds": int(uptime)
                    }
                    
                    socketio.emit('system_update', metrics, namespace='/')
                    
                    # Publish to MQTT every broadcast
                    mqtt_publish("edgeforce/system/cpu", cpu_percent)
                    mqtt_publish("edgeforce/system/ram", memory.percent)
                    mqtt_publish("edgeforce/system/temp", temp)
                    
                    # Log every 10 broadcasts (every 20 seconds)
                    if broadcast_count % 10 == 0:
                        print(f"📡 Broadcast #{broadcast_count}: CPU={cpu_percent:.1f}%, RAM={memory.percent:.1f}%, Temp={temp:.1f}°C")
                
                except Exception as e:
                    print(f"❌ Error creating system metrics: {e}")
            
            time.sleep(2)  # Update every 2 seconds
            
        except Exception as e:
            print(f"❌ Error in background broadcast: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(2)

def broadcast_can_message(message):
    """Broadcast CAN message to WebSocket clients"""
    try:
        socketio.emit('can_message', message, namespace='/')
    except Exception as e:
        print(f"WebSocket broadcast error: {e}")

def start_background_thread():
    """Start background thread after socketio is initialized"""
    background_thread = threading.Thread(target=background_broadcast, daemon=True)
    background_thread.start()
    print("✅ Background broadcast thread started")


# ============================================
# ADD WATCHDOG FEED IN BACKGROUND THREAD
# ============================================

def watchdog_feed_loop():
    """
    Background thread that feeds watchdog.
    This proves the main event loop is still running.
    """
    global _watchdog_feed_running
    while _watchdog_feed_running:
        try:
            # Feed watchdog to show we're alive
            watchdog.feed()
            
            # Also notify systemd we're alive (for systemd watchdog)
            try:
                systemd.daemon.notify('WATCHDOG=1')
            except:
                pass
            
        except Exception as e:
            print(f"❌ Watchdog feed error: {e}")
        
        # Sleep ALWAYS happens, outside the exception handling
        time.sleep(30)  # Feed every 30 seconds (timeout is 60s)

def start_watchdog_thread():
    """Start watchdog monitoring and feeding"""
    # Start watchdog timer
    watchdog.start()
    
    # Start feed thread (controlled by _watchdog_feed_running)
    global _watchdog_feed_thread, _watchdog_feed_running
    if _watchdog_feed_thread and _watchdog_feed_thread.is_alive():
        print("⚠️ Watchdog feed thread already running")
        return

    _watchdog_feed_running = True
    _watchdog_feed_thread = threading.Thread(
        target=watchdog_feed_loop,
        name="WatchdogFeed",
        daemon=True
    )
    _watchdog_feed_thread.start()
    
    print("✅ Watchdog monitoring started (60s timeout)")


def stop_watchdog_feed():
    """Stop the watchdog feed thread and the watchdog monitor"""
    global _watchdog_feed_thread, _watchdog_feed_running
    print("Stopping watchdog feed thread")
    _watchdog_feed_running = False
    if _watchdog_feed_thread:
        _watchdog_feed_thread.join(timeout=5)
        _watchdog_feed_thread = None
    # Also stop the software watchdog
    try:
        watchdog.stop()
    except:
        pass
    print("Watchdog feed stopped")

# ============================================
# ADD SIGNAL HANDLERS FOR GRACEFUL SHUTDOWN
# ============================================

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n⚠️ Received signal {sig}, shutting down gracefully...")
    
    # Stop watchdog
    watchdog.stop()
    
    # Stop daemon
    daemon.stop()
    
    # Notify systemd we're stopping
    try:
        systemd.daemon.notify('STOPPING=1')
    except:
        pass
    
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ============================================
# Main
# ============================================


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 EFIO API Server with Watchdog")
    print("=" * 60)
    print(f"📡 HTTP API: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    print(f"🔌 WebSocket: ws://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    print(f"🐕 Watchdog: 60s timeout with systemd integration")
    print("=" * 60 + "\n")
    
    # Initialize MQTT
    mqtt_initialized = init_mqtt()
    if mqtt_initialized:
        print("✅ MQTT broker connected")
    else:
        print("⚠️ Running without MQTT (fallback mode)")
    
    init_can_manager()
    can_manager.subscribe(broadcast_can_message)
    # Initialize Modbus-MQTT bridge
    init_modbus_mqtt_bridge()
    init_can_mqtt_bridge()
    # Initialize CAN manager
    
    
    
    # Start background threads
    start_background_thread()
    
    # Initialize OLED
    init_oled_display()
    import atexit
    atexit.register(stop_oled_display)
    
    # Cleanup bridge on exit
    def cleanup_bridge():
        if modbus_bridge:
            modbus_bridge.stop()
    atexit.register(cleanup_bridge)

    def cleanup_can():
        if can_manager.connected:
            can_manager.disconnect()
    import atexit
    atexit.register(cleanup_can)

    def cleanup_can_bridge():
        if can_mqtt_bridge:
            can_mqtt_bridge.stop()
    atexit.register(cleanup_can_bridge)
    
    # START WATCHDOG MONITORING
    start_watchdog_thread()
    
    # Notify systemd we're ready
    try:
        systemd.daemon.notify('READY=1')
        print("✅ Notified systemd: Service ready")
    except:
        print("⚠️ systemd notification not available (running standalone)")
    
    # Run with SocketIO
    socketio.run(
        app, 
        host=Config.FLASK_HOST, 
        port=Config.FLASK_PORT, 
        debug=Config.FLASK_DEBUG,
        use_reloader=Config.RELOAD_ON_CHANGE,
        allow_unsafe_werkzeug=True
    )