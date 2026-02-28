#!/usr/bin/env python3
"""
Fan & Power Control Page — v4.6 with i18n.
"""
import os, json, subprocess, shutil, glob, threading, time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
# CircularGauge integration removed as per instruction
from widgets.fan_curve import FanCurveWidget
import cairo
import math

class FanSparkline(Gtk.DrawingArea):
    def __init__(self, color, history_len=60):
        super().__init__()
        self.set_size_request(-1, 30)
        self.color = color
        self.history_len = history_len
        self.history = [0] * history_len
        self._dark = True
        self.set_draw_func(self._draw)

    def set_dark(self, is_dark):
        self._dark = is_dark
        self.queue_draw()

    def add_value(self, val):
        self.history.pop(0)
        self.history.append(val)
        self.queue_draw()

    def _draw(self, _, cr, w, h):
        cr.set_line_width(2)
        cr.set_line_cap(1)
        cr.set_line_join(1)
        
        max_val = max(max(self.history), 100) # prevent div by 0 and give baseline scale
        
        # Draw gradient under the line
        cr.save()
        pattern = cairo.LinearGradient(0, 0, 0, h)
        if self._dark:
            pattern.add_color_stop_rgba(0, self.color[0], self.color[1], self.color[2], 0.3)
            pattern.add_color_stop_rgba(1, self.color[0], self.color[1], self.color[2], 0.0)
        else:
            pattern.add_color_stop_rgba(0, self.color[0], self.color[1], self.color[2], 0.2)
            pattern.add_color_stop_rgba(1, self.color[0], self.color[1], self.color[2], 0.0)
            
        cr.set_source(pattern)

        dx = w / (self.history_len - 1)
        cr.move_to(0, h)
        
        for i, val in enumerate(self.history):
            x = i * dx
            y = h - (val / max_val) * (h - 2)
            cr.line_to(x, y)
            
        cr.line_to(w, h)
        cr.close_path()
        cr.fill()
        cr.restore()
        
        # Draw line graph
        cr.set_source_rgb(*self.color)
        for i, val in enumerate(self.history):
            x = i * dx
            y = h - (val / max_val) * (h - 2)
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()
        
        # Draw dot on current value
        current_y = h - (self.history[-1] / max_val) * (h - 2)
        cr.arc(w - 2, current_y, 3, 0, 2 * math.pi)
        if self._dark:
            cr.set_source_rgb(1, 1, 1)
        else:
            cr.set_source_rgb(*self.color)
        cr.fill()

class RotatingFanWidget(Gtk.DrawingArea):
    def __init__(self, size=160):
        super().__init__()
        self.set_size_request(size, size)
        self.val = 0
        self.txt = "0 RPM"
        self.rotation = 0.0
        self.fan_surface = None
        self._dark = True
        
        # Path fixed: src/gui/pages -> .. -> .. -> .. -> images
        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "images", "fanpage.png")
        if os.path.exists(img_path):
            try:
                self.fan_surface = cairo.ImageSurface.create_from_png(img_path)
            except Exception as e:
                print(f"Failed to load fan image: {e}")
                
        self.set_draw_func(self._draw)

    def set_val(self, value, text):
        self.val = value
        self.txt = text
        self.queue_draw()

    def set_dark(self, is_dark):
        self._dark = is_dark
        self.queue_draw()
        
    def tick_rotation(self, max_rpm=6000):
        if not self.fan_surface or self.val <= 0:
            return
            
        try:
            rpm = int(''.join(c for c in self.txt if c.isdigit()))
        except ValueError:
            rpm = (self.val / 100) * max_rpm
            
        if rpm > 0:
            base_increment = 0.1
            scale = rpm / max_rpm
            self.rotation += base_increment + (0.3 * scale)
            if self.rotation >= 2 * math.pi:
                self.rotation -= 2 * math.pi
            self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2
        r = min(cx, cy) - 10

        if self.fan_surface is not None:
            cr.save()
            cr.translate(cx, cy)
            cr.rotate(self.rotation)
            
            img_w = self.fan_surface.get_width()
            img_h = self.fan_surface.get_height()
            
            scale_x = (r * 2) / img_w
            scale_y = (r * 2) / img_h
            scale = min(scale_x, scale_y)
            
            cr.scale(scale, scale)
            cr.set_source_surface(self.fan_surface, -img_w / 2, -img_h / 2)
            
            opacity = 0.3 if self.val == 0 else 0.5 + (0.5 * (self.val / 100))
            if self._dark:
                cr.paint_with_alpha(opacity)
            else:
                # Tint image purely black for light backgrounds
                cr.save()
                cr.paint_with_alpha(opacity)
                cr.set_source_rgba(0, 0, 0, 1.0)
                cr.set_operator(cairo.OPERATOR_SOURCE)
                cr.mask_surface(self.fan_surface, -img_w / 2, -img_h / 2)
                cr.restore()
        else:
            # Fallback circle if no image
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            if self._dark:
                cr.set_source_rgba(1, 1, 1, 0.2)
            else:
                cr.set_source_rgba(0, 0, 0, 0.2)
            cr.fill()

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
        except Exception:
            pass
    return None


