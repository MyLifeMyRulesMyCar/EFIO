# EFIO Edge Controller

![EFIO Logo](https://via.placeholder.com/800x200/667eea/ffffff?text=EdgeForce-1000+Industrial+IoT+Controller)

**Industrial IoT Edge Controller** with 4 Digital Inputs, 4 Digital Outputs, Dual RS-485, OLED Display, and Web-based Management Interface.

[![Platform](https://img.shields.io/badge/Platform-Rockchip%20RK3588-blue)](https://www.rock-chips.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-green)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.0+-61dafb)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📋 Table of Contents

- [Features](#-features)
- [Hardware Requirements](#-hardware-requirements)
- [System Architecture](#-system-architecture)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
  - [1. System Setup](#1-system-setup)
  - [2. Backend Setup](#2-backend-setup)
  - [3. Frontend Setup](#3-frontend-setup)
- [Development](#-development)
- [Production Deployment](#-production-deployment)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 Features

### Hardware I/O
- ✅ **4 Digital Inputs** (24VDC, 2.5kV isolation)
- ✅ **4 Digital Outputs** (5A relay, 4kV isolation)
- ✅ **Dual RS-485 Ports** (Modbus RTU master)
- ✅ **OLED Display** (128x64 SSD1306)

### Software Features
- ✅ **Real-time WebSocket** communication
- ✅ **MQTT Publishing** for I/O state
- ✅ **Modbus RTU Master** with auto-scan
- ✅ **User Authentication** (JWT with roles)
- ✅ **System Monitoring** (CPU, RAM, temp)
- ✅ **Web-based Configuration** (Network, I/O, Modbus)
- ✅ **RESTful API** for integration

### User Interface
- ✅ Modern **React + Material-UI** dashboard
- ✅ Real-time I/O control and monitoring
- ✅ Modbus device management
- ✅ System metrics visualization
- ✅ Mobile-responsive design

---

## 🖥️ Hardware Requirements

### Minimum Requirements
- **Board**: Rockchip RK3588 based SBC (e.g., Radxa Rock 5B, Orange Pi 5 Plus)
- **RAM**: 2GB (4GB+ recommended)
- **Storage**: 8GB eMMC/SD card (16GB+ recommended)
- **Network**: Ethernet port
- **OS**: Ubuntu 22.04 LTS (ARM64)

### Optional Hardware
- **CM4 Carrier Board** with dual ethernet
- **OLED Display**: I2C SSD1306 (128x64)
- **RS-485 Adapters**: USB or built-in UART

### I/O Specifications
| Component | Specification |
|-----------|--------------|
| Digital Inputs | 15-30VDC, 6kΩ impedance, <3ms response |
| Digital Outputs | 5A @ 250VAC/30VDC, relay-based |
| RS-485 | Modbus RTU, 9600-115200 baud |
| Isolation | 2500V (DI), 4000V (DO) |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser (Client)                  │
│              http://192.168.5.103:5000                   │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
                     ▼
┌─────────────────────────────────────────────────────────┐
│             Flask API Server (Port 5000)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   REST API   │  │  WebSocket   │  │   Auth/JWT   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────┬────────────────┬──────────────────┬───────────┘
         │                │                  │
         ▼                ▼                  ▼
┌────────────────┐ ┌─────────────┐ ┌──────────────────┐
│  EFIO Daemon   │ │ MQTT Broker │ │ Modbus Manager   │
│  (I/O Polling) │ │ (Mosquitto) │ │ (RS-485 Comms)   │
└────────┬───────┘ └─────────────┘ └────────┬─────────┘
         │                                    │
         ▼                                    ▼
┌────────────────────────────────────────────────────────┐
│                   Hardware Layer                        │
│  [GPIO] [I2C-OLED] [RS-485-1] [RS-485-2] [Ethernet]   │
└────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### One-Line Installation (Automated)
```bash
# Clone and run setup script
git clone https://github.com/MyLifeMyRulesMyCar/EFIO.git
cd EFIO
chmod +x setup.sh
./setup.sh
```

### Manual Installation (Step by Step)
See detailed instructions below.

---

## 📦 Installation

### 1. System Setup

#### Clone Repository
```bash
# Clone from GitHub
git clone https://github.com/MyLifeMyRulesMyCar/EFIO.git
cd EFIO
```

#### Install System Dependencies
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install required system packages
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-libgpiod \
    python3-venv \
    mosquitto \
    mosquitto-clients \
    i2c-tools \
    git \
    curl \
    build-essential

# Install Node.js 18+ (for React frontend)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify installations
python3 --version   # Should be 3.8+
node --version      # Should be 18+
npm --version       # Should be 8+
```

#### Configure Hardware Interfaces
```bash
# Enable I2C (for OLED)
sudo nano /boot/config.txt
# Add: dtparam=i2c_arm=on

# Add user to required groups
sudo usermod -a -G gpio,i2c,dialout $USER

# Reboot to apply changes
sudo reboot
```

---

### 2. Backend Setup

#### Create Python Virtual Environment (Recommended)
```bash
cd ~/EFIO

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

#### Install Python Dependencies
```bash
# Install from requirements.txt
pip install -r requirements.txt

# Verify critical packages
python3 -c "import flask; print('Flask:', flask.__version__)"
python3 -c "import flask_socketio; print('SocketIO: OK')"
python3 -c "import minimalmodbus; print('Modbus: OK')"
```

#### Configure MQTT Broker
```bash
# Start Mosquitto
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# Test MQTT
mosquitto_sub -h localhost -t "edgeforce/#" -v &
mosquitto_pub -h localhost -t "edgeforce/test" -m "Hello EFIO"
```

#### Configure Application
```bash
# Create configuration directory
mkdir -p /home/$USER/efio

# Set simulation mode (for development without hardware)
# Edit efio_daemon/state.py
nano efio_daemon/state.py
# Set: "simulation": True  (False for real hardware)
```

#### Test Backend Server
```bash
# Start Flask development server
python3 api/app.py

# Server should start on: http://0.0.0.0:5000
# Check output for:
# ✅ MQTT broker connected
# ✅ efio-daemon running
# ✅ WebSocket enabled
```

---

### 3. Frontend Setup

#### Install Node Dependencies
```bash
# Navigate to frontend directory
cd efio-web

# Install dependencies (this may take a few minutes)
npm install

# If you encounter errors, try:
npm install --legacy-peer-deps
```

#### Configure API Endpoint
```bash
# The React app is already configured to use http://192.168.5.103:5000
# If your device has a different IP, update these files:
# - src/hooks/useEFIOWebSocket.js (line 28)
# - src/contexts/AuthContext.js (line 46, 77)
# - All pages that make fetch() calls

# Or set an environment variable
echo "REACT_APP_API_URL=http://YOUR_DEVICE_IP:5000" > .env
```

#### Start Development Server
```bash
# Start React development server (port 3000)
npm start

# Browser should open automatically at:
# http://localhost:3000
```

#### Build for Production
```bash
# Create optimized production build
npm run build

# Output will be in: efio-web/build/
# These static files can be served by Flask
```

---

## 💻 Development

### Project Structure
```
EFIO/
├── api/                          # Backend API
│   ├── app.py                    # Main Flask application
│   ├── auth_routes.py            # Authentication endpoints
│   ├── config_routes.py          # Configuration endpoints
│   ├── modbus_routes.py          # Basic Modbus endpoints
│   └── modbus_device_routes.py   # Modbus device management
│
├── efio_daemon/                  # Hardware daemon
│   ├── daemon.py                 # Main polling loop
│   ├── io_manager.py             # GPIO control
│   ├── modbus_manager.py         # Modbus communication
│   └── state.py                  # Shared state
│
├── oled_manager/                 # OLED display
│   ├── oled_hw.py                # Hardware driver
│   ├── oled_sim.py               # Simulator
│   └── oled_service.py           # Display service
│
├── efio-web/                     # React frontend
│   ├── public/                   # Static assets
│   ├── src/
│   │   ├── components/           # Reusable components
│   │   ├── contexts/             # React contexts (Auth)
│   │   ├── hooks/                # Custom hooks (WebSocket)
│   │   ├── pages/                # Page components
│   │   ├── App.js                # Main app component
│   │   └── index.js              # Entry point
│   └── package.json              # Node dependencies
│
├── utils/                        # Utilities
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

### Development Workflow

#### Backend Development
```bash
# Activate virtual environment
source venv/bin/activate

# Start backend with auto-reload
export FLASK_ENV=development
python3 api/app.py

# Backend runs on: http://0.0.0.0:5000
```

#### Frontend Development
```bash
# In separate terminal
cd efio-web
npm start

# Frontend runs on: http://localhost:3000
# Proxies API calls to backend on port 5000
```

#### Testing APIs
```bash
# Test REST API
curl http://localhost:5000/api/status

# Test I/O endpoint
curl http://localhost:5000/api/io

# Test WebSocket (use browser console)
# Open: http://localhost:3000
# Check: Console should show "✅ WebSocket Connected"
```

### Default Credentials
```
Admin User:
  Username: admin
  Password: admin123

Operator User:
  Username: operator
  Password: operator123
```

**⚠️ Change default passwords before production deployment!**

---

## 🚀 Production Deployment

### Option 1: Serve React Build from Flask

#### Build Frontend
```bash
cd efio-web
npm run build
cd ..
```

#### Configure Flask to Serve Static Files
Already configured in `api/app.py`. Just start the server:
```bash
python3 api/app.py
```

Access complete application at: **http://YOUR_DEVICE_IP:5000**

### Option 2: Systemd Service (Auto-Start)

#### Create Service File
```bash
sudo nano /etc/systemd/system/efio-api.service
```

```ini
[Unit]
Description=EFIO Edge Controller API
After=network.target mosquitto.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/EFIO
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/YOUR_USERNAME/EFIO/venv/bin/python3 /home/YOUR_USERNAME/EFIO/api/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable efio-api

# Start service
sudo systemctl start efio-api

# Check status
sudo systemctl status efio-api

# View logs
sudo journalctl -u efio-api -f
```

### Option 3: Production Server (Gunicorn)

```bash
# Install Gunicorn with eventlet
pip install gunicorn eventlet

# Run with Gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 api.app:app

# For systemd service, update ExecStart:
# ExecStart=/path/to/venv/bin/gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 api.app:app
```

---

## ⚙️ Configuration

### Network Configuration
Access: **Settings → Network Config** (Admin only)

- WAN Interface (eth0): DHCP or Static IP
- LAN Interface (eth1): Static IP with optional DHCP server
- DNS Servers

### I/O Configuration
Access: **Settings → I/O Config**

- Channel naming (DI1-4, DO1-4)
- Debounce timing for inputs
- Output inversion logic

### Modbus Configuration
Access: **Modbus Manager**

- Add/edit/delete devices
- Configure port, slave ID, baudrate
- Scan for devices
- Test read/write operations

### User Management
Access: **Settings → Users** (Admin only)

- Create/delete users
- Change passwords
- Assign roles (admin/operator/viewer)

---

## 📚 API Documentation

### REST API Endpoints

#### System
```
GET  /api/status              - Health check
GET  /api/system              - System metrics (CPU, RAM, temp)
```

#### I/O Control
```
GET  /api/io                  - Get I/O state
POST /api/io/do/<channel>     - Set digital output
```

#### Authentication
```
POST /api/auth/login          - User login (returns JWT)
POST /api/auth/refresh        - Refresh access token
GET  /api/auth/me             - Get current user info
POST /api/auth/logout         - Logout
```

#### Modbus
```
GET  /api/modbus/devices      - List all devices
POST /api/modbus/devices      - Create new device
PUT  /api/modbus/devices/:id  - Update device
DEL  /api/modbus/devices/:id  - Delete device
POST /api/modbus/devices/:id/connect    - Connect to device
POST /api/modbus/devices/:id/read       - Read registers
POST /api/modbus/devices/:id/write      - Write register
POST /api/modbus/scan         - Auto-scan for devices
```

### WebSocket Events

#### Client → Server
```javascript
socket.emit('request_io');      // Request I/O state
socket.emit('request_system');  // Request system metrics
socket.emit('set_do', {         // Set digital output
  channel: 0,
  value: 1
});
```

#### Server → Client
```javascript
socket.on('io_update', (data) => {
  // data: { di: [0,0,0,0], do: [0,0,0,0] }
});

socket.on('system_update', (data) => {
  // data: { cpu: {}, memory: {}, temperature: {}, ... }
});
```

### MQTT Topics

#### Published by Device
```
edgeforce/io/di/1             - Digital Input 1 state (0/1)
edgeforce/io/di/2             - Digital Input 2 state
edgeforce/io/di/3             - Digital Input 3 state
edgeforce/io/di/4             - Digital Input 4 state

edgeforce/io/do/1             - Digital Output 1 state (0/1)
edgeforce/io/do/2             - Digital Output 2 state
edgeforce/io/do/3             - Digital Output 3 state
edgeforce/io/do/4             - Digital Output 4 state

edgeforce/system/cpu          - CPU usage (%)
edgeforce/system/ram          - RAM usage (%)
edgeforce/system/temp         - Temperature (°C)
edgeforce/system/uptime       - Uptime (seconds)
```

#### Subscribe for Control
```
edgeforce/io/do/1/set         - Set Digital Output 1 (payload: 0/1)
edgeforce/io/do/2/set         - Set Digital Output 2
edgeforce/io/do/3/set         - Set Digital Output 3
edgeforce/io/do/4/set         - Set Digital Output 4
```

---

## 🔧 Troubleshooting

### WebSocket Not Connecting

**Symptoms**: Dashboard shows "Disconnected"

**Solutions**:
```bash
# 1. Check Flask server is running
curl http://192.168.5.103:5000/api/status

# 2. Check WebSocket port is open
sudo netstat -tulpn | grep 5000

# 3. Check firewall
sudo ufw status
sudo ufw allow 5000/tcp

# 4. Check browser console for errors (F12)
# Look for connection errors or CORS issues
```

### GPIO/Hardware Not Working

**Symptoms**: I/O readings all zero, outputs not switching

**Solutions**:
```bash
# 1. Check user permissions
groups $USER  # Should include: gpio, i2c, dialout

# 2. Test GPIO access
python3 -c "import gpiod; print('GPIO: OK')"

# 3. Enable simulation mode for testing
# Edit efio_daemon/state.py
# Set: "simulation": True

# 4. Check pin configuration in efio_daemon/io_manager.py
# Verify GPIO chip and line numbers match your hardware
```

### MQTT Not Publishing

**Symptoms**: No messages in MQTT broker

**Solutions**:
```bash
# 1. Check Mosquitto is running
sudo systemctl status mosquitto

# 2. Test MQTT manually
mosquitto_sub -h localhost -t "edgeforce/#" -v

# 3. Check MQTT logs
sudo journalctl -u mosquitto -f

# 4. Verify Flask connected to MQTT
# Flask console should show: "✅ Daemon: Connected to MQTT broker"
```

### Modbus Communication Errors

**Symptoms**: "No communication with instrument"

**Solutions**:
```bash
# 1. Check RS-485 port exists
ls -l /dev/ttyS2
ls -l /dev/ttyS7

# 2. Check user permissions
sudo usermod -a -G dialout $USER
# Then logout and login

# 3. Test port with minicom
sudo apt-get install minicom
minicom -D /dev/ttyS2 -b 9600

# 4. Verify wiring and termination
# RS-485 requires 120Ω termination resistors at both ends

# 5. Check device settings match
# Slave ID, baudrate, parity, stop bits must match device
```

### Frontend Build Errors

**Symptoms**: `npm run build` fails

**Solutions**:
```bash
# 1. Clear node_modules and reinstall
cd efio-web
rm -rf node_modules package-lock.json
npm install

# 2. Use legacy peer deps if needed
npm install --legacy-peer-deps

# 3. Check Node.js version
node --version  # Should be 16+

# 4. Update npm
sudo npm install -g npm@latest
```

### High CPU/Memory Usage

**Symptoms**: System slow, high resource usage

**Solutions**:
```bash
# 1. Check EFIO process
python3 check_memory.py

# 2. Disable debug mode
# Edit api/app.py, line 54
DEBUG_MQTT = False

# 3. Reduce polling frequency
# Edit efio_daemon/daemon.py, line 102
time.sleep(0.5)  # Increase from 0.1

# 4. Check for memory leaks
ps aux | grep python3
```

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup
```bash
# Fork and clone repository
git clone https://github.com/YOUR_USERNAME/EFIO.git
cd EFIO

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and test
python3 api/app.py  # Test backend
cd efio-web && npm start  # Test frontend

# Commit changes
git add .
git commit -m "Add: your feature description"

# Push and create pull request
git push origin feature/your-feature-name
```

### Code Style
- **Python**: Follow PEP 8
- **JavaScript**: Use ESLint (React)
- **Commits**: Use conventional commits (Add:, Fix:, Update:, etc.)

### Testing
- Test on real hardware if possible
- Verify WebSocket connections
- Check MQTT publishing
- Test Modbus communication

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Flask** - Web framework
- **React** - Frontend framework
- **Material-UI** - UI components
- **Mosquitto** - MQTT broker
- **libgpiod** - Modern GPIO library

---

## 📞 Support

- **Documentation**: [Wiki](https://github.com/MyLifeMyRulesMyCar/EFIO/wiki)
- **Issues**: [GitHub Issues](https://github.com/MyLifeMyRulesMyCar/EFIO/issues)
- **Discussions**: [GitHub Discussions](https://github.com/MyLifeMyRulesMyCar/EFIO/discussions)

---

## 🗺️ Roadmap

- [x] Core I/O functionality
- [x] WebSocket real-time updates
- [x] MQTT integration
- [x] Modbus RTU support
- [x] Web-based configuration
- [ ] Data logging and history
- [ ] Email/SMS alerts
- [ ] OPC UA server
- [ ] Cloud connectivity (AWS IoT, Azure)
- [ ] Mobile app (React Native)

---

**Made with ❤️ for Industrial IoT**

*EdgeForce-1000 - Bringing Intelligence to the Edge*