#!/usr/bin/env python3
# efio_daemon/io_manager.py
# SIMPLIFIED: No unnecessary health checks, just reliable I/O

import gpiod
from gpiod.line import Direction, Value, Bias
import threading
import time
from efio_daemon.state import state

# Pin Mapping
INPUT_PINS = {
    'DI0': ('/dev/gpiochip3', 3),
    'DI1': ('/dev/gpiochip1', 26),
    'DI2': ('/dev/gpiochip1', 17),
    'DI3': ('/dev/gpiochip3', 2),
}

OUTPUT_PINS = {
    'DO0': ('/dev/gpiochip1', 24),
    'DO1': ('/dev/gpiochip1', 27),
    'DO2': ('/dev/gpiochip1', 28),
    'DO3': ('/dev/gpiochip1', 29),
}


class IOManager:
    """
    Simple, reliable GPIO manager.
    
    Design principles:
    - No health checks (unused pins are normal)
    - Graceful degradation to simulation mode on hardware failure
    - Automatic recovery attempts in background
    - Simple error handling
    """
    
    def __init__(self):
        self.requests_in = {}
        self.requests_out = {}
        self._lock = threading.RLock()
        self._reinit_thread = None
        self._stop_reinit = False
        
        # Try to initialize hardware
        if not state["simulation"]:
            try:
                self._init_hardware()
                print("✅ GPIO initialized")
            except Exception as e:
                print(f"⚠️ GPIO init failed: {e}")
                print("💾 Running in simulation mode")
                state["simulation"] = True
                self._start_reinit_thread()

    # ================================
    # Hardware Setup
    # ================================
    def _setup_inputs(self):
        """Setup input pins"""
        chips = {}
        for name, (chip, line) in INPUT_PINS.items():
            chips.setdefault(chip, []).append(line)

        for chip, lines in chips.items():
            config = {
                ln: gpiod.LineSettings(
                    direction=Direction.INPUT,
                    bias=Bias.PULL_DOWN
                )
                for ln in lines
            }
            req = gpiod.request_lines(
                chip, consumer="efio_inputs", config=config
            )
            self.requests_in[chip] = req

    def _setup_outputs(self):
        """Setup output pins"""
        chips = {}
        for name, (chip, line) in OUTPUT_PINS.items():
            chips.setdefault(chip, []).append(line)

        for chip, lines in chips.items():
            config = {
                ln: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                    output_value=Value.INACTIVE
                )
                for ln in lines
            }
            req = gpiod.request_lines(
                chip, consumer="efio_outputs", config=config
            )
            self.requests_out[chip] = req

    def _cleanup_hardware(self):
        """Clean up GPIO requests"""
        try:
            for req in self.requests_in.values():
                try:
                    req.release()
                except:
                    pass
            self.requests_in.clear()
            
            for req in self.requests_out.values():
                try:
                    req.release()
                except:
                    pass
            self.requests_out.clear()
        except:
            pass

    def _init_hardware(self):
        """Initialize GPIO hardware"""
        self._cleanup_hardware()
        self._setup_inputs()
        self._setup_outputs()
        state["simulation"] = False

    # ================================
    # Public API
    # ================================
    def read_all_inputs(self):
        """
        Read all digital inputs.
        Returns list of [0, 0, 0, 0] values.
        
        Note: If hardware fails, switches to simulation mode
        and returns last known state.
        """
        if state["simulation"]:
            return state["di"]
        
        try:
            new_vals = []
            
            for name, (chip, line) in INPUT_PINS.items():
                req = self.requests_in.get(chip)
                if not req:
                    raise RuntimeError(f"GPIO chip {chip} not available")
                
                val_raw = req.get_value(line)
                val = 1 if val_raw == Value.ACTIVE else 0
                new_vals.append(val)
            
            # Update state
            state["di"] = new_vals
            return new_vals
            
        except Exception as e:
            # Hardware failure - switch to simulation
            print(f"❌ GPIO read error: {e}")
            
            if not state["simulation"]:
                print("⚠️ Switching to simulation mode")
                state["simulation"] = True
                self._start_reinit_thread()
            
            return state["di"]

    def write_output(self, ch, value):
        """
        Write digital output.
        
        Args:
            ch: Channel number (0-3)
            value: 1 (ON) or 0 (OFF)
        """
        # Always update state first
        state["do"][ch] = value
        
        # If in simulation, just log
        if state["simulation"]:
            print(f"💾 Simulation: DO{ch} = {value}")
            return
        
        # Try to write to hardware
        try:
            pin_key = f"DO{ch}"
            chip, line = OUTPUT_PINS[pin_key]
            
            req = self.requests_out.get(chip)
            if not req:
                raise RuntimeError(f"GPIO chip {chip} not available")
            
            req.set_value(line, Value.ACTIVE if value else Value.INACTIVE)
            print(f"✅ DO{ch} = {value}")
            
        except Exception as e:
            print(f"❌ GPIO write error: {e}")
            
            if not state["simulation"]:
                print("⚠️ Switching to simulation mode")
                state["simulation"] = True
                self._start_reinit_thread()

    # ================================
    # Background Recovery
    # ================================
    def _start_reinit_thread(self):
        """
        Start background thread to retry hardware initialization.
        
        Retry schedule:
        - Attempt 1: Wait 2s
        - Attempt 2: Wait 4s
        - Attempt 3: Wait 8s
        - Attempt 4: Wait 16s
        - Attempt 5: Wait 32s
        - Attempt 6+: Wait 60s (max)
        
        Stops automatically when hardware reconnects.
        """
        if self._reinit_thread and self._reinit_thread.is_alive():
            return
        
        self._stop_reinit = False
        
        def reinit_loop():
            backoff = 2
            attempt = 0
            
            print("🔄 GPIO recovery thread started")
            
            while not self._stop_reinit:
                attempt += 1
                
                # Wait before retry
                print(f"🔄 GPIO recovery attempt {attempt} in {backoff}s...")
                time.sleep(backoff)
                
                try:
                    # Try to reinitialize
                    self._init_hardware()
                    
                    # Success!
                    print("✅ GPIO hardware reconnected!")
                    state["simulation"] = False
                    break
                    
                except Exception as e:
                    print(f"⚠️ Recovery attempt {attempt} failed: {e}")
                    
                    # Exponential backoff (max 60s)
                    backoff = min(backoff * 2, 60)
        
        self._reinit_thread = threading.Thread(target=reinit_loop, daemon=True)
        self._reinit_thread.start()

    def stop_reinit_thread(self):
        """Stop recovery thread"""
        self._stop_reinit = True

    def get_status(self):
        """Get current status (for diagnostics)"""
        return {
            "simulation_mode": state["simulation"],
            "reinit_thread_active": self._reinit_thread and self._reinit_thread.is_alive(),
            "input_chips": len(self.requests_in),
            "output_chips": len(self.requests_out)
        }