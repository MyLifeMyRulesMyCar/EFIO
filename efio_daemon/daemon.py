import time
import threading
from efio_daemon.io_manager import IOManager
from efio_daemon.state import state
import paho.mqtt.client as mqtt

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


class EFIODeviceDaemon:
    def __init__(self):
        self.manager = IOManager()
        self.running = True
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect("localhost", 1883, 60)
        self.mqtt_client.loop_start()
        
        self.last_di = [0, 0, 0, 0]
        
    def loop(self):
        while self.running:
            # Read DI
            di_values = self.manager.read_all_inputs()
            
            # Publish only if changed
            for i, val in enumerate(di_values):
                if val != self.last_di[i]:
                    topic = f"edgeforce/io/di/{i+1}"
                    self.mqtt_client.publish(topic, val, retain=True)
            
            self.last_di = di_values
            state["di"] = di_values
            
            time.sleep(0.1)
