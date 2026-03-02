
 # HP Laptop Manager (Linux) v4.7 #
<p align="center">
  <img src="images/hplogolight.png" alt="Logo" width="250">

## 📖 About The Project
<p align="center">
  <img src="screenshots/dash.png" alt="Dashboard" width="45%">
  <img src="screenshots/fan.png" alt="Fan Control" width="45%">
</p>
<p align="center">
  <img src="screenshots/key.png" alt="Lighting" width="45%">
  <img src="screenshots/mux.png" alt="MUX Switch" width="45%">
</p>
<p align="center">
  <img src="screenshots/games.png" alt="Games" width="45%">
  <img src="screenshots/tools.png" alt="Tools" width="45%">
</p>
<p align="center">
  <img src="screenshots/settings.png" alt="Settings" width="45%">
</p>

**HP Laptop Manager** is a native Linux application designed to unlock the full potential of HP Omen and Victus series laptops. It serves as an open-source alternative to the official OMEN Gaming Hub, providing essential controls in a modern, user-friendly interface.

**New in v4.7:**
- 💫 **UI Hover Enhancements**: Added smooth glassmorphic scale and glow interactions to Dashboard Quick Actions, Performance Slider, and MUX/Fan profile buttons.
- 💡 **Dynamic Power Tooltips**: Power Profiles (ECO/Balanced/Performance) now feature intelligent mouse-hover tooltips reflecting real-time CPU/GPU hardware limits.
- 🏷️ **Global Tab Rename**: The Fan tab is now globally unified as the "Performance" Hub (Performans in Turkish).
- 📊 **Dashboard Segmented Control**: Integrated native GTK Segmented Control for power profiles inside the Dashboard, matching the sleek Fan page styling.
- ✨ **Unified Kernel Driver**: `hp-omen-core` companion driver with DKMS for out-of-the-box fan and RGB support without conflicts.
- 💤 **Smart GPU Sleep**: The background daemon natively detects if the discrete GPU (dGPU) is suspended (e.g., `d3cold`) and refrains from polling `nvidia-smi`.
- ⌨️ **Omen Key Support**: Pressing the physical Omen Key natively opens the manager GUI via lightweight input listening.
- 📝 **TOML Configuration**: Modern config management with automatic migration from older JSON settings.

## ✨ Features

### 🎨 RGB Lighting Control
- **4-Zone Control**: Customize colors for different keyboard zones.
- **Effects**: Static, Breathing, Wave, Cycle.
- **Brightness & Speed**: Adjustable parameters for dynamic effects.

### 📊 System Dashboard
- **Real-time Monitoring**: CPU/GPU temperatures and Fan speeds.
- **Performance Profiles**: One-click power profile switching (requires `power-profiles-daemon`).

### 🌪️ Fan Control
- **Standard Mode**: Intelligent software-controlled fan curve for balanced noise/performance.
- **Max Mode**: Forces fans to maximum speed for intensive tasks.
- **Custom Mode**: Drag-and-drop curve editor to create your own fan profiles.

### 🎮 GPU MUX Switch
- Switch between **Hybrid**, **Discrete**, and **Integrated** modes.
- *Note: Requires compatible tools like `envycontrol`, `supergfxctl`, or `prime-select`.*

## 🚀 Installation

### Prerequisites
- A Linux distribution (Ubuntu, Fedora, Arch, OpenSUSE, etc.)
- `git` installed

### Install
Open a terminal and run:

```bash
# Clone the repository
git clone https://github.com/yunusemreyl/LaptopManagerForHP.git
cd LaptopManagerForHP

# Run the installer (requires root)
chmod +x install.sh
sudo ./install.sh
```

The installer will automatically:
1. Detect your package manager and install dependencies.
2. Install the daemon and GUI components.
3. Set up system services.
4. Provide a troubleshooting guide if issues occur.

## 🗑️ Uninstallation

To completely remove the application and its services:

```bash
cd LaptopManagerForHP
chmod +x uninstall.sh
sudo ./uninstall.sh
```

## 🐧 Compatibility

| Distribution | Status | Notes |
|--------------|--------|-------|
| **Ubuntu 24.04 LTS / Zorin OS / Pop!_OS / Linux Mint** | ✅ Verified | Full support via `apt` |
| **Fedora 42+ / Nobara** | ✅ Verified | Full support via `dnf` |
| **Arch Linux / CachyOS / Manjaro** | ✅ Verified | Full support via `pacman` |
| **OpenSUSE Tumbleweed** | ✅ Verified | Full support via `zypper` |


## 👨‍💻 Credits & Acknowledgments
- **Lead Developer**: [yunusemreyl](https://github.com/yunusemreyl)
- **Kernel Module Development**: Special thanks to **[TUXOV](https://github.com/TUXOV/hp-wmi-fan-and-backlight-control)** for the `hp-wmi-fan-and-backlight-control` driver, which makes fan control possible.

## ⚖️ Legal Disclaimer
This tool is an independent open-source project developed by **yunusemreyl**.
It is **NOT** affiliated with or endorsed by **Hewlett-Packard (HP)**.
The software is provided “as is”, without warranty of any kind.

---
*Developed with ❤️ by yunusemreyl*
