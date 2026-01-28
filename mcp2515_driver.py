#!/usr/bin/env python3
"""
MCP2515 CAN Controller Driver - CORRECTED VERSION
Uses EXACT timing values from Arduino mcp2515.h library
Compatible with 8MHz, 16MHz, and 20MHz crystals

Author: Fixed version matching Arduino library
Date: 2026-01-27
"""

import spidev
import time

# MCP2515 SPI Commands
MCP2515_RESET = 0xC0
MCP2515_READ = 0x03
MCP2515_WRITE = 0x02
MCP2515_RTS = 0x80
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
EFLG = 0x2D

# TX/RX Buffers
TXB0CTRL = 0x30
TXB0SIDH = 0x31
TXB0SIDL = 0x32
TXB0EID8 = 0x33
TXB0EID0 = 0x34
TXB0DLC = 0x35
TXB0DATA = 0x36

RXB0CTRL = 0x60
RXB0SIDH = 0x61
RXB0SIDL = 0x62
RXB0EID8 = 0x63
RXB0EID0 = 0x64
RXB0DLC = 0x65
RXB0DATA = 0x66

RXB1CTRL = 0x70
RXB1SIDH = 0x71
RXB1SIDL = 0x72
RXB1EID8 = 0x73
RXB1EID0 = 0x74
RXB1DLC = 0x75
RXB1DATA = 0x76

# Operating Modes
MODE_NORMAL = 0x00
MODE_SLEEP = 0x20
MODE_LOOPBACK = 0x40
MODE_LISTENONLY = 0x60
MODE_CONFIG = 0x80

# ⭐⭐⭐ CORRECTED Bitrate Configurations - EXACT VALUES from Arduino mcp2515.h ⭐⭐⭐

# 8 MHz Crystal Configurations (FROM mcp2515.h)
CAN_SPEED_8MHZ = {
    1000000: [0x00, 0x80, 0x80],  # 1000 kbps (risky with 8MHz, but defined)
    500000:  [0x00, 0x90, 0x82],  # 500 kbps
    250000:  [0x00, 0xB1, 0x85],  # 250 kbps
    200000:  [0x00, 0xB4, 0x86],  # 200 kbps
    125000:  [0x01, 0xB1, 0x85],  # 125 kbps ⭐ MOST COMMON
    100000:  [0x01, 0xB4, 0x86],  # 100 kbps
    80000:   [0x01, 0xBF, 0x87],  # 80 kbps
    50000:   [0x03, 0xB4, 0x86],  # 50 kbps
    40000:   [0x03, 0xBF, 0x87],  # 40 kbps
    33333:   [0x47, 0xE2, 0x85],  # 33.3 kbps
    31250:   [0x07, 0xA4, 0x84],  # 31.25 kbps
    20000:   [0x07, 0xBF, 0x87],  # 20 kbps
    10000:   [0x0F, 0xBF, 0x87],  # 10 kbps
    5000:    [0x1F, 0xBF, 0x87],  # 5 kbps
}

# 16 MHz Crystal Configurations (FROM mcp2515.h)
CAN_SPEED_16MHZ = {
    1000000: [0x00, 0xD0, 0x82],  # 1000 kbps (1 Mbps)
    500000:  [0x00, 0xF0, 0x86],  # 500 kbps
    250000:  [0x41, 0xF1, 0x85],  # 250 kbps
    200000:  [0x01, 0xFA, 0x87],  # 200 kbps
    125000:  [0x03, 0xF0, 0x86],  # 125 kbps
    100000:  [0x03, 0xFA, 0x87],  # 100 kbps
    95000:   [0x03, 0xAD, 0x07],  # 95 kbps
    83333:   [0x03, 0xBE, 0x07],  # 83.3 kbps
    80000:   [0x03, 0xFF, 0x87],  # 80 kbps
    50000:   [0x07, 0xFA, 0x87],  # 50 kbps
    40000:   [0x07, 0xFF, 0x87],  # 40 kbps
    33333:   [0x4E, 0xF1, 0x85],  # 33.3 kbps
    20000:   [0x0F, 0xFF, 0x87],  # 20 kbps
    10000:   [0x1F, 0xFF, 0x87],  # 10 kbps
    5000:    [0x3F, 0xFF, 0x87],  # 5 kbps
}

