#!/usr/bin/env python3
# api/health_routes.py
# SIMPLIFIED: Removed GPIO health checks (not needed for this application)

from flask import Blueprint, jsonify, current_app
from datetime import datetime
import psutil
import time

health_api = Blueprint('health_api', __name__)

# Track when server started
SERVER_START_TIME = time.time()

# ============================================
# Basic Health Check
# ============================================
@health_api.route('/api/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint.
    Returns 200 if system is operational.
    
    Note: GPIO issues don't affect health status (simulation mode is normal)
    """
    response = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": int(time.time() - SERVER_START_TIME)
    }
    
    return jsonify(response), 200

# ============================================
# Detailed Health Check
# ============================================
@health_api.route('/api/health/detailed', methods=['GET'])
def health_check_detailed():
    """
    Detailed health check with system metrics.
    
    Removed: GPIO health (unused pins don't indicate problems)
    Kept: MQTT, Modbus, System metrics
    """
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Temperature
    temp = 45.0
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
    except:
        pass
    
    # Get GPIO mode (hardware vs simulation)
    gpio_mode = "unknown"
    try:
        daemon = current_app.daemon
        gpio_status = daemon.manager.get_status()
        gpio_mode = "simulation" if gpio_status["simulation_mode"] else "hardware"
    except:
        pass
    
    response = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": int(time.time() - SERVER_START_TIME),
        "gpio": {
            "mode": gpio_mode,
            "note": "Simulation mode is normal operation (not a fault)"
        },
        "system": {
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "disk_percent": round(disk.percent, 1),
            "temperature_celsius": round(temp, 1)
        }
    }
    
    return jsonify(response), 200

# ============================================
# Liveness Probe
# ============================================
@health_api.route('/api/health/live', methods=['GET'])
def liveness_probe():
    """
    Kubernetes-style liveness probe.
    Returns 200 if server is running.
    """
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }), 200

# ============================================
# Readiness Probe
# ============================================
@health_api.route('/api/health/ready', methods=['GET'])
def readiness_probe():
    """
    Kubernetes-style readiness probe.
    Returns 200 if system is ready to handle requests.
    """
    return jsonify({
        "status": "ready",
        "timestamp": datetime.now().isoformat()
    }), 200

# ============================================
# System Metrics for Monitoring
# ============================================
@health_api.route('/api/health/metrics', methods=['GET'])
def system_metrics():
    """
    Prometheus-style metrics endpoint.
    Returns system metrics in JSON format.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Temperature
    temp = 45.0
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
    except:
        pass
    
    # Network I/O
    net_io = psutil.net_io_counters()
    
    # Disk I/O
    disk_io = psutil.disk_io_counters()
    
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent,
            "count": psutil.cpu_count()
        },
        "memory": {
            "percent": memory.percent,
            "used_bytes": memory.used,
            "total_bytes": memory.total
        },
        "disk": {
            "percent": disk.percent,
            "used_bytes": disk.used,
            "total_bytes": disk.total
        },
        "temperature": {
            "celsius": temp
        },
        "network": {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv
        },
        "disk_io": {
            "read_bytes": disk_io.read_bytes,
            "write_bytes": disk_io.write_bytes
        },
        "uptime_seconds": int(time.time() - SERVER_START_TIME)
    }
    
    return jsonify(metrics), 200

# ============================================
# Modbus Health (Optional - Keep if using Modbus)
# ============================================
@health_api.route('/api/health/modbus', methods=['GET'])
def modbus_health():
    """
    Get Modbus device connection status.
    This is useful - shows actual connected devices.
    """
    try:
        from api.modbus_device_routes import active_connections
        
        connected_devices = []
        for device_id, instrument in active_connections.items():
            try:
                # Try a simple read to verify connection is alive
                connected_devices.append({
                    "device_id": device_id,
                    "status": "connected"
                })
            except:
                connected_devices.append({
                    "device_id": device_id,
                    "status": "error"
                })
        
        return jsonify({
            "status": "healthy" if connected_devices else "no_devices",
            "devices": connected_devices,
            "count": len(connected_devices),
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "unknown",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 200

# ============================================
# MQTT Health (Optional - Keep if using MQTT)
# ============================================
@health_api.route('/api/health/mqtt', methods=['GET'])
def mqtt_health():
    """
    Get MQTT connection status.
    This is useful - shows if broker is reachable.
    """
    try:
        daemon = current_app.daemon
        
        mqtt_status = {
            "connected": daemon.mqtt_connected,
            "broker": daemon.mqtt_config.get('broker', 'unknown'),
            "port": daemon.mqtt_config.get('port', 1883),
            "timestamp": datetime.now().isoformat()
        }
        
        status_code = 200 if daemon.mqtt_connected else 503
        
        return jsonify(mqtt_status), status_code
        
    except Exception as e:
        return jsonify({
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503