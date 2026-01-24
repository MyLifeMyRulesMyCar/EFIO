#!/usr/bin/env python3
"""
MCP2515 CAN Controller Driver for Radxa CM4
Supports reading and writing CAN messages via SPI
"""

import spidev
import time
from periphery import GPIO

# MCP2515 SPI Commands
MCP2515_RESET = 0xC0
MCP2515_READ = 0x03
MCP2515_WRITE = 0x02
MCP2515_RTS = 0x80  # Request to Send
MCP2515_READ_STATUS = 0xA0
MCP2515_BIT_MODIFY = 0x05
MCP2515_READ_RX_STATUS = 0xB0

# MCP2515 Registers
CANCTRL = 0x0F
CANSTAT = 0x0E
CNF1 = 0x2A
CNF2 = 0x29
CNF3 = 0x28
CANINTE = 0x2B
CANINTF = 0x2C

# TX Buffer 0
TXB0CTRL = 0x30
TXB0SIDH = 0x31
TXB0SIDL = 0x32
TXB0DLC = 0x35
TXB0DATA = 0x36

# RX Buffer 0
RXB0CTRL = 0x60
RXB0SIDH = 0x61
RXB0SIDL = 0x62
RXB0DLC = 0x65
RXB0DATA = 0x66

# RX Buffer 1
RXB1CTRL = 0x70
RXB1SIDH = 0x71

# Mode bits
MODE_NORMAL = 0x00
MODE_SLEEP = 0x20
MODE_LOOPBACK = 0x40
MODE_LISTENONLY = 0x60
MODE_CONFIG = 0x80

# CAN Speed Configurations (for 8MHz crystal)
CAN_SPEED = {
    5000: [0x1F, 0xBF, 0x07],     # 5 kbps
    10000: [0x0F, 0xBF, 0x07],    # 10 kbps
    20000: [0x07, 0xBF, 0x07],    # 20 kbps
    50000: [0x03, 0xBF, 0x07],    # 50 kbps
    100000: [0x01, 0xBF, 0x07],   # 100 kbps
    125000: [0x01, 0x9E, 0x03],   # 125 kbps
    250000: [0x00, 0x9E, 0x03],   # 250 kbps
    500000: [0x00, 0x92, 0x02],   # 500 kbps
}

class CANMessage:
    """CAN Message Structure"""
    def __init__(self, can_id=0, data=None, dlc=0, extended=False):
        self.can_id = can_id
        self.data = data if data else [0] * 8
        self.dlc = dlc if dlc else len(self.data)
        self.extended = extended
    
    def __repr__(self):
        data_str = ' '.join([f'0x{b:02X}' for b in self.data[:self.dlc]])
        return f"ID: 0x{self.can_id:03X}, DLC: {self.dlc}, Data: [{data_str}]"


