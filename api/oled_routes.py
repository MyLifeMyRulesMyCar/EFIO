#!/usr/bin/env python3
# api/oled_routes.py
# FIXED: Properly detect and handle simulation mode

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from oled_manager.auto_display import OLEDAutoDisplay
from efio_daemon.state import state
import os

oled_api = Blueprint('oled_api', __name__)

# Global display instance
display = None

def init_oled_display():
    """
    Initialize OLED display (call this at app startup)
    
    FIXED: Auto-detect if I2C hardware is available
    """
    global display
    if display is None:
        # Auto-detect simulation mode
        simulation = state.get_simulation_oled()
        
        # If not explicitly set, check if I2C device exists
        if not simulation:
            i2c_device = "/dev/i2c-9"
            if not os.path.exists(i2c_device):
                print(f"⚠️  I2C device {i2c_device} not found")
                print("📺 OLED: Running in simulation mode")
                simulation = True
                state.set_simulation_oled(True)
        
        try:
            display = OLEDAutoDisplay(simulation=simulation)
            display.start()
            
            if simulation:
                print("✅ OLED Auto-Display initialized (SIMULATION mode)")
                print("   Output: /tmp/oled_display.png")
            else:
                print("✅ OLED Auto-Display initialized (HARDWARE mode)")
                print("   Device: /dev/i2c-9")
        except Exception as e:
            print(f"❌ OLED initialization failed: {e}")
            print("📺 Falling back to simulation mode")
            
            # Fallback to simulation
            state.set_simulation_oled(True)
            display = OLEDAutoDisplay(simulation=True)
            display.start()

def stop_oled_display():
    """Stop OLED display (call this at app shutdown)"""
    global display
    if display:
        display.stop()
        display = None
        print("🛑 OLED Auto-Display stopped")

# ============================================
# OLED Control Endpoints
# ============================================

@oled_api.route('/api/oled/status', methods=['GET'])
@jwt_required()
def get_oled_status():
    """Get current OLED display status"""
    if not display:
        return jsonify({
            "error": "Display not initialized",
            "running": False
        }), 500
    
    return jsonify({
        "running": display.running,
        "current_screen": display.current_screen + 1,
        "total_screens": display.total_screens,
        "dimmed": display.dimmed,
        "simulation": display.simulation,
        "rotation_interval": display.rotation_interval
    }), 200

@oled_api.route('/api/oled/screen', methods=['POST'])
@jwt_required()
def set_screen():
    """Manually set display screen"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    data = request.get_json()
    screen_num = data.get('screen')
    
    if screen_num is None:
        return jsonify({"error": "screen number required"}), 400
    
    screen_num = int(screen_num) - 1  # Convert to 0-indexed
    
    if screen_num < 0 or screen_num >= display.total_screens:
        return jsonify({"error": f"screen must be 1-{display.total_screens}"}), 400
    
    display.set_screen(screen_num)
    
    return jsonify({
        "message": "Screen changed",
        "current_screen": screen_num + 1
    }), 200

@oled_api.route('/api/oled/screen/next', methods=['POST'])
@jwt_required()
def next_screen():
    """Go to next screen"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    display.next_screen()
    
    return jsonify({
        "message": "Moved to next screen",
        "current_screen": display.current_screen + 1
    }), 200

@oled_api.route('/api/oled/screen/prev', methods=['POST'])
@jwt_required()
def prev_screen():
    """Go to previous screen"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    display.prev_screen()
    
    return jsonify({
        "message": "Moved to previous screen",
        "current_screen": display.current_screen + 1
    }), 200

@oled_api.route('/api/oled/rotation', methods=['POST'])
@jwt_required()
def set_rotation():
    """Enable/disable auto-rotation"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    data = request.get_json()
    enabled = data.get('enabled', True)
    
    if enabled:
        if not display.running:
            display.start()
        return jsonify({"message": "Auto-rotation enabled"}), 200
    else:
        if display.running:
            display.stop()
        return jsonify({"message": "Auto-rotation disabled"}), 200

@oled_api.route('/api/oled/rotation/interval', methods=['POST'])
@jwt_required()
def set_rotation_interval():
    """Set rotation interval in seconds"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    data = request.get_json()
    interval = data.get('interval')
    
    if interval is None:
        return jsonify({"error": "interval required"}), 400
    
    interval = int(interval)
    
    if interval < 1 or interval > 60:
        return jsonify({"error": "interval must be 1-60 seconds"}), 400
    
    display.rotation_interval = interval
    
    return jsonify({
        "message": "Rotation interval updated",
        "interval": interval
    }), 200

@oled_api.route('/api/oled/brightness', methods=['POST'])
@jwt_required()
def set_brightness():
    """Set display brightness (0-100)"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    data = request.get_json()
    brightness = data.get('brightness')
    
    if brightness is None:
        return jsonify({"error": "brightness required"}), 400
    
    brightness = int(brightness)
    
    if brightness < 0 or brightness > 100:
        return jsonify({"error": "brightness must be 0-100"}), 400
    
    # TODO: Implement brightness control for SSD1306
    # Note: SSD1306 contrast control is limited, not true brightness
    
    return jsonify({
        "message": "Brightness control not yet implemented",
        "note": "SSD1306 has limited contrast control"
    }), 501

# ============================================
# Button Simulation Endpoints (for testing)
# ============================================

@oled_api.route('/api/oled/button/up', methods=['POST'])
@jwt_required()
def button_up():
    """Simulate UP button press"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    display.button_up()
    
    return jsonify({
        "message": "UP button pressed",
        "current_screen": display.current_screen + 1
    }), 200

@oled_api.route('/api/oled/button/down', methods=['POST'])
@jwt_required()
def button_down():
    """Simulate DOWN button press"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    display.button_down()
    
    return jsonify({
        "message": "DOWN button pressed",
        "current_screen": display.current_screen + 1
    }), 200

@oled_api.route('/api/oled/button/select', methods=['POST'])
@jwt_required()
def button_select():
    """Simulate SELECT button press"""
    if not display:
        return jsonify({"error": "Display not initialized"}), 500
    
    display.button_select()
    
    return jsonify({
        "message": "SELECT button pressed (config menu not yet implemented)"
    }), 200