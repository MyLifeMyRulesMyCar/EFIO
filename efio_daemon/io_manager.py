#!/usr/bin/env python3
# efio_daemon/io_manager.py
# FIXED: Proper locking for GPIO hardware access

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
    GPIO manager with proper thread safety.
    
    CRITICAL FIX: The _lock protects gpiod hardware access,
    while state.lock() protects shared state access.
    These are DIFFERENT locks serving different purposes.
    """
    
    def __init__(self):
        self.requests_in = {}
        self.requests_out = {}
        self._hw_lock = threading.RLock()  # Renamed for clarity
        self._reinit_thread = None
        self._stop_reinit = False
        
        # Try to initialize hardware
        if not state.get_simulation():
            try:
                self._init_hardware()
                print("✅ GPIO initialized")
            except Exception as e:
                print(f"⚠️ GPIO init failed: {e}")
                print("💾 Running in simulation mode")
                state.set_simulation(True)
                self._start_reinit_thread()

    # ================================
    # Hardware Setup
    # ================================
    def _setup_inputs(self):
        """Setup input pins (must be called with _hw_lock held)"""
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
        """Setup output pins (must be called with _hw_lock held)"""
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
        """Clean up GPIO requests (must be called with _hw_lock held)"""
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
        with self._hw_lock:
            self._cleanup_hardware()
            self._setup_inputs()
            self._setup_outputs()
        state.set_simulation(False)

    # ================================
    # Public API - FIXED RACE CONDITIONS
    # ================================
    def read_all_inputs(self):
        """
        Read all digital inputs with proper locking.
        
        CRITICAL FIX: Use BOTH locks in correct order:
        1. Hardware lock (protects gpiod calls)
        2. State lock (protects state updates)
        """
        if state.get_simulation():
            return state.get_di()
        
        try:
            # Step 1: Read from hardware (locked)
            with self._hw_lock:
                new_vals = []
                for name, (chip, line) in INPUT_PINS.items():
                    req = self.requests_in.get(chip)
                    if not req:
                        raise RuntimeError(f"GPIO chip {chip} not available")
                    
                    val_raw = req.get_value(line)
                    val = 1 if val_raw == Value.ACTIVE else 0
                    new_vals.append(val)

            # Step 2: Update state atomically (separate lock)
            state.set_di_all(new_vals)
            return new_vals
            
        except Exception as e:
            # Hardware failure - switch to simulation
            print(f"❌ GPIO read error: {e}")
            
            if not state.get_simulation():
                print("⚠️ Switching to simulation mode")
                state.set_simulation(True)
                self._start_reinit_thread()
            
            return state.get_di()

    def write_output(self, ch, value):
        """
        Write digital output with proper locking.
        
        CRITICAL FIX: Update state FIRST, then hardware.
        This ensures state is always consistent even if hardware fails.
        """
        # Step 1: Update state atomically (always succeeds)
        state.set_do(ch, value)
        
        # Step 2: If in simulation, we're done
        if state.get_simulation():
            print(f"💾 Simulation: DO{ch} = {value}")
            return
        
        # Step 3: Write to hardware (protected by hw_lock)
        try:
            pin_key = f"DO{ch}"
            chip, line = OUTPUT_PINS[pin_key]
            
            with self._hw_lock:
                req = self.requests_out.get(chip)
                if not req:
                    raise RuntimeError(f"GPIO chip {chip} not available")
                
                req.set_value(line, Value.ACTIVE if value else Value.INACTIVE)
            
            print(f"✅ DO{ch} = {value}")
            
        except Exception as e:
            print(f"❌ GPIO write error: {e}")
            
            if not state.get_simulation():
                print("⚠️ Switching to simulation mode")
                state.set_simulation(True)
                self._start_reinit_thread()

    # ================================
    # Background Recovery (unchanged)
    # ================================
    def _start_reinit_thread(self):
        """Start background thread to retry hardware initialization."""
        if self._reinit_thread and self._reinit_thread.is_alive():
            return
        
        self._stop_reinit = False
        
        def reinit_loop():
            backoff = 2
            attempt = 0
            
            print("🔄 GPIO recovery thread started")
            
            while not self._stop_reinit:
                attempt += 1
                print(f"🔄 GPIO recovery attempt {attempt} in {backoff}s...")
                time.sleep(backoff)
                
                try:
                    self._init_hardware()
                    print("✅ GPIO hardware reconnected!")
                    state.set_simulation(False)
                    break
                except Exception as e:
                    print(f"⚠️ Recovery attempt {attempt} failed: {e}")
                    backoff = min(backoff * 2, 60)
        
        self._reinit_thread = threading.Thread(target=reinit_loop, daemon=True)
        self._reinit_thread.start()

    def stop_reinit_thread(self):
        """Stop recovery thread"""
        self._stop_reinit = True

    def get_status(self):
        """Get current status (for diagnostics)"""
        return {
            "simulation_mode": state.get_simulation(),
            "reinit_thread_active": self._reinit_thread and self._reinit_thread.is_alive(),
            "input_chips": len(self.requests_in),
            "output_chips": len(self.requests_out)
        }