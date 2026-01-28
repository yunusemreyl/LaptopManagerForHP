# HP Omen Control (Linux) 🐧

![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge\&logo=linux\&logoColor=black)
![GTK4](https://img.shields.io/badge/GTK4-Libadwaita-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge\&logo=python\&logoColor=white)

A **Linux-compatible control and configuration tool** for **HP Victus / HP Omen** laptops.
This project brings **power management**, **RGB keyboard control**, and **system monitoring** together in a single, clean **GTK4 / Libadwaita** interface.

It is designed as a **lightweight, functional alternative** to the Windows-only **Omen Gaming Hub**.

---

## 🖼️ Screenshots

|      Installation Wizard      |      Installation Options     |           Main Control Panel (v2.1)          |
| :---------------------------: | :---------------------------: | :------------------------------------------: |
| ![Setup 1](images/setup1.png) | ![Setup 2](images/setup2.png) | ![App Screenshot](images/app_screenshot.png) |

---

## ✨ Features

### 🔋 Power Profiles

* **ECO / Balanced / Performance** modes
* Integrated with system power management daemons

### 🌡️ Live System Monitoring

* **CPU temperature** tracking
* **RAM usage** percentage
* **Disk usage** percentage

### ⌨️ RGB Keyboard Control

* **Zone-based control** (Zone 1–4)
* **Full keyboard sync** option
* **Static color** selection
* Dynamic **Wave effect** (Right-to-Left)
* Adjustable **brightness** and **animation speed**

---

## 🚀 Quick Start & Installation

### Supported Distributions

Tested on:

* **Fedora 41**
* **Ubuntu 24.04**
* **Arch Linux**

### Installation

Clone the repository and run the setup script:

```bash
git clone https://github.com/yunusemreyl/Omen-Control-App.git
cd Omen-Control-App
sudo python3 setup.py
```

> ⚠️ **Note:** Root privileges are required to install kernel modules and system services.

---

## 🧠 Foundations & Credits

This project builds upon and modernizes earlier community efforts:

* **hp-omen-linux-module**
  Provided the initial WMI kernel module logic for HP Omen / Victus laptops.
  [https://github.com/pelrun/hp-omen-linux-module](https://github.com/pelrun/hp-omen-linux-module)

* **hp-laptop-rgb-controller**
  Inspired the Python-based RGB keyboard control logic.
  [https://github.com/kaankutan/hp-laptop-rgb-controller](https://github.com/kaankutan/hp-laptop-rgb-controller)

### My Contributions

* Complete **GTK4 / Libadwaita** graphical interface
* Optimized **background service** with low resource usage
* Fixed **4-zone RGB communication issues** specific to the **Victus series**

---

## 💻 Supported Devices

* **HP Omen series laptops**
* **HP Victus series laptops**

> Compatibility may vary depending on firmware and keyboard model.

---

## 👤 Author

**Yunus Emre**
GitHub: [@yunusemreyl](https://github.com/yunusemreyl)

---

## ⚠️ Disclaimer

This project is an **independent open-source tool** and is **not affiliated with, endorsed by, or supported by HP**.

Use at your own risk. Firmware behavior may change with BIOS updates.
