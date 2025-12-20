# api/modbus_device_routes.py
# Modbus Device Management API Routes

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
import json
import os
from datetime import datetime
import minimalmodbus
import serial
import time
import threading

modbus_device_api = Blueprint('modbus_device_api', __name__)

# Configuration files
MODBUS_CONFIG_FILE = "/home/radxa/efio/modbus_devices.json"
MODBUS_LOG_FILE = "/home/radxa/efio/modbus_log.json"

# Port configurations
MODBUS_PORTS = {
    "ttyS2": {
        "device": "/dev/ttyS2",
        "name": "Primary RS-485",
        "description": "Daisy chain capable RS-485 port"
    },
    "ttyS7": {
        "device": "/dev/ttyS7", 
        "name": "Expansion RS-485",
        "description": "Secondary RS-485 expansion port"
    }
}

# Active connections cache
active_connections = {}
polling_threads = {}
polling_active = {}

# ============================================
# Helper Functions
# ============================================

def load_devices():
    """Load device configuration from JSON"""
    if not os.path.exists(MODBUS_CONFIG_FILE):
        return []
    try:
        with open(MODBUS_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading devices: {e}")
        return []

def save_devices(devices):
    """Save device configuration to JSON"""
    try:
        os.makedirs(os.path.dirname(MODBUS_CONFIG_FILE), exist_ok=True)
        with open(MODBUS_CONFIG_FILE, 'w') as f:
            json.dump(devices, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving devices: {e}")
        return False

def log_modbus_event(event_type, device_id, message, data=None):
    """Log Modbus events"""
    try:
        logs = []
        if os.path.exists(MODBUS_LOG_FILE):
            with open(MODBUS_LOG_FILE, 'r') as f:
                logs = json.load(f)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "device_id": device_id,
            "message": message,
            "data": data
        }
        
        logs.append(log_entry)
        
        # Keep only last 1000 logs
        logs = logs[-1000:]
        
        with open(MODBUS_LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Error logging event: {e}")

def create_modbus_connection(port, slave_id, baudrate=9600, parity='N', stopbits=1):
    """Create Modbus RTU connection"""
    try:
        device_path = MODBUS_PORTS[port]["device"]
        instrument = minimalmodbus.Instrument(device_path, slave_id)
        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = 8
        
        # Set parity
        if parity == 'N':
            instrument.serial.parity = serial.PARITY_NONE
        elif parity == 'E':
            instrument.serial.parity = serial.PARITY_EVEN
        elif parity == 'O':
            instrument.serial.parity = serial.PARITY_ODD
        
        instrument.serial.stopbits = stopbits
        instrument.serial.timeout = 1.0
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.clear_buffers_before_each_transaction = True
        
        return instrument
    except Exception as e:
        print(f"Error creating connection: {e}")
        return None

# ============================================
# Port Management Endpoints
# ============================================

@modbus_device_api.route('/api/modbus/ports', methods=['GET'])
@jwt_required()
def get_ports():
    """Get available Modbus ports"""
    return jsonify({
        "ports": MODBUS_PORTS
    }), 200

# ============================================
# Device Management Endpoints
# ============================================

@modbus_device_api.route('/api/modbus/devices', methods=['GET'])
@jwt_required()
def get_devices():
    """Get all configured Modbus devices"""
    devices = load_devices()
    
    # Add connection status
    for device in devices:
        device_id = device['id']
        device['connected'] = device_id in active_connections
        device['polling'] = polling_active.get(device_id, False)
    
    return jsonify({"devices": devices}), 200

@modbus_device_api.route('/api/modbus/devices', methods=['POST'])
@jwt_required()
def create_device():
    """Create new Modbus device configuration"""
    data = request.get_json()
    
    # Validate required fields
    required = ['name', 'port', 'slave_id']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    devices = load_devices()
    
    # Generate unique ID
    device_id = f"dev_{int(time.time())}_{data['slave_id']}"
    
    # Create device object
    device = {
        "id": device_id,
        "name": data['name'],
        "description": data.get('description', ''),
        "port": data['port'],
        "slave_id": int(data['slave_id']),
        "baudrate": int(data.get('baudrate', 9600)),
        "parity": data.get('parity', 'N'),
        "stopbits": int(data.get('stopbits', 1)),
        "registers": data.get('registers', []),
        "polling_enabled": data.get('polling_enabled', False),
        "polling_interval": int(data.get('polling_interval', 1000)),
        "enabled": data.get('enabled', True),
        "created_at": datetime.now().isoformat(),
        "last_connected": None
    }
    
    devices.append(device)
    
    if save_devices(devices):
        log_modbus_event("device_created", device_id, f"Device '{data['name']}' created")
        return jsonify({"message": "Device created", "device": device}), 201
    else:
        return jsonify({"error": "Failed to save device"}), 500

@modbus_device_api.route('/api/modbus/devices/<device_id>', methods=['PUT'])
@jwt_required()
def update_device(device_id):
    """Update existing Modbus device"""
    data = request.get_json()
    devices = load_devices()
    
    device_index = next((i for i, d in enumerate(devices) if d['id'] == device_id), None)
    
    if device_index is None:
        return jsonify({"error": "Device not found"}), 404
    
    # Update device fields
    device = devices[device_index]
    device.update({
        "name": data.get('name', device['name']),
        "description": data.get('description', device['description']),
        "port": data.get('port', device['port']),
        "slave_id": int(data.get('slave_id', device['slave_id'])),
        "baudrate": int(data.get('baudrate', device['baudrate'])),
        "parity": data.get('parity', device['parity']),
        "stopbits": int(data.get('stopbits', device['stopbits'])),
        "registers": data.get('registers', device.get('registers', [])),
        "polling_enabled": data.get('polling_enabled', device.get('polling_enabled', False)),
        "polling_interval": int(data.get('polling_interval', device.get('polling_interval', 1000))),
        "enabled": data.get('enabled', device.get('enabled', True))
    })
    
    devices[device_index] = device
    
    if save_devices(devices):
        log_modbus_event("device_updated", device_id, f"Device '{device['name']}' updated")
        return jsonify({"message": "Device updated", "device": device}), 200
    else:
        return jsonify({"error": "Failed to save device"}), 500

@modbus_device_api.route('/api/modbus/devices/<device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    """Delete Modbus device"""
    devices = load_devices()
    
    device = next((d for d in devices if d['id'] == device_id), None)
    
    if not device:
        return jsonify({"error": "Device not found"}), 404
    
    # Stop polling if active
    if device_id in polling_active and polling_active[device_id]:
        stop_device_polling(device_id)
    
    # Remove connection
    if device_id in active_connections:
        del active_connections[device_id]
    
    # Remove from list
    devices = [d for d in devices if d['id'] != device_id]
    
    if save_devices(devices):
        log_modbus_event("device_deleted", device_id, f"Device '{device['name']}' deleted")
        return jsonify({"message": "Device deleted"}), 200
    else:
        return jsonify({"error": "Failed to delete device"}), 500

# ============================================
# Connection Management
# ============================================

@modbus_device_api.route('/api/modbus/devices/<device_id>/connect', methods=['POST'])
@jwt_required()
def connect_device(device_id):
    """Connect to Modbus device"""
    devices = load_devices()
    device = next((d for d in devices if d['id'] == device_id), None)
    
    if not device:
        return jsonify({"error": "Device not found"}), 404
    
    try:
        instrument = create_modbus_connection(
            device['port'],
            device['slave_id'],
            device['baudrate'],
            device['parity'],
            device['stopbits']
        )
        
        if instrument:
            active_connections[device_id] = instrument
            
            # Update last connected time
            device['last_connected'] = datetime.now().isoformat()
            device_index = next(i for i, d in enumerate(devices) if d['id'] == device_id)
            devices[device_index] = device
            save_devices(devices)
            
            log_modbus_event("connected", device_id, f"Connected to '{device['name']}'")
            
            return jsonify({
                "message": "Connected successfully",
                "device_id": device_id
            }), 200
        else:
            return jsonify({"error": "Failed to create connection"}), 500
            
    except Exception as e:
        log_modbus_event("connection_error", device_id, f"Connection failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@modbus_device_api.route('/api/modbus/devices/<device_id>/disconnect', methods=['POST'])
@jwt_required()
def disconnect_device(device_id):
    """Disconnect from Modbus device"""
    if device_id in active_connections:
        # Stop polling if active
        if polling_active.get(device_id, False):
            stop_device_polling(device_id)
        
        del active_connections[device_id]
        
        devices = load_devices()
        device = next((d for d in devices if d['id'] == device_id), None)
        
        log_modbus_event("disconnected", device_id, f"Disconnected from '{device['name'] if device else device_id}'")
        
        return jsonify({"message": "Disconnected"}), 200
    
    return jsonify({"error": "Device not connected"}), 400

# ============================================
# Register Operations
# ============================================

@modbus_device_api.route('/api/modbus/devices/<device_id>/read', methods=['POST'])
@jwt_required()
def read_registers(device_id):
    """Read Modbus registers"""
    data = request.get_json()
    
    register = int(data.get('register', 0))
    count = int(data.get('count', 1))
    function_code = int(data.get('function_code', 3))
    
    if device_id not in active_connections:
        return jsonify({"error": "Device not connected"}), 400
    
    instrument = active_connections[device_id]
    
    try:
        results = []
        
        if function_code == 1:  # Read Coils
            for i in range(count):
                value = instrument.read_bit(register + i, functioncode=1)
                results.append({"register": register + i, "value": int(value)})
                
        elif function_code == 2:  # Read Discrete Inputs
            for i in range(count):
                value = instrument.read_bit(register + i, functioncode=2)
                results.append({"register": register + i, "value": int(value)})
                
        elif function_code == 3:  # Read Holding Registers
            for i in range(count):
                value = instrument.read_register(register + i, functioncode=3)
                results.append({"register": register + i, "value": value})
                
        elif function_code == 4:  # Read Input Registers
            for i in range(count):
                value = instrument.read_register(register + i, functioncode=4)
                results.append({"register": register + i, "value": value})
        
        log_modbus_event("read", device_id, f"Read FC{function_code} from {register}, count={count}", results)
        
        return jsonify({
            "success": True,
            "registers": results
        }), 200
        
    except Exception as e:
        log_modbus_event("read_error", device_id, f"Read failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@modbus_device_api.route('/api/modbus/devices/<device_id>/write', methods=['POST'])
@jwt_required()
def write_register(device_id):
    """Write to Modbus register"""
    data = request.get_json()
    
    register = int(data.get('register', 0))
    value = data.get('value')
    function_code = int(data.get('function_code', 6))
    
    if device_id not in active_connections:
        return jsonify({"error": "Device not connected"}), 400
    
    instrument = active_connections[device_id]
    
    try:
        if function_code == 5:  # Write Single Coil
            instrument.write_bit(register, int(value), functioncode=5)
            
        elif function_code == 6:  # Write Single Register
            instrument.write_register(register, int(value), functioncode=6)
        
        log_modbus_event("write", device_id, f"Write FC{function_code} to {register}, value={value}")
        
        return jsonify({
            "success": True,
            "register": register,
            "value": value
        }), 200
        
    except Exception as e:
        log_modbus_event("write_error", device_id, f"Write failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ============================================
# Auto-Scan Feature
# ============================================

@modbus_device_api.route('/api/modbus/scan', methods=['POST'])
@jwt_required()
def scan_devices():
    """Scan for Modbus devices on a port"""
    data = request.get_json()
    
    port = data.get('port', 'ttyS2')
    start_id = int(data.get('start_id', 1))
    end_id = int(data.get('end_id', 247))
    baudrate = int(data.get('baudrate', 9600))
    
    found_devices = []
    
    try:
        for slave_id in range(start_id, end_id + 1):
            try:
                instrument = create_modbus_connection(port, slave_id, baudrate)
                
                if instrument:
                    # Try to read a register to verify device exists
                    try:
                        instrument.read_register(0, functioncode=3)
                        found_devices.append({
                            "slave_id": slave_id,
                            "port": port,
                            "baudrate": baudrate,
                            "response": "Device responded"
                        })
                        print(f"✅ Found device at slave ID {slave_id}")
                    except:
                        pass
                    
            except Exception as e:
                continue
        
        log_modbus_event("scan", "system", f"Scanned {port} IDs {start_id}-{end_id}, found {len(found_devices)} devices")
        
        return jsonify({
            "success": True,
            "found": len(found_devices),
            "devices": found_devices
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# Register Polling
# ============================================

def poll_device_registers(device_id):
    """Background thread to poll device registers"""
    devices = load_devices()
    device = next((d for d in devices if d['id'] == device_id), None)
    
    if not device or device_id not in active_connections:
        return
    
    instrument = active_connections[device_id]
    interval = device.get('polling_interval', 1000) / 1000.0  # Convert to seconds
    
    while polling_active.get(device_id, False):
        try:
            results = {}
            
            for reg_config in device.get('registers', []):
                if reg_config.get('poll', True):
                    register = reg_config['address']
                    fc = reg_config.get('function_code', 3)
                    
                    try:
                        if fc in [1, 2]:
                            value = instrument.read_bit(register, functioncode=fc)
                        else:
                            value = instrument.read_register(register, functioncode=fc)
                        
                        results[register] = {
                            "value": value,
                            "name": reg_config.get('name', f'Register {register}'),
                            "timestamp": datetime.now().isoformat()
                        }
                    except Exception as e:
                        results[register] = {
                            "error": str(e),
                            "name": reg_config.get('name', f'Register {register}')
                        }
            
            # Store results (you can publish to MQTT here if needed)
            # For now, just log periodically
            
        except Exception as e:
            print(f"Polling error for {device_id}: {e}")
        
        time.sleep(interval)

def start_device_polling(device_id):
    """Start polling thread for device"""
    if polling_active.get(device_id, False):
        return  # Already polling
    
    polling_active[device_id] = True
    thread = threading.Thread(target=poll_device_registers, args=(device_id,), daemon=True)
    polling_threads[device_id] = thread
    thread.start()

def stop_device_polling(device_id):
    """Stop polling thread for device"""
    polling_active[device_id] = False
    if device_id in polling_threads:
        del polling_threads[device_id]

@modbus_device_api.route('/api/modbus/devices/<device_id>/polling/start', methods=['POST'])
@jwt_required()
def start_polling(device_id):
    """Start register polling for device"""
    if device_id not in active_connections:
        return jsonify({"error": "Device not connected"}), 400
    
    start_device_polling(device_id)
    
    return jsonify({"message": "Polling started"}), 200

@modbus_device_api.route('/api/modbus/devices/<device_id>/polling/stop', methods=['POST'])
@jwt_required()
def stop_polling(device_id):
    """Stop register polling for device"""
    stop_device_polling(device_id)
    
    return jsonify({"message": "Polling stopped"}), 200

# ============================================
# Logs
# ============================================

@modbus_device_api.route('/api/modbus/logs', methods=['GET'])
@jwt_required()
def get_logs():
    """Get Modbus communication logs"""
    try:
        if os.path.exists(MODBUS_LOG_FILE):
            with open(MODBUS_LOG_FILE, 'r') as f:
                logs = json.load(f)
            return jsonify({"logs": logs[-100:]}), 200  # Last 100 logs
        else:
            return jsonify({"logs": []}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@modbus_device_api.route('/api/modbus/logs/clear', methods=['POST'])
@jwt_required()
def clear_logs():
    """Clear Modbus logs"""
    try:
        if os.path.exists(MODBUS_LOG_FILE):
            os.remove(MODBUS_LOG_FILE)
        return jsonify({"message": "Logs cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500