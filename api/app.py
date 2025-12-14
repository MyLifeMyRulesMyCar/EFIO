#!/usr/bin/env python3
# api/app.py - Enhanced Flask API with WebSocket support

from flask import Flask, jsonify, request, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psutil
import threading
import time
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from efio_daemon.daemon import EFIODeviceDaemon
from efio_daemon.state import state
from utils.pairing import create_pairing, validate_pairing
from oled_manager.oled_service import show_qr, show_status, show_boot
from api.modbus_routes import modbus_api

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'edgeforce-secret-key-change-in-production'

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize SocketIO with CORS
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',  # Changed from eventlet to threading
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Initialize daemon
daemon = EFIODeviceDaemon()
daemon.start()

# Register blueprints
app.register_blueprint(modbus_api)

print("=" * 50)
print("EFIO API Server Starting...")
print("Flask-SocketIO initialized")
print("CORS enabled for all origins")
print("=" * 50)

# ============================================
# REST API Endpoints
# ============================================

@app.get("/api/status")
def status():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "message": "EFIO API online",
        "version": "1.0.0",
        "websocket": "enabled"
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
    
    state["do"][ch] = new_val
    daemon.manager.write_output(ch, new_val)
    
    # Broadcast change to all connected WebSocket clients
    socketio.emit('io_update', {
        'di': state["di"],
        'do': state["do"]
    }, broadcast=True)
    
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
            print(f"Cannot read temperature: {e}")
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Uptime
        uptime = time.time() - psutil.boot_time()
        
        return jsonify({
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
        })
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
    
    state["do"][ch] = value
    daemon.manager.write_output(ch, value)
    
    # Broadcast to all clients
    socketio.emit('io_update', {
        'di': state["di"],
        'do': state["do"]
    }, broadcast=True)
    
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
                
                # Always broadcast I/O state (even if unchanged for debugging)
                current_io = {"di": state["di"][:], "do": state["do"][:]}
                socketio.emit('io_update', current_io, namespace='/')
                
                if current_io != last_io_state:
                    print(f"📡 I/O state changed: {current_io}")
                    last_io_state = current_io
                
                # Broadcast system metrics every time
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
                    
                    # Log every 10 broadcasts (every 20 seconds) to avoid spam
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

# Start background broadcast thread AFTER app is created
def start_background_thread():
    """Start background thread after socketio is initialized"""
    background_thread = threading.Thread(target=background_broadcast, daemon=True)
    background_thread.start()
    print("✅ Background broadcast thread started")

# We'll call this after socketio.run() is ready

# ============================================
# Main
# ============================================

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🚀 EFIO API Server with WebSocket")
    print("=" * 50)
    print(f"📡 HTTP API: http://0.0.0.0:5000")
    print(f"🔌 WebSocket: ws://0.0.0.0:5000")
    print(f"🌐 CORS: Enabled for all origins")
    print("=" * 50 + "\n")
    
    # Start background thread before running socketio
    start_background_thread()
    
    # Run with SocketIO
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        use_reloader=False,  # Disable reloader to prevent duplicate threads
        allow_unsafe_werkzeug=True
    )