# HP Omen & Victus RGB Driver (Standalone Linux Kernel Module)

A lightweight, hardened, and standalone kernel driver for controlling the 4-zone RGB keyboard lighting on HP Omen and Victus laptops.

## ℹ️ About & Origins

This driver is a **modernized, stripped-down fork** of the original [hp-omen-linux-module](https://github.com/pelrun/hp-omen-linux-module) by **pelrun**.

While the original project aimed to replace the stock HP drivers entirely (handling thermals, fans, and performance), this project has a different philosophy: **"Do one thing and do it well."**

### ⚡ Key Differences from the Original
* **RGB Focused:** All thermal, fan control, and performance profile code has been removed to ensure zero conflict with the modern Linux kernel and stock `hp-wmi` driver.
* **Standalone Operation:** It does **NOT** conflict with or attempt to unregister the standard `hp-wmi` module. It creates a separate platform device (`hp-omen-rgb`) solely for lighting control.
* **Security Hardened:** Significant improvements were made to input validation (safe `zone_store`), memory safety (controlled `memcpy` boundaries), and race condition prevention (Mutex locking).
* **Universal DKMS:** Packaged with an automated installer script for easy deployment on Arch, Debian/Ubuntu, and Fedora-based systems.

## 🚀 Features

* **4-Zone Control:** Supports standard HP layouts (Left, Center, Right, Numpad).
* **Safe WMI Calls:** Interacts directly with the ACPI WMI method (`5FB7F034...`) without interfering with other system calls.
* **Simple API:** Control colors simply by writing HEX codes to sysfs files.

## 📦 Installation

### Method 1: Automatic Installer (Recommended)
This script detects your distribution, installs dependencies (DKMS, Headers), and sets up the driver.
```bash
git clone https://github.com/yunusemreyl/hp-omen-rgb-dkms.git
cd hp-omen-rgb-dkms
chmod +x install.sh
sudo ./install.sh
```
Method 2: Manual Installation (DKMS)
If you prefer to handle the DKMS process manually:
```bash
# 1. Copy source files to the system source directory
sudo cp -r . /usr/src/hp-omen-rgb-1.0

# 2. Add the module to DKMS tree
sudo dkms add -m hp-omen-rgb -v 1.0

# 3. Build and Install the module
sudo dkms build -m hp-omen-rgb -v 1.0
sudo dkms install -m hp-omen-rgb -v 1.0

# 4. Load the module
sudo modprobe hp-omen-rgb
```

🎮 Usage
The driver exposes a direct interface at /sys/devices/platform/hp-omen-rgb/.

Zone Mapping:

zone0: Left / WASD

zone1: Center

zone2: Right

zone3: Numpad / Macro Keys

Examples:

```bash
# Set WASD (Zone 0) to Red
echo "FF0000" | sudo tee /sys/devices/platform/hp-omen-rgb/zone0

# Set Center (Zone 1) to Green
echo "00FF00" | sudo tee /sys/devices/platform/hp-omen-rgb/zone1
```
⚠️ Compatibility
This driver uses the HP WMI GUID 5FB7F034-2C63-45e9-BE91-3D44E2C707E4. It is tested on:

HP Victus 16 (Intel/AMD variants)

HP Omen 16 / 17

⚖️ License
Based on work by pelrun.

Licensed under GPL-2.0-or-later. EOF
