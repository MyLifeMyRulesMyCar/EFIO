#!/usr/bin/env python3
# api/can_routes.py
# REST API endpoints for CAN bus management

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
import os
from datetime import datetime
import time
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


# ============================================
# Additional endpoints: detection, scanning, detailed status, filter validation
# ============================================


@can_api.route('/api/can/detect-bitrate', methods=['POST'])
@jwt_required()
def detect_bitrate():
    """Improved auto-detect with noise filtering"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    if can_manager.connected:
        return jsonify({"error": "Disconnect CAN bus before detection"}), 400
    
    try:
        config = load_can_config()
        controller_config = config.get('controller', {})
        
        # Test bitrates from most common to least
        test_bitrates = [125000, 250000, 500000, 100000, 50000]
        
        detected = None
        best_quality = 0
        results = []
        
        for bitrate in test_bitrates:
            print(f"🔍 Testing {bitrate} bps...")
            
            can_manager.spi_bus = controller_config.get('spi_bus', 2)
            can_manager.spi_device = controller_config.get('spi_device', 0)
            can_manager.bitrate = bitrate
            
            try:
                # Connect
                can_manager.connect()
                
                # Clear old data
                can_manager.clear_logs()
                time.sleep(0.2)
                
                # Sample for 5 seconds (longer = more reliable)
                start_count = can_manager.stats.get('rx_total', 0)
                start_errors = can_manager.stats.get('errors', 0)
                
                sample_time = 5
                time.sleep(sample_time)
                
                # Count valid messages
                end_count = can_manager.stats.get('rx_total', 0)
                end_errors = can_manager.stats.get('errors', 0)
                
                valid_msgs = max(0, end_count - start_count)
                errors = max(0, end_errors - start_errors)
                
                # Quality score (higher = better)
                # Penalize errors heavily
                msg_rate = valid_msgs / sample_time
                error_penalty = errors * 5
                quality = (valid_msgs * msg_rate) - error_penalty
                
                results.append({
                    'bitrate': bitrate,
                    'messages': valid_msgs,
                    'rate': msg_rate,
                    'errors': errors,
                    'quality': quality
                })
                
                print(f"   {valid_msgs} msgs, {msg_rate:.1f}/s, "
                      f"{errors} errors, quality={quality:.1f}")
                
                # Update best (require at least 10 messages)
                if quality > best_quality and valid_msgs >= 10:
                    best_quality = quality
                    detected = bitrate
                
                can_manager.disconnect()
                time.sleep(0.5)
                
            except Exception as e:
                print(f"   Failed: {e}")
                try:
                    can_manager.disconnect()
                except:
                    pass
                time.sleep(0.5)
        
        # Return results
        if detected and best_quality > 5:
            log_can_event("bitrate_detected", 
                         f"Detected {detected} bps (quality={best_quality:.1f})")
            return jsonify({
                "detected": True,
                "bitrate": detected,
                "quality": best_quality,
                "all_results": results
            }), 200
        else:
            log_can_event("bitrate_detection_failed", "No valid bitrate found")
            return jsonify({
                "detected": False,
                "error": "No reliable CAN traffic detected",
                "all_results": results
            }), 200
        
    except Exception as e:
        log_can_event("bitrate_detection_error", f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@can_api.route('/api/can/scan-nodes', methods=['POST'])
@jwt_required()
def scan_nodes():
    """
    Scan for active CAN nodes on the network
    Returns list of detected node IDs with message counts
    """
    if not can_manager.connected:
        return jsonify({"error": "CAN bus not connected"}), 400
    
    try:
        # Clear message log
        can_manager.clear_logs()
        
        # Wait for messages
        print("🔍 Scanning for active nodes...")
        time.sleep(5)  # Collect messages for 5 seconds
        
        # Get recent messages
        messages = can_manager.get_recent_messages(1000)
        
        # Count unique IDs
        node_stats = {}
        for msg in messages:
            can_id = msg.get('can_id')
            if can_id not in node_stats:
                node_stats[can_id] = {
                    'id': can_id,
                    'messages': 0,
                    'last_seen': msg.get('timestamp'),
                    'directions': set()
                }
            node_stats[can_id]['messages'] += 1
            node_stats[can_id]['directions'].add(msg.get('direction'))
            node_stats[can_id]['last_seen'] = msg.get('timestamp')
        
        # Convert to list and sort by message count
        nodes = []
        for node_id, stats in node_stats.items():
            nodes.append({
                'id': stats['id'],
                'messages': stats['messages'],
                'last_seen': stats['last_seen'],
                'rx': 'RX' in stats['directions'],
                'tx': 'TX' in stats['directions']
            })
        
        nodes.sort(key=lambda x: x['messages'], reverse=True)
        
        log_can_event("nodes_scanned", f"Found {len(nodes)} active nodes")
        
        return jsonify({
            "nodes": nodes,
            "total": len(nodes),
            "scan_duration": 5
        }), 200
        
    except Exception as e:
        log_can_event("node_scan_error", f"Scan failed: {str(e)}")
        return jsonify({"error": str(e)}), 500





@can_api.route('/api/can/filters/validate', methods=['POST'])
@jwt_required()
def validate_filters():
    """
    Validate filter configuration before applying
    Returns analysis of what the filters will accept/reject
    """
    data = request.get_json()
    filters = data.get('filters', [])
    
    try:
        analysis = []
        
        for i, f in enumerate(filters):
            filter_id = int(f.get('id', '0'), 16) if isinstance(f.get('id'), str) else f.get('id', 0)
            mask = int(f.get('mask', '0x7FF'), 16) if isinstance(f.get('mask'), str) else f.get('mask', 0x7FF)
            
            # Calculate which IDs will pass
            # For standard CAN (11-bit): mask with 0x7FF
            # For extended CAN (29-bit): mask with 0x1FFFFFFF
            
            if mask == 0x7FF:
                # Exact match filter
                accepted = [filter_id]
                description = f"Only accepts ID 0x{filter_id:03X}"
            else:
                # Range filter
                # Calculate range based on mask
                inverted_mask = ~mask & 0x7FF
                range_size = inverted_mask + 1
                range_start = filter_id & mask
                range_end = range_start + range_size - 1
                
                description = f"Accepts IDs 0x{range_start:03X} to 0x{range_end:03X}"
                accepted = list(range(range_start, min(range_end + 1, 0x800)))
            
            analysis.append({
                "filter_index": i,
                "id": f"0x{filter_id:03X}",
                "mask": f"0x{mask:03X}",
                "description": description,
                "accepted_count": len(accepted),
                "accepted_ids": [f"0x{id:03X}" for id in accepted[:10]]  # Show first 10
            })
        
        return jsonify({
            "filters": analysis,
            "total_filters": len(filters)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ============================================
# NEW: Health & Disconnection Monitoring
# ============================================

@can_api.route('/api/can/health', methods=['GET'])
@jwt_required()
def get_can_health():
    """
    Get comprehensive CAN health status.
    Shows hardware status, device liveness, and circuit breaker states.
    """
    try:
        status = can_manager.get_status()
        devices = can_manager.get_all_devices()
        
        # Analyze health
        health = "healthy"
        warnings = []
        
        # Check hardware connection
        if not status.get('connected'):
            health = "unhealthy"
            warnings.append("CAN hardware not connected")
        
        # Check hardware errors
        if status.get('hardware_failures', 0) > 5:
            health = "degraded"
            warnings.append(f"High hardware failure count: {status['hardware_failures']}")
        
        # Check device timeouts
        if status.get('device_timeouts', 0) > 0:
            health = "degraded"
            warnings.append(f"Device timeouts detected: {status['device_timeouts']}")
        
        # Check alive devices
        alive_count = status.get('alive_devices', 0)
        total_count = status.get('devices_count', 0)
        
        if total_count > 0 and alive_count == 0:
            health = "degraded"
            warnings.append("No devices responding")
        elif alive_count < total_count:
            warnings.append(f"Some devices not responding ({alive_count}/{total_count} alive)")
        
        # Device-level health
        device_health = []
        for device in devices:
            dev_health = {
                'id': device['id'],
                'name': device['name'],
                'can_id': f"0x{device['can_id']:03X}",
                'alive': device.get('alive', False),
                'last_seen': device.get('last_seen'),
                'rx_count': device.get('rx_count', 0),
                'timeout_threshold': device.get('timeout_threshold', 30)
            }
            
            # Calculate time since last RX
            if device.get('last_rx_time'):
                time_since_rx = time.time() - device['last_rx_time']
                dev_health['seconds_since_rx'] = round(time_since_rx, 1)
                
                if time_since_rx > device.get('timeout_threshold', 30):
                    dev_health['status'] = 'timeout'
                else:
                    dev_health['status'] = 'active'
            else:
                dev_health['status'] = 'never_seen'
                dev_health['seconds_since_rx'] = None
            
            device_health.append(dev_health)
        
        return jsonify({
            "health": health,
            "warnings": warnings,
            "timestamp": datetime.now().isoformat(),
            "hardware": {
                "connected": status.get('connected'),
                "bitrate": status.get('bitrate'),
                "errors": status.get('errors'),
                "hardware_failures": status.get('hardware_failures'),
                "circuit_breaker": status.get('hardware_circuit_breaker')
            },
            "devices": {
                "total": total_count,
                "alive": alive_count,
                "details": device_health
            },
            "statistics": {
                "rx_total": status.get('rx_total'),
                "tx_total": status.get('tx_total'),
                "device_timeouts": status.get('device_timeouts'),
                "auto_cleanups": status.get('auto_cleanups'),
                "uptime": status.get('uptime')
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@can_api.route('/api/can/devices/<device_id>/liveness', methods=['GET'])
@jwt_required()
def get_device_liveness(device_id):
    """
    Get detailed liveness information for a specific device.
    Useful for monitoring and debugging.
    """
    try:
        device = can_manager.get_device(device_id)
        
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # Calculate liveness metrics
        is_alive = device.is_alive()
        time_since_rx = None
        status = "never_seen"
        
        if device.last_rx_time:
            time_since_rx = time.time() - device.last_rx_time
            
            if is_alive:
                status = "alive"
            else:
                status = "timeout"
        
        return jsonify({
            "device_id": device_id,
            "name": device.name,
            "can_id": f"0x{device.can_id:03X}",
            "alive": is_alive,
            "status": status,
            "last_seen": device.last_seen,
            "seconds_since_rx": round(time_since_rx, 1) if time_since_rx else None,
            "timeout_threshold": device.timeout_threshold,
            "rx_count": device.rx_count,
            "tx_count": device.tx_count,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@can_api.route('/api/can/devices/<device_id>/timeout', methods=['POST'])
@jwt_required()
def set_device_timeout(device_id):
    """
    Set timeout threshold for device disconnection detection.
    
    Body: {"timeout": 30}  // seconds
    """
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    timeout = data.get('timeout')
    
    if timeout is None:
        return jsonify({"error": "timeout required"}), 400
    
    try:
        timeout = int(timeout)
        
        if timeout < 5 or timeout > 300:
            return jsonify({"error": "timeout must be 5-300 seconds"}), 400
        
        device = can_manager.get_device(device_id)
        
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        device.timeout_threshold = timeout
        
        # Update configuration file
        config = load_can_config()
        for dev in config.get('devices', []):
            if dev['id'] == device_id:
                dev['timeout_threshold'] = timeout
                break
        
        save_can_config(config)
        
        log_can_event(
            "timeout_updated",
            f"Timeout threshold updated for {device.name}",
            {"device_id": device_id, "timeout": timeout}
        )
        
        return jsonify({
            "message": "Timeout threshold updated",
            "device_id": device_id,
            "timeout": timeout
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# NEW: Circuit Breaker Management
# ============================================

@can_api.route('/api/can/circuit-breaker', methods=['GET'])
@jwt_required()
def get_circuit_breaker_status():
    """Get circuit breaker status for hardware and all devices"""
    try:
        status = can_manager.get_status()
        
        # Get hardware breaker
        hw_breaker = status.get('hardware_circuit_breaker', {})
        
        # Get device breakers
        device_breakers = {}
        for device_id, breaker in can_manager.device_breakers.items():
            device = can_manager.get_device(device_id)
            device_breakers[device_id] = {
                'device_name': device.name if device else 'Unknown',
                'can_id': f"0x{device.can_id:03X}" if device else None,
                'breaker': breaker.get_state()
            }
        
        return jsonify({
            "hardware": hw_breaker,
            "devices": device_breakers
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@can_api.route('/api/can/circuit-breaker/reset', methods=['POST'])
@jwt_required()
def reset_circuit_breakers():
    """Reset all circuit breakers (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        # Reset hardware breaker
        can_manager.hw_breaker.reset()
        
        # Reset all device breakers
        for breaker in can_manager.device_breakers.values():
            breaker.reset()
        
        log_can_event("circuit_breakers_reset", "All circuit breakers manually reset")
        
        return jsonify({
            "message": "All circuit breakers reset",
            "hardware_breaker": can_manager.hw_breaker.get_state()
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@can_api.route('/api/can/devices/<device_id>/circuit-breaker/reset', methods=['POST'])
@jwt_required()
def reset_device_circuit_breaker(device_id):
    """Reset circuit breaker for specific device"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        if device_id not in can_manager.device_breakers:
            return jsonify({"error": "No circuit breaker found for device"}), 404
        
        breaker = can_manager.device_breakers[device_id]
        breaker.reset()
        
        device = can_manager.get_device(device_id)
        device_name = device.name if device else device_id
        
        log_can_event(
            "circuit_breaker_reset",
            f"Circuit breaker reset for {device_name}",
            {"device_id": device_id}
        )
        
        return jsonify({
            "message": "Circuit breaker reset",
            "device_id": device_id,
            "breaker": breaker.get_state()
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# NEW: Testing & Simulation Endpoints
# ============================================

@can_api.route('/api/can/test/simulate-timeout', methods=['POST'])
@jwt_required()
def simulate_device_timeout():
    """
    TESTING ENDPOINT: Simulate device timeout by forcing last_rx_time to old value.
    
    Body: {"device_id": "can_123", "seconds_ago": 60}
    """
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    device_id = data.get('device_id')
    seconds_ago = data.get('seconds_ago', 60)
    
    try:
        device = can_manager.get_device(device_id)
        
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # Force old timestamp
        device.last_rx_time = time.time() - seconds_ago
        device.last_seen = datetime.fromtimestamp(device.last_rx_time).isoformat()
        
        log_can_event(
            "timeout_simulated",
            f"Simulated timeout for {device.name}",
            {"device_id": device_id, "seconds_ago": seconds_ago}
        )
        
        return jsonify({
            "message": "Timeout simulated",
            "device_id": device_id,
            "device_name": device.name,
            "simulated_last_rx": device.last_seen,
            "will_timeout_in": f"{device.timeout_threshold - seconds_ago}s"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@can_api.route('/api/can/test/simulate-hardware-failure', methods=['POST'])
@jwt_required()
def simulate_hardware_failure():
    """
    TESTING ENDPOINT: Trigger hardware failure detection.
    WARNING: This will disconnect the CAN bus!
    """
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        # Force hardware cleanup
        can_manager._cleanup_on_hardware_failure("Test simulation")
        
        log_can_event(
            "hardware_failure_simulated",
            "Hardware failure simulated for testing"
        )
        
        return jsonify({
            "message": "Hardware failure simulated",
            "warning": "CAN bus has been disconnected",
            "reconnect_with": "POST /api/can/connect"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@can_api.route('/api/can/test/force-device-cleanup', methods=['POST'])
@jwt_required()
def force_device_cleanup():
    """
    TESTING ENDPOINT: Force device timeout handler to run.
    
    Body: {"device_id": "can_123"}
    """
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    device_id = data.get('device_id')
    
    try:
        device = can_manager.get_device(device_id)
        
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # Force timeout handler
        can_manager._handle_device_timeout(device)
        
        log_can_event(
            "device_cleanup_forced",
            f"Forced cleanup for {device.name}",
            {"device_id": device_id}
        )
        
        return jsonify({
            "message": "Device cleanup forced",
            "device_id": device_id,
            "device_name": device.name
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# Enhanced Status Endpoints
# ============================================

@can_api.route('/api/can/status/detailed', methods=['GET'])
@jwt_required()
def get_detailed_status():
    """
    Get detailed CAN bus status including:
    - Hardware health
    - Device liveness
    - Circuit breaker states
    - Error statistics
    """
    try:
        status = can_manager.get_status()
        devices = can_manager.get_all_devices()
        
        # Calculate additional metrics
        total_errors = status.get('errors', 0)
        total_messages = status.get('rx_total', 0) + status.get('tx_total', 0)
        error_rate = (total_errors / total_messages * 100) if total_messages > 0 else 0
        
        # Categorize devices
        alive_devices = [d for d in devices if d.get('alive', False)]
        timeout_devices = [d for d in devices if not d.get('alive', False) and d.get('last_rx_time')]
        never_seen_devices = [d for d in devices if not d.get('last_rx_time')]
        
        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "hardware": {
                "connected": status.get('connected'),
                "bitrate": status.get('bitrate'),
                "uptime": status.get('uptime'),
                "circuit_breaker": status.get('hardware_circuit_breaker')
            },
            "statistics": {
                "rx_total": status.get('rx_total'),
                "tx_total": status.get('tx_total'),
                "errors": total_errors,
                "error_rate_percent": round(error_rate, 2),
                "hardware_failures": status.get('hardware_failures'),
                "device_timeouts": status.get('device_timeouts'),
                "auto_cleanups": status.get('auto_cleanups'),
                "overruns": status.get('overruns')
            },
            "devices": {
                "total": len(devices),
                "alive": len(alive_devices),
                "timeout": len(timeout_devices),
                "never_seen": len(never_seen_devices),
                "alive_list": [d['id'] for d in alive_devices],
                "timeout_list": [d['id'] for d in timeout_devices],
                "never_seen_list": [d['id'] for d in never_seen_devices]
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
