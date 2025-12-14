import serial

class RS485Port:
    def __init__(self, port="/dev/ttyS2", baudrate=115200):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5
        )

    def fileno(self):
        return self.ser.fileno()

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
