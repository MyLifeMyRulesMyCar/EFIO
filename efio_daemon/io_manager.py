import gpiod
from gpiod.line import Direction, Value, Bias
import threading
import time
from efio_daemon.state import state
from efio_daemon.resilience import (
    CircuitBreaker,
    retry_with_backoff,
    health_status
)

# ------------ Pin Mapping (update as needed) -----------

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
    def __init__(self):
        self.requests_in = {}
        self.requests_out = {}
        self._gpio_failure_count = 0
        # track last seen values and change timestamps per-input for watchdog
        self._last_input_values = {}
        self._last_input_change = {}
        self._input_seen = {}
        self._gpio_lock = threading.RLock()
        self._reinit_thread = None
        self._stop_reinit = False

        # Circuit breaker for GPIO operations
        self.gpio_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30,
            expected_exception=Exception,
            name="GPIO"
        )

        if not state["simulation"]:
            # Try initialization with retries
            try:
                self._init_hardware()
            except Exception as e:
                print(f"GPIO initial setup failed: {e}; entering simulation mode")
                state["simulation"] = True
                health_status.update("gpio", "degraded", "GPIO init failed, simulation mode")
                # start background reinit attempts
                self._start_reinit_thread()

    # -------- Setup hardware pins --------
    def _setup_inputs(self):
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

    @retry_with_backoff(max_retries=3, initial_delay=1, expected_exception=Exception)
    def _init_hardware(self):
        """Attempt to initialize GPIO hardware (raises on failure)."""
        # perform both setups; allow exceptions to bubble for retry
        self._setup_inputs()
        self._setup_outputs()
        # success
        state["simulation"] = False
        health_status.update("gpio", "healthy", "GPIO initialized")

    # -------- Public API ------------

    def read_all_inputs(self):
        """Return list of DI values"""
        if state["simulation"]:
            return state["di"]  # real hardware not required
        # Circuit-breaker protected read with input watchdog
        GPIO_STUCK_SECONDS = 5

        @self.gpio_breaker.call
        def _read():
            new_vals = []
            now = time.time()
            for i, (name, (chip, line)) in enumerate(INPUT_PINS.items()):
                try:
                    req = self.requests_in.get(chip)
                    if not req:
                        # no request object for this chip; treat as 0 but mark seen
                        new_vals.append(0)
                        if name not in self._input_seen:
                            self._input_seen[name] = True
                            self._last_input_change[name] = now
                            self._last_input_values[name] = 0
                        continue

                    val_raw = req.get_value(line)
                    val = 1 if val_raw == Value.ACTIVE else 0
                    new_vals.append(val)

                    # initialize tracking
                    if name not in self._input_seen:
                        self._input_seen[name] = True
                        self._last_input_values[name] = val
                        self._last_input_change[name] = now
                    else:
                        if self._last_input_values.get(name) != val:
                            # value changed -> update timestamp
                            self._last_input_values[name] = val
                            self._last_input_change[name] = now

                except Exception as e:
                    print(f"GPIO read failed for {chip} line {line}: {e}")
                    # count consecutive failures
                    with self._gpio_lock:
                        self._gpio_failure_count += 1
                        if self._gpio_failure_count >= 5:
                            # degrade to simulation and start reinit attempts
                            print("GPIO: too many read failures, switching to simulation mode")
                            # preserve last-known DI values in state
                            state["simulation"] = True
                            health_status.update("gpio", "degraded", "Consecutive read failures")
                            self._start_reinit_thread()
                    new_vals.append(0)

            # reset failure counter on successful read
            with self._gpio_lock:
                self._gpio_failure_count = 0

            # Update shared state with last-known values (graceful degradation)
            try:
                # keep previous state if we are switching to simulation
                state["di"] = new_vals
            except Exception:
                pass

            # Watchdog: if any input has been inactive (0) with no change for longer than threshold, mark degraded
            degraded = False
            degraded_msgs = []
            for name in INPUT_PINS.keys():
                last_change = self._last_input_change.get(name)
                seen = self._input_seen.get(name, False)
                val = self._last_input_values.get(name, None)
                if seen and last_change and val == 0:
                    if now - last_change > GPIO_STUCK_SECONDS:
                        degraded = True
                        degraded_msgs.append(f"{name} inactive for {int(now - last_change)}s")

            if degraded:
                health_status.update("gpio", "degraded", ", ".join(degraded_msgs))
            else:
                health_status.update("gpio", "healthy", "I/O operational")

            return new_vals

        return _read()

    def write_output(self, ch, value):
        state["do"][ch] = value

        if state["simulation"]:
            return

        pin_key = f"DO{ch}"
        chip, line = OUTPUT_PINS[pin_key]
        # Circuit-breaker protected write
        @self.gpio_breaker.call
        def _write():
            try:
                req = self.requests_out.get(chip)
                if not req:
                    print(f"GPIO write: no request for chip {chip}")
                    raise RuntimeError(f"No request for chip {chip}")
                req.set_value(line, Value.ACTIVE if value else Value.INACTIVE)
            except Exception as e:
                print(f"GPIO write failed for {chip} line {line}: {e}")
                with self._gpio_lock:
                    self._gpio_failure_count += 1
                    if self._gpio_failure_count >= 5:
                        state["simulation"] = True
                        health_status.update("gpio", "degraded", "Consecutive write failures")
                        self._start_reinit_thread()
                raise

        try:
            _write()
        except Exception:
            # swallow to avoid crashing caller; circuit breaker handles state
            return

    def _start_reinit_thread(self):
        """Start background thread to attempt hardware re-initialization."""
        if self._reinit_thread and self._reinit_thread.is_alive():
            return
        self._stop_reinit = False

        def reinit_loop():
            backoff = 2
            while not self._stop_reinit:
                try:
                    print("GPIO reinit: attempting to initialize hardware...")
                    self._init_hardware()
                    print("GPIO reinit: hardware initialized successfully")
                    health_status.update("gpio", "healthy", "GPIO reinitialized")
                    break
                except Exception as e:
                    print(f"GPIO reinit failed: {e}; retrying in {backoff}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)

        self._reinit_thread = threading.Thread(target=reinit_loop, daemon=True)
        self._reinit_thread.start()

    def stop_reinit_thread(self):
        self._stop_reinit = True
