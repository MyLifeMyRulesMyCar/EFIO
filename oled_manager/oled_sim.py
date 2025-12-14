from PIL import Image, ImageDraw, ImageFont
import time
import os


OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_PATH = "/tmp/oled.png"

class OledSimulator:
    def __init__(self):
        self.width = OLED_WIDTH
        self.height = OLED_HEIGHT
        self.clear()

    def clear(self):
        self.img = Image.new("1", (self.width, self.height), 0)
        self.draw = ImageDraw.Draw(self.img)

    def save(self):
        self.img.save(OLED_PATH)

    def text(self, message, x=0, y=0, size=12):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            font = ImageFont.load_default()
        self.draw.text((x, y), message, 1, font=font)
        self.save()

    def image(self, pil_img):
        """Draw another PIL image onto screen"""
        self.clear()
        self.img.paste(pil_img)
        self.save()

    def splash(self):
        self.clear()
        self.text("EFIO Booting...", 0, 20, 14)
        self.save()
