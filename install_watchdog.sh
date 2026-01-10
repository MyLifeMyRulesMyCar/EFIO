#!/bin/bash
# install_watchdog.sh
# Install and configure watchdog timer for EFIO system

set -e

echo "================================================"
echo "EFIO Watchdog Timer Installation"
echo "================================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (sudo ./install_watchdog.sh)"
    exit 1
fi

EFIO_DIR="/home/radxa/efio"
SERVICE_FILE="/etc/systemd/system/efio-api.service"

# Determine python binary to use for service (prefer project venv if present)
PYTHON_BIN="/usr/bin/python3"
if [ -x "${EFIO_DIR}/venv/bin/python3" ]; then
    PYTHON_BIN="${EFIO_DIR}/venv/bin/python3"
    echo "✅ Using virtualenv Python for service: ${PYTHON_BIN}"
else
    echo "⚠️  Using system Python: ${PYTHON_BIN}"
fi

echo ""
echo "📦 Step 1: Installing Python dependencies"
echo "-------------------------------------------"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Detected virtualenv: $VIRTUAL_ENV — using pip to install Python package"
    pip3 install systemd-python
else
    echo "Not running in a virtualenv — installing system package 'python3-systemd' via apt"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3-systemd
fi

echo ""
echo "📝 Step 2: Creating watchdog module"
echo "-------------------------------------------"
# The watchdog.py file should already exist in efio_daemon/
if [ ! -f "$EFIO_DIR/efio_daemon/watchdog.py" ]; then
    echo "❌ watchdog.py not found in $EFIO_DIR/efio_daemon/"
    echo "   Please create the file first"
    exit 1
fi
echo "✅ Watchdog module found"

echo ""
echo "📋 Step 3: Installing systemd service"
echo "-------------------------------------------"

# Backup existing service if it exists
if [ -f "$SERVICE_FILE" ]; then
    echo "⚠️  Backing up existing service file"
    cp "$SERVICE_FILE" "$SERVICE_FILE.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Create service file with proper variable expansion
cat > "$SERVICE_FILE" << EOFSERVICE
[Unit]
Description=EFIO Edge Controller API Service
Documentation=https://github.com/edgeforce/efio
After=network.target mosquitto.service
Wants=network.target

[Service]
Type=notify
User=radxa
Group=radxa
WorkingDirectory=/home/radxa/efio

# Main service command
ExecStart=${PYTHON_BIN} /home/radxa/efio/api/app.py

# Restart configuration
Restart=always
RestartSec=10

# Restart limits (prevent rapid restart loops)
StartLimitInterval=200
StartLimitBurst=5

# Watchdog configuration
WatchdogSec=90
TimeoutStartSec=60
TimeoutStopSec=30

# Resource limits
MemoryMax=2G
CPUQuota=75%

# Process management
KillMode=mixed
KillSignal=SIGTERM

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=efio-api

# Environment
Environment="PYTHONUNBUFFERED=1"
Environment="FLASK_ENV=production"

[Install]
WantedBy=multi-user.target
EOFSERVICE

echo "✅ Service file created: $SERVICE_FILE"

# Verify the ExecStart line
echo ""
echo "🔍 Verifying service configuration:"
echo "-------------------------------------------"
EXEC_LINE=$(grep "^ExecStart=" "$SERVICE_FILE")
echo "   $EXEC_LINE"

if [[ "$EXEC_LINE" == *"/venv/bin/python3"* ]]; then
    echo "   ✅ Using virtualenv Python"
elif [[ "$EXEC_LINE" == *"/usr/bin/python3"* ]]; then
    echo "   ⚠️  Using system Python (make sure dependencies are installed)"
fi

echo ""
echo "🔄 Step 4: Reloading systemd"
echo "-------------------------------------------"
systemctl daemon-reload
echo "✅ Systemd reloaded"

echo ""
echo "🎯 Step 5: Enabling service"
echo "-------------------------------------------"
systemctl enable efio-api.service
echo "✅ Service enabled (will start on boot)"

echo ""
echo "================================================"
echo "✅ Installation Complete!"
echo "================================================"
echo ""
echo "Service Configuration:"
echo "  Python: ${PYTHON_BIN}"
echo "  Working Dir: /home/radxa/efio"
echo "  Watchdog: 90 seconds"
echo ""
echo "Next steps:"
echo ""
echo "1. Verify the configuration:"
echo "   cat /etc/systemd/system/efio-api.service | grep ExecStart"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start efio-api"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status efio-api"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u efio-api -f"
echo ""
echo "5. Test watchdog:"
echo "   curl http://localhost:5000/api/health/watchdog"
echo ""
echo "================================================"

# Optionally start the service now
read -p "Start the service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting service..."
    systemctl start efio-api
    sleep 3
    echo ""
    echo "📊 Service status:"
    systemctl status efio-api --no-pager
    echo ""
    
    if systemctl is-active --quiet efio-api; then
        echo "✅ Service started successfully!"
        echo ""
        echo "View real-time logs:"
        echo "   sudo journalctl -u efio-api -f"
    else
        echo "❌ Service failed to start. Check logs:"
        echo "   sudo journalctl -u efio-api -n 50"
    fi
fi

echo ""
echo "Installation script complete."