import os
import json
import secrets
import qrcode

PAIRING_FILE = "/home/radxa/efio/pairing.json"


def load_pairing_data():
    if not os.path.exists(PAIRING_FILE):
        return {}
    with open(PAIRING_FILE, "r") as f:
        return json.load(f)


def save_pairing_data(data):
    with open(PAIRING_FILE, "w") as f:
        json.dump(data, f)


def generate_token():
    """Generate secure 32-char token"""
    return secrets.token_hex(16)


def create_pairing(sn):
    """Create token + QR for serial number"""
    data = load_pairing_data()

    token = generate_token()
    data[sn] = token

    save_pairing_data(data)

    # Generate the URL shown on QR
    url = f"http://{sn}/pair?sn={sn}&tok={token}"

    img = qrcode.make(url)
    img.save("/tmp/oled.png")

    return token, "/tmp/oled.png", url


def validate_pairing(sn, tok):
    """Validate SN + token combo"""
    data = load_pairing_data()

    if sn not in data:
        return False

    return data[sn] == tok
