from periphery import I2C
import time

I2C_BUS = "/dev/i2c-9"
I2C_ADDR = 0x3C


class OledHardware:
    """Driver for SSD1306 OLED display via I2C"""
    
    def __init__(self):
        self.i2c = I2C(I2C_BUS)
        self.init_display()

    def send_cmd(self, cmd):
        """Send a command byte to the display"""
        self.i2c.transfer(I2C_ADDR, [I2C.Message([0x00, cmd])])

    def send_data(self, data):
        """Send a data byte to the display"""
        self.i2c.transfer(I2C_ADDR, [I2C.Message([0x40, data])])

    def init_display(self):
        """Initialize the SSD1306 display with standard settings"""
        init_cmds = [
            0xAE,  # Display OFF
            0x00,  # Set lower column address
            0x10,  # Set higher column address
            0x40,  # Set display start line
            0xB0,  # Set page address
            0x81,  # Set contrast control
            0xCF,  # Contrast value
            0xA1,  # Set segment remap (flip horizontal)
            0xA6,  # Set normal display (not inverted)
            0xA8,  # Set multiplex ratio
            0x3F,  # 64 MUX
            0xC8,  # Set COM output scan direction (flip vertical)
            0xD3,  # Set display offset
            0x00,  # No offset
            0xD5,  # Set display clock divide ratio
            0x80,  # Default ratio
            0xD9,  # Set pre-charge period
            0xF1,  # Pre-charge value
            0xDA,  # Set COM pins hardware configuration
            0x12,  # Alternative COM pin config
            0xDB,  # Set VCOMH deselect level
            0x40,  # VCOMH value
            0x8D,  # Charge pump setting
            0x14,  # Enable charge pump
            0xAF   # Display ON
        ]
        for cmd in init_cmds:
            self.send_cmd(cmd)
            time.sleep(0.001)  # Small delay between commands

    def clear(self):
        """Clear the entire display"""
        for page in range(8):
            self.send_cmd(0xB0 + page)  # Set page address
            self.send_cmd(0x00)         # Set lower column address
            self.send_cmd(0x10)         # Set higher column address
            for _ in range(128):
                self.send_data(0x00)

    def draw_buffer(self, buf):
        """Write a full 128x64 image buffer to the display
        
        Args:
            buf: List of 1024 bytes (128 columns × 8 pages)
        """
        if len(buf) != 1024:
            raise ValueError(f"Buffer must be 1024 bytes, got {len(buf)}")
        
        for page in range(8):
            self.send_cmd(0xB0 + page)  # Set page address
            self.send_cmd(0x00)         # Set lower column address
            self.send_cmd(0x10)         # Set higher column address
            start = page * 128
            for byte_val in buf[start:start+128]:
                self.send_data(byte_val)

    def close(self):
        """Close the I2C connection"""
        self.i2c.close()


def pil_to_ssd1306_buffer(img):
    """Convert PIL image to SSD1306 buffer format
    
    Args:
        img: PIL Image object (will be converted to 1-bit and resized to 128x64)
    
    Returns:
        List of 1024 bytes in SSD1306 page format
    """
    # Convert to 1-bit pixels and resize to 128x64
    img = img.convert("1").resize((128, 64))

    buffer = []
    # SSD1306 uses 8 pages of 128 bytes each
    for page in range(8):
        for x in range(128):
            byte = 0
            # Each byte represents 8 vertical pixels
            for bit in range(8):
                y = page * 8 + bit
                pixel = img.getpixel((x, y))
                # In mode "1", 0 is black, 255 is white
                # SSD1306: bit=1 means pixel ON (lit)
                if pixel == 0:  # BLACK pixel
                    byte |= (1 << bit)
            buffer.append(byte)

    return buffer