class MCP2515:
    """MCP2515 CAN Controller Driver"""
    
    def __init__(self, spi_bus=2, spi_device=0, cs_pin=None, speed=500000, crystal=8000000):
        """
        Initialize MCP2515
        
        Args:
            spi_bus: SPI bus number (default 2 for SPI2)
            spi_device: SPI device number (default 0)
            cs_pin: GPIO pin for chip select (optional, SPI handles it)
            speed: SPI communication speed in Hz
            crystal: MCP2515 crystal frequency in Hz (default 8MHz)
        """
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.crystal = crystal
        self.cs_pin = None
        
        # Initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = speed
        self.spi.mode = 0  # SPI Mode 0 (CPOL=0, CPHA=0)
        
        print(f"MCP2515 initialized on SPI{spi_bus}.{spi_device}")
        print(f"SPI Speed: {speed} Hz, Crystal: {crystal/1000000} MHz")
    
    def reset(self):
        """Reset MCP2515"""
        self.spi.xfer2([MCP2515_RESET])
        time.sleep(0.01)  # Wait for reset
        print("MCP2515 reset complete")
    
    def read_register(self, address):
        """Read a single register"""
        result = self.spi.xfer2([MCP2515_READ, address, 0x00])
        return result[2]
    
    def write_register(self, address, value):
        """Write a single register"""
        self.spi.xfer2([MCP2515_WRITE, address, value])
    
    def modify_register(self, address, mask, value):
        """Modify specific bits in a register"""
        self.spi.xfer2([MCP2515_BIT_MODIFY, address, mask, value])
    
    def set_mode(self, mode):
        """Set MCP2515 operating mode"""
        self.modify_register(CANCTRL, 0xE0, mode)
        time.sleep(0.01)
        
        # Verify mode change
        current_mode = self.read_register(CANSTAT) & 0xE0
        if current_mode == mode:
            mode_name = {
                MODE_NORMAL: "NORMAL",
                MODE_SLEEP: "SLEEP",
                MODE_LOOPBACK: "LOOPBACK",
                MODE_LISTENONLY: "LISTEN ONLY",
                MODE_CONFIG: "CONFIG"
            }.get(mode, "UNKNOWN")
            print(f"Mode set to: {mode_name}")
            return True
        else:
            print(f"Failed to set mode! Current: 0x{current_mode:02X}")
            return False
    
    def set_bitrate(self, bitrate):
        """Set CAN bus bitrate"""
        if bitrate not in CAN_SPEED:
            print(f"Unsupported bitrate: {bitrate}. Using 125000 bps")
            bitrate = 125000
        
        config = CAN_SPEED[bitrate]
        
        # Must be in config mode to change bitrate
        self.set_mode(MODE_CONFIG)
        
        self.write_register(CNF1, config[0])
        self.write_register(CNF2, config[1])
        self.write_register(CNF3, config[2])
        
        print(f"Bitrate set to: {bitrate} bps")
    
    def init(self, bitrate=125000, mode=MODE_NORMAL):
        """Initialize MCP2515 with specified bitrate and mode"""
        self.reset()
        self.set_bitrate(bitrate)
        
        # Enable all interrupts (optional)
        self.write_register(CANINTE, 0xFF)
        
        # Configure RX buffers to receive all messages
        self.write_register(RXB0CTRL, 0x60)  # Receive all messages
        self.write_register(RXB1CTRL, 0x60)
        
        # Set to requested mode
        return self.set_mode(mode)
    
    def send_message(self, msg):
        """
        Send a CAN message
        
        Args:
            msg: CANMessage object
        """
        # Wait for TX buffer to be free
        ctrl = self.read_register(TXB0CTRL)
        if ctrl & 0x08:  # TXREQ bit set
            print("TX buffer busy!")
            return False
        
        # Write message ID
        sidh = (msg.can_id >> 3) & 0xFF
        sidl = (msg.can_id << 5) & 0xE0
        
        if msg.extended:
            sidl |= 0x08  # Set EXIDE bit
        
        self.write_register(TXB0SIDH, sidh)
        self.write_register(TXB0SIDL, sidl)
        
        # Write DLC
        self.write_register(TXB0DLC, msg.dlc & 0x0F)
        
        # Write data bytes
        for i in range(msg.dlc):
            self.write_register(TXB0DATA + i, msg.data[i])
        
        # Request to send
        self.spi.xfer2([MCP2515_RTS | 0x01])
        
        return True
    
    def read_message(self):
        """
        Read a CAN message from RX buffer
        
        Returns:
            CANMessage object or None
        """
        # Check if message available in RX buffer 0
        status = self.spi.xfer2([MCP2515_READ_RX_STATUS, 0x00])
        
        if not (status[1] & 0x40):  # No message in RXB0
            return None
        
        # Read message from RXB0
        sidh = self.read_register(RXB0SIDH)
        sidl = self.read_register(RXB0SIDL)
        dlc = self.read_register(RXB0DLC) & 0x0F
        
        # Extract ID
        can_id = (sidh << 3) | (sidl >> 5)
        extended = bool(sidl & 0x08)
        
        # Read data
        data = []
        for i in range(dlc):
            data.append(self.read_register(RXB0DATA + i))
        
        # Clear interrupt flag
        self.modify_register(CANINTF, 0x01, 0x00)
        
        return CANMessage(can_id, data, dlc, extended)
    
    def available(self):
        """Check if messages are available"""
        status = self.spi.xfer2([MCP2515_READ_RX_STATUS, 0x00])
        return bool(status[1] & 0x40)  # Message in RXB0
    
    def close(self):
        """Close SPI connection"""
        self.spi.close()
        print("MCP2515 closed")


if __name__ == "__main__":
    print("MCP2515 Driver Test")
    print("This is the driver library - use can_read.py or can_write.py for testing")