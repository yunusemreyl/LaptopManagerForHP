#!/usr/bin/env python3
"""
Fan & Power Control Page — v4.0 with i18n.
"""
import os, json, subprocess, shutil, glob, threading, time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from widgets.circular_gauge import CircularGauge
from widgets.fan_curve import FanCurveWidget


def T(k):
    from i18n import T as _T
    return _T(k)


def _find_hwmon_by_name(name):
    for d in sorted(os.listdir("/sys/class/hwmon")):
        path = os.path.join("/sys/class/hwmon", d)
        nf = os.path.join(path, "name")
        try:
            with open(nf) as f:
                if f.read().strip().lower() == name:
                    return path
        except:
            pass
    return None


class SystemMonitor(threading.Thread):
    def __init__(self, service_provider):
        super().__init__(daemon=True)
        self.service_provider = service_provider
        self.running = True
        self.lock = threading.Lock()
        self.data = {
            "cpu_temp": 0, "gpu_temp": 0,
            "fan_info": {}, "power_profile": {},
            "all_sensors": [],
        }

    def run(self):
        while self.running:
            c = self._get_cpu()
            g = self._get_gpu()
            sensors = self._get_all_sensors()
            fi, pp = {}, {}
            service = self.service_provider()
            if service:
                try: fi = json.loads(service.GetFanInfo())
                except: pass
                try: pp = json.loads(service.GetPowerProfile())
                except: pass

            with self.lock:
                self.data["cpu_temp"] = c
                self.data["gpu_temp"] = g
                self.data["fan_info"] = fi
                self.data["power_profile"] = pp
                self.data["all_sensors"] = sensors
            time.sleep(1.0)

    def _get_cpu(self):
        for driver in ("coretemp", "k10temp"):
            hp = _find_hwmon_by_name(driver)
            if hp:
                try:
                    with open(os.path.join(hp, "temp1_input")) as f:
                        return int(f.read().strip()) / 1000
                except: pass
        hp = _find_hwmon_by_name("acpitz")
        if hp:
            try:
                with open(os.path.join(hp, "temp1_input")) as f:
                    return int(f.read().strip()) / 1000
            except: pass
        return 0

    def _get_gpu(self):
        if shutil.which("nvidia-smi"):
            try:
                return float(subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                    stderr=subprocess.DEVNULL
                ).decode().strip())
            except: pass
        hp = _find_hwmon_by_name("amdgpu")
        if hp:
            try:
                with open(os.path.join(hp, "temp1_input")) as f:
                    return int(f.read().strip()) / 1000
            except: pass
        return 0

    def _get_all_sensors(self):
        sensors = []
        try:
            for d in sorted(os.listdir("/sys/class/hwmon")):
                path = os.path.join("/sys/class/hwmon", d)
                name = "unknown"
                try:
                    with open(os.path.join(path, "name")) as f:
                        name = f.read().strip()
                except: continue

                for tf in sorted(glob.glob(os.path.join(path, "temp*_input"))):
                    try:
                        with open(tf) as f:
                            temp = int(f.read().strip()) / 1000
                        label_file = tf.replace("_input", "_label")
                        try:
                            with open(label_file) as f:
                                label = f.read().strip()
                        except:
                            label = os.path.basename(tf).replace("_input", "")
                        sensors.append({"driver": name, "label": label, "temp": temp})
                    except: pass
        except: pass
        return sensors

    def get_data(self):
        with self.lock:
            return self.data.copy()

    def stop(self):
        self.running = False


class FanPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.service = service
        self.fan_mode = "standard" # Default to standard, will sync later
        self._curve_timer = None
        self._sensors_expanded = False
        
        # Stability vars
        self.temp_history = []
        self.last_applied_rpm = {} # {fan_idx: rpm}

        self.monitor = SystemMonitor(lambda: self.service)
        self.monitor.start()

        self._build_ui()
        self._timer = GLib.timeout_add(1000, self._refresh)

    # ... (other methods unchanged) ...

    def _apply_fan_curve(self):
        # Only apply in software control modes
        if self.fan_mode not in ("standard", "custom"):
            return
            
        if not self.temp_history:
            return

        # Use average temp for stability
        avg_temp = sum(self.temp_history) / len(self.temp_history)
        
        # Calculate target percentage
        fan_pct = 0
        if self.fan_mode == "standard":
            # Stepped logic (User request: "Dümdüz çizgi", Flat lines)
            # < 48: 0
            # 48 - 58: 2000 RPM (~35%)
            # 58 - 70: 3500 RPM (~60%)
            # 70 - 78: 4200 RPM (~72%)
            # 78 - 85: 4200 RPM (72%) (Assuming flat until 85)
            # >= 85: 100%
            if avg_temp < 48:
                fan_pct = 0
            elif avg_temp < 58:
                fan_pct = 35 # ~2000 RPM
            elif avg_temp < 70:
                fan_pct = 60 # ~3500 RPM
            elif avg_temp < 85:
                fan_pct = 72 # ~4200 RPM, keeps flat till 85
            else:
                fan_pct = 100
        else:
            # Custom mode: Use curve widget interpolation
            fan_pct = self.fan_curve.get_fan_pct_for_temp(avg_temp)
        
        if self.service:
            try:
                # We need max rpm to calculate target
                # We can cache this or get from monitor data
                data = self.monitor.get_data()
                info = data.get("fan_info", {})
                fans = info.get("fans", {})
                
                for fn, fd in fans.items():
                    max_rpm = fd.get("max", 5800)
                    if max_rpm <= 0: max_rpm = 5800
                    
                    target_rpm = int(max_rpm * fan_pct / 100)
                    
                    # Hysteresis: Don't change if difference is small (< 300 RPM)
                    # unless we are at very low or very high temps
                    last = self.last_applied_rpm.get(fn, -1)
                    if last >= 0 and abs(target_rpm - last) < 300:
                        continue
                        
                    self.service.SetFanTarget(int(fn), target_rpm)
                    self.last_applied_rpm[fn] = target_rpm
            except Exception as e:
                print(f"Fan control error: {e}")
                pass

    def _refresh(self):
        data = self.monitor.get_data()
        cpu_t = data.get("cpu_temp", 0)
        gpu_t = data.get("gpu_temp", 0)
        
        # Update history
        self.temp_history.append(cpu_t)
        if len(self.temp_history) > 5: # Keep last 5 seconds
            self.temp_history.pop(0)
            
        # Draw current temp marker on curve (use instant or avg? instant is better for visual)
        self.fan_curve.set_current_temp(cpu_t)
        
        self.cpu_label.set_label(f"{int(cpu_t)}°C")
        self.gpu_label.set_label(f"{int(gpu_t)}°C")

        if self.fan_mode in ("standard", "custom"):
            self._apply_fan_curve()
            
        # ... rest of refresh ...

        available = fan_info.get("available", False)
        if available:
            self.fan_warning.set_visible(False)
            daemon_mode = fan_info.get("mode", "auto")
            
            # Map daemon modes to UI modes
            # Daemon 'auto' -> Force to 'standard' (software control)
            # Daemon 'custom' -> 'standard' or 'custom' depending on current
            # Daemon 'max' -> 'max'
            
            target_ui_mode = self.fan_mode
            
            if daemon_mode == "auto":
                # If daemon is in hardware auto, we want to force software standard
                target_ui_mode = "standard"
                if self.fan_mode != "standard":
                     self._on_fan_mode("standard") # Apply standard mode immediately
            elif daemon_mode == "max":
                target_ui_mode = "max"
            elif daemon_mode == "custom":
                # If we are already in standard or custom, stay there
                # If we are in max, default to standard?
                if self.fan_mode not in ("standard", "custom"):
                    target_ui_mode = "standard"
            
            if target_ui_mode != self.fan_mode:
                self.fan_mode = target_ui_mode
                if target_ui_mode in self.fan_mode_buttons:
                     self.fan_mode_buttons[target_ui_mode].set_active(True)
            
            # Update gauges
            fans = fan_info.get("fans", {})
            if "1" in fans:
                rpm1, max1 = fans["1"]["current"], fans["1"]["max"]
                pct1 = min(rpm1 / max1 * 100, 100) if max1 > 0 else 0
                self.fan1_gauge.set_val(pct1, f"{rpm1}")
                self.fan1_rpm_lbl.set_label(f"{rpm1} RPM")
            if "2" in fans:
                rpm2, max2 = fans["2"]["current"], fans["2"]["max"]
                pct2 = min(rpm2 / max2 * 100, 100) if max2 > 0 else 0
                self.fan2_gauge.set_val(pct2, f"{rpm2}")
                self.fan2_rpm_lbl.set_label(f"{rpm2} RPM")
        else:
            self.fan_warning.set_visible(True)

        if self._sensors_expanded:
            self._update_sensor_list(data.get("all_sensors", []))
        return True

    def cleanup(self):
        if hasattr(self, '_timer') and self._timer:
            GLib.source_remove(self._timer)
        self.monitor.stop()
