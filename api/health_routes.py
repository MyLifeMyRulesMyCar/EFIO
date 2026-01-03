#!/usr/bin/env python3
# api/health_routes.py
# Health check endpoints for monitoring and alerting

from flask import Blueprint, jsonify, current_app
from datetime import datetime
import psutil
import time

# Import health status from resilience module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from efio_daemon.resilience import health_status

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
    Returns 200 if system is operational, 503 if unhealthy.
    
    Response format:
    {
        "status": "healthy" | "degraded" | "unhealthy",
        "timestamp": "ISO8601",
        "uptime": 12345
    }
    """
    overall_status = health_status.get_overall_status()
    
    response = {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "uptime": int(time.time() - SERVER_START_TIME)
    }
    
    status_code = 200 if overall_status in ["healthy", "degraded"] else 503
    return jsonify(response), status_code

# ============================================
# Detailed Health Check
# ============================================
@health_api.route('/api/health/detailed', methods=['GET'])
def health_check_detailed():
    """
    Detailed health check with component status.
    
    Response format:
    {
        "status": "healthy",
        "timestamp": "...",
        "uptime": 12345,
        "components": {
            "mqtt": {...},
            "gpio": {...},
            "daemon": {...}
        },
        "system": {
            "cpu": 45.2,
            "memory": 62.1,
            "disk": 38.5,
            "temperature": 52.3
        }
    }
    """
    overall_status = health_status.get_overall_status()
    components = health_status.get_status()
    
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
    
    response = {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "uptime": int(time.time() - SERVER_START_TIME),
        "components": components,
        "system": {
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "disk_percent": round(disk.percent, 1),
            "temperature_celsius": round(temp, 1)
        }
    }
    
    status_code = 200 if overall_status in ["healthy", "degraded"] else 503
    return jsonify(response), status_code

# ============================================
# Liveness Probe
# ============================================
@health_api.route('/api/health/live', methods=['GET'])
def liveness_probe():
    """
    Kubernetes-style liveness probe.
    Returns 200 if server is running (even if degraded).
    
    This should ONLY fail if the server process is dead/hung.
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
    Returns 200 only if system is ready to handle requests.
    
    Returns 503 if critical components are unhealthy.
    """
    overall_status = health_status.get_overall_status()
    
    # Check critical components
    daemon_status = health_status.get_status("daemon")
    gpio_status = health_status.get_status("gpio")
    
    is_ready = (
        overall_status != "unhealthy" and
        daemon_status.get("status") != "unhealthy" and
        gpio_status.get("status") != "unhealthy"
    )
    
    response = {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now().isoformat()
    }
    
    return jsonify(response), 200 if is_ready else 503

# ============================================
# Component Health Status
# ============================================
@health_api.route('/api/health/components/<component>', methods=['GET'])
def component_health(component):
    """
    Get health status for specific component.
    
    Example: /api/health/components/mqtt
    """
    status = health_status.get_status(component)
    
    if status.get("status") == "unknown":
        return jsonify({
            "error": f"Component '{component}' not found"
        }), 404
    
    return jsonify(status), 200

# ============================================
# Daemon-Specific Health
# ============================================
@health_api.route('/api/health/daemon', methods=['GET'])
def daemon_health():
    """
    Get detailed daemon health including circuit breaker status.
    """
    try:
        daemon = current_app.daemon
        daemon_status = daemon.get_health_status()
        
        return jsonify({
            "status": "healthy" if daemon.running else "unhealthy",
            "details": daemon_status,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

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
# Circuit Breaker Status
# ============================================
@health_api.route('/api/health/circuit-breakers', methods=['GET'])
def circuit_breaker_status():
    """
    Get status of all circuit breakers in the system.
    """
    try:
        daemon = current_app.daemon
        
        breakers = {
            "mqtt": daemon.mqtt_breaker.get_state()
        }
        
        return jsonify({
            "circuit_breakers": breakers,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500