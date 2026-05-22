
 # OMEN Command Center for Linux v1.3.7 #
<p align="center">
  <img src="images/omenapplogo.png" alt="Logo" width="250">

## 📖 About The Project
<p align="center">
  <img src="screenshots/start.png" alt="Launcher" width="45%">
  <img src="screenshots/dash.png" alt="Dashboard" width="45%">
</p>
<p align="center">
  <img src="screenshots/keyboard.png" alt="Keyboard" width="45%">
  <img src="screenshots/mux.png" alt="MUX Switch" width="45%">
</p>
<p align="center">
  <img src="screenshots/settings.png" alt="Settings" width="45%">
  <img src="screenshots/performance.png" alt="Performance" width="45%">
</p>

**OMEN Command Center for Linux** is a native Linux application designed to unlock the full potential of HP Omen and Victus series laptops. It serves as an open-source alternative to the official OMEN Gaming Hub, providing essential controls in a modern, user-friendly interface.

---

## 🛠️ What's New in v1.3.7?

### 🚀 New: `omen` Command Line Interface (CLI)
Introducing a powerful new CLI for terminal lovers. Control your laptop's core features without opening the GUI.
```bash
omen fan max          # Set fans to max speed
omen fan auto         # Restore auto fan control
omen mode performance # Enable high-performance mode (lifts 80W cap)
omen mode balanced    # Switch to balanced profile
omen mode quiet       # Switch to quiet/power-saver mode
omen mux hybrid       # Switch to Hybrid GPU mode
omen mux discrete     # Switch to Discrete GPU mode
```

### ⚡ GPU Power Limit (80W Cap) Resolution
The 80W power limit issue on NVIDIA GPUs is now fully resolved.
- **Kernel-level TGP & PPAB Control**: Added support for lifting power caps on OMEN/Victus laptops via the patched `hp-wmi` driver.
- **Automatic Sync**: Switching to "Performance" mode now automatically triggers both NVIDIA-SMI limits and kernel-level power expansion (lifting the 80W cap to 140W+ on supported hardware).

### 🔧 Driver & Stability Improvements
- **Fixed INIT_DELAYED_WORK Race Condition**: Prevented potential kernel crashes during module initialization.
- **Fixed TOCTOU Vulnerabilities**: Synchronized GPU power state updates in the driver for better data integrity.
- **Improved NULL-Safety**: Hardened the `hp-wmi` driver against unexpected WMI responses.
- **Cleaned up Fan Fallbacks**: Improved reliability on newer Victus-S series boards.

---


## ✨ Features

### 🎨 RGB Lighting Control
- **4-Zone Control**: Customize colors for different keyboard zones.
- **Effects**: Static, Breathing, Wave, Cycle.
- **Brightness & Speed**: Adjustable parameters for dynamic effects.
- **Low-CPU Wave Engine**: Wave mode CPU usage dropped from ~22-28% to ~2% in stress conditions.

### 📊 System Dashboard
- **Real-time Monitoring**: CPU/GPU temperatures, fan speeds, battery health.
- **Performance Profiles**: One-click power profile switching (requires `power-profiles-daemon`).

### 🌪️ Fan Control
- **Standard Mode**: EC-controlled automatic fan management.
- **Max Mode**: Forces fans to maximum speed for intensive tasks.
- **Custom Mode**: Drag-and-drop curve editor to create your own fan profiles.

### 🎮 GPU MUX Switch (BETA)
- Switch between **Hybrid**, **Discrete**, and **Integrated** modes.
- Backend can be selected from **Settings → GPU / MUX**.
- Auto mode prefers `envycontrol` / `supergfxctl` / `prime-select` before HP WMI direct.
- ⚠️ Some hardware/BIOS combinations may require a reboot.

