import time
import threading
from efio_daemon.io_manager import IOManager
from efio_daemon.state import state

class EFIODeviceDaemon:
    def __init__(self):
        self.manager = IOManager()
        self.running = True

    def loop(self):
        while self.running:
            # Read DI
            di_values = self.manager.read_all_inputs()
            state["di"] = di_values

            # DO state already set by API writes
            # hardware sync happens in write_output()

            time.sleep(0.1)  # 100ms

    def start(self):
        t = threading.Thread(target=self.loop, daemon=True)
        t.start()
        print("efio-daemon running...")
