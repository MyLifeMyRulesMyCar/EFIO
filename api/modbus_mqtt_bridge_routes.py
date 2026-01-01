# api/modbus_mqtt_bridge_routes.py
# REST API endpoints for Modbus-MQTT Bridge configuration

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
import os

modbus_mqtt_api = Blueprint('modbus_mqtt_api', __name__)

# Configuration file
BRIDGE_CONFIG_FILE = "/home/radxa/efio/modbus_mqtt_bridge.json"

# Bridge instance (will be set by app.py)
bridge_instance = None

def set_bridge_instance(bridge):
    """Set the bridge instance (called from app.py)"""
    global bridge_instance
    bridge_instance = bridge

def admin_required():
    """Check if current user is admin"""
    claims = get_jwt()
    return claims.get('role') == 'admin'

def load_bridge_config():
    """Load bridge configuration from file"""
    if not os.path.exists(BRIDGE_CONFIG_FILE):
        return {
            "enabled": False,
            "poll_interval": 1.0,
            "mappings": []
        }
    try:
        with open(BRIDGE_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading bridge config: {e}")
        return {
            "enabled": False,
            "poll_interval": 1.0,
            "mappings": []
        }

def save_bridge_config(config):
    """Save bridge configuration to file"""
    try:
        os.makedirs(os.path.dirname(BRIDGE_CONFIG_FILE), exist_ok=True)
        with open(BRIDGE_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving bridge config: {e}")
        return False

# ============================================
# Configuration Endpoints
# ============================================

@modbus_mqtt_api.route('/api/modbus-mqtt/config', methods=['GET'])
@jwt_required()
def get_bridge_config():
    """Get current bridge configuration"""
    config = load_bridge_config()
    
    # Add runtime status if bridge is running
    if bridge_instance:
        status = bridge_instance.get_status()
        config['status'] = status
    else:
        config['status'] = {
            "running": False,
            "mqtt_connected": False,
            "mappings_count": 0,
            "poll_interval": 1.0
        }
    
    return jsonify(config), 200

@modbus_mqtt_api.route('/api/modbus-mqtt/config', methods=['POST'])
@jwt_required()
def update_bridge_config():
    """Update bridge configuration"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    
    # Validate configuration
    if 'mappings' not in data:
        return jsonify({"error": "mappings required"}), 400
    
    # Save configuration
    if save_bridge_config(data):
        return jsonify({
            "message": "Configuration saved",
            "note": "Restart bridge for changes to take effect"
        }), 200
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

# ============================================
# Mapping Management
# ============================================

@modbus_mqtt_api.route('/api/modbus-mqtt/mappings', methods=['GET'])
@jwt_required()
def get_mappings():
    """Get all register-to-topic mappings"""
    config = load_bridge_config()
    return jsonify({"mappings": config.get('mappings', [])}), 200

@modbus_mqtt_api.route('/api/modbus-mqtt/mappings', methods=['POST'])
@jwt_required()
def add_mapping():
    """Add new register-to-topic mapping"""
    data = request.get_json()
    
    # Validate required fields
    required = ['device_id', 'register', 'function_code', 'topic', 'name']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Validate function code
    if data['function_code'] not in [3, 4]:
        return jsonify({"error": "Only FC3 and FC4 are supported"}), 400
    
    # Load current config
    config = load_bridge_config()
    mappings = config.get('mappings', [])
    
    # Generate unique ID
    import time
    mapping_id = f"map_{int(time.time())}_{data['register']}"
    
    # Create mapping object
    mapping = {
        "id": mapping_id,
        "device_id": data['device_id'],
        "device_name": data.get('device_name', ''),
        "register": int(data['register']),
        "function_code": int(data['function_code']),
        "topic": data['topic'],
        "name": data['name'],
        "unit": data.get('unit', ''),
        "enabled": data.get('enabled', True),
        "scaling": data.get('scaling', {
            "multiplier": 1.0,
            "offset": 0.0,
            "decimals": 0
        })
    }
    
    mappings.append(mapping)
    config['mappings'] = mappings
    
    if save_bridge_config(config):
        return jsonify({
            "message": "Mapping added",
            "mapping": mapping
        }), 201
    else:
        return jsonify({"error": "Failed to save mapping"}), 500

@modbus_mqtt_api.route('/api/modbus-mqtt/mappings/<mapping_id>', methods=['PUT'])
@jwt_required()
def update_mapping(mapping_id):
    """Update existing mapping"""
    data = request.get_json()
    config = load_bridge_config()
    mappings = config.get('mappings', [])
    
    # Find mapping
    mapping_index = next((i for i, m in enumerate(mappings) if m['id'] == mapping_id), None)
    
    if mapping_index is None:
        return jsonify({"error": "Mapping not found"}), 404
    
    # Update fields
    mapping = mappings[mapping_index]
    mapping.update({
        "device_id": data.get('device_id', mapping['device_id']),
        "device_name": data.get('device_name', mapping.get('device_name', '')),
        "register": int(data.get('register', mapping['register'])),
        "function_code": int(data.get('function_code', mapping['function_code'])),
        "topic": data.get('topic', mapping['topic']),
        "name": data.get('name', mapping['name']),
        "unit": data.get('unit', mapping.get('unit', '')),
        "enabled": data.get('enabled', mapping.get('enabled', True)),
        "scaling": data.get('scaling', mapping.get('scaling', {}))
    })
    
    mappings[mapping_index] = mapping
    config['mappings'] = mappings
    
    if save_bridge_config(config):
        return jsonify({
            "message": "Mapping updated",
            "mapping": mapping
        }), 200
    else:
        return jsonify({"error": "Failed to update mapping"}), 500

@modbus_mqtt_api.route('/api/modbus-mqtt/mappings/<mapping_id>', methods=['DELETE'])
@jwt_required()
def delete_mapping(mapping_id):
    """Delete mapping"""
    config = load_bridge_config()
    mappings = config.get('mappings', [])
    
    # Filter out the mapping
    original_count = len(mappings)
    mappings = [m for m in mappings if m['id'] != mapping_id]
    
    if len(mappings) == original_count:
        return jsonify({"error": "Mapping not found"}), 404
    
    config['mappings'] = mappings
    
    if save_bridge_config(config):
        return jsonify({"message": "Mapping deleted"}), 200
    else:
        return jsonify({"error": "Failed to delete mapping"}), 500

# ============================================
# Bridge Control
# ============================================

@modbus_mqtt_api.route('/api/modbus-mqtt/start', methods=['POST'])
@jwt_required()
def start_bridge():
    """Start the bridge service"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    if not bridge_instance:
        return jsonify({"error": "Bridge not initialized"}), 500
    
    from api.mqtt_config import load_mqtt_config
    mqtt_config = load_mqtt_config()
    
    if not mqtt_config.get('enabled', True):
        return jsonify({
            "error": "MQTT publishing is disabled. Please enable MQTT in MQTT Settings first.",
            "hint": "Go to Settings → MQTT Settings and enable MQTT publishing"
        }), 400
    
    if not bridge_instance:
        return jsonify({"error": "Bridge not initialized"}), 500
    
    # Load configuration
    config = load_bridge_config()
    mappings = config.get('mappings', [])
    
    # Filter enabled mappings only
    enabled_mappings = [m for m in mappings if m.get('enabled', True)]
    
    if not enabled_mappings:
        return jsonify({"error": "No enabled mappings configured"}), 400
    
    # Load mappings into bridge
    bridge_instance.load_mappings(enabled_mappings)
    
    # Set poll interval
    poll_interval = config.get('poll_interval', 1.0)
    bridge_instance.set_poll_interval(poll_interval)
    
    # Start bridge
    if bridge_instance.start():
        # Update config
        config['enabled'] = True
        save_bridge_config(config)
        
        return jsonify({
            "message": "Bridge started",
            "mappings_count": len(enabled_mappings),
            "poll_interval": poll_interval
        }), 200
    else:
        return jsonify({"error": "Failed to start bridge"}), 500

@modbus_mqtt_api.route('/api/modbus-mqtt/stop', methods=['POST'])
@jwt_required()
def stop_bridge():
    """Stop the bridge service"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    if not bridge_instance:
        return jsonify({"error": "Bridge not initialized"}), 500
    
    bridge_instance.stop()
    
    # Update config
    config = load_bridge_config()
    config['enabled'] = False
    save_bridge_config(config)
    
    return jsonify({"message": "Bridge stopped"}), 200

@modbus_mqtt_api.route('/api/modbus-mqtt/status', methods=['GET'])
@jwt_required()
def get_bridge_status():
    """Get bridge runtime status"""
    if not bridge_instance:
        return jsonify({
            "running": False,
            "mqtt_connected": False,
            "mappings_count": 0,
            "error": "Bridge not initialized"
        }), 200
    
    status = bridge_instance.get_status()
    return jsonify(status), 200

# ============================================
# Helper: Get Available Devices
# ============================================

@modbus_mqtt_api.route('/api/modbus-mqtt/available-devices', methods=['GET'])
@jwt_required()
def get_available_devices():
    """Get list of connected Modbus devices for mapping selection"""
    # Import here to avoid circular dependency
    from api.modbus_device_routes import load_devices, active_connections
    
    devices = load_devices()
    
    # Filter only connected devices
    available = []
    for device in devices:
        if device['id'] in active_connections:
            available.append({
                "id": device['id'],
                "name": device['name'],
                "slave_id": device['slave_id'],
                "port": device['port']
            })
    
    return jsonify({"devices": available}), 200