### ⌨️ Desktop Shortcuts (Recommended)
 To minimize background resource usage, we recommend creating a **Custom Shortcut** in your Desktop Environment settings (GNOME, KDE, etc.):
 - **Command**: `hp-manager`
 - **Shortcut Key**: Your **OMEN Key** (detected as `KEY_PROG2`) or any preferred key combination.

---

## 🚀 Installation

### Prerequisites
- A Linux distribution (Ubuntu, Fedora, Arch, OpenSUSE, etc.)
- `git` installed

### Install
Open a terminal and run:

```bash
# Clone the repository
git clone https://github.com/yunusemreyl/OmenCommandCenterforLinux.git
cd OmenCommandCenterforLinux

# Run the installer (requires root)
chmod +x setup.sh
sudo ./setup.sh install
```
Note: For compatibility with older documentation, `sudo ./install.sh` redirects to `setup.sh install`.
Installation Warning ⚠️: We recommend restarting your computer after installation.

### Updating

```bash
cd OmenCommandCenterforLinux
git pull
sudo ./setup.sh update
```

> ⚠️ **Upgrading from v1.3.0 or earlier?** The architecture changed from a single monolithic daemon to microservices. You **must** use `sudo ./setup.sh update` to cleanly remove old services and install the new ones.

### Script Layout

Maintenance scripts are organized under:

- `scripts/fixes/`
- `scripts/diagnostics/`
- `scripts/tests/`

Legacy entry points (`fix_hp_wmi.sh`, `fix_omen.sh`, `dump_log.sh`, `test_nvidia.py`) are kept at the repository root as compatibility wrappers.

For OMEN Max 16 / hp-wmi probe troubleshooting, use:
- `scripts/tests/test_hp_wmi_raw_payload.sh`

The installer will automatically:
1. Detect your package manager and install dependencies.
2. Detect your kernel version and install the appropriate driver:
   - **Kernel ≥ 7.0**: Only installs `hp-rgb-lighting` (RGB). Fan control is provided by the stock `hp-wmi` module.
     - **Exception**: OMEN Max 16 board `8D41` is forced to the custom `hp-wmi` path due to stock probe incompatibility.
   - **Kernel < 7.0**: Installs both the custom `hp-wmi` driver (backported) and `hp-rgb-lighting`.
3. Install the daemon and GUI components.
4. Set up the 5 microservices.

## 🗑️ Uninstallation

To completely remove the application and its services:

```bash
cd OmenCommandCenterforLinux
sudo ./setup.sh uninstall
```

## 🐛 Troubleshooting

If the `omen` CLI fails with a `pydbus` import error, your `PATH` may be pointing to a non-system Python (e.g., Conda) that does not share packages with the system Python where `python3-pydbus` was installed. See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for the fix.

## 🐧 Compatibility

| Distribution | Status | Notes |
|--------------|--------|-------|
| **Ubuntu 24.04 LTS / Zorin OS / Pop!_OS / Linux Mint** | ✅ Verified | Full support via `apt` |
| **Fedora 42+ / Nobara** | ✅ Verified | Full support via `dnf` |
| **Arch Linux / CachyOS / Manjaro** | ✅ Verified | Full support via `pacman` |
| **OpenSUSE Tumbleweed** | ✅ Verified | Full support via `zypper` |


## 👨‍💻 Credits & Acknowledgments
- **Lead Developer**: [yunusemreyl](https://github.com/yunusemreyl)
- **Kernel Module Development**: Special thanks to **[TUXOV](https://github.com/TUXOV/hp-wmi-fan-and-backlight-control)** for the `hp-wmi-fan-and-backlight-control` driver. Also thanks to **xcellsior** for the Nvidia Dynamic Boost 80W cap mitigation patch.

## ⚖️ Legal Disclaimer
This tool is an independent open-source project developed by **yunusemreyl**.
It is **NOT** affiliated with or endorsed by **Hewlett-Packard (HP)**.
The software is provided "as is", without warranty of any kind.

---
*Developed with ❤️ by yunusemreyl*
