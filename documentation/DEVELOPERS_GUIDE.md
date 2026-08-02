# Developer's Guide: Step-by-Step Code Modification

This guide is designed for developers who want to modify OmenCtl. If you are asking yourself: *"I want to change X, which file do I edit?"*, this is your map.

OmenCtl is strictly split into **Frontend (GUI)** and **Backend (Root Daemon)**. The two communicate via D-Bus.

---

## Scenario A: Changing the User Interface (GUI)

All graphical elements, sliders, buttons, and visual logic live in `src/gui/`. OmenCtl uses GTK4 and Libadwaita.

### 1. I want to change the Fan Curve editor or add a new Fan Mode button
**File:** `src/gui/pages/fan_page.py`
- **What to do:** Locate the `_build_ui()` method. Here you will find the GTK `Adw.PreferencesGroup` that constructs the buttons. 
- **Action:** If you add a new mode button (e.g., "Turbo"), you must bind its `connect("clicked", ...)` signal to a method that fires `self.services["fan"].SetFanMode("turbo")`.

### 2. I want to add a new CPU Undervolting slider or Power Limit entry
**File:** `src/gui/pages/power_page.py`
- **What to do:** Locate the `Gtk.Scale` objects for Core Voltage and Cache Voltage. 
- **Action:** If you want to add a slider for *System Agent Voltage*, copy the existing GTK Scale logic, and ensure its `value-changed` signal sends the new value via `self.services["power"].SetUndervolt(...)`.

### 3. I want to change the Tray Icon's right-click menu
**File:** `src/omen-tray.py`
- **What to do:** This file builds the `pystray` icon. Locate the `pystray.Menu(...)` array around line 200.
- **Action:** To add a "Quit" button or a new "Eco Mode" option, append a `pystray.MenuItem("Eco Mode", set_power_eco)` to the tuple.

---

## Scenario B: Modifying Hardware Logic (Daemon)

When the GUI sends a command, it is caught by the Daemon running as root. All hardware abstractions live in `src/daemon/`.

### 1. I want to change how the Custom Fan Curve calculates speed
**File:** `src/daemon/services/fan_service.py`
- **What to do:** Locate the `_curve_fan_pct()` method.
- **Action:** Currently, it uses a linear spline interpolation (`scipy` style math) across a 15-sample moving average deadband. If you want to change it to a step-function or exponential curve, modify the math in this exact function.

### 2. I want to change how often the background service polls WMI (The Tick Rate)
**File:** `src/daemon/services/fan_service.py`
- **What to do:** Locate the `_monitor_loop()` thread function.
- **Action:** Change `time.sleep(2.0)` to `time.sleep(5.0)` if you want to reduce battery usage, or `time.sleep(0.5)` if you want highly aggressive thermal polling.

### 3. I want to add a new RGB Animation (e.g., "Matrix Rain")
**File:** `src/daemon/services/rgb_service.py`
- **What to do:** Locate the `_animation_loop()` thread.
- **Action:** Create a new `elif mode == "matrix":` block. You must write a mathematical function that outputs a 12-byte array (4 zones x 3 RGB values) and call `self._rgb.set_zones(zones)` in a `time.sleep(0.033)` loop to achieve 30 FPS.

---

## Scenario C: Adding Support for a New Laptop Model

HP frequently releases new Board IDs. If a user says "Power Tuning is greyed out" or "Fans don't spin," it means the capability mapper doesn't recognize their motherboard.

### Adding a new Board ID
**File:** `src/daemon/common/capabilities.py`

1. Ask the user to run: `cat /sys/class/dmi/id/board_name`. (Let's say it returns `8E35`).
2. Open the file and locate the `KNOWN_MODELS` dictionary.
3. Add a new entry:
   ```python
   "8E35": ModelCapabilities(
       "8E35", 
       "OMEN MAX 16t", 
       has_mux_switch=True, 
       supports_fan_control_ec=True, # Set to False if EC writing causes a system crash!
       supports_undervolt=True
   ),
   ```
4. Restart the daemon. The UI will dynamically un-hide the MUX switch and Undervolt pages based on these boolean flags.

---

## Scenario D: Modifying Deep Hardware / EC Access

If you are reverse-engineering a new ACPI method or finding a new EC offset for a broken laptop model.

### 1. Writing to a new Embedded Controller (EC) Register
**File:** `src/daemon/common/ec_controller.py`
- **What to do:** Let's say you discovered that writing `0x01` to `0x88` turns on Max Fans on a 2025 OMEN.
- **Action:** Add `REG_NEW_FAN_BOOST = 0x88`. Then create a method `def set_new_fan_boost(): self.write_byte(REG_NEW_FAN_BOOST, 0x01)`. Make sure to bypass the `is_unsafe_ec_model` lock if you are testing.

### 2. Hunting for new WMI / ACPI Methods
**File:** `src/daemon/common/acpi_mapper.py`
- **What to do:** This utility automatically dumps the DSDT table from `/sys/firmware/acpi/tables/DSDT`, decompiles it using `iasl`, and regex searches for `PNP0C14` WMI GUIDs.
- **Action:** If you are hunting for a new GPU Power limit method, add your regex string to `INTERESTING_METHODS` dictionary in this file to automate the search across different user machines.
