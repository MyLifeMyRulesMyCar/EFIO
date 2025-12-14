from efio_daemon.state import state
from oled_manager.oled_sim import OledSimulator
from oled_manager.oled_hw import OledHardware, pil_to_ssd1306_buffer
from oled_manager.qr_renderer import generate_qr
from PIL import Image, ImageDraw, ImageFont

# Instantiate simulation OLED always
oled_sim = OledSimulator()

# Instantiate hardware OLED only when needed
oled_hw = None


# --------------------------------------------------
# OLED selector
# --------------------------------------------------
def get_oled():
    """Return the appropriate OLED instance based on simulation state"""
    global oled_hw
    if state["simulation_oled"]:
        return oled_sim
    else:
        if oled_hw is None:
            oled_hw = OledHardware()
        return oled_hw


# --------------------------------------------------
# Generate boot screen (Pillow)
# --------------------------------------------------
def generate_boot_img():
    """Create boot screen image"""
    img = Image.new("1", (128, 64), 0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
    draw.text((10, 20), "EFIO Booting...", 1, font=font)
    return img


# --------------------------------------------------
# Generate status screen (Pillow)
# --------------------------------------------------
def generate_status_img(ip, status):
    """Create status screen image with IP and status"""
    img = Image.new("1", (128, 64), 0)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except:
        font = ImageFont.load_default()
    draw.text((0, 0), f"IP: {ip}", 1, font=font)
    draw.text((0, 20), f"Status: {status}", 1, font=font)
    return img


# --------------------------------------------------
# SHOW: Boot screen
# --------------------------------------------------
def show_boot():
    """Display boot screen on OLED"""
    oled = get_oled()

    if state["simulation_oled"]:
        oled.splash()   # simulated screen
    else:
        img = generate_boot_img()
        buffer = pil_to_ssd1306_buffer(img)
        oled.draw_buffer(buffer)


# --------------------------------------------------
# SHOW: Status screen
# --------------------------------------------------
def show_status(ip, status):
    """Display status screen with IP and status message"""
    oled = get_oled()

    if state["simulation_oled"]:
        oled.clear()
        oled.text(f"IP: {ip}", 0, 0, 12)
        oled.text(f"Status: {status}", 0, 20, 12)
    else:
        img = generate_status_img(ip, status)
        buffer = pil_to_ssd1306_buffer(img)
        oled.draw_buffer(buffer)


# --------------------------------------------------
# SHOW: QR code
# --------------------------------------------------
def show_qr(url):
    """Display QR code on OLED"""
    oled = get_oled()

    # Generate QR code and resize to fit display
    qr_img = generate_qr(url).resize((64, 64))

    if state["simulation_oled"]:
        oled.image(qr_img)  # draw on simulated OLED
    else:
        # Center the QR code on the display
        full_img = Image.new("1", (128, 64), 0)
        full_img.paste(qr_img, (32, 0))  # Center horizontally
        buffer = pil_to_ssd1306_buffer(full_img)
        oled.draw_buffer(buffer)


# --------------------------------------------------
# Cleanup function
# --------------------------------------------------
def cleanup_oled():
    """Close hardware OLED connection if open"""
    global oled_hw
    if oled_hw is not None:
        oled_hw.close()
        oled_hw = None