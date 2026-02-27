#!/usr/bin/env python3
"""
Fan & Power Control Page — v4.5 with i18n.
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
        self.temp_unit = "C"  # "C" or "F"
        
        # Stability vars
        self.temp_history = []
        self.last_applied_rpm = {} # {fan_idx: rpm}
        
        self._block_sync = False  # Prevents UI reverting due to stale cached data

        self.monitor = SystemMonitor(lambda: self.service)
        self.monitor.start()

        self._build_ui()
        self._timer = GLib.timeout_add(1000, self._refresh)

    def set_service(self, service):
        self.service = service

    def set_temp_unit(self, unit):
        self.temp_unit = unit

    def _format_temp(self, celsius):
        """Format temperature value for display in the user's preferred unit."""
        if self.temp_unit == "F":
            return f"{int(celsius * 9 / 5 + 32)}°F"
        return f"{int(celsius)}°C"

    def set_dark(self, is_dark):
        self.fan1_gauge.set_dark(is_dark)
        self.fan2_gauge.set_dark(is_dark)

    def _build_ui(self):
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_top(30)
        content.set_margin_start(40)
        content.set_margin_end(40)
        content.set_margin_bottom(30)

        title = Gtk.Label(label=T("fan_control"), xalign=0)
        title.add_css_class("page-title")
        content.append(title)

        # ═══ 1. SYSTEM STATUS CARD ═══
        fan_temp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        fan_temp_card.add_css_class("card")

        ft_header = Gtk.Box(spacing=10)
        ft_header.append(Gtk.Image.new_from_icon_name("weather-tornado-symbolic"))
        ft_header.append(Gtk.Label(label=T("system_status"), css_classes=["section-title"]))
        fan_temp_card.append(ft_header)

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, homogeneous=True)

        # Fan 1
        f1_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
        self.fan1_gauge = CircularGauge("CPU Fan", (0.3, 0.6, 1.0), 160)
        f1_box.append(self.fan1_gauge)
        self.fan1_rpm_lbl = Gtk.Label(label="0 RPM", css_classes=["stat-lbl"])
        f1_box.append(self.fan1_rpm_lbl)
        h_box.append(f1_box)

        # Temps
        temp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, halign=Gtk.Align.CENTER)
        cpu_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        cpu_icon.set_pixel_size(24)
        cpu_box.append(cpu_icon)
        self.cpu_label = Gtk.Label(label="--°C", css_classes=["stat-big"])
        cpu_box.append(self.cpu_label)
        self.cpu_name = Gtk.Label(label="CPU", css_classes=["stat-lbl"])
        cpu_box.append(self.cpu_name)
        temp_box.append(cpu_box)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_size_request(100, -1)
        temp_box.append(sep)

        gpu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, halign=Gtk.Align.CENTER)
        gpu_icon = Gtk.Image.new_from_icon_name("video-display-symbolic")
        gpu_icon.set_pixel_size(24)
        gpu_box.append(gpu_icon)
        self.gpu_label = Gtk.Label(label="--°C", css_classes=["stat-big"])
        gpu_box.append(self.gpu_label)
        self.gpu_name = Gtk.Label(label="GPU", css_classes=["stat-lbl"])
        gpu_box.append(self.gpu_name)
        temp_box.append(gpu_box)
        h_box.append(temp_box)

        # Fan 2
        f2_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
        self.fan2_gauge = CircularGauge("GPU Fan", (0.9, 0.4, 0.1), 160)
        f2_box.append(self.fan2_gauge)
        self.fan2_rpm_lbl = Gtk.Label(label="0 RPM", css_classes=["stat-lbl"])
        f2_box.append(self.fan2_rpm_lbl)
        h_box.append(f2_box)

        fan_temp_card.append(h_box)

        self.fan_warning = Gtk.Label(label=T("fan_disabled"), css_classes=["warning-text"])
        self.fan_warning.set_visible(False)
        fan_temp_card.append(self.fan_warning)

        # Sensor expander
        expander_btn = Gtk.Button()
        expander_btn.add_css_class("flat")
        self._expander_arrow = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        self._expander_arrow.set_pixel_size(16)
        exp_box = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        exp_box.append(self._expander_arrow)
        self._sensor_label = Gtk.Label(label=T("all_sensors"), css_classes=["stat-lbl"])
        exp_box.append(self._sensor_label)
        expander_btn.set_child(exp_box)
        expander_btn.connect("clicked", self._toggle_sensors)
        fan_temp_card.append(expander_btn)

        self.sensor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.sensor_box.set_visible(False)
        self.sensor_box.set_margin_top(10)
        fan_temp_card.append(self.sensor_box)
        content.append(fan_temp_card)

        # ═══ 2. PERFORMANCE CARD ═══
        perf_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        perf_card.add_css_class("card")

        pp_header = Gtk.Box(spacing=10)
        pp_header.append(Gtk.Image.new_from_icon_name("battery-level-80-symbolic"))
        pp_header.append(Gtk.Label(label=T("power_profile"), css_classes=["section-title"]))
        perf_card.append(pp_header)

        self.profile_box = Gtk.Box(spacing=15, halign=Gtk.Align.CENTER, homogeneous=True)
        self.profile_group = None
        profiles = [
            ("power-saver", "🔋", T("saver")),
            ("balanced", "⚖️", T("balanced")),
            ("performance", "🚀", T("performance")),
        ]
        self.profile_buttons = {}
        for pid, emoji, label in profiles:
            btn = Gtk.ToggleButton()
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            btn_box.set_margin_top(14)
            btn_box.set_margin_bottom(14)
            btn_box.set_margin_start(20)
            btn_box.set_margin_end(20)
            btn_box.append(Gtk.Label(label=emoji, css_classes=["profile-emoji"]))
            btn_box.append(Gtk.Label(label=label, css_classes=["profile-label"]))
            btn.set_child(btn_box)
            btn.add_css_class("profile-btn")
            if self.profile_group:
                btn.set_group(self.profile_group)
            else:
                self.profile_group = btn
            btn.connect("toggled", lambda w, p=pid: self._set_profile(p) if w.get_active() else None)
            self.profile_box.append(btn)
            self.profile_buttons[pid] = btn

        perf_card.append(self.profile_box)
        self.pp_status = Gtk.Label(label=T("checking"), css_classes=["stat-lbl"])
        perf_card.append(self.pp_status)

        perf_card.append(Gtk.Separator())

        fm_header = Gtk.Box(spacing=10)
        fm_header.append(Gtk.Image.new_from_icon_name("weather-tornado-symbolic"))
        fm_header.append(Gtk.Label(label=T("fan_mode"), css_classes=["section-title"]))
        perf_card.append(fm_header)

        self.mode_selector = Gtk.Box(spacing=0, halign=Gtk.Align.CENTER)
        self.mode_selector.add_css_class("mode-selector-strip")
        self.fan_mode_group = None
        modes = [("standard", T("standard")), ("max", T("max")), ("custom", T("custom"))]
        self.fan_mode_buttons = {}
        for mid, label in modes:
            btn = Gtk.ToggleButton()
            btn.add_css_class("fan-mode-btn")
            btn.set_child(Gtk.Label(label=label))
            if self.fan_mode_group:
                btn.set_group(self.fan_mode_group)
            else:
                self.fan_mode_group = btn
            btn.connect("toggled", lambda w, m=mid: self._on_fan_mode(m) if w.get_active() else None)
            self.mode_selector.append(btn)
            self.fan_mode_buttons[mid] = btn

        perf_card.append(self.mode_selector)
        self.fan_mode_status = Gtk.Label(label="", css_classes=["stat-lbl"])
        perf_card.append(self.fan_mode_status)
        content.append(perf_card)

        # ═══ 3. FAN CURVE ═══
        self.curve_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.curve_card.add_css_class("card")
        self.curve_card.set_visible(False)

        curve_header = Gtk.Box(spacing=10)
        curve_header.append(Gtk.Image.new_from_icon_name("document-edit-symbolic"))
        curve_header.append(Gtk.Label(label=T("fan_curve"), css_classes=["section-title"]))
        self.curve_card.append(curve_header)

        curve_desc = Gtk.Label(label=T("curve_desc"), css_classes=["stat-lbl"], xalign=0, wrap=True)
        self.curve_card.append(curve_desc)

        self.fan_curve = FanCurveWidget()
        self.fan_curve.on_curve_changed = self._on_curve_changed
        self.curve_card.append(self.fan_curve)
        content.append(self.curve_card)

        scroll.set_child(content)
        self.append(scroll)
        
        # Default points backup
        self.default_points = [(48, 0), (58, 35), (70, 60), (78, 72), (85, 100)]
        self.custom_points = list(self.default_points)
        
        # Initial mode set (will be updated by daemon sync)
        self.set_fan_mode_ui("standard")

    def _unblock_sync(self):
        self._block_sync = False
        return False

    def set_fan_mode_ui(self, mode):
        self.fan_mode = mode
        if mode in self.fan_mode_buttons:
            self.fan_mode_buttons[mode].set_active(True)

    def _toggle_sensors(self, btn):
        self._sensors_expanded = not self._sensors_expanded
        self.sensor_box.set_visible(self._sensors_expanded)
        self._expander_arrow.set_from_icon_name(
            "pan-up-symbolic" if self._sensors_expanded else "pan-down-symbolic")

    def _update_sensor_list(self, sensors):
        while True:
            child = self.sensor_box.get_first_child()
            if child is None: break
            self.sensor_box.remove(child)
        if not sensors:
            self.sensor_box.append(Gtk.Label(label=T("no_sensor"), css_classes=["stat-lbl"]))
            return
        for s in sensors:
            row = Gtk.Box(spacing=10)
            driver_lbl = Gtk.Label(label=s["driver"], css_classes=["stat-lbl"], xalign=0)
            driver_lbl.set_size_request(100, -1)
            row.append(driver_lbl)
            row.append(Gtk.Label(label=s["label"], hexpand=True, xalign=0, css_classes=["stat-lbl"]))
            temp_val = self._format_temp(s['temp'])
            temp_lbl = Gtk.Label(label=temp_val, xalign=1)
            temp_lbl.add_css_class("stat-big" if s["temp"] > 80 else "stat-lbl")
            row.append(temp_lbl)
            self.sensor_box.append(row)

    def _set_profile(self, profile):
        if self._block_sync:
            return  # Skip triggering if we are programmatically updating UI
        self._block_sync = True
        GLib.timeout_add(1500, self._unblock_sync)
        if self.service:
            try:
                self.service.SetPowerProfile(profile)
                self.pp_status.set_label(f"{T('active_profile')}: {profile}")
            except Exception as e:
                self.pp_status.set_label(f"{T('error')}: {e}")

    def _on_fan_mode(self, mode):
        self.fan_mode = mode

        # Standard = EC auto control (pwm1_enable=2, no RPM commands)
        # Custom   = software-controlled fan curve (pwm1_enable=1)
        # Max      = hardware max speed (pwm1_enable=0)

        if mode == "standard":
            daemon_mode = "auto"
        elif mode == "custom":
            daemon_mode = "custom"
        else:
            daemon_mode = "max"

        # Curve visibility (only for custom)
        self.curve_card.set_visible(mode == "custom")
        self.fan_curve.set_interactive(mode == "custom")

        if mode == "custom":
            self.fan_curve.set_points(self.custom_points)

        # Clear applied RPM cache when switching modes
        self.last_applied_rpm = {}

        if self._block_sync:
            return # if programmatic UI update, do nothing
        self._block_sync = True
        GLib.timeout_add(1500, self._unblock_sync)

        if self.service:
            try:
                self.service.SetFanMode(daemon_mode)
                labels = {"standard": T("standard"), "max": T("max"), "custom": T("custom")}
                self.fan_mode_status.set_label(f"{T('mode')}: {labels.get(mode, mode)}")
            except Exception as e:
                self.fan_mode_status.set_label(f"{T('error')}: {e}")

        # Only apply fan curve in custom mode (standard delegates to EC)
        if mode == "custom":
            self._apply_fan_curve()

    def _on_curve_changed(self, points):
        if self.fan_mode == "custom":
            self.custom_points = points
            if self._curve_timer:
                GLib.source_remove(self._curve_timer)
            self._curve_timer = GLib.timeout_add(200, self._apply_fan_curve_debounced)

    def _apply_fan_curve_debounced(self):
        self._apply_fan_curve()
        self._curve_timer = None
        return False

    def _apply_fan_curve(self):
        """Apply fan curve — only used in 'custom' mode."""
        if self.fan_mode != "custom":
            return

        if not self.temp_history:
            return

        avg_temp = sum(self.temp_history) / len(self.temp_history)
        fan_pct = self.fan_curve.get_fan_pct_for_temp(avg_temp)

        if self.service:
            try:
                data = self.monitor.get_data()
                info = data.get("fan_info", {})
                fans = info.get("fans", {})

                for fn, fd in fans.items():
                    max_rpm = fd.get("max", 5800)
                    if max_rpm <= 0:
                        max_rpm = 5800

                    target_rpm = int(max_rpm * fan_pct / 100)

                    # Hysteresis: skip if RPM change < 300
                    last = self.last_applied_rpm.get(fn, -1)
                    if last >= 0 and abs(target_rpm - last) < 300:
                        continue

                    self.service.SetFanTarget(int(fn), target_rpm)
                    self.last_applied_rpm[fn] = target_rpm
            except Exception as e:
                print(f"Fan control error: {e}")

    def _refresh(self):
        data = self.monitor.get_data()
        cpu_t = data.get("cpu_temp", 0)
        gpu_t = data.get("gpu_temp", 0)
        fan_info = data.get("fan_info", {})
        power_profile = data.get("power_profile", {})
        
        # Update history
        self.temp_history.append(cpu_t)
        if len(self.temp_history) > 5: # Keep last 5 seconds
            self.temp_history.pop(0)
            
        # Draw current temp marker on curve
        self.fan_curve.set_current_temp(cpu_t)
        
        self.cpu_label.set_label(self._format_temp(cpu_t))
        self.gpu_label.set_label(self._format_temp(gpu_t))

        if self.fan_mode == "custom":
            self._apply_fan_curve()
            
        # Sync Power Profile UI
        active_profile = power_profile.get("active", "")
        if active_profile and active_profile in self.profile_buttons and not self._block_sync:
             btn = self.profile_buttons[active_profile]
             if not btn.get_active():
                 # Temporarily block sync so we don't send the command back to daemon
                 self._block_sync = True
                 btn.set_active(True)
                 self._block_sync = False
        
        if active_profile:
             self.pp_status.set_label(f"{T('active_profile')}: {active_profile}")

        # Sync Fan Data
        available = fan_info.get("available", False)
        if available:
            self.fan_warning.set_visible(False)
            daemon_mode = fan_info.get("mode", "auto")
            
            # Map daemon modes to UI modes
            if not self._block_sync:
                if daemon_mode == "auto" and self.fan_mode != "standard":
                    self._block_sync = True; self.set_fan_mode_ui("standard"); self._block_sync = False
                elif daemon_mode == "max" and self.fan_mode != "max":
                    self._block_sync = True; self.set_fan_mode_ui("max"); self._block_sync = False
                elif daemon_mode == "custom" and self.fan_mode != "custom":
                    self._block_sync = True; self.set_fan_mode_ui("custom"); self._block_sync = False
            
            # Update gauges
            fans = fan_info.get("fans", {})
            if "1" in fans:
                rpm1 = fans["1"].get("current", 0)
                max1 = fans["1"].get("max", 5800)
                pct1 = min(rpm1 / max1 * 100, 100) if max1 > 0 else 0
                self.fan1_gauge.set_val(pct1, f"{rpm1}")
                self.fan1_rpm_lbl.set_label(f"{rpm1} RPM")
            if "2" in fans:
                rpm2 = fans["2"].get("current", 0)
                max2 = fans["2"].get("max", 5800)
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
