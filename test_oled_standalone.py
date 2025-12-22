#!/usr/bin/env python3
# test_oled_standalone.py
# Standalone OLED test without dependencies

import sys
import os
import time
import threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

try:
    import netifaces
except ImportError:
    print("⚠️  netifaces not installed, network info will be limited")
    netifaces = None

try:
    import psutil
except ImportError:
    print("⚠️  psutil not installed, system metrics will be limited")
    psutil = None

# Mock hardware if not available
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from oled_manager.oled_hw import OledHardware, pil_to_ssd1306_buffer
    HAS_HARDWARE = True
except ImportError:
    print("⚠️  Hardware OLED module not available, simulation only")
    HAS_HARDWARE = False
    
    def pil_to_ssd1306_buffer(img):
        """Dummy function for simulation"""
        return []

# Mock state
state = {
    "di": [0, 1, 0, 1],
    "do": [1, 0, 1, 0],
    "simulation": False,
    "simulation_oled": "--sim" in sys.argv
}


class OLEDAutoDisplay:
    """Standalone OLED auto-display"""
    
    def __init__(self, simulation=False):
        self.simulation = simulation
        self.oled = None
        
        if not simulation and HAS_HARDWARE:
            try:
                self.oled = OledHardware()
                print("✅ Hardware OLED initialized")
            except Exception as e:
                print(f"❌ Hardware OLED failed: {e}")
                print("   Falling back to simulation mode")
                self.simulation = True
        else:
            self.simulation = True
            print("📱 Running in simulation mode")
        
        # Display state
        self.current_screen = 0
        self.total_screens = 4
        self.rotation_interval = 5
        self.running = False
        self.thread = None
        
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
        """Get system temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return int(f.read().strip()) / 1000.0
        except:
            return 45.0
    
    def _get_uptime_string(self):
        """Get uptime string"""
        if not psutil:
            return "N/A"
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
    
    def _draw_screen_indicator(self, draw, current):
        """Draw screen indicator dots"""
        x_start = 128 - (self.total_screens * 8)
        y = 58
        
        for i in range(self.total_screens):
            x = x_start + (i * 8)
            if i == current:
                draw.ellipse([(x, y), (x+4, y+4)], fill=1)
            else:
                draw.ellipse([(x, y), (x+4, y+4)], outline=1)
    
    def draw_network_screen(self):
        """Screen 1: Network Status"""
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        draw.text((2, 0), "EdgeForce-1000", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        # Try to get WAN IP (eth0 or alternatives)
        wan_ip = self._get_ip_address('eth0')
        
        # If still None, try to auto-detect primary interface
        if wan_ip is None:
            detected_iface, detected_ip = self._detect_network_interface()
            if detected_ip:
                wan_ip = detected_ip
        
        # Get LAN IP (may not exist on single ethernet boards)
        lan_ip = self._get_ip_address('eth1')
        
        # Display WAN
        if wan_ip:
            draw.text((2, 20), f"WAN: {wan_ip}", 1, font=self.font_small)
        else:
            draw.text((2, 20), "WAN: N/A", 1, font=self.font_small)
        
        # Display LAN (or skip if not available)
        if lan_ip:
            draw.text((2, 32), f"LAN: {lan_ip}", 1, font=self.font_small)
        else:
            draw.text((2, 32), "LAN: -", 1, font=self.font_small)
        
        # Connection status
        if wan_ip:
            status = "Connected"
            draw.text((2, 44), f"Status: {status}", 1, font=self.font_small)
        else:
            draw.text((2, 44), "Status: No Network", 1, font=self.font_small)
        
        self._draw_screen_indicator(draw, 0)
        return img
    
    def draw_io_screen(self):
        """Screen 2: I/O Status"""
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        draw.text((2, 0), "I/O Status", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        di_str = "DI: "
        for val in state["di"]:
            di_str += ("■ " if val else "□ ")
        draw.text((2, 20), di_str, 1, font=self.font_medium)
        
        do_str = "DO: "
        for val in state["do"]:
            do_str += ("■ " if val else "□ ")
        draw.text((2, 35), do_str, 1, font=self.font_medium)
        
        draw.text((2, 50), "Update: 10Hz", 1, font=self.font_small)
        
        self._draw_screen_indicator(draw, 1)
        return img
    
    def draw_system_screen(self):
        """Screen 3: System Metrics"""
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        draw.text((2, 0), "System Metrics", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        if psutil:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
        else:
            cpu_percent = 0
            memory = type('obj', (object,), {'percent': 0})()
        
        temp = self._get_temperature()
        uptime = self._get_uptime_string()
        
        draw.text((2, 20), f"CPU: {int(cpu_percent)}%", 1, font=self.font_medium)
        draw.text((65, 20), f"RAM: {int(memory.percent)}%", 1, font=self.font_medium)
        draw.text((2, 35), f"Temp: {int(temp)}°C", 1, font=self.font_medium)
        draw.text((2, 50), f"Up: {uptime}", 1, font=self.font_small)
        
        self._draw_screen_indicator(draw, 2)
        return img
    
    def draw_expansion_screen(self):
        """Screen 4: Expansion Modules"""
        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        
        draw.text((2, 0), "Expansion", 1, font=self.font_large)
        draw.line([(0, 16), (128, 16)], fill=1)
        
        # Mock modules for testing
        modules = [
            {"id": 1, "type": "DIO-16", "status": "OK"},
            {"id": 2, "type": "AIO-8", "status": "OK"}
        ]
        
        if modules:
            y = 20
            for mod in modules[:3]:
                status = "✓" if mod["status"] == "OK" else "✗"
                text = f"M{mod['id']}: {mod['type']} {status}"
                draw.text((2, y), text, 1, font=self.font_small)
                y += 12
            
            draw.text((2, 50), f"Total: {len(modules)} modules", 1, font=self.font_small)
        else:
            draw.text((2, 25), "No expansion", 1, font=self.font_medium)
            draw.text((2, 40), "modules found", 1, font=self.font_medium)
        
        self._draw_screen_indicator(draw, 3)
        return img
    
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
            img.save("/tmp/oled_display.png")
            print(f"📺 Screen {screen_num + 1}/{self.total_screens} → /tmp/oled_display.png")
        else:
            buffer = pil_to_ssd1306_buffer(img)
            self.oled.draw_buffer(buffer)
            print(f"📺 Screen {screen_num + 1}/{self.total_screens} displayed on hardware")
    
    def next_screen(self):
        """Go to next screen"""
        self.current_screen = (self.current_screen + 1) % self.total_screens
        self.show_screen(self.current_screen)
    
    def _rotation_loop(self):
        """Background rotation thread"""
        while self.running:
            time.sleep(self.rotation_interval)
            self.next_screen()
    
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
        if self.oled and not self.simulation:
            self.oled.clear()
        print("✅ OLED Auto-Display: Stopped")


if __name__ == "__main__":
    print("=" * 50)
    print("OLED Auto-Display Standalone Test")
    print("=" * 50)
    
    # Check for dependencies
    missing = []
    if not netifaces:
        missing.append("netifaces")
    if not psutil:
        missing.append("psutil")
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("   Install with: pip3 install " + " ".join(missing))
        print("   Continuing with limited functionality...\n")
    
    # Show network detection info
    if netifaces:
        print("🔍 Network Interface Detection:")
        try:
            interfaces = netifaces.interfaces()
            print(f"   Available interfaces: {interfaces}")
            
            for iface in interfaces:
                if iface == 'lo':
                    continue
                try:
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        ip = addrs[netifaces.AF_INET][0]['addr']
                        print(f"   ✅ {iface}: {ip}")
                except:
                    pass
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print()
    
    # Detect mode
    simulation = "--sim" in sys.argv
    print(f"Mode: {'Simulation' if simulation else 'Hardware'}")
    print("=" * 50 + "\n")
    
    # Create and start display
    display = OLEDAutoDisplay(simulation=simulation)
    display.start()
    
    try:
        print("⏳ Running for 30 seconds...")
        print("   Press Ctrl+C to stop\n")
        
        if simulation:
            print("💡 View output: display /tmp/oled_display.png")
            print("   Or copy: scp radxa@192.168.5.103:/tmp/oled_display.png .\n")
        
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    finally:
        display.stop()
        print("\n✅ Test complete")