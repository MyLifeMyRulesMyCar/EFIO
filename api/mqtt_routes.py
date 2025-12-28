# api/mqtt_routes.py
# MQTT Configuration Management

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
import os
import paho.mqtt.client as mqtt

mqtt_config_api = Blueprint('mqtt_config_api', __name__)

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

def admin_required():
    """Check if current user is admin"""
    claims = get_jwt()
    return claims.get('role') == 'admin'

def load_mqtt_config():
    """Load MQTT configuration"""
    if not os.path.exists(MQTT_CONFIG_FILE):
        return DEFAULT_MQTT_CONFIG
    try:
        with open(MQTT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading MQTT config: {e}")
        return DEFAULT_MQTT_CONFIG

def save_mqtt_config(config):
    """Save MQTT configuration"""
    try:
        os.makedirs(os.path.dirname(MQTT_CONFIG_FILE), exist_ok=True)
        with open(MQTT_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving MQTT config: {e}")
        return False

@mqtt_config_api.route('/api/config/mqtt', methods=['GET'])
@jwt_required()
def get_mqtt_config():
    """Get current MQTT configuration"""
    config = load_mqtt_config()
    
    # Don't send password in response (mask it)
    if config.get('password'):
        config['password'] = '********'
    
    return jsonify(config), 200

@mqtt_config_api.route('/api/config/mqtt', methods=['POST'])
@jwt_required()
def update_mqtt_config():
    """Update MQTT configuration (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    
    # Validate required fields
    if not data.get('broker'):
        return jsonify({"error": "Broker host required"}), 400
    
    if not isinstance(data.get('port', 1883), int):
        return jsonify({"error": "Port must be an integer"}), 400
    
    # Load existing config to preserve password if masked
    existing = load_mqtt_config()
    
    # If password is masked, keep existing password
    if data.get('password') == '********':
        data['password'] = existing.get('password', '')
    
    # Save configuration
    if save_mqtt_config(data):
        return jsonify({
            "message": "MQTT configuration saved",
            "restart_required": True,
            "note": "Restart EFIO service for changes to take effect"
        }), 200
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

@mqtt_config_api.route('/api/config/mqtt/test', methods=['POST'])
@jwt_required()
def test_mqtt_connection():
    """Test MQTT connection with current or provided config"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json() or {}
    
    # Use provided config or load from file
    broker = data.get('broker') or load_mqtt_config().get('broker')
    port = data.get('port', 1883)
    username = data.get('username', '')
    password = data.get('password', '')
    use_tls = data.get('use_tls', False)
    
    try:
        # Create test client
        test_client = mqtt.Client(client_id="efio_test_connection")
        
        if username and password:
            test_client.username_pw_set(username, password)
        
        if use_tls:
            test_client.tls_set()
        
        # Connection result tracking
        connection_result = {"success": False, "error": None}
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connection_result["success"] = True
            else:
                connection_result["error"] = f"Connection failed (code {rc})"
        
        test_client.on_connect = on_connect
        
        # Attempt connection with 5 second timeout
        test_client.connect(broker, port, keepalive=5)
        test_client.loop_start()
        
        # Wait for connection
        import time
        timeout = 5
        elapsed = 0
        while elapsed < timeout and not connection_result["success"] and not connection_result["error"]:
            time.sleep(0.1)
            elapsed += 0.1
        
        test_client.loop_stop()
        test_client.disconnect()
        
        if connection_result["success"]:
            return jsonify({
                "success": True,
                "message": f"Successfully connected to {broker}:{port}"
            }), 200
        elif connection_result["error"]:
            return jsonify({
                "success": False,
                "error": connection_result["error"]
            }), 400
        else:
            return jsonify({
                "success": False,
                "error": "Connection timeout"
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mqtt_config_api.route('/api/config/mqtt/status', methods=['GET'])
@jwt_required()
def get_mqtt_status():
    """Get current MQTT connection status"""
    # This would query the actual daemon's MQTT connection
    # For now, return mock status
    config = load_mqtt_config()
    
    return jsonify({
        "broker": config.get('broker'),
        "port": config.get('port'),
        "connected": True,  # TODO: Query actual daemon status
        "last_message": "2 seconds ago"
    }), 200