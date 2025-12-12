#!/bin/bash
set -e

echo "=== NESPi 4 Safe Shutdown Installer (Raspberry Pi OS Bookworm/Trixie) ==="

REPO_BASE_URL="https://raw.githubusercontent.com/fry747/nespi4-safe-shutdown/main"

# 1. Install Python GPIO dependency (use rpi-lgpio backend)
echo "[1/5] Installing Python GPIO package (python3-rpi-lgpio)..."
sudo apt update
# Remove legacy RPi.GPIO if present (optional but recommended)
sudo apt remove -y python3-rpi.gpio || true
sudo apt install -y python3-rpi-lgpio wget

# 2. Install SafeShutdown.py
echo "[2/5] Installing SafeShutdown.py to /opt/RetroFlag..."
sudo mkdir -p /opt/RetroFlag
sudo wget -O /opt/RetroFlag/SafeShutdown.py "${REPO_BASE_URL}/SafeShutdown.py"
sudo chmod +x /opt/RetroFlag/SafeShutdown.py

# 3. Install Device Tree overlay
echo "[3/5] Installing RetroFlag_pw_io.dtbo overlay..."

if [ -d /boot/firmware/overlays ]; then
    TARGET_OVERLAYS="/boot/firmware/overlays"
elif [ -d /boot/overlays ]; then
    TARGET_OVERLAYS="/boot/overlays"
else
    echo "ERROR: Could not find overlays directory (/boot/firmware/overlays or /boot/overlays)."
    exit 1
fi

sudo wget -O "${TARGET_OVERLAYS}/RetroFlag_pw_io.dtbo" "${REPO_BASE_URL}/RetroFlag_pw_io.dtbo"

# 4. Update config.txt (Bookworm / Trixie layout)
echo "[4/5] Updating config.txt (enable overlay and UART)..."

if [ -f /boot/firmware/config.txt ]; then
    CFG="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CFG="/boot/config.txt"
else
    echo "ERROR: Could not find config.txt (neither /boot/firmware/config.txt nor /boot/config.txt)."
    exit 1
fi

# Add dtoverlay only if not present
if ! grep -q "dtoverlay=RetroFlag_pw_io.dtbo" "${CFG}"; then
    echo "dtoverlay=RetroFlag_pw_io.dtbo" | sudo tee -a "${CFG}" > /dev/null
fi

# Ensure enable_uart=1
if ! grep -q "^enable_uart=1" "${CFG}"; then
    echo "enable_uart=1" | sudo tee -a "${CFG}" > /dev/null
fi

# 5. Install systemd service
echo "[5/5] Installing systemd service nespi-safe-shutdown.service..."

sudo wget -O /etc/systemd/system/nespi-safe-shutdown.service \
    "${REPO_BASE_URL}/nespi-safe-shutdown.service"

sudo systemctl daemon-reload
sudo systemctl enable nespi-safe-shutdown.service
sudo systemctl restart nespi-safe-shutdown.service

echo
echo "Installation finished."
echo "Check status with:  systemctl status nespi-safe-shutdown.service"
echo "A reboot is recommended:"
echo "  sudo reboot"
