#!/usr/bin/env python3
# api/can_routes.py
# REST API endpoints for CAN bus management

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
import os
from datetime import datetime
from efio_daemon.can_manager import can_manager, CANDevice

can_api = Blueprint('can_api', __name__)

# Configuration file
CAN_CONFIG_FILE = "/home/radxa/efio/can_config.json"
CAN_LOG_FILE = "/home/radxa/efio/can_log.json"

# ============================================
# Helper Functions
# ============================================

def admin_required():
    """Check if current user is admin"""
    claims = get_jwt()
    return claims.get('role') == 'admin'

def load_can_config():
    """Load CAN configuration from file"""
    if not os.path.exists(CAN_CONFIG_FILE):
        return {
            "controller": {
                "spi_bus": 2,
                "spi_device": 0,
                "spi_speed": 1000000,
                "bitrate": 125000,
                "mode": "normal",
                "crystal": 8000000
            },
            "devices": [],
            "filters": [],
            "auto_connect": False
        }
    
    try:
        with open(CAN_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading CAN config: {e}")
        return None

def save_can_config(config):
    """Save CAN configuration to file"""
    try:
        os.makedirs(os.path.dirname(CAN_CONFIG_FILE), exist_ok=True)
        with open(CAN_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving CAN config: {e}")
        return False

def log_can_event(event_type, message, data=None):
    """Log CAN events"""
    try:
        logs = []
        if os.path.exists(CAN_LOG_FILE):
            with open(CAN_LOG_FILE, 'r') as f:
                logs = json.load(f)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "data": data
        }
        
        logs.append(log_entry)
        logs = logs[-1000:]  # Keep last 1000 logs
        
        with open(CAN_LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Error logging CAN event: {e}")

# ============================================
# Configuration Endpoints
# ============================================

@can_api.route('/api/can/config', methods=['GET'])
@jwt_required()
def get_can_config():
    """Get current CAN configuration"""
    config = load_can_config()
    if config:
        # Add runtime status
        config['status'] = can_manager.get_status()
        return jsonify(config), 200
    else:
        return jsonify({"error": "Failed to load configuration"}), 500

@can_api.route('/api/can/config', methods=['POST'])
@jwt_required()
def update_can_config():
    """Update CAN configuration (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    
    if save_can_config(data):
        log_can_event("config_updated", "CAN configuration updated")
        return jsonify({
            "message": "Configuration saved",
            "note": "Reconnect CAN bus for changes to take effect"
        }), 200
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

# ============================================
# Connection Management
# ============================================

@can_api.route('/api/can/connect', methods=['POST'])
@jwt_required()
def connect_can():
    """Connect to CAN bus"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        # Load configuration
        config = load_can_config()
        if not config:
            return jsonify({"error": "Configuration not found"}), 500
        
        controller_config = config.get('controller', {})
        
        # Update manager settings
        can_manager.spi_bus = controller_config.get('spi_bus', 2)
        can_manager.spi_device = controller_config.get('spi_device', 0)
        can_manager.bitrate = controller_config.get('bitrate', 125000)
        
        # Connect
        can_manager.connect()
        
        log_can_event("connected", f"CAN bus connected at {can_manager.bitrate} bps")
        
        return jsonify({
            "message": "CAN bus connected",
            "status": can_manager.get_status()
        }), 200
        
    except Exception as e:
        log_can_event("connection_error", f"Connection failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/disconnect', methods=['POST'])
@jwt_required()
def disconnect_can():
    """Disconnect from CAN bus"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        can_manager.disconnect()
        log_can_event("disconnected", "CAN bus disconnected")
        
        return jsonify({"message": "CAN bus disconnected"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/status', methods=['GET'])
@jwt_required()
def get_can_status():
    """Get CAN bus status"""
    try:
        status = can_manager.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# Device Management
# ============================================

@can_api.route('/api/can/devices', methods=['GET'])
@jwt_required()
def get_can_devices():
    """Get all CAN devices"""
    try:
        devices = can_manager.get_all_devices()
        return jsonify({"devices": devices}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/devices', methods=['POST'])
@jwt_required()
def create_can_device():
    """Create new CAN device"""
    data = request.get_json()
    
    # Validate required fields
    required = ['name', 'can_id']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    try:
        # Generate unique ID
        import time
        device_id = f"can_{int(time.time())}_{data['can_id']}"
        
        # Create device object
        device = CANDevice(
            device_id=device_id,
            name=data['name'],
            can_id=int(data['can_id']),
            extended=data.get('extended', False),
            enabled=data.get('enabled', True)
        )
        
        # Add message definitions if provided
        device.messages = data.get('messages', [])
        
        # Add to manager
        can_manager.add_device(device)
        
        # Update configuration file
        config = load_can_config()
        config['devices'].append({
            'id': device.id,
            'name': device.name,
            'can_id': device.can_id,
            'extended': device.extended,
            'enabled': device.enabled,
            'messages': device.messages,
            'description': data.get('description', ''),
            'created_at': datetime.now().isoformat()
        })
        save_can_config(config)
        
        log_can_event("device_created", f"Device '{data['name']}' created", {
            "device_id": device_id,
            "can_id": device.can_id
        })
        
        return jsonify({
            "message": "Device created",
            "device": device.to_dict()
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/devices/<device_id>', methods=['PUT'])
@jwt_required()
def update_can_device(device_id):
    """Update CAN device"""
    data = request.get_json()
    
    try:
        device = can_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # Update fields
        device.name = data.get('name', device.name)
        device.can_id = int(data.get('can_id', device.can_id))
        device.extended = data.get('extended', device.extended)
        device.enabled = data.get('enabled', device.enabled)
        device.messages = data.get('messages', device.messages)
        
        # Update configuration file
        config = load_can_config()
        for i, dev in enumerate(config['devices']):
            if dev['id'] == device_id:
                config['devices'][i].update({
                    'name': device.name,
                    'can_id': device.can_id,
                    'extended': device.extended,
                    'enabled': device.enabled,
                    'messages': device.messages,
                    'description': data.get('description', dev.get('description', '')),
                    'updated_at': datetime.now().isoformat()
                })
                break
        save_can_config(config)
        
        log_can_event("device_updated", f"Device '{device.name}' updated")
        
        return jsonify({
            "message": "Device updated",
            "device": device.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/devices/<device_id>', methods=['DELETE'])
@jwt_required()
def delete_can_device(device_id):
    """Delete CAN device"""
    try:
        device = can_manager.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        device_name = device.name
        
        # Remove from manager
        can_manager.remove_device(device_id)
        
        # Update configuration file
        config = load_can_config()
        config['devices'] = [d for d in config['devices'] if d['id'] != device_id]
        save_can_config(config)
        
        log_can_event("device_deleted", f"Device '{device_name}' deleted")
        
        return jsonify({"message": "Device deleted"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# Message Transmission
# ============================================

@can_api.route('/api/can/send', methods=['POST'])
@jwt_required()
def send_can_message():
    """Send CAN message"""
    data = request.get_json()
    
    # Validate required fields
    if 'can_id' not in data or 'data' not in data:
        return jsonify({"error": "Missing can_id or data"}), 400
    
    try:
        can_id = int(data['can_id'])
        msg_data = data['data']
        extended = data.get('extended', False)
        
        # Validate data
        if not isinstance(msg_data, list):
            return jsonify({"error": "data must be a list"}), 400
        
        if len(msg_data) > 8:
            return jsonify({"error": "data length must be ≤ 8"}), 400
        
        # Convert to integers
        msg_data = [int(b) for b in msg_data]
        
        # Send message
        success = can_manager.send_message(
            can_id=can_id,
            data=msg_data,
            extended=extended
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "CAN message sent",
                "can_id": can_id,
                "data": msg_data
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Failed to send message"
            }), 500
        
    except Exception as e:
        log_can_event("send_error", f"Send failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ============================================
# Message Sniffing / Monitoring
# ============================================

@can_api.route('/api/can/messages', methods=['GET'])
@jwt_required()
def get_can_messages():
    """Get recent CAN messages (for sniffing)"""
    try:
        # Get query parameters
        count = int(request.args.get('count', 100))
        filter_id = request.args.get('filter_id')
        direction = request.args.get('direction')  # 'RX', 'TX', or None for both
        
        # Get recent messages
        messages = can_manager.get_recent_messages(count)
        
        # Apply filters
        if filter_id:
            filter_id = int(filter_id, 16) if filter_id.startswith('0x') else int(filter_id)
            messages = [m for m in messages if m['can_id'] == filter_id]
        
        if direction:
            messages = [m for m in messages if m['direction'] == direction.upper()]
        
        return jsonify({
            "messages": messages,
            "count": len(messages),
            "total": can_manager.stats['rx_total'] + can_manager.stats['tx_total']
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/messages/clear', methods=['POST'])
@jwt_required()
def clear_can_messages():
    """Clear message log"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        can_manager.clear_logs()
        log_can_event("logs_cleared", "Message log cleared")
        
        return jsonify({"message": "Message log cleared"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# Statistics
# ============================================

@can_api.route('/api/can/statistics', methods=['GET'])
@jwt_required()
def get_can_statistics():
    """Get CAN bus statistics"""
    try:
        status = can_manager.get_status()
        devices = can_manager.get_all_devices()
        
        # Calculate additional stats
        active_devices = sum(1 for d in devices if d.get('last_seen'))
        total_rx = sum(d.get('rx_count', 0) for d in devices)
        total_tx = sum(d.get('tx_count', 0) for d in devices)
        
        return jsonify({
            "bus": status,
            "devices": {
                "total": len(devices),
                "active": active_devices,
                "total_rx": total_rx,
                "total_tx": total_tx
            },
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/statistics/reset', methods=['POST'])
@jwt_required()
def reset_can_statistics():
    """Reset statistics counters"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        can_manager.reset_statistics()
        log_can_event("statistics_reset", "Statistics counters reset")
        
        return jsonify({"message": "Statistics reset"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# Event Logs
# ============================================

@can_api.route('/api/can/logs', methods=['GET'])
@jwt_required()
def get_can_logs():
    """Get CAN event logs"""
    try:
        if os.path.exists(CAN_LOG_FILE):
            with open(CAN_LOG_FILE, 'r') as f:
                logs = json.load(f)
            
            # Get query parameters
            count = int(request.args.get('count', 100))
            event_type = request.args.get('type')
            
            # Apply filters
            if event_type:
                logs = [l for l in logs if l['type'] == event_type]
            
            return jsonify({
                "logs": logs[-count:],
                "total": len(logs)
            }), 200
        else:
            return jsonify({"logs": [], "total": 0}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/logs/clear', methods=['POST'])
@jwt_required()
def clear_can_logs():
    """Clear event logs"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        if os.path.exists(CAN_LOG_FILE):
            os.remove(CAN_LOG_FILE)
        
        return jsonify({"message": "Event logs cleared"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# Hardware Filters (Advanced)
# ============================================

@can_api.route('/api/can/filters', methods=['GET'])
@jwt_required()
def get_can_filters():
    """Get configured hardware filters"""
    try:
        config = load_can_config()
        return jsonify({"filters": config.get('filters', [])}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/filters', methods=['POST'])
@jwt_required()
def set_can_filters():
    """Configure hardware filters"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    
    try:
        filters = data.get('filters', [])
        
        # TODO: Apply filters to MCP2515 hardware
        # This requires extending the mcp2515_driver.py to support RXF/RXM registers
        
        # Save to configuration
        config = load_can_config()
        config['filters'] = filters
        save_can_config(config)
        
        log_can_event("filters_updated", f"Hardware filters updated ({len(filters)} filters)")
        
        return jsonify({
            "message": "Filters updated",
            "note": "Reconnect for filters to take effect"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500