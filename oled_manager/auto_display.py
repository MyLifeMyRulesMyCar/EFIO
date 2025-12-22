#!/usr/bin/env python3
# oled_manager/auto_display.py
# Auto-rotating OLED display system per PRD specifications

import sys
import os
import time
import threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import netifaces
import psutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from efio_daemon.state import state
from oled_manager.oled_hw import OledHardware, pil_to_ssd1306_buffer

class OLEDAutoDisplay:
    """
    Auto-rotating OLED display manager
    Implements PRD Section 4.2.6 - Display Content (Auto-Rotating Screens)
    
    Screens:
    1. Network Status (Default)
    2. I/O Status
    3. System Metrics
    4. Expansion Modules (if any)
    """
    
    def __init__(self, simulation=False):
        self.simulation = simulation
        self.oled = None if simulation else OledHardware()
        
        # Display state
        self.current_screen = 0
        self.total_screens = 4
        self.rotation_interval = 5  # seconds
        self.dimmed = False
        self.last_interaction = time.time()
        self.screensaver_timeout = 300  # 5 minutes
        
        # Screen rotation control
        self.running = False
        self.thread = None
        
        # Manual control via buttons
        self.button_override = False
        self.override_timeout = 10  # seconds
        
        # Fonts
        try:
            self.font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
            )
            self.font_medium = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
            self.font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10
            )
        except:
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
    # ============================================
    # Screen 1: Network Status
    # ============================================
    def draw_network_screen(self):
        """
        Network Status Screen:
        ┌─────────────────────┐
        │ EdgeForce-1000      │
        │ WAN: 192.168.5.103  │
        │ LAN: 192.168.100.1  │
        │ Status: Connected   │
        └─────────────────────┘
        """
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        # Title
        draw.text((2, 0), "EdgeForce-1000", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        # Get network info
        wan_ip = self._get_ip_address('eth0') or "N/A"
        lan_ip = self._get_ip_address('eth1') or "N/A"
        
        # Network info
        draw.text((2, 20), f"WAN: {wan_ip}", 1, font=self.font_small)
        draw.text((2, 32), f"LAN: {lan_ip}", 1, font=self.font_small)
        
        # Connection status
        status = "Connected" if wan_ip != "N/A" else "No Network"
        draw.text((2, 44), f"Status: {status}", 1, font=self.font_small)
        
        # Screen indicator
        self._draw_screen_indicator(draw, 0)
        
        return img
    
    # ============================================
    # Screen 2: I/O Status
    # ============================================
    def draw_io_screen(self):
        """
        I/O Status Screen:
        ┌─────────────────────┐
        │ I/O Status          │
        │ DI: [1][0][1][0]    │
        │ DO: [0][1][0][1]    │
        │ Update: 10Hz        │
        └─────────────────────┘
        """
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        # Title
        draw.text((2, 0), "I/O Status", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        # Digital Inputs
        di_str = "DI: "
        for i, val in enumerate(state["di"]):
            symbol = "■" if val else "□"
            di_str += f"{symbol} "
        draw.text((2, 20), di_str, 1, font=self.font_medium)
        
        # Digital Outputs
        do_str = "DO: "
        for i, val in enumerate(state["do"]):
            symbol = "■" if val else "□"
            do_str += f"{symbol} "
        draw.text((2, 35), do_str, 1, font=self.font_medium)
        
        # Update rate
        draw.text((2, 50), "Update: 10Hz", 1, font=self.font_small)
        
        # Screen indicator
        self._draw_screen_indicator(draw, 1)
        
        return img
    
    # ============================================
    # Screen 3: System Metrics
    # ============================================
    def draw_system_screen(self):
        """
        System Metrics Screen:
        ┌─────────────────────┐
        │ System Metrics      │
        │ CPU: 45%  RAM: 62%  │
        │ Temp: 52°C          │
        │ Uptime: 2d 4h       │
        └─────────────────────┘
        """
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        # Title
        draw.text((2, 0), "System Metrics", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        # Get system info
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Temperature
        temp = self._get_temperature()
        
        # Uptime
        uptime = self._get_uptime_string()
        
        # Display metrics
        draw.text((2, 20), f"CPU: {int(cpu_percent)}%", 1, font=self.font_medium)
        draw.text((65, 20), f"RAM: {int(memory.percent)}%", 1, font=self.font_medium)
        draw.text((2, 35), f"Temp: {int(temp)}°C", 1, font=self.font_medium)
        draw.text((2, 50), f"Up: {uptime}", 1, font=self.font_small)
        
        # Screen indicator
        self._draw_screen_indicator(draw, 2)
        
        return img
    
    # ============================================
    # Screen 4: Expansion Modules
    # ============================================
    def draw_expansion_screen(self):
        """
        Expansion Modules Screen:
        ┌─────────────────────┐
        │ Expansion           │
        │ Mod 1: DIO-16  [OK] │
        │ Mod 2: AIO-8   [OK] │
        │ Total: 2 modules    │
        └─────────────────────┘
        """
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        # Title
        draw.text((2, 0), "Expansion", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        # TODO: Get actual expansion module data from system
        # For now, show placeholder
        modules = [
            {"id": 1, "type": "DIO-16", "status": "OK"},
            {"id": 2, "type": "AIO-8", "status": "OK"}
        ]
        
        if modules:
            y = 20
            for mod in modules[:3]:  # Show max 3 modules
                status = "✓" if mod["status"] == "OK" else "✗"
                text = f"M{mod['id']}: {mod['type']} {status}"
                draw.text((2, y), text, 1, font=self.font_small)
                y += 12
            
            draw.text((2, 50), f"Total: {len(modules)} modules", 1, font=self.font_small)
        else:
            draw.text((2, 25), "No expansion", 1, font=self.font_medium)
            draw.text((2, 40), "modules found", 1, font=self.font_medium)
        
        # Screen indicator
        self._draw_screen_indicator(draw, 3)
        
        return img
    
    # ============================================
    # Helper Functions
    # ============================================
    def _draw_screen_indicator(self, draw, current):
        """Draw screen indicator dots at bottom"""
        x_start = 128 - (self.total_screens * 8)
        y = 58
        
        for i in range(self.total_screens):
            x = x_start + (i * 8)
            if i == current:
                # Filled circle for current screen
                draw.ellipse([(x, y), (x+4, y+4)], fill=1)
            else:
                # Empty circle for other screens
                draw.ellipse([(x, y), (x+4, y+4)], outline=1)
    
    def _get_ip_address(self, interface):
        """Get IP address for interface"""
        if not netifaces:
            return "N/A"
        try:
            # First check if the specific interface exists
            if interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    return addrs[netifaces.AF_INET][0]['addr']
            
            # If eth0 not found, try common alternatives
            if interface == 'eth0':
                alternatives = ['enp1s0', 'end0', 'enp0s3', 'ens33']
                for alt in alternatives:
                    if alt in netifaces.interfaces():
                        addrs = netifaces.ifaddresses(alt)
                        if netifaces.AF_INET in addrs:
                            print(f"📡 Found {interface} as {alt}: {addrs[netifaces.AF_INET][0]['addr']}")
                            return addrs[netifaces.AF_INET][0]['addr']
            
            # If eth1 not found, return None (single ethernet board)
            if interface == 'eth1':
                return None
                
        except Exception as e:
            print(f"❌ Error getting IP for {interface}: {e}")
            pass
        return None
    
    def _detect_network_interface(self):
        """Detect available network interfaces"""
        if not netifaces:
            return None, None
        
        try:
            interfaces = netifaces.interfaces()
            print(f"🔍 Available interfaces: {interfaces}")
            
            # Find first active interface with IP (excluding loopback)
            for iface in interfaces:
                if iface == 'lo':
                    continue
                try:
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        ip = addrs[netifaces.AF_INET][0]['addr']
                        print(f"✅ Active interface: {iface} = {ip}")
                        return iface, ip
                except:
                    continue
        except Exception as e:
            print(f"❌ Error detecting interfaces: {e}")
        
        return None, None
    
    def _get_temperature(self):
        """Get RK3588 temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return int(f.read().strip()) / 1000.0
        except:
            return 45.0
    
    def _get_uptime_string(self):
        """Get uptime as human-readable string"""
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            
            if days > 0:
                return f"{days}d {hours}h"
            else:
                return f"{hours}h {int((uptime_seconds % 3600) // 60)}m"
        except:
            return "N/A"
    
    # ============================================
    # Display Control
    # ============================================
    def show_screen(self, screen_num):
        """Display specific screen"""
        if screen_num == 0:
            img = self.draw_network_screen()
        elif screen_num == 1:
            img = self.draw_io_screen()
        elif screen_num == 2:
            img = self.draw_system_screen()
        elif screen_num == 3:
            img = self.draw_expansion_screen()
        else:
            return
        
        if self.simulation:
            # Save to file for debugging
            img.save("/tmp/oled_display.png")
            print(f"📺 OLED: Screen {screen_num + 1}/{self.total_screens} saved to /tmp/oled_display.png")
        else:
            # Send to hardware
            buffer = pil_to_ssd1306_buffer(img)
            self.oled.draw_buffer(buffer)
            print(f"📺 OLED: Screen {screen_num + 1}/{self.total_screens} displayed")
    
    def next_screen(self):
        """Go to next screen"""
        self.current_screen = (self.current_screen + 1) % self.total_screens
        self.show_screen(self.current_screen)
        self.last_interaction = time.time()
    
    def prev_screen(self):
        """Go to previous screen"""
        self.current_screen = (self.current_screen - 1) % self.total_screens
        self.show_screen(self.current_screen)
        self.last_interaction = time.time()
    
    def set_screen(self, screen_num):
        """Jump to specific screen"""
        if 0 <= screen_num < self.total_screens:
            self.current_screen = screen_num
            self.show_screen(self.current_screen)
            self.last_interaction = time.time()
    
    # ============================================
    # Auto-Rotation Thread
    # ============================================
    def _rotation_loop(self):
        """Background thread for auto-rotation"""
        next_rotation = time.time() + self.rotation_interval
        
        while self.running:
            current_time = time.time()
            
            # Check for screensaver
            idle_time = current_time - self.last_interaction
            if idle_time > self.screensaver_timeout and not self.dimmed:
                print("💤 OLED: Dimming display (screensaver)")
                # TODO: Implement dimming (brightness reduction)
                self.dimmed = True
            elif idle_time <= self.screensaver_timeout and self.dimmed:
                print("👀 OLED: Restoring brightness")
                self.dimmed = False
            
            # Auto-rotation (unless button override active)
            if not self.button_override and current_time >= next_rotation:
                self.next_screen()
                next_rotation = current_time + self.rotation_interval
            
            time.sleep(0.5)
    
    def start(self):
        """Start auto-rotation"""
        if self.running:
            return
        
        print("🔄 OLED Auto-Display: Starting...")
        self.running = True
        
        # Show initial screen
        self.show_screen(self.current_screen)
        
        # Start rotation thread
        self.thread = threading.Thread(target=self._rotation_loop, daemon=True)
        self.thread.start()
        
        print("✅ OLED Auto-Display: Running")
    
    def stop(self):
        """Stop auto-rotation"""
        print("🛑 OLED Auto-Display: Stopping...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.oled:
            self.oled.clear()
        print("✅ OLED Auto-Display: Stopped")
    
    # ============================================
    # Button Handlers (for manual control)
    # ============================================
    def button_up(self):
        """Handle UP button press (previous screen)"""
        print("🔼 Button: UP pressed")
        self.button_override = True
        self.prev_screen()
        # Reset override after timeout
        threading.Timer(self.override_timeout, self._clear_override).start()
    
    def button_down(self):
        """Handle DOWN button press (next screen)"""
        print("🔽 Button: DOWN pressed")
        self.button_override = True
        self.next_screen()
        # Reset override after timeout
        threading.Timer(self.override_timeout, self._clear_override).start()
    
    def button_select(self):
        """Handle SELECT button press (enter config menu)"""
        print("✓ Button: SELECT pressed")
        # TODO: Implement configuration menu
        pass
    
    def _clear_override(self):
        """Clear button override flag"""
        self.button_override = False
        print("🔄 OLED: Resuming auto-rotation")


# ============================================
# Standalone Test
# ============================================
if __name__ == "__main__":
    import sys
    
    # Check for simulation mode
    simulation = "--sim" in sys.argv
    
    print("=" * 50)
    print("OLED Auto-Display Test")
    print(f"Mode: {'Simulation' if simulation else 'Hardware'}")
    print("=" * 50)
    
    # Create display
    display = OLEDAutoDisplay(simulation=simulation)
    
    # Start auto-rotation
    display.start()
    
    try:
        # Run for 30 seconds showing all screens
        print("\n⏳ Running for 30 seconds...")
        print("   Press Ctrl+C to stop\n")
        time.sleep(30)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        display.stop()
        print("\n✅ Test complete")