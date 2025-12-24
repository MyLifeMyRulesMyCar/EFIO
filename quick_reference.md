# EFIO Edge Controller - Quick Reference Guide

Essential commands and file locations for daily operations.

---

## 📂 File Structure

```
/home/YOUR_USERNAME/
├── EFIO/                          # Main installation directory
│   ├── api/                       # Backend API
│   ├── efio_daemon/               # Hardware control daemon
│   ├── efio-web/                  # React frontend
│   │   └── build/                 # Production build (served by Flask)
│   ├── oled_manager/              # OLED display
│   ├── utils/                     # Utilities
│   ├── backup_restore.py          # Backup/restore utility
│   ├── setup.sh                   # Installation script
│   ├── fix_serial_permissions.sh  # Serial port fix script
│   ├── requirements.txt           # Python dependencies
│   └── venv/                      # Python virtual environment
│
└── efio/                          # Configuration directory
    ├── users.json                 # User accounts
    ├── network_config.json        # Network settings
    ├── io_config.json             # I/O configuration
    ├── alarm_config.json          # Alarm settings
    ├── modbus_devices.json        # Modbus device list
    └── modbus_log.json            # Modbus communication logs

/home/YOUR_USERNAME/efio_backups/  # Backup storage
└── efio_backup_YYYYMMDD_HHMMSS.tar.gz
```

---

## 🚀 Service Management

### Start/Stop Service

```bash
# Start EFIO service
sudo systemctl start efio-api

# Stop EFIO service
sudo systemctl stop efio-api

# Restart EFIO service
sudo systemctl restart efio-api

# Check service status
sudo systemctl status efio-api

# Enable auto-start on boot
sudo systemctl enable efio-api

# Disable auto-start
sudo systemctl disable efio-api
```

### View Logs

```bash
# View real-time logs
sudo journalctl -u efio-api -f

# View last 50 lines
sudo journalctl -u efio-api -n 50

# View logs since today
sudo journalctl -u efio-api --since today

# View logs for last hour
sudo journalctl -u efio-api --since "1 hour ago"

# View logs between timestamps
sudo journalctl -u efio-api --since "2024-12-23 10:00" --until "2024-12-23 12:00"

# Save logs to file
sudo journalctl -u efio-api -n 1000 > efio_logs.txt
```

---

## 💾 Backup & Restore

### Create Backup

```bash
# Navigate to EFIO directory
cd ~/EFIO

# Create backup (without logs)
./backup_restore.py backup

# Create backup with logs
./backup_restore.py backup --include-logs

# Create backup with custom name
./backup_restore.py backup -o ~/my_backup.tar.gz
```

### List Backups

```bash
# List all available backups
./backup_restore.py list

# Output example:
# efio_backup_20241223_120000.tar.gz     45.2 KB 2024-12-23 12:00:00
# efio_backup_20241222_120000.tar.gz     44.8 KB 2024-12-22 12:00:00
```

### Restore Backup

```bash
# Restore from specific backup (with confirmation)
./backup_restore.py restore efio_backup_20241223_120000.tar.gz

# Restore without confirmation prompt
./backup_restore.py restore efio_backup_20241223_120000.tar.gz -f

# After restore, restart service
sudo systemctl restart efio-api
```

### Check Configuration Status

```bash
# Show current configuration files
./backup_restore.py status

# Export configuration as JSON
./backup_restore.py export
./backup_restore.py export -o my_config.json
```

---

## 🔧 Serial Port Permissions

### Fix Serial Ports After Reboot

If you get "Permission denied" errors for `/dev/ttyS2` or `/dev/ttyS7`:

```bash
# Run the fix script (one-time setup)
cd ~/EFIO
sudo ./fix_serial_permissions.sh

# Verify permissions
ls -l /dev/ttyS2 /dev/ttyS7

# Expected output:
# crw-rw-rw- 1 root dialout 4, 66 Dec 23 10:00 /dev/ttyS2
#             ↑ 666 permissions
```

### Manual Fix (temporary, until next reboot)

```bash
# Set permissions (lost after reboot)
sudo chmod 666 /dev/ttyS2
sudo chmod 666 /dev/ttyS7

# Verify
ls -l /dev/ttyS2 /dev/ttyS7
```

### Check User Permissions

```bash
# Check if user is in dialout group
groups $USER

# Add user to dialout group (if missing)
sudo usermod -a -G dialout $USER

# Logout and login for changes to take effect
```

---

## 🌐 Network Access

### Find Device IP Address

```bash
# Show all network interfaces
ip -4 addr show

# Show only ethernet interfaces
ip -4 addr show | grep "inet " | grep -v 127.0.0.1

# Get primary IP
ip route get 1.1.1.1 | grep -oP 'src \K\S+'
```

### Test API Access

```bash
# Test from local machine
curl http://localhost:5000/api/status

# Test from network
curl http://192.168.5.103:5000/api/status

# Expected response:
# {"status":"ok","message":"EFIO API online","version":"1.0.0"}
```

### Check Port Listening

