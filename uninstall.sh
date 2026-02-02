#!/bin/bash

# --- COLORS ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- BANNER ---
echo -e "${RED}"
echo "#################################################"
echo "#     HP OMEN CONTROL CENTER - UNINSTALLER      #"
echo "#        v3.0 Universal | yunusemreyl           #"
echo "#################################################"
echo -e "${NC}"

# --- ROOT CHECK ---
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run as root: sudo ./uninstall.sh${NC}"
  exit 1
fi

# --- VARIABLES ---
APP_DIR="/usr/share/hp-omen-control"
BIN_LINK="/usr/local/bin/omen-control"
DESKTOP_FILE="/usr/share/applications/com.yyl.hpcontrolcenter.desktop"
SERVICE_FILE="/etc/systemd/system/com.yyl.hpcontrolcenter.service"
DBUS_FILE="/etc/dbus-1/system.d/com.yyl.hpcontrolcenter.conf"
DKMS_NAME="hp-omen-rgb"
DKMS_VER="1.0"

echo -e "${YELLOW}[WARNING] This will remove HP Omen Control Center and the RGB driver from your system.${NC}"
read -p "Are you sure you want to continue? (y/N): " confirm
if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "Aborted."
    exit 1
fi

# --- 1. STOP & REMOVE SERVICE ---
echo -e "${GREEN}[1/5] Stopping and removing background service...${NC}"
# Universal systemd check
if command -v systemctl &> /dev/null; then
    if systemctl is-active --quiet com.yyl.hpcontrolcenter.service; then
        systemctl stop com.yyl.hpcontrolcenter.service
    fi
    systemctl disable com.yyl.hpcontrolcenter.service 2>/dev/null
    
    if [ -f "$SERVICE_FILE" ]; then
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        echo " -> Service removed."
    fi
else
    echo " -> Systemd not found, skipping service stop."
fi

# --- 2. REMOVE DRIVER (DKMS) ---
echo -e "${GREEN}[2/5] Removing RGB Driver (DKMS)...${NC}"

# Unload module from kernel
modprobe -r $DKMS_NAME 2>/dev/null

# Remove from DKMS (Universal Command)
if command -v dkms &> /dev/null; then
    if dkms status | grep -q "$DKMS_NAME"; then
        dkms remove -m $DKMS_NAME -v $DKMS_VER --all
        echo " -> Driver unregistered from DKMS."
    fi
fi

# Remove source files
if [ -d "/usr/src/$DKMS_NAME-$DKMS_VER" ]; then
    rm -rf "/usr/src/$DKMS_NAME-$DKMS_VER"
fi

# Clean /etc/modules (Debian/Ubuntu/Mint)
if [ -f /etc/modules ]; then
    sed -i '/hp-omen-rgb/d' /etc/modules
fi

# Clean /etc/modules-load.d (Arch/Fedora/Manjaro/OpenSUSE)
if [ -f /etc/modules-load.d/hp-omen-rgb.conf ]; then
    rm -f /etc/modules-load.d/hp-omen-rgb.conf
fi

# --- 3. REMOVE APP FILES ---
echo -e "${GREEN}[3/5] Deleting application files...${NC}"
rm -rf "$APP_DIR"
rm -f "$BIN_LINK"
rm -f "$DBUS_FILE"

# --- 4. REMOVE DESKTOP SHORTCUT ---
echo -e "${GREEN}[4/5] Removing desktop shortcut...${NC}"
rm -f "$DESKTOP_FILE"
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true

# --- 5. FINISH ---
echo -e "${GREEN}[5/5] Cleanup finished.${NC}"

echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "${YELLOW}  UNINSTALLATION COMPLETED SUCCESSFULLY${NC}"
echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "Note: We kept dependencies (python, gtk, etc.) to avoid breaking other apps."
echo -e ""
