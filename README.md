<div align="center">
<img src="images/omenspace.png" alt="OMENSpace Logo" width="150">

**Next-Generation Linux Control Center for HP Omen, Victus & Transcend Laptops**  
*An open-source, Rust-powered GTK4 suite for managing performance profiles, custom fan curves, RGB lighting, Ryzen SMU tuning, and hardware limits seamlessly on Linux.*

[![Version: 2.0.0](https://img.shields.io/badge/Release-v2.0.0-blue.svg)](https://github.com/yunusemreyl/omen-space/releases)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-green.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-lightgrey.svg)]()
[![Built with Rust](https://img.shields.io/badge/Language-Rust-orange.svg)]()
[![UI: GTK4 & Libadwaita](https://img.shields.io/badge/UI-GTK4%20%26%20Libadwaita-blueviolet.svg)]()

---

### [ ⚡ Quick Install ](#quick-install) &nbsp;•&nbsp; [ 📸 Screenshots ](#screenshots) &nbsp;•&nbsp; [ ✨ Features ](#features) &nbsp;•&nbsp; [ 🌟 Rust vs Legacy ](#evolution) &nbsp;•&nbsp; [ 🏗️ Architecture ](#architecture) &nbsp;•&nbsp; [ 📦 Packages ](#packages)

---

</div>

<a id="quick-install"></a>
## ⚡ Quick Install

Install OMENSpace in one step. Automatically detects your package manager, resolves dependencies, compiles with release optimizations, configures systemd & D-Bus, and loads the kernel module.

#### 🚀 1-Line Web Installer *(Recommended)*
```bash
curl -sSL https://raw.githubusercontent.com/yunusemreyl/omen-space/main/install.sh | sudo bash
```
> 💡 *The installer lets you choose between **🟢 Stable** (Latest Official Release) and **🟡 Canary** (Bleeding-edge `main` branch with the newest commits). You can also pre-select your channel directly:*
> ```bash
> # Direct Stable install
> curl -sSL https://raw.githubusercontent.com/yunusemreyl/omen-space/main/install.sh | sudo bash -s -- --stable
>
> # Direct Canary (main branch) install
> curl -sSL https://raw.githubusercontent.com/yunusemreyl/omen-space/main/install.sh | sudo bash -s -- --canary
> ```

<details>
<summary><b>📦 Alternative Install Options (Git Clone, Arch Linux, NixOS)</b></summary>
<br>

**Via Git Clone (Ubuntu / Debian, Fedora / RHEL, Arch, openSUSE):**
```bash
git clone https://github.com/yunusemreyl/omen-space.git
cd omen-space
chmod +x setup.sh
sudo ./setup.sh install
```

**Arch Linux (AUR / PKGBUILD):**
```bash
git clone https://github.com/yunusemreyl/omen-space.git
cd omen-space
makepkg -si
```

**NixOS (Flakes):**
```bash
nix profile install github:yunusemreyl/omen-space
```

**System Management:**
```bash
sudo ./setup.sh update      # Pulls latest changes, rebuilds, and restarts daemon
sudo ./setup.sh uninstall   # Cleanly purges all binaries, services, and DKMS drivers
```

</details>

---

<a id="screenshots"></a>
## 📸 Screenshots

### 🌟 Core Highlights *(Click any image for full resolution)*

| 🎛️ **Custom Fan Curves & Telemetry** | ⚡ **Performance & Thermal Profiles** |
| :---: | :---: |
| <a href="images/perf.png"><img src="images/perf.png" alt="Fan Curve Splines & Telemetry" width="100%"></a> | <a href="images/profile.png"><img src="images/profile.png" alt="Thermal Profiles" width="100%"></a> |
| *Real-time spline curve editor with moving average deadband* | *Switch between Power Saver, Balanced, and Performance modes* |

| 🌈 **RGB Keyboard Lighting Studio** | 🚀 **Ryzen SMU & Undervolting** |
| :---: | :---: |
| <a href="images/rgb.png"><img src="images/rgb.png" alt="RGB Keyboard Lighting" width="100%"></a> | <a href="images/undervolt.png"><img src="images/undervolt.png" alt="Ryzen SMU & Undervolting" width="100%"></a> |
| *4-Zone & Per-Key animated effects (Breathing, Wave, Cycle)* | *Direct MSR undervolt, TCC offsets, GPU TGP limits, and SMU power limits* |

<details>
<summary><b>🔍 View Advanced Controls & System Tools (MUX Switch, Diagnostics, BIOS Updater, Settings, CLI)</b></summary>
<br>

| 🎮 **GPU MUX Switch (Hybrid / Discrete)** | 🩺 **Hardware Diagnostics** |
| :---: | :---: |
| <a href="images/mux.png"><img src="images/mux.png" alt="MUX Switch" width="100%"></a> | <a href="images/diagno.png"><img src="images/diagno.png" alt="Diagnostics" width="100%"></a> |
| *Native Optimus / dGPU display routing control* | *Real-time thermals, clock rates, battery health, and sensor telemetry* |

| 🔄 **HP BIOS Updater** | ⚙️ **Settings & Preferences** |
| :---: | :---: |
| <a href="images/updater.png"><img src="images/updater.png" alt="BIOS Updater" width="100%"></a> | <a href="images/settings.png"><img src="images/settings.png" alt="Settings" width="100%"></a> |
| *Automatic DMI-based HP server queries for motherboard firmware updates* | *Startup behavior, daemon preferences, polling intervals, and tray toggles* |

| 💻 **High-Performance Command Line Interface** | |
| :---: | :---: |
| <a href="images/cli.png"><img src="images/cli.png" alt="CLI" width="100%"></a> | |
| *Fast, scriptable hardware control directly from your terminal* | |

</details>

---

<a id="features"></a>
## ⚡ Features at a Glance

* 🎛️ **Fan & Thermal Mastery:** Create custom Fan curve splines with a 15-sample moving average deadband for near-silent operation without thermal throttling. Includes a dedicated **Fan Cleaning Mode** to blow out trapped dust.
* ⚡ **Power & Performance Switching:** Seamlessly toggle between `power-saver`, `balanced`, and `performance` hardware profiles via ACPI and WMI.
* 🚀 **Ryzen SMU & Undervolting:** Direct MSR-based undervolting, TCC offset control, GPU TGP limits, and AMD Ryzen SMU tuning for maximum thermal headroom.
* 🎮 **MUX Switch Control:** Native interface for Optimus / dGPU routing switching (uses undocumented WMI payload `0x52`).
* 🌈 **RGB Keyboard Lighting:** Configure your 4-Zone or Per-Key keyboard backlighting with wave, breathing, cycle, and static colors. Hardware accelerated via sysfs.
* 🎯 **Game & App Automation:** Define custom power limits and fan curves for individual games (Steam, Lutris, Flatpak). Zero-fork process detection doesn't waste CPU cycles.
* 🔄 **Smart BIOS Checker:** Automatically checks HP servers for the latest BIOS update for your specific motherboard (DMI).
* 💻 **CLI & System Tray:** Control profiles and fan speeds from the terminal (`omen-cli`) or desktop panel applet (`omen-tray`).

---

<a id="evolution"></a>
## 🌟 The Evolution: From OmenCtl to OMENSpace

**OMENSpace** is a complete, ground-up rewrite of the legacy Python-based *OmenCtl* project. We transitioned from Python to **Rust** to deliver zero-cost abstractions, maximum memory safety, and native performance.

### Why the upgrade?
| Feature / Metric | Legacy OmenCtl (Python) | **OMENSpace (Rust)** |
| :--- | :--- | :--- |
| **Performance & RAM** | ~40MB RAM (Python interpreter overhead) | **~2.8MB binary, < 5MB RAM** (Zero overhead) |
| **Architecture** | Sync loops, heavy `subprocess` usage | **Tokio Async**, Zero-fork `/proc` & Sysfs telemetry |
| **GUI Framework** | Python GTK Bindings (Sluggish) | **Native GTK4 & Libadwaita** (Extremely fast & responsive) |
| **Inter-Process Comm** | `pydbus` | `zbus` (Pure Rust, highly concurrent) |
| **Hardware Tuning** | Standard ACPI Power Profiles | **Ryzen SMU Tuning, Undervolting & Fan Cleaning Mode!** |

---

<a id="architecture"></a>
## 🏗️ Architecture Overview

The OMENSpace stack is split into four distinct Rust crates and a kernel module:

1. **`omen-space-daemon` (The Backend)**
   - Runs as a systemd service (`omen-space-daemon.service`) with root privileges.
   - Manages direct hardware interaction via WMI, ACPI, Sysfs, and MSR.
   - Exposes hardware control safely over **D-Bus** (`org.hp.omen.*`).

2. **`omen-gui` (The Frontend)**
   - A modern graphical interface built using **GTK4** and **Libadwaita**.
   - Runs in user-space without requiring `sudo`.
   - Communicates with the daemon exclusively via D-Bus (`zbus` crate).

3. **`omen-cli` (Command Line Interface)**
   - A fast terminal tool for users who prefer the command line or want to script hardware changes.

4. **`omen-tray` (System Tray)**
   - A lightweight background applet providing quick access to thermal profiles and fan modes from your desktop panel.

5. **`hp-omen-extra` (Kernel Module)**
   - Custom DKMS driver providing extended WMI and sysfs interfaces for fans, thermal sensors, and RGB control.

---

<a id="packages"></a>
## 📦 Installation & Package Management

### Detailed Setup Script Options
The `setup.sh` script automates compilation with `LTO` and `opt-level=z` optimizations:

```bash
sudo ./setup.sh install    # Cleans legacy omenctl, builds Rust binaries, installs system files & driver
sudo ./setup.sh update     # Pulls latest git changes, rebuilds, and restarts the daemon
sudo ./setup.sh uninstall  # Completely removes OMENSpace, daemon, and the DKMS kernel module
```

### Supported Distributions
- **Fedora / RHEL:** Uses `dnf` to automatically install build tools, GTK4, Libadwaita, and kernel headers.
- **Ubuntu / Debian / Pop!_OS:** Uses `apt-get` to install dependencies and kernel development packages.
- **Arch Linux / Manjaro:** Uses `pacman` to install build dependencies, or install directly using the provided `PKGBUILD` (`makepkg -si`).
- **NixOS:** Provided `flake.nix` enables simple installation via `nix profile install github:yunusemreyl/omen-space`.
- **OpenSUSE:** Uses `zypper` to install dependencies and kernel development packages.

---

## 👨‍💻 Credits & Contributors

OMENSpace wouldn't exist without its amazing open-source community.

* **[yunusemreyl](https://github.com/yunusemreyl)** - Lead Developer
* **[tuxov](https://github.com/tuxov)** - Kernel Module Lead
* **[theantipopau](https://github.com/theantipopau/omencore)** - Inspiration and reference from omencore.
* **[OmenLinux/omen-rgb-keyboard](https://github.com/OmenLinux/omen-rgb-keyboard)** - Kernel module providing hardware-accelerated RGB lighting effects.

### Top Contributors
[@CodesRahul96](https://github.com/CodesRahul96), [@xcellsior](https://github.com/xcellsior), [@TitoTFP](https://github.com/TitoTFP), [@SafSaf0999](https://github.com/SafSaf0999), [@yijean34-source](https://github.com/yijean34-source).

*(For the full list of community members and bug testers, check the commit history—thank you all!)*

---

## ⚖️ License
OMENSpace is licensed under the **GNU General Public License v3.0** (GPL-3.0). See the [LICENSE](LICENSE) file for details.

*OMENSpace is an independent open-source project and is **NOT** officially affiliated with, authorized, or endorsed by **Hewlett-Packard (HP)**.*
