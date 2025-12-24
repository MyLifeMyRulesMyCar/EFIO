#!/bin/bash
# EFIO Edge Controller - Automated Setup Script
# Run this script after cloning the repository

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/EFIO"
CONFIG_DIR="$HOME/efio"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="efio-api"
CURRENT_USER=$(whoami)

# ============================================
# Helper Functions
# ============================================

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_root() {
    if [ "$EUID" -eq 0 ]; then 
        print_error "Please do not run this script as root"
        print_info "Run as normal user: ./setup.sh"
        exit 1
    fi
}

check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        print_error "Cannot determine OS"
        exit 1
    fi
    
    if [ "$OS" != "ubuntu" ] && [ "$OS" != "debian" ]; then
        print_warning "This script is designed for Ubuntu/Debian"
        print_info "Detected: $OS $VER"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# ============================================
# Installation Steps
# ============================================

step1_system_packages() {
    print_header "Step 1: Installing System Packages"
    
    print_info "Updating package lists..."
    sudo apt-get update
    
    print_info "Installing required packages..."
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
        build-essential \
        || { print_error "Failed to install system packages"; exit 1; }
    
    print_success "System packages installed"
}

step2_nodejs() {
    print_header "Step 2: Installing Node.js 18+"
    
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VERSION" -ge 18 ]; then
            print_success "Node.js $NODE_VERSION already installed"
            return
        fi
    fi
    
    print_info "Installing Node.js 18..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs || { print_error "Failed to install Node.js"; exit 1; }
    
    print_success "Node.js $(node --version) installed"
    print_success "npm $(npm --version) installed"
}

step3_user_groups() {
    print_header "Step 3: Configuring User Permissions"
    
    print_info "Adding user to required groups..."
    sudo usermod -a -G gpio,i2c,dialout $CURRENT_USER
    
    print_success "User added to groups: gpio, i2c, dialout"
    print_warning "You may need to logout/login for group changes to take effect"
}

step4_python_venv() {
    print_header "Step 4: Setting Up Python Environment"
    
    cd "$INSTALL_DIR"
    
    print_info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    print_info "Upgrading pip..."
    pip install --upgrade pip
    
    print_info "Installing Python dependencies..."
    pip install -r requirements.txt || { print_error "Failed to install Python packages"; exit 1; }
    
    print_success "Python environment configured"
}

step5_config_dirs() {
    print_header "Step 5: Creating Configuration Directories"
    
    print_info "Creating config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
    
    # Create default configuration files if they don't exist
    if [ ! -f "$CONFIG_DIR/users.json" ]; then
        print_info "Creating default users file..."
        cat > "$CONFIG_DIR/users.json" << 'EOF'
{
  "admin": {
    "username": "admin",
    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWpqJ4jfPYO",
    "role": "admin",
    "email": "admin@edgeforce.local",
    "full_name": "Administrator"
  },
  "operator": {
    "username": "operator",
    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyWpqJ4jfPYO",
    "role": "operator",
    "email": "operator@edgeforce.local",
    "full_name": "Operator User"
  }
}
EOF
        print_success "Default users created (admin/admin123, operator/operator123)"
    fi
    
    print_success "Configuration directories ready"
}

step6_mqtt() {
    print_header "Step 6: Configuring MQTT Broker"
    
    print_info "Starting Mosquitto MQTT broker..."
    sudo systemctl start mosquitto
    sudo systemctl enable mosquitto
    
    print_info "Testing MQTT connection..."
    timeout 2 mosquitto_sub -h localhost -t "test/#" -C 1 &
    sleep 1
    mosquitto_pub -h localhost -t "test/efio" -m "Hello EFIO"
    
    print_success "MQTT broker configured"
}

step7_frontend_build() {
    print_header "Step 7: Building React Frontend"
    
    cd "$INSTALL_DIR/efio-web"
    
    print_info "Installing Node dependencies..."
    npm install --legacy-peer-deps || { print_error "Failed to install npm packages"; exit 1; }
    
    print_info "Building production frontend..."
    npm run build || { print_error "Frontend build failed"; exit 1; }
    
    print_success "Frontend built successfully"
}

step8_systemd_service() {
    print_header "Step 8: Creating Systemd Service"
    
    print_info "Creating service file..."
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=EFIO Edge Controller API
After=network.target mosquitto.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
Environment="PYTHONUNBUFFERED=1"
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/api/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    print_info "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    
    print_info "Enabling service to start on boot..."
    sudo systemctl enable ${SERVICE_NAME}
    
    print_success "Systemd service created: ${SERVICE_NAME}"
}

