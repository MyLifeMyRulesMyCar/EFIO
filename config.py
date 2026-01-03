#!/usr/bin/env python3
# config.py - Centralized Configuration Management
# Place in project root directory

import os
import socket
import netifaces
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    env_path = Path('/home/radxa/efio/.env')

load_dotenv(dotenv_path=env_path)

class Config:
    """Centralized configuration with auto-detection"""
    
    # ============================================
    # Auto-detect Local IP
    # ============================================
    @staticmethod
    def get_local_ip():
        """Auto-detect primary network interface IP"""
        try:
            # Method 1: Try netifaces (most reliable)
            if netifaces:
                interfaces = netifaces.interfaces()
                # Priority order: eth0, enp*, wlan0, any other
                priority = ['eth0', 'enp1s0', 'end0', 'wlan0']
                
                for iface in priority:
                    if iface in interfaces:
                        addrs = netifaces.ifaddresses(iface)
                        if netifaces.AF_INET in addrs:
                            ip = addrs[netifaces.AF_INET][0]['addr']
                            if ip and not ip.startswith('127.'):
                                print(f"✅ Detected IP: {ip} ({iface})")
                                return ip
                
                # Fallback: first non-loopback interface
                for iface in interfaces:
                    if iface == 'lo':
                        continue
                    try:
                        addrs = netifaces.ifaddresses(iface)
                        if netifaces.AF_INET in addrs:
                            ip = addrs[netifaces.AF_INET][0]['addr']
                            print(f"✅ Detected IP: {ip} ({iface})")
                            return ip
                    except:
                        continue
        except Exception as e:
            print(f"⚠️ netifaces detection failed: {e}")
        
        try:
            # Method 2: Socket connection (fallback)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            print(f"✅ Detected IP (socket): {ip}")
            return ip
        except Exception as e:
            print(f"⚠️ Socket detection failed: {e}")
        
        # Method 3: Last resort fallback
        default_ip = os.getenv('DEFAULT_WAN_IP', '192.168.100.1')
        print(f"⚠️ Using default IP: {default_ip}")
        return default_ip
    
    # ============================================
    # Server Configuration
    # ============================================
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # ============================================
    # Network Configuration
    # ============================================
    API_HOST_MODE = os.getenv('API_HOST', 'auto')
    
    # Determine actual API host
    if API_HOST_MODE == 'auto':
        LOCAL_IP = get_local_ip.__func__()
    else:
        LOCAL_IP = API_HOST_MODE
    
    API_BASE_URL = f"http://{LOCAL_IP}:{FLASK_PORT}"
    
    # CORS Configuration
    CORS_ORIGINS_STR = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5000')
    
    # Build CORS origins list
    CORS_ORIGINS = []
    for origin in CORS_ORIGINS_STR.split(','):
        CORS_ORIGINS.append(origin.strip())
    
    # Add auto-detected IPs
    CORS_ORIGINS.extend([
        f"http://{LOCAL_IP}:3000",
        f"http://{LOCAL_IP}:5000",
        f"http://{LOCAL_IP}",
        "http://localhost:3000",
        "http://localhost:5000"
    ])
    
    # Allow wildcard in development
    if FLASK_DEBUG:
        CORS_ORIGINS.append("*")
    
    # ============================================
    # Security
    # ============================================
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '28800'))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', '2592000'))
    
    # ============================================
    # MQTT Configuration
    # ============================================
    MQTT_CONFIG = {
        'broker': os.getenv('MQTT_BROKER', 'localhost'),
        'port': int(os.getenv('MQTT_PORT', '1883')),
        'username': os.getenv('MQTT_USERNAME', ''),
        'password': os.getenv('MQTT_PASSWORD', ''),
        'client_id': os.getenv('MQTT_CLIENT_ID', 'efio-daemon'),
        'use_tls': os.getenv('MQTT_USE_TLS', 'False').lower() == 'true',
        'keepalive': int(os.getenv('MQTT_KEEPALIVE', '60')),
        'qos': int(os.getenv('MQTT_QOS', '1')),
        'enabled': os.getenv('MQTT_ENABLED', 'True').lower() == 'true'
    }
    
    # ============================================
    # File Paths
    # ============================================
    EFIO_CONFIG_DIR = Path(os.getenv('EFIO_CONFIG_DIR', '/home/radxa/efio'))
    EFIO_BACKUP_DIR = Path(os.getenv('EFIO_BACKUP_DIR', '/home/radxa/efio_backups'))
    EFIO_LOG_DIR = Path(os.getenv('EFIO_LOG_DIR', '/home/radxa/efio/logs'))
    
    # Ensure directories exist
    EFIO_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    EFIO_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    EFIO_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # ============================================
    # Hardware Configuration
    # ============================================
    SIMULATION_MODE = os.getenv('SIMULATION_MODE', 'False').lower() == 'true'
    SIMULATION_OLED = os.getenv('SIMULATION_OLED', 'False').lower() == 'true'
    
    WAN_INTERFACE = os.getenv('WAN_INTERFACE', 'eth0')
    LAN_INTERFACE = os.getenv('LAN_INTERFACE', 'eth1')
    
    # ============================================
    # Developer Options
    # ============================================
    DEBUG_MQTT = os.getenv('DEBUG_MQTT', 'False').lower() == 'true'
    RELOAD_ON_CHANGE = os.getenv('RELOAD_ON_CHANGE', 'False').lower() == 'true'
    
    # ============================================
    # Display Configuration
    # ============================================
    @classmethod
    def print_config(cls):
        """Print configuration summary"""
        print("=" * 60)
        print("EFIO Configuration Summary")
        print("=" * 60)
        print(f"API Base URL:     {cls.API_BASE_URL}")
        print(f"Local IP:         {cls.LOCAL_IP}")
        print(f"Flask Host:       {cls.FLASK_HOST}:{cls.FLASK_PORT}")
        print(f"Debug Mode:       {cls.FLASK_DEBUG}")
        print(f"MQTT Broker:      {cls.MQTT_CONFIG['broker']}:{cls.MQTT_CONFIG['port']}")
        print(f"MQTT Enabled:     {cls.MQTT_CONFIG['enabled']}")
        print(f"Config Dir:       {cls.EFIO_CONFIG_DIR}")
        print(f"Simulation:       {cls.SIMULATION_MODE}")
        print(f"CORS Origins:     {len(cls.CORS_ORIGINS)} configured")
        print("=" * 60)

# Print config on import
Config.print_config()

# ============================================
# Resilience Configuration
# ============================================
class ResilienceConfig:
    # Circuit Breaker Settings
    MQTT_CIRCUIT_BREAKER_THRESHOLD = 5
    MQTT_CIRCUIT_BREAKER_TIMEOUT = 60
    
    MODBUS_CIRCUIT_BREAKER_THRESHOLD = 3
    MODBUS_CIRCUIT_BREAKER_TIMEOUT = 30
    
    # Retry Settings
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1
    MAX_RETRY_DELAY = 30
    
    # Health Check
    HEALTH_CHECK_INTERVAL = 10  # seconds