```bash
# Check if port 5000 is listening
sudo netstat -tulpn | grep 5000

# Alternative command
sudo ss -tulpn | grep 5000

# Expected output:
# tcp   0   0 0.0.0.0:5000   0.0.0.0:*   LISTEN   1234/python3
```

---

## 🔍 Hardware Diagnostics

### Check GPIO Access

```bash
# Test GPIO library
python3 -c "import gpiod; print('GPIO: OK')"

# List GPIO chips
gpiodetect

# Show GPIO chip info
gpioinfo
```

### Check I2C Devices

```bash
# List I2C buses
ls -l /dev/i2c-*

# Scan I2C bus 9 (for OLED)
sudo i2cdetect -y 9

# Expected: 0x3C (OLED address)
```

### Check RS-485 Ports

```bash
# List serial ports
ls -l /dev/ttyS*

# Test serial port access
python3 -c "import serial; s=serial.Serial('/dev/ttyS2', 9600); s.close(); print('OK')"
```

---

## 📊 System Monitoring

### Check System Resources

```bash
# CPU usage
top -bn1 | grep "Cpu(s)"

# Memory usage
free -h

# Disk usage
df -h

# Temperature
cat /sys/class/thermal/thermal_zone0/temp
# (divide by 1000 for °C)
```

### Check MQTT Broker

```bash
# Check Mosquitto status
sudo systemctl status mosquitto

# Subscribe to EFIO topics
mosquitto_sub -h localhost -t "edgeforce/#" -v

# Publish test message
mosquitto_pub -h localhost -t "edgeforce/test" -m "Hello"
```

---

## 🔐 User Management

### Web Interface Access

**URL:** `http://YOUR_IP:5000`

**Default Credentials:**
- **Admin:** `admin` / `admin123`
- **Operator:** `operator` / `operator123`

### Change Password (via web interface)

1. Login as admin
2. Go to **Settings → Users**
3. Click on user
4. Enter new password
5. Click **Save**

### Create New User (via API)

```bash
# Create new user
curl -X POST http://localhost:5000/api/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "username": "newuser",
    "password": "password123",
    "role": "operator",
    "full_name": "New User"
  }'
```

---

## 🐛 Troubleshooting

### Service Not Starting

```bash
# Check detailed error logs
sudo journalctl -u efio-api -n 100 --no-pager

# Test manually to see errors
cd ~/EFIO
source venv/bin/activate
python3 api/app.py
```

### WebSocket Not Connecting

```bash
# Check if service is running
sudo systemctl status efio-api

# Check firewall
sudo ufw status
sudo ufw allow 5000/tcp

# Test from browser console (F12)
# Should see: "✅ WebSocket Connected"
```

### Permission Errors

```bash
# Check user groups
groups $USER

# Add missing groups
sudo usermod -a -G gpio,i2c,dialout $USER

# Logout/login or reboot
sudo reboot
```

### High CPU/Memory

```bash
# Check process usage
top

# Check EFIO memory
ps aux | grep python3

# Reduce polling frequency (edit efio_daemon/daemon.py)
# Change: time.sleep(0.1) → time.sleep(0.5)

# Disable debug MQTT (edit api/app.py)
# Set: DEBUG_MQTT = False
```

---

## 🔄 Updates

### Update System Packages

```bash
# Update package list
sudo apt-get update

# Upgrade packages
sudo apt-get upgrade -y

# Reboot if kernel updated
sudo reboot
```

### Update Python Dependencies

```bash
cd ~/EFIO
source venv/bin/activate

# Update specific package
pip install --upgrade flask

# Update all packages
pip install --upgrade -r requirements.txt

# Restart service
sudo systemctl restart efio-api
```

### Update Frontend

```bash
cd ~/EFIO/efio-web

# Update dependencies
npm update

# Rebuild
npm run build

# Restart service
sudo systemctl restart efio-api
```

---

## 📞 Quick Contact

### Support Resources

- **Documentation:** [GitHub Wiki](https://github.com/MyLifeMyRulesMyCar/EFIO/wiki)
- **Issues:** [GitHub Issues](https://github.com/MyLifeMyRulesMyCar/EFIO/issues)
- **Discussions:** [GitHub Discussions](https://github.com/MyLifeMyRulesMyCar/EFIO/discussions)

### System Information

```bash
# Get system info
uname -a

# Get EFIO version
curl http://localhost:5000/api/status | jq .version

# Get device IP
hostname -I

# Get uptime
uptime
```

---

## 🎯 Common Tasks Cheatsheet

| Task | Command |
|------|---------|
| **Start service** | `sudo systemctl start efio-api` |
| **View logs** | `sudo journalctl -u efio-api -f` |
| **Create backup** | `./backup_restore.py backup` |
| **Restore backup** | `./backup_restore.py restore <file>` |
| **Fix serial ports** | `sudo ./fix_serial_permissions.sh` |
| **Restart service** | `sudo systemctl restart efio-api` |
| **Check status** | `sudo systemctl status efio-api` |
| **Web interface** | `http://YOUR_IP:5000` |
| **Test API** | `curl http://localhost:5000/api/status` |
| **Watch MQTT** | `mosquitto_sub -h localhost -t "edgeforce/#" -v` |

---

**Keep this guide handy for quick reference!**