step9_hardware_config() {
    print_header "Step 9: Hardware Configuration"
    
    print_info "Checking for I2C interface..."
    if [ -e /dev/i2c-9 ]; then
        print_success "I2C interface detected: /dev/i2c-9"
    else
        print_warning "I2C interface not found. OLED display may not work."
        print_info "You may need to enable I2C in device tree or boot config"
    fi
    
    print_info "Checking for RS-485 ports..."
    if [ -e /dev/ttyS2 ]; then
        print_success "RS-485 port found: /dev/ttyS2"
    else
        print_warning "Primary RS-485 port (/dev/ttyS2) not found"
    fi
    
    if [ -e /dev/ttyS7 ]; then
        print_success "Secondary RS-485 port found: /dev/ttyS7"
    else
        print_info "Secondary RS-485 port (/dev/ttyS7) not found (optional)"
    fi
    
    # Configure persistent serial port permissions via udev
    print_info "Configuring persistent serial port permissions..."
    
    # Create udev rule for RS-485 ports
    sudo tee /etc/udev/rules.d/99-efio-serial.rules > /dev/null << 'EOF'
# EFIO Edge Controller - Serial Port Permissions
# This ensures RS-485 ports are accessible after reboot

# Primary RS-485 port (ttyS2)
KERNEL=="ttyS2", MODE="0666", GROUP="dialout"

# Secondary RS-485 port (ttyS7) 
KERNEL=="ttyS7", MODE="0666", GROUP="dialout"

# Alternative: All ttyS* ports (use if port numbers vary)
# KERNEL=="ttyS*", MODE="0666", GROUP="dialout"
EOF
    
    # Reload udev rules
    print_info "Reloading udev rules..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    # Apply permissions immediately for current session
    if [ -e /dev/ttyS2 ]; then
        sudo chmod 666 /dev/ttyS2
        print_success "Permissions set for /dev/ttyS2 (mode 666)"
    fi
    
    if [ -e /dev/ttyS7 ]; then
        sudo chmod 666 /dev/ttyS7
        print_success "Permissions set for /dev/ttyS7 (mode 666)"
    fi
    
    print_success "Serial port permissions configured (persistent across reboots)"
    print_info "Udev rule created: /etc/udev/rules.d/99-efio-serial.rules"
}

step10_network_config() {
    print_header "Step 10: Network Configuration"
    
    print_info "Detecting network interfaces..."
    ip -br link show | grep -E "^(eth|en)" || print_warning "No ethernet interfaces detected"
    
    print_info "Current IP addresses:"
    ip -4 addr show | grep inet | grep -v 127.0.0.1
    
    # Get primary IP
    PRIMARY_IP=$(ip route get 1.1.1.1 | grep -oP 'src \K\S+')
    
    if [ -n "$PRIMARY_IP" ]; then
        print_success "Primary IP: $PRIMARY_IP"
        print_info "Web interface will be available at: http://$PRIMARY_IP:5000"
    else
        print_warning "Could not determine primary IP address"
    fi
}

step11_firewall() {
    print_header "Step 11: Firewall Configuration"
    
    if command -v ufw &> /dev/null; then
        print_info "UFW firewall detected"
        print_info "Opening port 5000 for web interface..."
        sudo ufw allow 5000/tcp || print_warning "Failed to configure firewall"
        print_success "Firewall configured"
    else
        print_info "UFW not installed, skipping firewall configuration"
    fi
}

# ============================================
# Main Installation Flow
# ============================================

main() {
    clear
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   EFIO Edge Controller - Automated Setup     ║${NC}"
    echo -e "${GREEN}║   Industrial IoT Controller Installation     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Pre-flight checks
    check_root
    check_os
    
    # Confirm installation
    echo -e "${YELLOW}This script will install EFIO and its dependencies.${NC}"
    echo -e "${YELLOW}Installation directory: $INSTALL_DIR${NC}"
    echo ""
    read -p "Continue with installation? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installation cancelled"
        exit 0
    fi
    
    # Run installation steps
    step1_system_packages
    step2_nodejs
    step3_user_groups
    step4_python_venv
    step5_config_dirs
    step6_mqtt
    step7_frontend_build
    step8_systemd_service
    step9_hardware_config
    step10_network_config
    step11_firewall
    
    # Installation complete
    print_header "Installation Complete!"
    
    echo ""
    print_success "EFIO Edge Controller has been installed successfully!"
    echo ""
    print_info "Next steps:"
    echo ""
    echo "  1. Reboot or re-login for group changes to take effect:"
    echo "     ${BLUE}sudo reboot${NC}"
    echo ""
    echo "  2. Start the EFIO service:"
    echo "     ${BLUE}sudo systemctl start ${SERVICE_NAME}${NC}"
    echo ""
    echo "  3. Check service status:"
    echo "     ${BLUE}sudo systemctl status ${SERVICE_NAME}${NC}"
    echo ""
    echo "  4. View logs:"
    echo "     ${BLUE}sudo journalctl -u ${SERVICE_NAME} -f${NC}"
    echo ""
    echo "  5. Access web interface:"
    if [ -n "$PRIMARY_IP" ]; then
        echo "     ${GREEN}http://$PRIMARY_IP:5000${NC}"
    else
        echo "     ${GREEN}http://YOUR_IP_ADDRESS:5000${NC}"
    fi
    echo ""
    echo "  Default credentials:"
    echo "     Username: ${GREEN}admin${NC}"
    echo "     Password: ${GREEN}admin123${NC}"
    echo ""
    print_warning "Remember to change default passwords after first login!"
    echo ""
    
    # Offer to start service now
    read -p "Would you like to start the service now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Starting EFIO service..."
        sudo systemctl start ${SERVICE_NAME}
        sleep 2
        sudo systemctl status ${SERVICE_NAME} --no-pager
    fi
}

# Run main installation
main