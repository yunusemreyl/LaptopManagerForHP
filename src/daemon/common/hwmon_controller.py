#!/usr/bin/env python3
"""
OMEN Command Center for Linux — HwMon Controller.

Linux hwmon sensor interface for temperature monitoring.
Reads from /sys/class/hwmon/* to get CPU and GPU temperatures.
This is preferred over EC-based temperature reading when available.
"""

import os
import glob
import time
import logging
import threading

logger = logging.getLogger("hwmon_controller")

HWMON_PATH = "/sys/class/hwmon"
THERMAL_ZONE_PATH = "/sys/class/thermal"
MIN_TEMP_C = 1.0
MAX_TEMP_C = 115.0

# HP WMI hwmon is primarily a fan/power driver; its thermal sensors are
# often bogus (returning -273000 millidegrees = 0 Kelvin). We still
# register it as a fallback but give real CPU sensors higher priority.
_HP_WMI_DRIVER_NAMES = {"hp", "hp-omen", "hp_wmi"}


class LinuxHwMonController:
    def __init__(self):
        self._lock = threading.Lock()
        self._cpu_sensor_paths = []
        self._gpu_sensor_paths = []
        self._sensor_failure_count = {}
        self._max_failures_before_skip = 5
        self._last_full_scan = 0.0
        self._rescan_interval = 300.0  # 5 minutes
        
        self.discover_sensors()

    @property
    def has_cpu_sensor(self):
        with self._lock:
            return len(self._cpu_sensor_paths) > 0

    @property
    def has_gpu_sensor(self):
        with self._lock:
            return len(self._gpu_sensor_paths) > 0

    @property
    def available_sensor_count(self):
        with self._lock:
            return len(self._cpu_sensor_paths) + len(self._gpu_sensor_paths)

    def discover_sensors(self):
        with self._lock:
            self._cpu_sensor_paths.clear()
            self._gpu_sensor_paths.clear()
            # Periodically clear failure count so skipped sensors get a retry
            self._sensor_failure_count.clear()
            self._last_full_scan = time.monotonic()
            
            self._discover_hwmon_sensors()
            self._discover_thermal_zones()
        
    def _discover_hwmon_sensors(self):
        if not os.path.exists(HWMON_PATH):
            return

        # Two-pass: real CPU sensors first, HP WMI fallback second.
        # This ensures HP's often-bogus thermal registers don't shadow
        # coretemp / k10temp readings.
        primary_cpu_dirs = []
        fallback_hp_dirs = []

        for hwmon_dir in glob.glob(os.path.join(HWMON_PATH, "hwmon*")):
            name_path = os.path.join(hwmon_dir, "name")
            if not os.path.exists(name_path):
                continue

            try:
                with open(name_path, "r") as f:
                    name = f.read().strip().lower()

                # Primary CPU sensors — reliable drivers
                if any(x in name for x in ["coretemp", "k10temp", "zenpower", "amd_energy", "thinkpad", "acpitz"]):
                    primary_cpu_dirs.append(hwmon_dir)

                # HP WMI / OMEN platform driver — fan/power primary, thermals unreliable
                elif name in _HP_WMI_DRIVER_NAMES:
                    fallback_hp_dirs.append(hwmon_dir)

                # GPU sensors
                if any(x in name for x in ["nvidia", "nouveau", "amdgpu", "radeon"]):
                    self._add_gpu_sensor_paths(hwmon_dir)
            except Exception:
                pass

        for d in primary_cpu_dirs:
            self._add_cpu_sensor_paths(d, is_hp_wmi=False)

        # Only add HP WMI thermals as fallback when no primary sensor found
        if not self._cpu_sensor_paths:
            for d in fallback_hp_dirs:
                self._add_cpu_sensor_paths(d, is_hp_wmi=True)
                
    def _discover_thermal_zones(self):
        if not os.path.exists(THERMAL_ZONE_PATH):
            return
            
        for zone_dir in glob.glob(os.path.join(THERMAL_ZONE_PATH, "thermal_zone*")):
            type_path = os.path.join(zone_dir, "type")
            temp_path = os.path.join(zone_dir, "temp")
            
            if not os.path.exists(type_path) or not os.path.exists(temp_path):
                continue
                
            try:
                with open(type_path, "r") as f:
                    zone_type = f.read().strip().lower()
                    
                # CPU-related thermal zones
                if any(x in zone_type for x in ["x86_pkg", "acpitz", "cpu", "soc"]):
                    if temp_path not in self._cpu_sensor_paths:
                        self._cpu_sensor_paths.append(temp_path)
                        
                # GPU thermal zones
                if any(x in zone_type for x in ["gpu", "nvidia"]):
                    if temp_path not in self._gpu_sensor_paths:
                        self._gpu_sensor_paths.append(temp_path)
            except Exception:
                pass

    def _add_cpu_sensor_paths(self, hwmon_dir, is_hp_wmi=False):
        # Scan all temp*_input files; for HP WMI driver pre-validate that
        # the value is actually in a believable range before registering.
        for temp_file in sorted(glob.glob(os.path.join(hwmon_dir, "temp*_input"))):
            if temp_file in self._cpu_sensor_paths:
                continue
            if is_hp_wmi:
                # Validate that the HP WMI sensor gives a sane temperature
                # before registering it — avoids -273°C phantom sensors.
                t = self._read_temperature_file(temp_file)
                if t is None:
                    continue
            self._cpu_sensor_paths.append(temp_file)

    def _add_gpu_sensor_paths(self, hwmon_dir):
        for suffix in ["temp1_input", "temp2_input"]:
            path = os.path.join(hwmon_dir, suffix)
            if os.path.exists(path) and path not in self._gpu_sensor_paths:
                self._gpu_sensor_paths.append(path)

    def get_cpu_temperature(self):
        """Return the highest valid CPU temperature across all registered sensors.

        Using the *maximum* rather than the first-valid reading avoids
        phantom zeros from stale/uninitialized sensors masking a real hot core.
        """
        with self._lock:
            paths = list(self._cpu_sensor_paths)
        return self._get_max_temperature_reading(paths)

    def get_gpu_temperature(self):
        with self._lock:
            paths = list(self._gpu_sensor_paths)
        return self._get_max_temperature_reading(paths)

    def _should_skip_sensor(self, path):
        with self._lock:
            return self._sensor_failure_count.get(path, 0) >= self._max_failures_before_skip

    def _get_temperature_reading(self, sensor_paths):
        """Return the first valid temperature (legacy, kept for get_all_sensors)."""
        with self._lock:
            should_rescan = (time.monotonic() - self._last_full_scan) > self._rescan_interval

        if should_rescan:
            self.discover_sensors()

        for path in sensor_paths:
            if self._should_skip_sensor(path):
                continue

            temp = self._read_temperature_file(path)
            if temp is not None:
                self._reset_sensor_failure(path)
                return temp

            self._record_sensor_failure(path)

        return None

    def _get_max_temperature_reading(self, sensor_paths):
        """Return the highest valid temperature across all sensors.

        This prevents a stale/zero sensor from hiding a genuinely hot reading,
        and avoids phantom -273°C values from HP WMI bogus registers.
        """
        with self._lock:
            should_rescan = (time.monotonic() - self._last_full_scan) > self._rescan_interval

        if should_rescan:
            self.discover_sensors()

        best = None
        for path in sensor_paths:
            if self._should_skip_sensor(path):
                continue

            temp = self._read_temperature_file(path)
            if temp is not None:
                self._reset_sensor_failure(path)
                if best is None or temp > best:
                    best = temp
            else:
                self._record_sensor_failure(path)

        return best

    def _record_sensor_failure(self, path):
        with self._lock:
            self._sensor_failure_count[path] = self._sensor_failure_count.get(path, 0) + 1

    def _reset_sensor_failure(self, path):
        with self._lock:
            self._sensor_failure_count[path] = 0

    def _read_temperature_file(self, path):
        """Read a hwmon temp*_input file and return °C, or None if bogus.

        Rejects:
        - Values ≤ 0°C (includes -273°C = 0 Kelvin from HP WMI BIOS bug)
        - Values above MAX_TEMP_C (runaway/corrupted register)
        - Non-numeric content
        """
        try:
            if not os.path.exists(path):
                return None

            with open(path, "r") as f:
                content = f.read().strip()

            # Accept only digit-only strings (positive millidegrees).
            # A negative millidegree value like "-273000" means the sensor
            # is uninitialized or reporting absolute-zero — reject it.
            if not content.lstrip('-').isdigit():
                return None

            value = int(content)
            if value <= 0:
                # Covers -273000 (0 Kelvin phantom) and uninitialized 0
                return None

            temperature = value / 1000.0
            if MIN_TEMP_C <= temperature <= MAX_TEMP_C:
                return temperature
        except Exception:
            pass
        return None

    def get_all_sensors(self):
        results = []
        if not os.path.exists(HWMON_PATH):
            return results
            
        for hwmon_dir in glob.glob(os.path.join(HWMON_PATH, "hwmon*")):
            name = "unknown"
            try:
                name_path = os.path.join(hwmon_dir, "name")
                if os.path.exists(name_path):
                    with open(name_path, "r") as f:
                        name = f.read().strip()
            except Exception:
                pass
                
            for temp_file in glob.glob(os.path.join(hwmon_dir, "temp*_input")):
                try:
                    with open(temp_file, "r") as f:
                        content = f.read().strip()
                        if content.isdigit() or (content.startswith('-') and content[1:].isdigit()):
                            millidegrees = int(content)
                            label = os.path.basename(temp_file).replace("_input", "")
                            results.append({
                                "name": name,
                                "label": label,
                                "temp": millidegrees / 1000.0
                            })
                except Exception:
                    pass
                    
        return results