# 20 MHz Crystal Configurations (FROM mcp2515.h)
CAN_SPEED_20MHZ = {
    1000000: [0x00, 0xD9, 0x82],  # 1000 kbps
    500000:  [0x00, 0xFA, 0x87],  # 500 kbps
    250000:  [0x41, 0xFB, 0x86],  # 250 kbps
    200000:  [0x01, 0xFF, 0x87],  # 200 kbps
    125000:  [0x03, 0xFA, 0x87],  # 125 kbps
    100000:  [0x04, 0xFA, 0x87],  # 100 kbps
    83333:   [0x04, 0xFE, 0x87],  # 83.3 kbps
    80000:   [0x04, 0xFF, 0x87],  # 80 kbps
    50000:   [0x09, 0xFA, 0x87],  # 50 kbps
    40000:   [0x09, 0xFF, 0x87],  # 40 kbps
    33333:   [0x0B, 0xFF, 0x87],  # 33.3 kbps
}


class CANMessage:
    """CAN Message Structure"""
    def __init__(self, can_id=0, data=None, dlc=0, extended=False, rtr=False):
        self.can_id = can_id
        self.data = data if data else [0] * 8
        self.dlc = dlc if dlc else len(self.data)
        self.extended = extended
        self.rtr = rtr  # Remote Transmission Request
    
    def __repr__(self):
        if self.rtr:
            return f"ID: 0x{self.can_id:03X}, RTR, DLC: {self.dlc}"
        data_str = ' '.join([f'0x{b:02X}' for b in self.data[:self.dlc]])
        ext_str = " (EXT)" if self.extended else ""
        return f"ID: 0x{self.can_id:03X}{ext_str}, DLC: {self.dlc}, Data: [{data_str}]"