class SystemMonitor(threading.Thread):
    def __init__(self, service_provider):
        super().__init__(daemon=True)
        self.service_provider = service_provider
        self.running = True
        self.lock = threading.Lock()
        self.data = {
            "cpu_temp": 0.0,
            "gpu_temp": 0.0,
            "fan_info": dict(),
            "power_profile": dict(),
            "all_sensors": [],
        }

    def run(self):
        while self.running:
            c, g = 0.0, 0.0
            fi, pp, si = {}, {}, {}
            service = self.service_provider()
            
            if service:
                try: 
                    si = json.loads(service.GetSystemInfo())
                    c = si.get("cpu_temp", 0.0)
                    g = si.get("gpu_temp", 0.0)
                except Exception: pass
                
                try: fi = json.loads(service.GetFanInfo())
                except Exception: pass
                
                try: pp = json.loads(service.GetPowerProfile())
                except Exception: pass

            sensors = self._get_all_sensors()

            with self.lock:
                self.data["cpu_temp"] = c
                self.data["gpu_temp"] = g
                self.data["fan_info"] = fi
                self.data["power_profile"] = pp
                self.data["all_sensors"] = sensors
                
            time.sleep(2.5)

    def _get_all_sensors(self):
        sensors = []
        try:
            for d in sorted(os.listdir("/sys/class/hwmon")):
                path = os.path.join("/sys/class/hwmon", d)
                name = "unknown"
                try:
                    with open(os.path.join(path, "name")) as f:
                        name = f.read().strip()
                except Exception: continue

                for tf in sorted(glob.glob(os.path.join(path, "temp*_input"))):
                    try:
                        with open(tf) as f:
                            temp = int(f.read().strip()) / 1000
                        label_file = tf.replace("_input", "_label")
                        try:
                            with open(label_file) as f:
                                label = f.read().strip()
                        except Exception:
                            label = os.path.basename(tf).replace("_input", "")
                        sensors.append({"driver": name, "label": label, "temp": temp})
                    except Exception: pass
        except Exception: pass
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
        self._anim_timer = GLib.timeout_add(33, self._anim_tick)

    def _anim_tick(self):
        self.fan1_gauge.tick_rotation()
        self.fan2_gauge.tick_rotation()
        return True

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
        self.fan1_spark.set_dark(is_dark)
        self.fan2_spark.set_dark(is_dark)

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


        

        h_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 20)
        h_box.set_homogeneous(True)
        h_box.set_margin_top(40)
        h_box.set_margin_bottom(40)

        # Fan 1 (CPU)
        f1_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
        f1_box.set_halign(Gtk.Align.CENTER)
        f1_box.append(Gtk.Label(label="CPU Fan", css_classes=["fan-title"]))
        self.fan1_gauge = RotatingFanWidget(160)
        f1_box.append(self.fan1_gauge)
        self.fan1_rpm_lbl = Gtk.Label(label="0 RPM", css_classes=["stat-rpm"])
        f1_box.append(self.fan1_rpm_lbl)
        self.fan1_spark = FanSparkline((0.3, 0.6, 1.0))
        self.fan1_spark.set_size_request(120, 30)
        f1_box.append(self.fan1_spark)
        h_box.append(f1_box)

        # Temps (Central Circle)
        temp_center_container = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        temp_center_container.set_halign(Gtk.Align.CENTER)
        temp_center_container.set_valign(Gtk.Align.CENTER)
        
        temp_circle = Gtk.Box.new(Gtk.Orientation.VERTICAL, 15)
        temp_circle.set_halign(Gtk.Align.CENTER)
        temp_circle.set_valign(Gtk.Align.CENTER)
        temp_circle.add_css_class("temp-circle")
        
        cpu_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        cpu_box.set_halign(Gtk.Align.CENTER)
        self.cpu_label = Gtk.Label(label="--°C", css_classes=["stat-big"])
        cpu_box.append(self.cpu_label)
        self.cpu_name = Gtk.Label(label="CPU", css_classes=["stat-lbl"])
        cpu_box.append(self.cpu_name)
        temp_circle.append(cpu_box)

        sep = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        sep.set_size_request(60, -1)
        temp_circle.append(sep)

        gpu_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        gpu_box.set_halign(Gtk.Align.CENTER)
        self.gpu_label = Gtk.Label(label="--°C", css_classes=["stat-big"])
        gpu_box.append(self.gpu_label)
        self.gpu_name = Gtk.Label(label="GPU", css_classes=["stat-lbl"])
        gpu_box.append(self.gpu_name)
        temp_circle.append(gpu_box)
        
        temp_center_container.append(temp_circle)
        h_box.append(temp_center_container)

        # Fan 2 (GPU)
        f2_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
        f2_box.set_halign(Gtk.Align.CENTER)
        f2_box.append(Gtk.Label(label="GPU Fan", css_classes=["fan-title"]))
        self.fan2_gauge = RotatingFanWidget(160)
        f2_box.append(self.fan2_gauge)
        self.fan2_rpm_lbl = Gtk.Label(label="0 RPM", css_classes=["stat-rpm"])
        f2_box.append(self.fan2_rpm_lbl)
        self.fan2_spark = FanSparkline((0.9, 0.4, 0.1))
        self.fan2_spark.set_size_request(120, 30)
        f2_box.append(self.fan2_spark)
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

        self.sensor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.sensor_box.set_valign(Gtk.Align.START)
        self.sensor_box.set_hexpand(True)
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
        # Clear child widgets (in GTK4 Box, we use get_first_child and get_next_sibling or similar)
        while True:
            child = self.sensor_box.get_first_child()
            if child is None: break
            self.sensor_box.remove(child)
        if not sensors:
            self.sensor_box.append(Gtk.Label(label=T("no_sensor"), css_classes=["stat-lbl"]))
            return
        cats = {"CPU": [], "GPU": [], "Diğer": []}
        for s in sensors:
            lbl = s["label"].lower()
            dr = s["driver"].lower()
            
            # User specifically noted 'Package id 0' represents their RTX 4050 sensor reading
            if "package id 0" in lbl:
                cats["GPU"].append(s)
            elif "core" in lbl or "cpu" in lbl or "tctl" in lbl:
                cats["CPU"].append(s)
            elif "gpu" in lbl or "edge" in lbl or "junction" in lbl or "nouveau" in dr or "amdgpu" in dr or "nvidia" in dr:
                cats["GPU"].append(s)
            else:
                cats["Diğer"].append(s)

        main_grid = Gtk.Grid(column_spacing=20, column_homogeneous=True)
        main_grid.set_hexpand(True)
        
        def create_pill(title_text, items):
            if not items: return None
            pill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            pill.add_css_class("card")
            pill.set_hexpand(True)
            
            title_lbl = Gtk.Label(label=title_text, xalign=0, css_classes=["stat-big"])
            title_lbl.set_margin_bottom(5)
            pill.append(title_lbl)
            
            for s in items:
                row = Gtk.Box(spacing=10)
                driver_lbl = Gtk.Label(label=s["driver"], css_classes=["stat-lbl"], xalign=0)
                driver_lbl.set_size_request(80, -1)
                row.append(driver_lbl)
                row.append(Gtk.Label(label=s["label"], hexpand=True, xalign=0, css_classes=["stat-lbl"]))
                temp_val = self._format_temp(s['temp'])
                temp_lbl = Gtk.Label(label=temp_val, xalign=1)
                temp_lbl.add_css_class("stat-big" if s["temp"] > 80 else "stat-lbl")
                row.append(temp_lbl)
                pill.append(row)
            return pill

        def _sort_cpu(item):
            lbl = item["label"].lower()
            if lbl.startswith("core"):
                import re
                m = re.search(r'\d+', lbl)
                if m:
                    return (0, int(m.group()))
            return (1, lbl)

        cats["CPU"].sort(key=_sort_cpu)

        cpu_pill = create_pill("CPU", cats["CPU"])
        if cpu_pill:
            cpu_pill.set_vexpand(True)
            main_grid.attach(cpu_pill, 0, 0, 1, 1)

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        right_box.set_hexpand(True)
        
        gpu_pill = create_pill("GPU", cats["GPU"])
        if gpu_pill:
            right_box.append(gpu_pill)
            
        diger_pill = create_pill("Diğer", cats["Diğer"])
        if diger_pill:
            diger_pill.set_vexpand(True)
            right_box.append(diger_pill)
            
        main_grid.attach(right_box, 1, 0, 1, 1)

        self.sensor_box.append(main_grid)

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
                    last = self.last_applied_rpm.get(str(fn), -1)
                    if last >= 0 and abs(target_rpm - last) < 300:
                        continue

                    self.service.SetFanTarget(int(str(fn)), target_rpm)
                    self.last_applied_rpm[str(fn)] = target_rpm
            except Exception as e:
                print(f"Fan control error: {e}")

    def _refresh(self):
        if not self.get_mapped():
            return True
            
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
                self.fan1_spark.add_value(rpm1)
            if "2" in fans:
                rpm2 = fans["2"].get("current", 0)
                max2 = fans["2"].get("max", 5800)
                pct2 = min(rpm2 / max2 * 100, 100) if max2 > 0 else 0
                self.fan2_gauge.set_val(pct2, f"{rpm2}")
                self.fan2_rpm_lbl.set_label(f"{rpm2} RPM")
                self.fan2_spark.add_value(rpm2)
        else:
            self.fan_warning.set_visible(True)

        if self._sensors_expanded:
            self._update_sensor_list(data.get("all_sensors", []))
            
        return True

    def cleanup(self):
        if hasattr(self, '_timer') and self._timer:
            GLib.source_remove(self._timer)
        if hasattr(self, '_anim_timer') and self._anim_timer:
            GLib.source_remove(self._anim_timer)
        self.monitor.stop()
