import gpiod
from gpiod.line import Direction, Value, Bias
from efio_daemon.state import state

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

        if not state["simulation"]:
            try:
                self._setup_inputs()
                self._setup_outputs()
            except Exception as e:
                # if GPIO setup fails, fall back to simulation mode and log error
                print(f"GPIO setup failed, switching to simulation mode: {e}")
                state["simulation"] = True

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
            try:
                req = gpiod.request_lines(
                    chip, consumer="efio_inputs", config=config
                )
                self.requests_in[chip] = req
            except Exception as e:
                print(f"GPIO input request failed for {chip}: {e}")
                # continue, other chips may be available

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
            try:
                req = gpiod.request_lines(
                    chip, consumer="efio_outputs", config=config
                )
                self.requests_out[chip] = req
            except Exception as e:
                print(f"GPIO output request failed for {chip}: {e}")
                # continue, other chips may be available

    # -------- Public API ------------

    def read_all_inputs(self):
        """Return list of DI values"""
        if state["simulation"]:
            return state["di"]  # real hardware not required

        new_vals = []
        for i, (name, (chip, line)) in enumerate(INPUT_PINS.items()):
            try:
                req = self.requests_in.get(chip)
                if not req:
                    # missing chip request, return default
                    new_vals.append(0)
                    continue

                val = req.get_value(line)
                new_vals.append(1 if val == Value.ACTIVE else 0)
            except Exception as e:
                print(f"GPIO read failed for {chip} line {line}: {e}")
                new_vals.append(0)

        return new_vals

    def write_output(self, ch, value):
        state["do"][ch] = value

        if state["simulation"]:
            return

        pin_key = f"DO{ch}"
        chip, line = OUTPUT_PINS[pin_key]
        try:
            req = self.requests_out.get(chip)
            if not req:
                print(f"GPIO write: no request for chip {chip}")
                return
            req.set_value(line, Value.ACTIVE if value else Value.INACTIVE)
        except Exception as e:
            print(f"GPIO write failed for {chip} line {line}: {e}")
            # on failure, mark simulation to avoid repeated errors
            state["simulation"] = True