class MCP2515:
    """
    MCP2515 CAN Controller Driver
    Uses exact timing values from Arduino mcp2515.h library
    """
    
    def __init__(self, spi_bus=2, spi_device=0, speed=1000000, crystal=8000000):
        """
        Initialize MCP2515
        
        Args:
            spi_bus: SPI bus (2 for SPI2 on Radxa CM4)
            spi_device: SPI device (0 for CS0)
            speed: SPI speed in Hz (1 MHz default, can go up to 10 MHz)
            crystal: MCP2515 crystal frequency (8000000, 16000000, or 20000000)
        """
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.crystal = crystal
        
        # Select speed configuration table based on crystal
        if crystal == 16000000:
            self.speed_table = CAN_SPEED_16MHZ
            self.crystal_name = "16 MHz"
        elif crystal == 20000000:
            self.speed_table = CAN_SPEED_20MHZ
            self.crystal_name = "20 MHz"
        else:
            self.speed_table = CAN_SPEED_8MHZ
            self.crystal_name = "8 MHz"
            if crystal != 8000000:
                print(f"⚠️  Unknown crystal {crystal/1000000} MHz, using 8 MHz config")
        
        # Initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = speed
        self.spi.mode = 0  # SPI Mode 0 (CPOL=0, CPHA=0)
        
        print(f"🔧 MCP2515 CAN Controller")
        print(f"   SPI: Bus {spi_bus}, Device {spi_device}, Speed {speed/1000000:.1f} MHz")
        print(f"   Crystal: {self.crystal_name}")
    
    def reset(self):
        """Reset MCP2515 to default state"""
        self.spi.xfer2([MCP2515_RESET])
        time.sleep(0.01)  # Wait for reset to complete
    
    def read_register(self, address):
        """Read single register"""
        result = self.spi.xfer2([MCP2515_READ, address, 0x00])
        return result[2]
    
    def read_registers(self, address, count):
        """Read multiple consecutive registers"""
        cmd = [MCP2515_READ, address] + [0x00] * count
        result = self.spi.xfer2(cmd)
        return result[2:]
    
    def write_register(self, address, value):
        """Write single register"""
        self.spi.xfer2([MCP2515_WRITE, address, value])
    
    def write_registers(self, address, values):
        """Write multiple consecutive registers"""
        cmd = [MCP2515_WRITE, address] + list(values)
        self.spi.xfer2(cmd)
    
    def modify_register(self, address, mask, value):
        """Modify specific bits in register"""
        self.spi.xfer2([MCP2515_BIT_MODIFY, address, mask, value])
    
    def set_mode(self, mode):
        """Set operating mode"""
        self.modify_register(CANCTRL, 0xE0, mode)
        time.sleep(0.01)
        
        # Verify mode change
        current_mode = self.read_register(CANSTAT) & 0xE0
        
        mode_names = {
            MODE_NORMAL: "NORMAL",
            MODE_SLEEP: "SLEEP",
            MODE_LOOPBACK: "LOOPBACK",
            MODE_LISTENONLY: "LISTEN-ONLY",
            MODE_CONFIG: "CONFIG"
        }
        
        if current_mode == mode:
            print(f"✅ Mode: {mode_names.get(mode, 'UNKNOWN')}")
            return True
        else:
            print(f"❌ Mode change FAILED! Expected 0x{mode:02X}, got 0x{current_mode:02X}")
            return False
    
    def set_bitrate(self, bitrate):
        """
        Set CAN bitrate using exact Arduino library values
        
        Args:
            bitrate: Baud rate in bps (e.g., 125000 for 125 kbps)
        """
        if bitrate not in self.speed_table:
            print(f"❌ Bitrate {bitrate} bps NOT supported with {self.crystal_name} crystal!")
            print(f"   Supported rates: {sorted(self.speed_table.keys())}")
            
            # Find closest supported rate
            closest = min(self.speed_table.keys(), key=lambda x: abs(x - bitrate))
            print(f"   📌 Using closest: {closest} bps")
            bitrate = closest
        
        config = self.speed_table[bitrate]
        
        # Enter config mode
        if not self.set_mode(MODE_CONFIG):
            print("❌ Failed to enter CONFIG mode!")
            return False
        
        # Write CNF registers
        self.write_register(CNF1, config[0])
        self.write_register(CNF2, config[1])
        self.write_register(CNF3, config[2])
        
        # Verify configuration
        cnf1 = self.read_register(CNF1)
        cnf2 = self.read_register(CNF2)
        cnf3 = self.read_register(CNF3)
        
        if cnf1 == config[0] and cnf2 == config[1] and cnf3 == config[2]:
            print(f"✅ Bitrate: {bitrate} bps")
            print(f"   CNF Registers: [0x{cnf1:02X}, 0x{cnf2:02X}, 0x{cnf3:02X}]")
            return True
        else:
            print(f"⚠️  CNF register verification FAILED!")
            print(f"   Expected: [0x{config[0]:02X}, 0x{config[1]:02X}, 0x{config[2]:02X}]")
            print(f"   Got:      [0x{cnf1:02X}, 0x{cnf2:02X}, 0x{cnf3:02X}]")
            return False
    
    def init(self, bitrate=125000, mode=MODE_NORMAL, loopback=False):
        """
        Initialize MCP2515 with specified settings
        
        Args:
            bitrate: CAN bus speed in bps (default: 125000)
            mode: Operating mode (default: MODE_NORMAL)
            loopback: Enable loopback mode for testing (default: False)
        """
        print(f"\n{'='*60}")
        print(f"Initializing MCP2515 CAN Controller")
        print(f"{'='*60}")
        
        # Reset controller
        self.reset()
        print("✅ Reset complete")
        
        # Set bitrate
        if not self.set_bitrate(bitrate):
            return False
        
        # Configure RX buffers to receive all messages (no filtering)
        # RXB0CTRL: Turn off mask/filters, enable rollover to RXB1
        self.write_register(RXB0CTRL, 0x60)  # Receive all valid messages
        
        # RXB1CTRL: Turn off mask/filters
        self.write_register(RXB1CTRL, 0x60)  # Receive all valid messages
        
        # Enable interrupts
        self.write_register(CANINTE, 0x03)  # Enable RX0IF and RX1IF interrupts
        
        # Clear any pending interrupts
        self.write_register(CANINTF, 0x00)
        
        # Enter requested mode
        if loopback:
            mode = MODE_LOOPBACK
            print("🔄 Loopback mode enabled (for testing)")
        
        success = self.set_mode(mode)
        
        if success:
            print(f"{'='*60}")
            print(f"✅ MCP2515 initialization complete!")
            print(f"{'='*60}\n")
        else:
            print(f"{'='*60}")
            print(f"❌ MCP2515 initialization FAILED!")
            print(f"{'='*60}\n")
        
        return success
    
    def send_message(self, msg, txbuf=0):
        """
        Send CAN message
        
        Args:
            msg: CANMessage object to send
            txbuf: TX buffer to use (0, 1, or 2)
        """
        # TX buffer addresses
        tx_buffers = [
            (TXB0CTRL, TXB0SIDH, TXB0DLC, TXB0DATA),
            (0x40, 0x41, 0x45, 0x46),  # TXB1
            (0x50, 0x51, 0x55, 0x56),  # TXB2
        ]
        
        if txbuf >= len(tx_buffers):
            txbuf = 0
        
        ctrl_reg, sidh_reg, dlc_reg, data_reg = tx_buffers[txbuf]
        
        # Check if TX buffer is free
        ctrl = self.read_register(ctrl_reg)
        if ctrl & 0x08:  # TXREQ bit set = buffer busy
            return False
        
        # Prepare ID bytes
        if msg.extended:
            # Extended ID (29-bit)
            sidh = (msg.can_id >> 21) & 0xFF
            sidl = ((msg.can_id >> 13) & 0xE0) | 0x08 | ((msg.can_id >> 16) & 0x03)
            eid8 = (msg.can_id >> 8) & 0xFF
            eid0 = msg.can_id & 0xFF
            
            self.write_register(sidh_reg, sidh)
            self.write_register(sidh_reg + 1, sidl)
            self.write_register(sidh_reg + 2, eid8)
            self.write_register(sidh_reg + 3, eid0)
        else:
            # Standard ID (11-bit)
            sidh = (msg.can_id >> 3) & 0xFF
            sidl = (msg.can_id << 5) & 0xE0
            
            self.write_register(sidh_reg, sidh)
            self.write_register(sidh_reg + 1, sidl)
        
        # Write DLC
        dlc_value = msg.dlc & 0x0F
        if msg.rtr:
            dlc_value |= 0x40  # Set RTR bit
        self.write_register(dlc_reg, dlc_value)
        
        # Write data bytes
        if not msg.rtr:
            for i in range(msg.dlc):
                self.write_register(data_reg + i, msg.data[i])
        
        # Request to send
        self.spi.xfer2([MCP2515_RTS | (1 << txbuf)])
        
        return True
    
    def read_message(self, rxbuf=0):
        """
        Read CAN message from RX buffer
        
        Args:
            rxbuf: RX buffer to read (0 or 1)
        """
        # RX buffer addresses
        if rxbuf == 0:
            sidh_reg = RXB0SIDH
            dlc_reg = RXB0DLC
            data_reg = RXB0DATA
            intf_bit = 0x01  # CANINTF RX0IF
        else:
            sidh_reg = RXB1SIDH
            dlc_reg = RXB1DLC
            data_reg = RXB1DATA
            intf_bit = 0x02  # CANINTF RX1IF
        
        # Read ID and control bytes
        sidh = self.read_register(sidh_reg)
        sidl = self.read_register(sidh_reg + 1)
        eid8 = self.read_register(sidh_reg + 2)
        eid0 = self.read_register(sidh_reg + 3)
        dlc_byte = self.read_register(dlc_reg)
        
        # Extract message properties
        extended = bool(sidl & 0x08)
        rtr = bool(dlc_byte & 0x40)
        dlc = dlc_byte & 0x0F
        
        # Extract CAN ID
        if extended:
            # Extended ID (29-bit)
            can_id = ((sidh << 21) | 
                     ((sidl & 0xE0) << 13) | 
                     ((sidl & 0x03) << 16) |
                     (eid8 << 8) | 
                     eid0)
        else:
            # Standard ID (11-bit)
            can_id = (sidh << 3) | (sidl >> 5)
        
        # Read data bytes
        data = []
        if not rtr:
            for i in range(min(dlc, 8)):
                data.append(self.read_register(data_reg + i))
        
        # Clear interrupt flag
        self.modify_register(CANINTF, intf_bit, 0x00)
        
        return CANMessage(can_id, data, dlc, extended, rtr)
    
    def available(self):
        """
        Check if message is available in any RX buffer
        
        Returns:
            0: No message
            1: Message in RXB0
            2: Message in RXB1
        """
        intf = self.read_register(CANINTF)
        
        if intf & 0x01:  # RX0IF
            return 1
        elif intf & 0x02:  # RX1IF
            return 2
        else:
            return 0
    
    def get_error_flags(self):
        """Get error flags from EFLG register"""
        return self.read_register(EFLG)
    
    def clear_rx_overflow(self):
        """Clear RX buffer overflow flags"""
        self.modify_register(EFLG, 0xC0, 0x00)  # Clear RX1OVR and RX0OVR
    
    def get_status(self):
        """Get quick status (TX/RX buffer status)"""
        result = self.spi.xfer2([0xA0, 0x00])  # READ STATUS instruction
        return result[1]
    
    def close(self):
        """Close SPI connection"""
        self.spi.close()
        print("🔌 SPI connection closed")


if __name__ == "__main__":
    print("=" * 60)
    print("MCP2515 CAN Driver - Corrected Version")
    print("Matches Arduino mcp2515.h library exactly")
    print("=" * 60)
    print("\nUsage:")
    print("  from mcp2515_driver import MCP2515, CANMessage")
    print("")
    print("Example:")
    print("  mcp = MCP2515(crystal=8000000)")
    print("  mcp.init(bitrate=125000)")
    print("")
    print("Supported bitrates (8 MHz):")
    for rate in sorted(CAN_SPEED_8MHZ.keys()):
        print(f"  - {rate:7d} bps")
    print("\n" + "=" * 60)