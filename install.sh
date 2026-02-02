#!/bin/bash

# --- COLORS ---
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- BANNER ---
echo -e "${YELLOW}"
echo "#################################################"
echo "#      HP OMEN CONTROL CENTER - INSTALLER       #"
echo "#           v3.0 Universal | yunusemreyl        #"
echo "#################################################"
echo -e "${NC}"

# --- ROOT CHECK ---
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run as root: sudo ./install.sh${NC}"
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

# --- 1. DETECT DISTRO & INSTALL DEPENDENCIES ---
echo -e "${GREEN}[1/6] Detecting distribution and installing dependencies...${NC}"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo -e "${RED}[ERROR] Cannot detect distribution.${NC}"
    exit 1
fi

case "$DISTRO" in
    ubuntu|debian|linuxmint|pop|zorin|kali)
        echo -e "${YELLOW} -> Detected Debian/Ubuntu based system.${NC}"
        apt-get update
        apt-get install -y python3-gi python3-pydbus libgtk-4-dev libadwaita-1-dev \
            build-essential linux-headers-$(uname -r) python3-pip dkms git
        ;;
    fedora)
        echo -e "${YELLOW} -> Detected Fedora.${NC}"
        dnf install -y python3-gobject gtk4-devel libadwaita-devel \
            kernel-devel-$(uname -r) python3-pip dkms git gcc make
        ;;
    arch|manjaro)
        echo -e "${YELLOW} -> Detected Arch Linux based system.${NC}"
        pacman -Sy --noconfirm python-gobject gtk4 libadwaita \
            linux-headers python-pip dkms git base-devel
        ;;
    *)
        echo -e "${RED}[ERROR] Unsupported distribution: $DISTRO${NC}"
        echo "Please install dependencies manually: python3-gi, gtk4, libadwaita, dkms, linux-headers"
        exit 1
        ;;
esac

# EnvyControl Installation
if ! command -v envycontrol &> /dev/null; then
    echo -e "${YELLOW} -> Installing EnvyControl from GitHub (bayasdev)...${NC}"
    # --break-system-packages is mostly for Debian/Ubuntu/Fedora recent versions
    pip3 install git+https://github.com/bayasdev/envycontrol.git --break-system-packages 2>/dev/null || \
    pip3 install git+https://github.com/bayasdev/envycontrol.git
else
    echo -e "${GREEN} -> EnvyControl is already installed.${NC}"
fi

# --- 2. AUTOMATIC DRIVER SETUP (DKMS) ---
echo -e "${GREEN}[2/6] Configuring DKMS for automatic kernel updates...${NC}"

# Clean old
dkms remove -m $DKMS_NAME -v $DKMS_VER --all &>/dev/null
rm -rf "/usr/src/$DKMS_NAME-$DKMS_VER"
mkdir -p "/usr/src/$DKMS_NAME-$DKMS_VER"

if [ -f "driver/src/hp-omen-rgb.c" ]; then
    cp driver/src/hp-omen-rgb.c "/usr/src/$DKMS_NAME-$DKMS_VER/"
else
    echo -e "${RED}[ERROR] Driver source not found at driver/src/hp-omen-rgb.c${NC}"
    exit 1
fi

cat > "/usr/src/$DKMS_NAME-$DKMS_VER/dkms.conf" <<EOF
PACKAGE_NAME="$DKMS_NAME"
PACKAGE_VERSION="$DKMS_VER"
BUILT_MODULE_NAME[0]="$DKMS_NAME"
DEST_MODULE_LOCATION[0]="/extra"
AUTOINSTALL="yes"
EOF

cat > "/usr/src/$DKMS_NAME-$DKMS_VER/Makefile" <<EOF
obj-m += hp-omen-rgb.o
all:
	make -C /lib/modules/\$(shell uname -r)/build M=\$(PWD) modules
clean:
	make -C /lib/modules/\$(shell uname -r)/build M=\$(PWD) clean
EOF

echo -e " -> Building module with DKMS..."
dkms add -m $DKMS_NAME -v $DKMS_VER
dkms build -m $DKMS_NAME -v $DKMS_VER
dkms install -m $DKMS_NAME -v $DKMS_VER

if [ $? -eq 0 ]; then
    echo -e "${GREEN} -> Driver registered successfully.${NC}"
    modprobe $DKMS_NAME
    if ! grep -q "$DKMS_NAME" /etc/modules; then echo "$DKMS_NAME" >> /etc/modules; fi
    # Arch Linux modules load file location fix
    if [ -d "/etc/modules-load.d" ]; then
        echo "$DKMS_NAME" > /etc/modules-load.d/hp-omen-rgb.conf
    fi
else
    echo -e "${RED}[ERROR] DKMS build failed! Check kernel headers.${NC}"
    exit 1
fi

# --- 3. FILES SETUP ---
echo -e "${GREEN}[3/6] Copying application files...${NC}"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/src" "$APP_DIR/images"
cp -r src "$APP_DIR/"
cp -r images "$APP_DIR/"
chmod +x "$APP_DIR/src/daemon/omen_service.py"
chmod +x "$APP_DIR/src/gui/main_window.py"

# --- 4. D-BUS & SERVICE CONFIG ---
echo -e "${GREEN}[4/6] Configuring D-Bus and Systemd service...${NC}"

cat > $DBUS_FILE <<EOF
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="root">
    <allow own="com.yyl.hpcontrolcenter"/><allow send_destination="com.yyl.hpcontrolcenter"/>
  </policy>
  <policy context="default">
    <allow send_destination="com.yyl.hpcontrolcenter"/><allow receive_sender="com.yyl.hpcontrolcenter"/><allow send_interface="com.yyl.hpcontrolcenter"/>
  </policy>
</busconfig>
EOF

cat > $SERVICE_FILE <<EOF
[Unit]
Description=HP Omen Control Daemon
After=multi-user.target
[Service]
Type=simple
ExecStart=/usr/bin/python3 $APP_DIR/src/daemon/omen_service.py
Restart=always
User=root
Environment=PYTHONUNBUFFERED=1
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable com.yyl.hpcontrolcenter.service
systemctl restart com.yyl.hpcontrolcenter.service

# --- 5. UI INTEGRATION ---
echo -e "${GREEN}[5/6] Creating desktop shortcuts...${NC}"

cat > $BIN_LINK <<EOF
#!/bin/bash
/usr/bin/python3 $APP_DIR/src/gui/main_window.py "\$@"
EOF
chmod +x $BIN_LINK

cat > $DESKTOP_FILE <<EOF
[Desktop Entry]
Name=HP Omen Control
Comment=Control RGB and GPU for HP Omen/Victus
Exec=$BIN_LINK
Icon=$APP_DIR/images/app_logo.png
Terminal=false
Type=Application
Categories=Utility;Settings;System;
StartupNotify=true
EOF

gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true

# --- 6. FINISH ---
echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "${YELLOW}  INSTALLATION COMPLETED! v3.0 Final${NC}"
echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "Supported: Debian/Ubuntu, Fedora, Arch/Manjaro"
echo -e "You can now open 'HP Omen Control' from your menu."
echo -e ""
