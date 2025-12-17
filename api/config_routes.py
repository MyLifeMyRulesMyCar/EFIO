# api/config_routes.py
# System configuration endpoints (network, I/O, alarms)

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
import json
import os
import subprocess

config_api = Blueprint('config_api', __name__)

# Configuration files
NETWORK_CONFIG_FILE = "/home/radxa/efio/network_config.json"
IO_CONFIG_FILE = "/home/radxa/efio/io_config.json"
ALARM_CONFIG_FILE = "/home/radxa/efio/alarm_config.json"

# ============================================
# Helper Functions
# ============================================

def admin_required():
    """Check if current user is admin"""
    claims = get_jwt()
    return claims.get('role') == 'admin'

def load_json_config(filepath, default=None):
    """Load JSON configuration file"""
    if not os.path.exists(filepath):
        return default if default is not None else {}
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return default if default is not None else {}

def save_json_config(filepath, data):
    """Save JSON configuration file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

# ============================================
# Network Configuration
# ============================================

DEFAULT_NETWORK_CONFIG = {
    "wan": {
        "interface": "eth0",
        "mode": "dhcp",  # dhcp or static
        "ip": "192.168.5.103",  # Updated to match your current IP
        "netmask": "255.255.255.0",
        "gateway": "192.168.5.1",
        "dns1": "8.8.8.8",
        "dns2": "8.8.4.4"
    },
    "lan": {
        "interface": "eth1",
        "mode": "static",
        "ip": "192.168.100.1",
        "netmask": "255.255.255.0",
        "dhcp_enabled": False,  # Disabled by default for single ethernet
        "dhcp_start": "192.168.100.100",
        "dhcp_end": "192.168.100.200",
        "enabled": False  # Mark as disabled for single ethernet boards
    },
    "hostname": "edgeforce-1000",
    "single_ethernet": True  # Flag to indicate single ethernet mode
}

@config_api.route('/api/config/network', methods=['GET'])
@jwt_required()
def get_network_config():
    """Get current network configuration"""
    config = load_json_config(NETWORK_CONFIG_FILE, DEFAULT_NETWORK_CONFIG)
    
    # Add current IP addresses from system
    try:
        import netifaces
        if 'eth0' in netifaces.interfaces():
            addrs = netifaces.ifaddresses('eth0')
            if netifaces.AF_INET in addrs:
                config['wan']['current_ip'] = addrs[netifaces.AF_INET][0]['addr']
        
        if 'eth1' in netifaces.interfaces():
            addrs = netifaces.ifaddresses('eth1')
            if netifaces.AF_INET in addrs:
                config['lan']['current_ip'] = addrs[netifaces.AF_INET][0]['addr']
    except:
        pass
    
    return jsonify(config), 200

@config_api.route('/api/config/network', methods=['POST'])
@jwt_required()
def update_network_config():
    """Update network configuration (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    
    # Validate configuration
    if 'wan' not in data or 'lan' not in data:
        return jsonify({"error": "Invalid configuration format"}), 400
    
    # Save configuration
    if save_json_config(NETWORK_CONFIG_FILE, data):
        return jsonify({
            "message": "Network configuration saved",
            "restart_required": True,
            "note": "Changes will take effect after system restart"
        }), 200
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

@config_api.route('/api/config/network/apply', methods=['POST'])
@jwt_required()
def apply_network_config():
    """Apply network configuration (requires system restart)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    # In production, this would trigger network reconfiguration
    # For MVP, we'll just return a message
    return jsonify({
        "message": "Network configuration applied",
        "note": "Please restart the system for changes to take effect"
    }), 200

# ============================================
# I/O Configuration
# ============================================

DEFAULT_IO_CONFIG = {
    "di": [
        {"channel": 0, "name": "DI1", "debounce_ms": 10, "enabled": True},
        {"channel": 1, "name": "DI2", "debounce_ms": 10, "enabled": True},
        {"channel": 2, "name": "DI3", "debounce_ms": 10, "enabled": True},
        {"channel": 3, "name": "DI4", "debounce_ms": 10, "enabled": True}
    ],
    "do": [
        {"channel": 0, "name": "DO1", "enabled": True, "inverted": False},
        {"channel": 1, "name": "DO2", "enabled": True, "inverted": False},
        {"channel": 2, "name": "DO3", "enabled": True, "inverted": False},
        {"channel": 3, "name": "DO4", "enabled": True, "inverted": False}
    ]
}

@config_api.route('/api/config/io', methods=['GET'])
@jwt_required()
def get_io_config():
    """Get I/O configuration"""
    config = load_json_config(IO_CONFIG_FILE, DEFAULT_IO_CONFIG)
    return jsonify(config), 200

@config_api.route('/api/config/io', methods=['POST'])
@jwt_required()
def update_io_config():
    """Update I/O configuration"""
    data = request.get_json()
    
    # Validate configuration
    if 'di' not in data or 'do' not in data:
        return jsonify({"error": "Invalid configuration format"}), 400
    
    # Validate DI configuration
    if len(data['di']) != 4:
        return jsonify({"error": "Must have exactly 4 digital inputs"}), 400
    
    # Validate DO configuration
    if len(data['do']) != 4:
        return jsonify({"error": "Must have exactly 4 digital outputs"}), 400
    
    # Save configuration
    if save_json_config(IO_CONFIG_FILE, data):
        return jsonify({"message": "I/O configuration saved"}), 200
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

# ============================================
# Alarm Configuration
# ============================================

DEFAULT_ALARM_CONFIG = {
    "enabled": False,
    "email": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "from_email": "",
        "to_emails": []
    },
    "alarms": [
        {
            "id": "temp_high",
            "name": "High Temperature",
            "type": "system_metric",
            "metric": "temperature",
            "condition": "greater_than",
            "threshold": 70,
            "enabled": True
        },
        {
            "id": "cpu_high",
            "name": "High CPU Usage",
            "type": "system_metric",
            "metric": "cpu",
            "condition": "greater_than",
            "threshold": 80,
            "enabled": True
        }
    ]
}

@config_api.route('/api/config/alarms', methods=['GET'])
@jwt_required()
def get_alarm_config():
    """Get alarm configuration"""
    config = load_json_config(ALARM_CONFIG_FILE, DEFAULT_ALARM_CONFIG)
    # Don't send password in response
    if 'email' in config and 'password' in config['email']:
        config['email']['password'] = '********' if config['email']['password'] else ''
    return jsonify(config), 200

@config_api.route('/api/config/alarms', methods=['POST'])
@jwt_required()
def update_alarm_config():
    """Update alarm configuration (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    
    # Load existing config to preserve password if not changed
    existing = load_json_config(ALARM_CONFIG_FILE, DEFAULT_ALARM_CONFIG)
    
    # If password is masked, keep existing password
    if 'email' in data and data['email'].get('password') == '********':
        if 'email' in existing:
            data['email']['password'] = existing['email'].get('password', '')
    
    # Save configuration
    if save_json_config(ALARM_CONFIG_FILE, data):
        return jsonify({"message": "Alarm configuration saved"}), 200
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

@config_api.route('/api/config/alarms/test', methods=['POST'])
@jwt_required()
def test_alarm():
    """Send test alarm email (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    # In production, this would send a test email
    return jsonify({
        "message": "Test email functionality not implemented in MVP",
        "note": "Email sending will be implemented in future version"
    }), 200

# ============================================
# System Information
# ============================================

@config_api.route('/api/config/system', methods=['GET'])
@jwt_required()
def get_system_info():
    """Get system information"""
    try:
        import platform
        import socket
        
        info = {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version()
        }
        
        # Get IP addresses
        try:
            import netifaces
            interfaces = {}
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    interfaces[iface] = addrs[netifaces.AF_INET][0]['addr']
            info['interfaces'] = interfaces
        except:
            pass
        
        return jsonify(info), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500