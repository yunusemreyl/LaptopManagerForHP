# Source Code & Method Reference

This document provides an in-depth breakdown of the most critical classes and methods within the OmenCtl codebase. It explains **what** each method does, **why** it was written (its purpose), and **what is expected** (inputs/outputs).

---

## 1. Embedded Controller (`src/daemon/common/ec_controller.py`)

The `LinuxEcController` class is responsible for direct memory manipulation of the laptop's Embedded Controller.

### `_ensure_ec_sys(self)`
- **What it does:** Attempts to mount `debugfs` and load the kernel module `ec_sys` with the `write_support=1` parameter.
- **Purpose:** By default, Linux does not allow writing to the Embedded Controller because it is extremely dangerous. This method forcefully bypasses those limits so OmenCtl can send fan curves and thermal profiles on legacy laptops.
- **Expectations:** Expects root privileges. It checks for Kernel Lockdown (e.g., Secure Boot). If lockdown is active, it degrades gracefully and disables EC access to prevent the app from crashing.

### `read_byte(self, reg: int) -> int` / `write_byte(self, reg: int, val: int) -> bool`
- **What it does:** Opens `/sys/kernel/debug/ec/ec0/io` as a binary file, seeks to the specific offset (`reg`), and reads/writes exactly 1 byte.
- **Purpose:** The core I/O abstraction. It wraps the operation in a `threading.Lock()` to ensure that if two threads (e.g., RGB service and Fan service) try to talk to the EC at the exact same millisecond, they don't corrupt the I/O bus.
- **Expectations:** Expects an integer offset (e.g., `0x57`). Returns an integer (for read) or boolean (for write success).

### `set_perf_mode(self, mode: str) -> bool`
- **What it does:** Translates a string mode like `"performance"` into an EC hex value (`0x31`) and writes it to `0x95` (or the fallback `0x59`).
- **Purpose:** Some specific laptops (like the Victus 8E35) have broken ACPI WMI tables where the standard performance mode toggle fails silently. This method was written specifically to provide an undocumented hardware fallback for those broken boards.
- **Expectations:** Expects a mode string. Returns `True` if the write succeeded.

---

## 2. Fan Daemon (`src/daemon/services/fan_service.py`)

The Fan Service handles the D-Bus endpoints and the background thermal intelligence.

### `_monitor_loop(self)`
- **What it does:** An infinite `while True:` thread loop that ticks every 2 seconds. It reads the maximum CPU/GPU temperature, evaluates the custom fan curve, and writes the new RPM targets to the hardware.
- **Purpose:** To act as the brain of the custom fan curve feature. Since the BIOS fan curve is overridden, if this loop stops, the fans would freeze at their current speed and the laptop would melt. 
- **Expectations:** Expects to never block or crash. It constantly updates `self._fan_cache` so that the GUI can fetch the data asynchronously without hitting the hardware.

### `_curve_fan_pct(self, curve_data, current_temp) -> int`
- **What it does:** Calculates the required fan speed percentage for a given temperature using linear interpolation across the points defined in `curve_data` (e.g., `[[40, 30], [80, 100]]`).
- **Purpose:** To smooth out the fan speeds. It includes a **15-sample moving average history** (`self._temp_history`). If the CPU spikes to 90°C for half a second and drops back to 50°C, the moving average prevents the fans from nervously spinning up to 100% and back down.
- **Expectations:** Expects an array of temperature-percentage pairs and a float temperature. Returns an integer `0-100` representing the target fan PWM.

### `GetFanInfo(self) -> str`
- **What it does:** A D-Bus exposed method. It locks the cache, creates a deep copy of the `_fan_cache` dictionary, dynamically fetches the *latest* current and target fan RPMs from `hp-wmi`, and returns it as a JSON string.
- **Purpose:** To provide the GUI with real-time telemetry. By only fetching RPMs *inside* this method (which is only called when the GUI is actively open), it prevents the background daemon from spamming the WMI driver with queries when the laptop is idle.
- **Expectations:** Returns a JSON string.

---

## 3. RGB Lighting Engine (`src/daemon/services/rgb_service.py`)

### `_animation_loop(self)`
- **What it does:** A high-frequency (30 FPS) thread that calculates sine waves for colors and pushes the calculated RGB values to the keyboard hardware.
- **Purpose:** Omen keyboards do not have an onboard animation controller for complex effects like "Wave" or "Cycle". To make the keyboard animate smoothly, this loop acts as a software GPU, rendering the color frames in real-time.
- **Expectations:** Uses `time.sleep(0.033)` to maintain exactly ~30 frames per second. It packs exactly 12 bytes (4 zones × 3 colors) to avoid I2C bus overhead.

### `hsl_to_rgb(self, h, s, l) -> tuple`
- **What it does:** Converts Hue, Saturation, and Lightness floats (0.0 - 1.0) into 8-bit RGB integers (0 - 255).
- **Purpose:** Essential for the "Cycle" and "Wave" animations, where shifting the Hue mathematically across the color wheel is significantly easier and smoother than calculating RGB gradients.
- **Expectations:** Fast execution. It avoids complex Python libraries, relying purely on built-in math to prevent frame stuttering.

---

## 4. Power & Tuning (`src/daemon/services/power_service.py`)

### `apply_power_limits(self)`
- **What it does:** Depending on the CPU vendor (Intel vs AMD), it invokes third-party binaries or shell commands. For AMD, it executes `ryzenadj --stapm-limit=X --fast-limit=Y`. For Intel, it executes `undervolt --core X --cache Y`.
- **Purpose:** To give the user direct hardware-level control over power consumption. By integrating RyzenAdj and Undervolt, OmenCtl abstracts away the complex command-line arguments into simple GUI sliders.
- **Expectations:** Expects the underlying tools (`ryzenadj` or `undervolt`) to be installed in the system `PATH`. If they fail, it logs the stderr silently without crashing the main Daemon.
