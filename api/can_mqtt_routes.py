#!/usr/bin/env python3
# api/can_mqtt_routes.py
# REST API endpoints for CAN-MQTT Bridge configuration

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
import os
import time

can_mqtt_api = Blueprint('can_mqtt_api', __name__)

# Configuration file path
CAN_MQTT_CONFIG_FILE = "/home/radxa/efio/can_mqtt_bridge.json"

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
    if not os.path.exists(CAN_MQTT_CONFIG_FILE):
        return {
            "enabled": False,
            "mappings": []
        }
    try:
        with open(CAN_MQTT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading CAN-MQTT bridge config: {e}")
        return {
            "enabled": False,
            "mappings": []
        }

def save_bridge_config(config):
    """Save bridge configuration to file"""
    try:
        os.makedirs(os.path.dirname(CAN_MQTT_CONFIG_FILE), exist_ok=True)
        with open(CAN_MQTT_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving CAN-MQTT bridge config: {e}")
        return False

# ============================================
# Configuration Endpoints
# ============================================

@can_mqtt_api.route('/api/can-mqtt/config', methods=['GET'])
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
            "can_connected": False,
            "mappings_count": 0
        }
    
    return jsonify(config), 200

@can_mqtt_api.route('/api/can-mqtt/config', methods=['POST'])
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

@can_mqtt_api.route('/api/can-mqtt/mappings', methods=['GET'])
@jwt_required()
def get_mappings():
    """Get all CAN ID to MQTT topic mappings"""
    config = load_bridge_config()
    return jsonify({"mappings": config.get('mappings', [])}), 200

@can_mqtt_api.route('/api/can-mqtt/mappings', methods=['POST'])
@jwt_required()
def add_mapping():
    """Add new CAN ID to MQTT topic mapping"""
    data = request.get_json()
    
    # Validate required fields
    required = ['can_id', 'topic', 'name']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Load current config
    config = load_bridge_config()
    mappings = config.get('mappings', [])
    
    # Generate unique ID
    mapping_id = f"map_{int(time.time())}_{data['can_id']}"
    
    # Create mapping object
    mapping = {
        "id": mapping_id,
        "name": data['name'],
        "can_id": int(data['can_id']),
        "topic": data['topic'],
        "enabled": data.get('enabled', True),
        "publish_on_change": data.get('publish_on_change', True),
        "min_interval_ms": int(data.get('min_interval_ms', 100)),
        "qos": int(data.get('qos', 1))
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

@can_mqtt_api.route('/api/can-mqtt/mappings/<mapping_id>', methods=['PUT'])
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
        "name": data.get('name', mapping['name']),
        "can_id": int(data.get('can_id', mapping['can_id'])),
        "topic": data.get('topic', mapping['topic']),
        "enabled": data.get('enabled', mapping.get('enabled', True)),
        "publish_on_change": data.get('publish_on_change', mapping.get('publish_on_change', True)),
        "min_interval_ms": int(data.get('min_interval_ms', mapping.get('min_interval_ms', 100))),
        "qos": int(data.get('qos', mapping.get('qos', 1)))
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

@can_mqtt_api.route('/api/can-mqtt/mappings/<mapping_id>', methods=['DELETE'])
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

@can_mqtt_api.route('/api/can-mqtt/start', methods=['POST'])
@jwt_required()
def start_bridge():
    """Start the bridge service"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    # Check if MQTT is enabled
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
    
    # Start bridge
    if bridge_instance.start():
        # Update config
        config['enabled'] = True
        save_bridge_config(config)
        
        return jsonify({
            "message": "Bridge started",
            "mappings_count": len(enabled_mappings)
        }), 200
    else:
        return jsonify({"error": "Failed to start bridge"}), 500

@can_mqtt_api.route('/api/can-mqtt/stop', methods=['POST'])
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

@can_mqtt_api.route('/api/can-mqtt/status', methods=['GET'])
@jwt_required()
def get_bridge_status():
    """Get bridge runtime status"""
    if not bridge_instance:
        return jsonify({
            "running": False,
            "mqtt_connected": False,
            "can_connected": False,
            "mappings_count": 0,
            "enabled_mappings": 0,
            "statistics": {}
        }), 200
    
    status = bridge_instance.get_status()
    return jsonify(status), 200

# ============================================
# Statistics
# ============================================

@can_mqtt_api.route('/api/can-mqtt/statistics', methods=['GET'])
@jwt_required()
def get_statistics():
    """Get bridge statistics"""
    if not bridge_instance:
        return jsonify({"error": "Bridge not initialized"}), 500
    
    status = bridge_instance.get_status()
    return jsonify(status.get('statistics', {})), 200

@can_mqtt_api.route('/api/can-mqtt/statistics/reset', methods=['POST'])
@jwt_required()
def reset_statistics():
    """Reset statistics counters"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    if not bridge_instance:
        return jsonify({"error": "Bridge not initialized"}), 500
    
    bridge_instance.reset_statistics()
    return jsonify({"message": "Statistics reset"}), 200