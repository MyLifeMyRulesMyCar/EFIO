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

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from efio_daemon.daemon import EFIODeviceDaemon
from efio_daemon.state import state
from utils.pairing import create_pairing, validate_pairing
from oled_manager.oled_service import show_qr, show_status, show_boot
from api.modbus_routes import modbus_api
from api.auth_routes import auth_api
from api.config_routes import config_api
from api.modbus_device_routes import modbus_device_api
from api.oled_routes import oled_api, init_oled_display, stop_oled_display
from api.backup_routes import backup_api 
from api.mqtt_routes import mqtt_config_api
# ============================================
# Initialize Flask app
# ============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'edgeforce-secret-key-change-in-production'
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 28800  # 8 hours
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 2592000  # 30 days

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})



# Initialize JWT
jwt = JWTManager(app)

# Initialize SocketIO with CORS
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Initialize daemon with debug mode (set to True to see all MQTT publishes)
DEBUG_MQTT = False  # Set to True for verbose MQTT logging
daemon = EFIODeviceDaemon(debug_mqtt=DEBUG_MQTT)
daemon.start()

# Register blueprints
app.register_blueprint(modbus_api)
app.register_blueprint(auth_api)
app.register_blueprint(config_api)
app.register_blueprint(modbus_device_api)
app.register_blueprint(oled_api)
app.register_blueprint(backup_api)
app.register_blueprint(mqtt_config_api)

print("=" * 50)
print("EFIO API Server Starting...")
print("Flask-SocketIO initialized")
print("CORS enabled for all origins")
print("=" * 50)

# ============================================
# MQTT Integration
# ============================================

mqtt_client = None

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback when MQTT client connects"""
    if rc == 0:
        print("✅ MQTT: Connected to broker")
        # Subscribe to all EFIO topics
        client.subscribe("edgeforce/#")
        print("📡 MQTT: Subscribed to edgeforce/#")
        
        # Publish initial state
        for i, val in enumerate(state["di"]):
            client.publish(f"edgeforce/io/di/{i+1}", val, retain=True)
        for i, val in enumerate(state["do"]):
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
                        state['di'][channel] = value
                        # Broadcast to WebSocket clients
                        socketio.emit('io_update', {
                            'di': state['di'], 
                            'do': state['do']
                        }, namespace='/')
                        
                    elif io_type == 'do' and 0 <= channel < 4:
                        # Update digital output state (read-back)
                        state['do'][channel] = value
                        socketio.emit('io_update', {
                            'di': state['di'], 
                            'do': state['do']
                        }, namespace='/')
                        
                except ValueError:
                    print(f"⚠️ MQTT: Invalid value '{payload}' for {topic}")
            
            # Handle system metrics updates
            elif category == 'system':
                metric_name = parts[2] if len(parts) > 2 else None
                if metric_name:
                    # Store system metrics in state (optional)
                    if 'mqtt_system' not in state:
                        state['mqtt_system'] = {}
                    state['mqtt_system'][metric_name] = payload
                    
    except Exception as e:
        print(f"❌ MQTT message handler error: {e}")
        import traceback
        traceback.print_exc()

def init_mqtt():
    """Initialize MQTT client"""
    global mqtt_client
    
    try:
        mqtt_client = mqtt.Client(client_id="efio-daemon")
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect
        mqtt_client.on_message = on_mqtt_message
        
        # Connect to local Mosquitto broker
        mqtt_client.connect("localhost", 1883, 60)
        mqtt_client.loop_start()
        
        print("🔌 MQTT: Client initialized")
        return True
        
    except Exception as e:
        print(f"❌ MQTT: Initialization failed: {e}")
        print("⚠️ MQTT: System will continue without MQTT (fallback mode)")
        return False

# Helper function to publish to MQTT
def mqtt_publish(topic, payload, retain=False):
    """Publish message to MQTT broker"""
    if mqtt_client and mqtt_client.is_connected():
        try:
            mqtt_client.publish(topic, payload, retain=retain)
            return True
        except Exception as e:
            print(f"❌ MQTT publish error: {e}")
            return False
    return False

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
        "mqtt": mqtt_status
    })

@app.get("/api/io")
def get_io():
    """Get current I/O state"""
    return jsonify({
        "di": state["di"],
        "do": state["do"],
        "timestamp": time.time()
    })

@app.post("/api/io/do/<int:ch>")
def set_do(ch):
    """Set digital output state"""
    if ch < 0 or ch >= len(state["do"]):
        return jsonify({"error": "Invalid channel"}), 400
    
    data = request.get_json()
    new_val = 1 if data.get("state") else 0
    
    # Update local state
    state["do"][ch] = new_val
    
    # Write to hardware
    daemon.manager.write_output(ch, new_val)
    
    # Publish to MQTT (command topic)
    mqtt_publish(f"edgeforce/io/do/{ch+1}/set", new_val, retain=False)
    
    # Publish actual state (feedback topic)
    mqtt_publish(f"edgeforce/io/do/{ch+1}", new_val, retain=True)
    
    # Broadcast change to WebSocket clients
    socketio.emit('io_update', {
        'di': state["di"],
        'do': state["do"]
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
# WebSocket Events
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('✅ WebSocket: Client connected')
    # Send initial state
    emit('io_update', {
        'di': state["di"],
        'do': state["do"]
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
        'di': state["di"],
        'do': state["do"]
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
    
    if ch < 0 or ch >= len(state["do"]):
        emit('error', {'message': 'Invalid channel'})
        return
    
    # Update state
    state["do"][ch] = value
    
    # Write to hardware
    daemon.manager.write_output(ch, value)
    
    # Publish to MQTT
    mqtt_publish(f"edgeforce/io/do/{ch+1}/set", value)
    mqtt_publish(f"edgeforce/io/do/{ch+1}", value, retain=True)
    
    # Broadcast to all clients
    socketio.emit('io_update', {
        'di': state["di"],
        'do': state["do"]
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
                current_io = {"di": state["di"][:], "do": state["do"][:]}
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

def start_background_thread():
    """Start background thread after socketio is initialized"""
    background_thread = threading.Thread(target=background_broadcast, daemon=True)
    background_thread.start()
    print("✅ Background broadcast thread started")

# ============================================
# Main
# ============================================

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🚀 EFIO API Server with WebSocket + MQTT")
    print("=" * 50)
    print(f"📡 HTTP API: http://0.0.0.0:5000")
    print(f"🔌 WebSocket: ws://0.0.0.0:5000")
    print("MQTT Config API registered")
    print(f"🌐 CORS: Enabled for all origins")
    print("=" * 50 + "\n")
    
    # Initialize MQTT
    mqtt_initialized = init_mqtt()
    if mqtt_initialized:
        print("✅ MQTT broker connected")
    else:
        print("⚠️ Running without MQTT (fallback mode)")
    
    # Start background thread
    start_background_thread()
    
    init_oled_display()
    import atexit
    atexit.register(stop_oled_display)
    start_background_thread()

    # Run with SocketIO
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )