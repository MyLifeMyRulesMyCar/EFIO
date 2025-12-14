import minimalmodbus
import serial
from efio_daemon.state import state

class ModbusManager:
    def __init__(self, device="/dev/ttyS2"):
        self.device = device
        self.instrument = None

    def connect(self, slave_id):
        try:
            self.instrument = minimalmodbus.Instrument(self.device, slave_id)
            self.instrument.serial.baudrate = 115200
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity = serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            self.instrument.serial.timeout = 0.5
            self.instrument.mode = minimalmodbus.MODE_RTU
            return True
        except Exception as e:
            print("Modbus connect error:", e)
            return False

    def read_register(self, reg):
        try:
            if not self.instrument:
                return None
            value = self.instrument.read_register(reg, 0)
            return value
        except Exception as e:
            print("Modbus read error:", e)
            return None

modbus_manager = ModbusManager()
