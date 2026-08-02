#!/usr/bin/env python3
"""
OMEN Gaming Hub Style Consolidated Master Dashboard Redesign
Extremely high-fidelity Cairo drawings that strictly replicate the official 
OMEN Gaming Hub interface, featuring mechanical brackets, speedometer radial ticks,
rounded segmented button tabs, thin flat sliders, and organic connected widgets.
Customizable spacing, enlarged gauges, real-time sensor panel, and Feral GameMode diagnostics.
Features ovalized cards and cTGP, PPAB, and GameMode toggle switches.
"""
import os, json, subprocess, shutil, glob, threading, time, concurrent.futures, math
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GObject
from widgets.smooth_scroll import SmoothScrolledWindow
from widgets.fan_curve import FanCurveWidget
from components.custom_widgets import OmenHighTechGauge, OmenSpecsBridge
from utils.system_monitor import SystemMonitor
import cairo

DEFAULT_MODE_SYNC_DELAY_MS = 1500
CUSTOM_MODE_SYNC_DELAY_MS = 3000
_DBUS_TIMEOUT = 5
_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dbus")

def T(k):
    from i18n import T as _T
    return _T(k)

def _dbus_call(fn, *args, timeout=_DBUS_TIMEOUT):
    """Run a D-Bus proxy call with a timeout to avoid indefinite blocking."""
    fut = _dbus_pool.submit(fn, *args)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        print(f"⚠ D-Bus call timed out after {timeout}s: {fn}")
        return None
    except Exception as e:
        print(f"⚠ D-Bus call failed: {e}")
        return None

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB for the color wheel."""
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (r + m, g + m, b + m)

# ═════════════════════════════════════════════════════════════════════════════
#  HIGH-FIDELITY CAIRO INSTRUMENT PANELS
# ═════════════════════════════════════════════════════════════════════════════

class FanPage(Gtk.Box):
    def __init__(self, service=None, on_profile_change=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        
        self.service = service  # fan service D-Bus proxy
        self._platform_svc = None
        self._power_svc = None
        self._rgb_svc = None
        self.on_profile_change = on_profile_change
        
        self.active_mode = "balanced"  # quiet, balanced, performance, custom
        self.temp_unit = "C"
        self.temp_history = []
        self.last_applied_rpm = {}
        self._block_sync = False
        self._pending_power_mode = None
        self._pending_power_started = 0.0
        self._sensor_labels = {}
        self.is_dark = True
        self.fan_control_level = 0
        self.fan_control_mode = "auto"
        self._fan_mode_synced = False
        self.fan_curve_editor_open = False

        self._css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
        self._update_theme_css(self.is_dark)

        # Monitor Thread
        self.monitor = SystemMonitor(lambda: {
            "fan": self.service,
            "platform": self._platform_svc,
            "power": self._power_svc,
            "rgb": self._rgb_svc,
        })
        self.monitor.start()

        self._build_ui()
        self._timer = None
        self._anim_timer = None
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def _update_theme_css(self, is_dark):
        if is_dark:
            capsule_bg = "rgba(14, 12, 20, 0.85)"
            capsule_border = "rgba(168, 85, 247, 0.16)"
            btn_color = "#8890a0"
            btn_hover_color = "#ffffff"
            btn_hover_bg = "rgba(255, 255, 255, 0.02)"
            btn_checked_bg = "linear-gradient(135deg, rgba(168, 85, 247, 0.35), rgba(236, 72, 153, 0.2))"
            btn_checked_border = "rgba(168, 85, 247, 0.45)"
            btn_checked_shadow = "inset 0 0 8px rgba(168, 85, 247, 0.2), 0 0 12px rgba(168, 85, 247, 0.3)"
            card_bg = "rgba(18, 16, 24, 0.72)"
            card_border = "rgba(168, 85, 247, 0.08)"
            card_shadow = "none"
            card_title_color = "#a0aec0"
            sep_color = "rgba(255, 255, 255, 0.06)"
            slider_bg = "#4a5568"
            bad_active_bg = "rgba(236, 72, 153, 0.12)"
            bad_active_border = "rgba(236, 72, 153, 0.3)"
            bad_inactive_bg = "rgba(255, 255, 255, 0.03)"
            bad_inactive_border = "rgba(255, 255, 255, 0.08)"
            act_btn_bg = "rgba(255, 255, 255, 0.04)"
            act_btn_border = "rgba(255, 255, 255, 0.1)"
            act_btn_color = "#ffffff"
            act_btn_hover_bg = "rgba(255, 255, 255, 0.08)"
            sensor_row_border = "rgba(255, 255, 255, 0.02)"
        else:
            capsule_bg = "rgba(255, 255, 255, 0.85)"
            capsule_border = "rgba(168, 85, 247, 0.25)"
            btn_color = "#475569"
            btn_hover_color = "#000000"
            btn_hover_bg = "rgba(0, 0, 0, 0.03)"
            btn_checked_bg = "linear-gradient(135deg, rgba(168, 85, 247, 0.75), rgba(236, 72, 153, 0.6))"
            btn_checked_border = "rgba(168, 85, 247, 0.85)"
            btn_checked_shadow = "inset 0 0 8px rgba(168, 85, 247, 0.2), 0 0 12px rgba(168, 85, 247, 0.4)"
            card_bg = "rgba(255, 255, 255, 0.85)"
            card_border = "rgba(0, 0, 0, 0.06)"
            card_shadow = "0 4px 16px rgba(0, 0, 0, 0.05)"
            card_title_color = "#334155"
            sep_color = "rgba(0, 0, 0, 0.08)"
            slider_bg = "#cbd5e1"
            bad_active_bg = "rgba(236, 72, 153, 0.18)"
            bad_active_border = "rgba(236, 72, 153, 0.4)"
            bad_inactive_bg = "rgba(0, 0, 0, 0.03)"
            bad_inactive_border = "rgba(0, 0, 0, 0.08)"
            act_btn_bg = "rgba(0, 0, 0, 0.04)"
            act_btn_border = "rgba(0, 0, 0, 0.1)"
            act_btn_color = "#0f172a"
            act_btn_hover_bg = "rgba(0, 0, 0, 0.08)"
            sensor_row_border = "rgba(0, 0, 0, 0.04)"

        css_data = f"""
        .mode-selector-capsule {{
            background-color: {capsule_bg};
            border: 1px solid {capsule_border};
            border-radius: 24px;
            padding: 2px;
            margin: 18px 0;
        }}
        .mode-selector-btn {{
            background: transparent;
            color: {btn_color};
            border: none;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            font-family: "Inter", "Geist", sans-serif;
            padding: 8px 26px;
            transition: all 180ms ease;
            box-shadow: none;
            border-bottom: none;
        }}
        .mode-selector-btn:hover {{
            color: {btn_hover_color};
            background-color: {btn_hover_bg};
        }}
        .mode-selector-btn:checked {{
            color: #ffffff;
            background: {btn_checked_bg};
            box-shadow: {btn_checked_shadow};
            border: 1px solid {btn_checked_border};
        }}
        .fan-control-btn.active {{
            color: #ffffff;
            background: {btn_checked_bg};
            box-shadow: {btn_checked_shadow};
            border: 1px solid {btn_checked_border};
        }}
        .omen-dashboard-card {{
            background-color: {card_bg};
            border: 1px solid {card_border};
            border-radius: 24px; /* Highly ovalized card layout */
            padding: 22px;
            box-shadow: {card_shadow};
        }}
        .omen-dashboard-card separator {{
            background-color: {sep_color};
        }}
        .omen-dashboard-card-title {{
            font-size: 10px;
            font-weight: 800;
            color: {card_title_color};
            letter-spacing: 1.2px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .gaming-switch {{
            background-color: rgba(125, 211, 252, 0.18);
        }}
        .gaming-switch slider {{
            background-color: rgba(186, 230, 253, 0.95);
            border-radius: 99px;
            transition: background-color 180ms ease, box-shadow 180ms ease;
        }}
        .gaming-switch:checked {{
            background-color: rgba(125, 211, 252, 0.42);
        }}
        .gaming-switch:checked slider {{
            background-color: #7dd3fc;
            box-shadow: 0 0 8px rgba(125, 211, 252, 0.75);
        }}
        .fan-control-strip {{
            margin: 6px 0 18px 0;
        }}
        .fan-control-btn {{
            min-width: 0;
        }}
        .sensor-temp-val {{
            font-size: 17px;
            font-weight: 800;
        }}
        .warning-label {{
            color: #ef5b4a;
            font-size: 11px;
            font-weight: bold;
        }}
        .gamemode-badge-active {{
            color: #ec4899;
            font-weight: 800;
            background-color: {bad_active_bg};
            border: 1px solid {bad_active_border};
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 11px;
        }}
        .gamemode-badge-inactive {{
            color: #718096;
            font-weight: 600;
            background-color: {bad_inactive_bg};
            border: 1px solid {bad_inactive_border};
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 11px;
        }}
        .gaming-action-btn {{
            background-color: {act_btn_bg};
            border: 1px solid {act_btn_border};
            color: {act_btn_color};
            font-weight: bold;
            font-size: 12px;
            border-radius: 4px;
            padding: 8px 18px;
            transition: all 180ms ease;
        }}
        .gaming-action-btn:hover {{
            background-color: {act_btn_hover_bg};
            border-color: rgba(168, 85, 247, 0.5);
            box-shadow: 0 0 10px rgba(168, 85, 247, 0.25);
        }}
        .sensor-row {{
            padding: 4px 6px;
            border-bottom: 1px solid {sensor_row_border};
        }}
        """
        self._css_provider.load_from_data(css_data.encode())

    def _start_timers(self):
        if self._timer is None:
            self._timer = GLib.timeout_add(1500, self._refresh)
        if self._anim_timer is None:
            self._anim_timer = GLib.timeout_add(40, self._anim_tick)

    def _stop_timers(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        if self._anim_timer:
            GLib.source_remove(self._anim_timer)
            self._anim_timer = None

    def _on_map(self, *_args):
        self.monitor.set_active(True)
        self._start_timers()
        self._refresh()

    def _on_unmap(self, *_args):
        self.monitor.set_active(False)
        self._stop_timers()

    def _anim_tick(self):
        if not self.get_mapped():
            return True
        self.fan1_gauge.tick_rotation()
        self.fan2_gauge.tick_rotation()
        return True

    def set_service(self, service):
        self.service = service

    def set_platform_service(self, service):
        self._platform_svc = service

    def set_power_service(self, service):
        self._power_svc = service

    def set_rgb_service(self, service):
        self._rgb_svc = service

    def set_temp_unit(self, unit):
        self.temp_unit = unit

    def set_dark(self, is_dark):
        self.is_dark = is_dark
        if hasattr(self, "fan1_gauge") and self.fan1_gauge is not None:
            self.fan1_gauge.set_dark(is_dark)
        if hasattr(self, "fan2_gauge") and self.fan2_gauge is not None:
            self.fan2_gauge.set_dark(is_dark)
        if hasattr(self, "ram_bridge") and self.ram_bridge is not None:
            self.ram_bridge.set_dark(is_dark)
        if hasattr(self, "disk_bridge") and self.disk_bridge is not None:
            self.disk_bridge.set_dark(is_dark)
        if hasattr(self, "bat_bridge") and self.bat_bridge is not None:
            self.bat_bridge.set_dark(is_dark)
        self._update_theme_css(is_dark)

    def _rebuild_mode_selector(self, profiles):
        # Prevent rebuilding if the profiles list hasn't actually changed
        current_profiles = list(self.selector_buttons.keys())
        if sorted(profiles) == sorted(current_profiles):
            return

        # Clear existing buttons
        while True:
            child = self.selector_capsule.get_first_child()
            if child is None:
                break
            self.selector_capsule.remove(child)

        self.selector_group = None
        self.selector_buttons = {}

        # Fallback to defaults if profiles list is empty
        if not profiles:
            profiles = ["power-saver", "balanced", "performance"]

        mode_mapping = {
            "power-saver": T("saver"),
            "quiet": T("saver"),
            "low-power": T("saver"),
            "eco": T("saver"),
            "balanced": T("balanced"),
            "performance": T("performance"),
            "throughput-performance": T("performance"),
        }

        for mid in profiles:
            label = mode_mapping.get(mid, mid.replace("-", " ").title())
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-selector-btn")
            if self.selector_group:
                btn.set_group(self.selector_group)
            else:
                self.selector_group = btn

            btn.connect("toggled", lambda w, m=mid: self._on_mode_toggled(w, m))
            self.selector_capsule.append(btn)
            self.selector_buttons[mid] = btn

        # Highlight current active mode
        if self.active_mode in self.selector_buttons:
            self._sync_mode_buttons(self.active_mode)

    @staticmethod
    def _human_storage(value_bytes):
        try:
            val = float(value_bytes)
        except Exception:
            return "N/A"
        if val <= 0:
            return "N/A"
        gib = val / (1024 ** 3)
        if gib >= 1024:
            return f"{gib / 1024:.1f} TB"
        return f"{gib:.0f} GB"

    @staticmethod
    def _trim_hw_text(text, max_len=30):
        txt = " ".join(str(text or "").split())
        if len(txt) <= max_len:
            return txt
        return txt[:max_len - 1].rstrip() + "..."

    def _get_hardware_info(self):
        info = {
            "cpu": "N/A",
            "disk": "N/A",
            "gpu": "N/A",
            "ram": "N/A",
        }

        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        info["cpu"] = self._trim_hw_text(line.split(":", 1)[1].strip(), 34)
                        break
        except Exception:
            pass

        try:
            total, _used, _free = shutil.disk_usage("/")
            info["disk"] = self._human_storage(total)
        except Exception:
            pass

        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        gib = kb / (1024 * 1024)
                        info["ram"] = f"{gib:.1f} GB"
                        break
        except Exception:
            pass

        try:
            n_smi = shutil.which("nvidia-smi")
            if n_smi:
                out = subprocess.check_output(
                    [n_smi, "--query-gpu=name", "--format=csv,noheader"],
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                ).decode().strip().splitlines()
                if out and out[0].strip():
                    info["gpu"] = self._trim_hw_text(out[0].strip(), 30)
            if info["gpu"] == "N/A":
                out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, timeout=1.5).decode("utf-8", "ignore")
                for line in out.splitlines():
                    low = line.lower()
                    if "vga compatible controller" in low or "3d controller" in low:
                        info["gpu"] = self._trim_hw_text(line.split(":", 2)[-1].strip(), 30)
                        break
        except Exception:
            pass

        return info

    def _get_device_model_name(self):
        invalid = {
            "",
            "to be filled by o.e.m.",
            "not applicable",
            "default string",
            "system product name",
            "unknown",
            "hp laptop",
        }
        try:
            for dmi_file in (
                "/sys/class/dmi/id/product_name",
                "/sys/class/dmi/id/product_family",
                "/sys/class/dmi/id/board_name",
            ):
                if os.path.exists(dmi_file):
                    with open(dmi_file, "r") as f:
                        name = " ".join(f.read().strip().split())
                    if name.lower() not in invalid:
                        return name
        except Exception:
            pass
        return "HP Gaming System"

    def _build_ui(self):
        scroll = SmoothScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_bottom(20)
        self._content_box = content
        
        # Fan Control Status Box (Top Right)
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.set_halign(Gtk.Align.END)
        self.fc_status_badge = Gtk.Box(valign=Gtk.Align.CENTER)
        self.fc_status_badge.add_css_class("osd")
        self.fc_status_lbl = Gtk.Label(label="Fan Control: Checking...", css_classes=["caption", "accent"])
        self.fc_status_lbl.set_margin_start(10)
        self.fc_status_lbl.set_margin_end(10)
        self.fc_status_lbl.set_margin_top(2)
        self.fc_status_lbl.set_margin_bottom(2)
        self.fc_status_badge.append(self.fc_status_lbl)
        top_bar.append(self.fc_status_badge)
        content.append(top_bar)

        # ─── 1. DYNAMIC CENTERED SPEEDOMETER GAUGES & COMPACT RAM BRIDGE ───
        gauges_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32, halign=Gtk.Align.CENTER)
        gauges_row.set_homogeneous(False)
        gauges_row.set_margin_top(14)
        gauges_row.set_margin_bottom(14)
        self._gauges_row = gauges_row

        # CPU Left Gauge (260x260, large!)
        self.fan1_gauge = OmenHighTechGauge(label="CPU", is_left=True, active_color=(0.66, 0.33, 0.97))
        gauges_row.append(self.fan1_gauge)

        # Center bridges column (RAM, Disk, Battery)
        middle_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        middle_column.set_valign(Gtk.Align.CENTER)

        self.ram_bridge = OmenSpecsBridge(color=(0.24, 0.60, 1.0))
        middle_column.append(self.ram_bridge)

        self.disk_bridge = OmenSpecsBridge(color=(0.66, 0.33, 0.97))
        middle_column.append(self.disk_bridge)

        self.bat_bridge = OmenSpecsBridge(color=(0.06, 0.72, 0.44))
        middle_column.append(self.bat_bridge)

        gauges_row.append(middle_column)

        # GPU Right Gauge
        self.fan2_gauge = OmenHighTechGauge(label="GPU", is_left=False, active_color=(0.93, 0.28, 0.60))
        gauges_row.append(self.fan2_gauge)

        content.append(gauges_row)

        self.fan_warning = Gtk.Label(label=T("fan_disabled"), css_classes=["warning-label"])
        self.fan_warning.set_halign(Gtk.Align.CENTER)
        self.fan_warning.set_visible(False)
        content.append(self.fan_warning)

        # ─── 2. SLEEK SEGMENTED MODE SELECTOR TABS ───
        self.selector_capsule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, halign=Gtk.Align.CENTER)
        self.selector_capsule.add_css_class("mode-selector-capsule")
        self.selector_group = None
        self.selector_buttons = {}

        modes = [
            ("power-saver", T("saver")),
            ("balanced", T("balanced")),
            ("performance", T("performance"))
        ]

        for idx, (mid, label) in enumerate(modes):
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-selector-btn")
            if self.selector_group:
                btn.set_group(self.selector_group)
            else:
                self.selector_group = btn

            btn.connect("toggled", lambda w, m=mid: self._on_mode_toggled(w, m))
            self.selector_capsule.append(btn)
            self.selector_buttons[mid] = btn

        content.append(self.selector_capsule)

        self.fan_control_strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.fan_control_strip.add_css_class("fan-control-strip")

        fan_control_head = Gtk.Label(label="FAN CONTROL", xalign=0)
        fan_control_head.add_css_class("omen-dashboard-card-title")
        self.fan_control_strip.append(fan_control_head)

        self.fan_control_capsule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, halign=Gtk.Align.CENTER)
        self.fan_control_capsule.add_css_class("mode-selector-capsule")
        self.fan_control_group = None
        self.fan_control_buttons = {}
        self.fan_control_custom_btn = None

        fan_levels = [
            (0, "Auto"),
            (1, "Performance"),
            (2, "Max"),
        ]

        for level, label in fan_levels:
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-selector-btn")
            btn.add_css_class("fan-control-btn")
            if self.fan_control_group:
                btn.set_group(self.fan_control_group)
            else:
                self.fan_control_group = btn
            btn.connect("toggled", lambda w, l=level: self._on_fan_control_toggled(w, l))
            self.fan_control_capsule.append(btn)
            self.fan_control_buttons[level] = btn

        self.fan_control_custom_btn = Gtk.Button(label="Custom")
        self.fan_control_custom_btn.add_css_class("mode-selector-btn")
        self.fan_control_custom_btn.add_css_class("fan-control-btn")
        self.fan_control_custom_btn.connect("clicked", self._on_custom_fan_control_clicked)
        self.fan_control_capsule.append(self.fan_control_custom_btn)

        self.fan_control_strip.append(self.fan_control_capsule)
        content.append(self.fan_control_strip)

        # ─── 3. FAN CURVE CARD (Shown in custom mode) ───
        self.curve_card = Gtk.Revealer()
        self.curve_card.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.curve_card.set_transition_duration(260)
        self.curve_card.set_reveal_child(False)

        curve_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        curve_panel.add_css_class("omen-dashboard-card")

        curve_header = Gtk.Box(spacing=10)
        curve_header.append(Gtk.Image.new_from_icon_name("document-edit-symbolic"))
        curve_header.append(Gtk.Label(label=T("fan_curve"), css_classes=["section-title"]))
        curve_panel.append(curve_header)

        curve_desc = Gtk.Label(label=T("curve_desc"), css_classes=["dim-label"], xalign=0, wrap=True)
        curve_panel.append(curve_desc)

        self.fan_curve = FanCurveWidget()
        self.fan_curve.on_curve_changed = self._on_curve_changed
        curve_panel.append(self.fan_curve)

        apply_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        apply_row.set_halign(Gtk.Align.END)
        self.curve_apply_btn = Gtk.Button(label="Apply")
        self.curve_apply_btn.add_css_class("suggested-action")
        self.curve_apply_btn.connect("clicked", self._on_custom_curve_apply)
        apply_row.append(self.curve_apply_btn)
        curve_panel.append(apply_row)

        self.curve_card.set_child(curve_panel)
        content.append(self.curve_card)

        # TLP / Auto-cpufreq Conflict label
        self._pp_conflict_lbl = Gtk.Label(label="", use_markup=True, xalign=0.5)
        self._pp_conflict_lbl.add_css_class("warning-label")
        self._pp_conflict_lbl.set_visible(False)
        content.append(self._pp_conflict_lbl)

        # ─── 3. OVAL DASHBOARD GRIDS ───
        self.dashboard_grid = Gtk.Grid(column_spacing=18, row_spacing=18)
        self.dashboard_grid.set_column_homogeneous(True)
        self.dashboard_grid.set_hexpand(True)
        content.append(self.dashboard_grid)

        # LEFT CARD: Real-time Sensor Panel
        self.sensor_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.sensor_card.add_css_class("omen-dashboard-card")
        
        lbl_s = Gtk.Label(label=T("system_status"), xalign=0, css_classes=["omen-dashboard-card-title"])
        self.sensor_card.append(lbl_s)
        self.sensor_card.append(Gtk.Separator())

        # Scrollable sensor list
        sensor_scroll = Gtk.ScrolledWindow(height_request=150, vexpand=True)
        sensor_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sensor_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sensor_scroll.set_child(self.sensor_list_box)
        self.sensor_card.append(sensor_scroll)
        
        self.dashboard_grid.attach(self.sensor_card, 0, 0, 1, 1)

        # RIGHT CARD: Gaming Optimization & Diagnostics
        self.gaming_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.gaming_card.add_css_class("omen-dashboard-card")
        
        lbl_g = Gtk.Label(label="GAMING OPTIMIZATION", xalign=0, css_classes=["omen-dashboard-card-title"])
        self.gaming_card.append(lbl_g)
        self.gaming_card.append(Gtk.Separator())

        # 1. Windows Key Lock (Oyun Tuş Kilidi) Toggle Row
        win_lock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        win_lock_row.set_valign(Gtk.Align.CENTER)
        win_lock_row.append(Gtk.Image.new_from_icon_name("changes-prevent-symbolic"))
        win_lock_row.append(Gtk.Label(label=T("win_lock"), xalign=0, css_classes=["dim-label"]))
        win_lock_row.append(Gtk.Label(hexpand=True))
        
        self.win_lock_switch = Gtk.Switch()
        self.win_lock_switch.add_css_class("gaming-switch")
        self.win_lock_switch.connect("state-set", self._on_win_lock_toggled)
        win_lock_row.append(self.win_lock_switch)
        self.gaming_card.append(win_lock_row)

        self.gaming_card.append(Gtk.Separator())

        # 2. cTGP Toggle Row
        ctgp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ctgp_row.set_valign(Gtk.Align.CENTER)
        ctgp_row.append(Gtk.Image.new_from_icon_name("video-display-symbolic"))
        ctgp_row.append(Gtk.Label(label="cTGP Boost Mode", xalign=0, css_classes=["dim-label"]))
        ctgp_row.append(Gtk.Label(hexpand=True))
        self.ctgp_status_label = Gtk.Label(label=T("inactive"))
        self.ctgp_status_label.add_css_class("gamemode-badge-inactive")
        self.ctgp_status_label.set_margin_end(6)
        ctgp_row.append(self.ctgp_status_label)
        self.gaming_card.append(ctgp_row)

        self.gaming_card.append(Gtk.Separator())

        # 3. PPAB Toggle Row
        ppab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ppab_row.set_valign(Gtk.Align.CENTER)
        ppab_row.append(Gtk.Image.new_from_icon_name("processor-symbolic"))
        ppab_row.append(Gtk.Label(label="PPAB Dynamic Boost", xalign=0, css_classes=["dim-label"]))
        ppab_row.append(Gtk.Label(hexpand=True))
        self.ppab_status_label = Gtk.Label(label=T("inactive"))
        self.ppab_status_label.add_css_class("gamemode-badge-inactive")
        self.ppab_status_label.set_margin_end(6)
        ppab_row.append(self.ppab_status_label)
        self.gaming_card.append(ppab_row)

        self.gaming_card.append(Gtk.Separator())

        # 4. Feral GameMode Status Row (no toggle switch, only badge)
        gm_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        gm_row.set_valign(Gtk.Align.CENTER)
        gm_row.append(Gtk.Image.new_from_icon_name("applications-games-symbolic"))
        gm_row.append(Gtk.Label(label="Feral GameMode Status", xalign=0, css_classes=["dim-label"]))
        gm_row.append(Gtk.Label(hexpand=True))
        
        # GameMode status text badge/label
        self.gamemode_status_label = Gtk.Label(label=T("inactive"))
        self.gamemode_status_label.add_css_class("gamemode-badge-inactive")
        self.gamemode_status_label.set_margin_end(6)
        gm_row.append(self.gamemode_status_label)
        
        self.gaming_card.append(gm_row)

        self.dashboard_grid.attach(self.gaming_card, 1, 0, 1, 1)

        # ─── 5. SYSTEM SPECIFICATIONS CARD ───
        self.sys_info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.sys_info_card.add_css_class("omen-dashboard-card")
        self.sys_info_card.set_margin_top(8)

        sys_header = Gtk.Box(spacing=10)
        sys_header.set_valign(Gtk.Align.CENTER)
        sys_header.append(Gtk.Image.new_from_icon_name("computer-symbolic"))
        
        # Determine language (TR fallback)
        lang_is_tr = T("fan") == "Performans" or "tr" in os.getenv("LANG", "").lower()
        sys_title_lbl = Gtk.Label(label="SİSTEM BİLGİSİ" if lang_is_tr else "SYSTEM INFORMATION", xalign=0)
        sys_title_lbl.add_css_class("section-title")
        sys_header.append(sys_title_lbl)
        
        self.sys_info_card.append(sys_header)
        self.sys_info_card.append(Gtk.Separator())

        # Motherboard model name row
        model_name = self._get_device_model_name()
        model_row = Gtk.Box(spacing=10, margin_top=4, margin_bottom=4)
        model_row.set_valign(Gtk.Align.CENTER)
        
        model_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        model_icon.set_pixel_size(24)
        model_icon.add_css_class("nav-icon")
        model_row.append(model_icon)

        model_label = Gtk.Label(label=model_name, xalign=0)
        model_label.add_css_class("stat-big")
        model_row.append(model_label)
        self.sys_info_card.append(model_row)
        self.sys_info_card.append(Gtk.Separator())

        # 4 specs item grid/box
        spec_box = Gtk.Box(spacing=12, homogeneous=True, margin_top=8, margin_bottom=8)
        self.sys_info_card.append(spec_box)

        hw = self._get_hardware_info()
        labels = {
            "cpu": "CPU",
            "disk": "Depolama" if lang_is_tr else "Storage",
            "gpu": "GPU",
            "ram": "Bellek" if lang_is_tr else "Memory",
        }
        icons = {
            "cpu": "processor-symbolic",
            "disk": "drive-harddisk-symbolic",
            "gpu": "video-display-symbolic",
            "ram": "media-memory-symbolic",
        }

        for key in ("cpu", "gpu", "ram", "disk"):
            item = Gtk.Box(spacing=10)
            item.add_css_class("home-spec-item")
            item.set_valign(Gtk.Align.CENTER)

            ico = Gtk.Image.new_from_icon_name(icons[key])
            ico.set_pixel_size(18)
            ico.add_css_class("nav-icon")
            item.append(ico)

            txt_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            ttl = Gtk.Label(label=labels[key], xalign=0)
            ttl.add_css_class("home-spec-title")
            txt_col.append(ttl)
            
            val = Gtk.Label(label=hw.get(key, "N/A"), xalign=0)
            val.add_css_class("home-spec-value")
            txt_col.append(val)
            item.append(txt_col)

            spec_box.append(item)

        content.append(self.sys_info_card)

        scroll.set_child(content)
        self.append(scroll)
        
        self.default_points = [(48, 0), (58, 35), (70, 60), (78, 72), (85, 100)]
        self.performance_points = [(35, 0), (50, 45), (65, 70), (75, 90), (82, 100)]
        self.auto_points = [(40, 0), (55, 30), (65, 45), (75, 65), (85, 100)]
        self.custom_points = list(self.default_points)

        # Set default active state
        self._sync_fan_control_buttons(self.fan_control_level)
        self._set_custom_button_active(False)
        self._sync_mode_buttons("balanced")
        self.set_ui_scale("normal")

    def set_ui_scale(self, bucket, _width=0, _height=0):
        content = getattr(self, "_content_box", None)
        if content is not None:
            if bucket == "compact":
                content.set_margin_start(14)
                content.set_margin_end(14)
                content.set_spacing(12)
            elif bucket == "spacious":
                content.set_margin_start(34)
                content.set_margin_end(34)
                content.set_spacing(20)
            else:
                content.set_margin_start(24)
                content.set_margin_end(24)
                content.set_spacing(16)

        row = getattr(self, "_gauges_row", None)
        if row is not None:
            row.set_spacing(20 if bucket == "compact" else 48 if bucket == "spacious" else 36)

    def _sync_mode_buttons(self, mode):
        """Match UI toggle buttons with requested mode silently."""
        if mode in self.selector_buttons:
            btn = self.selector_buttons[mode]
            if not btn.get_active():
                prev = self._block_sync
                self._block_sync = True
                btn.set_active(True)
                self._block_sync = prev

    def _expected_power_state(self, mode):
        mapping = {
            "quiet": ("power-saver", "auto"),
            "balanced": ("balanced", "auto"),
            "performance": ("performance", "auto"),
            "custom": ("performance", "custom"),
        }
        return mapping.get(mode, ("balanced", "auto"))

    def _power_mode_confirmed(self, power_profile, fan_info, mode):
        expected_profile, _ = self._expected_power_state(mode)
        active_profile = power_profile.get("active", "")
        return active_profile == expected_profile

    def _set_pending_power_mode(self, mode):
        self._pending_power_mode = mode
        self._pending_power_started = time.monotonic()

    def _clear_pending_power_mode(self):
        self._pending_power_mode = None
        self._pending_power_started = 0.0
        return False

    def _sync_fan_control_buttons(self, level):
        if hasattr(self, "fan_control_buttons") and self.fan_control_buttons:
            prev = self._block_sync
            self._block_sync = True
            level = int(level)
            for idx, btn in self.fan_control_buttons.items():
                target_active = idx == level and level in self.fan_control_buttons
                if btn.get_active() != target_active:
                    btn.set_active(target_active)
            self._block_sync = prev

    def _set_custom_button_active(self, active):
        if hasattr(self, "fan_control_custom_btn") and self.fan_control_custom_btn is not None:
            if active:
                self.fan_control_custom_btn.add_css_class("active")
            else:
                self.fan_control_custom_btn.remove_css_class("active")

    def _open_custom_curve_editor(self):
        self.fan_control_mode = "custom"
        self.fan_control_level = 3
        self._sync_fan_control_buttons(self.fan_control_level)
        self.fan_curve_editor_open = True
        self._set_custom_button_active(True)
        if hasattr(self, "curve_card") and self.curve_card is not None:
            self.curve_card.set_reveal_child(True)
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.fan_curve.set_interactive(True)
            self.fan_curve.set_points(self.custom_points)

    def _close_custom_curve_editor(self):
        self.fan_curve_editor_open = False
        if hasattr(self, "curve_card") and self.curve_card is not None:
            self.curve_card.set_reveal_child(False)
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.fan_curve.set_interactive(False)

    def _on_custom_fan_control_clicked(self, _btn):
        self._open_custom_curve_editor()

    def _on_custom_curve_apply(self, _btn):
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.custom_points = self.fan_curve.get_points()
            if self.service:
                try:
                    import json
                    _dbus_call(self.service.SaveCustomCurve, json.dumps(self.custom_points))
                except Exception as e:
                    print(f"Failed to save custom curve: {e}")
        self._set_daemon_fan_mode("custom")
        self._apply_fan_curve()
        self._close_custom_curve_editor()

    def _set_daemon_fan_mode(self, mode):
        if self.service:
            try:
                _dbus_call(self.service.SetFanMode, mode)
            except Exception:
                pass

    def _curve_fan_pct_for_temp(self, points, temp, rpm_floor=None, fan_max=None):
        if not points:
            return 0

        if rpm_floor is not None and fan_max:
            normalized_points = []
            for idx, (point_temp, point_value) in enumerate(points):
                if idx == 1 and point_temp == 50:
                    normalized_points.append((point_temp, (rpm_floor * 100.0) / fan_max))
                else:
                    normalized_points.append((point_temp, point_value))
            points = normalized_points

        if temp <= points[0][0]:
            return points[0][1]
        if temp >= points[-1][0]:
            return points[-1][1]

        for idx in range(len(points) - 1):
            t0, f0 = points[idx]
            t1, f1 = points[idx + 1]
            if t0 <= temp <= t1:
                ratio = (temp - t0) / (t1 - t0) if t1 != t0 else 0
                return f0 + (f1 - f0) * ratio

        return points[-1][1]

    def _apply_fan_control_level(self, level):
        level = max(0, min(2, int(level)))
        self.fan_control_level = level

        fan_modes = {
            0: ("auto", None),
            1: ("performance", None),
            2: ("max", None),   # Max mode is handled entirely by driver/BIOS
        }
        fan_mode, fan_pct = fan_modes.get(level, ("auto", None))
        self.fan_control_mode = {0: "auto", 1: "performance", 2: "max"}.get(level, "auto")
        self._sync_fan_control_buttons(level)
        self._set_custom_button_active(False)
        self.fan_curve_editor_open = False
        if hasattr(self, "curve_card") and self.curve_card is not None:
            self.curve_card.set_reveal_child(False)
        if hasattr(self, "fan_curve") and self.fan_curve is not None:
            self.fan_curve.set_interactive(False)

        def _bg():
            try:
                if self.service:
                    if fan_mode is not None:
                        _dbus_call(self.service.SetFanMode, fan_mode)
                    if fan_pct is not None:
                        data = self.monitor.get_data()
                        fan_info = data.get("fan_info", {})
                        fans = fan_info.get("fans", {})
                        for fn, fd in fans.items():
                            max_rpm = fd.get("max", 5800) or 5800
                            target_rpm = int(max_rpm * fan_pct / 100)
                            _dbus_call(self.service.SetFanTarget, int(str(fn)), target_rpm)
                    elif level == 1:
                        self._set_daemon_fan_mode("performance")
                        self._apply_fan_curve(points=self.performance_points)
            except Exception as e:
                print(f"Fan control preset error: {e}")

        threading.Thread(target=_bg, daemon=True).start()

    def _on_fan_control_toggled(self, btn, level):
        if not btn.get_active() or self._block_sync:
            return
        self._apply_fan_control_level(level)

    def _on_mode_toggled(self, btn, mode):
        if not btn.get_active() or self._block_sync:
            return
        
        self.active_mode = mode
        self._set_pending_power_mode(mode)
        
        # Mapping UI modes to Daemon actions
        daemon_profile = "balanced"
        daemon_fan = None
        
        if mode in ("quiet", "power-saver", "eco", "low-power"):
            daemon_profile = "power-saver"
        elif mode == "balanced":
            daemon_profile = "balanced"
        elif mode in ("performance", "throughput-performance"):
            daemon_profile = "performance"
        elif mode == "custom":
            daemon_profile = "performance"
            daemon_fan = "custom"

        self.last_applied_rpm = {}

        # Defer calling D-Bus proxy services in a worker thread
        self._block_sync = True
        GLib.timeout_add(1200, self._unblock_sync)

        def _bg():
            # Automatically turn on cTGP and PPAB boost paths at hardware level if in performance/custom
            if daemon_profile == "performance":
                try:
                    for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
                        tgp_p = f"{base}/gpu_tgp"
                        ppab_p = f"{base}/gpu_ppab"
                        if os.path.exists(tgp_p):
                            with open(tgp_p, "w") as f:
                                f.write("1")
                        if os.path.exists(ppab_p):
                            with open(ppab_p, "w") as f:
                                f.write("1")
                except: pass

            # Update power profiles
            if self._power_svc:
                try:
                    result = _dbus_call(self._power_svc.SetPowerProfile, daemon_profile)
                    if result != "OK":
                        GLib.idle_add(self._clear_pending_power_mode)
                except:
                    GLib.idle_add(self._clear_pending_power_mode)

            # Keep fan daemon decoupled from power profile changes as requested.
            # Changing the power profile no longer automatically overrides or alters the user's selected fan mode.
            pass
                    
            if callable(self.on_profile_change):
                try: GLib.idle_add(self.on_profile_change, daemon_profile)
                except: pass

        threading.Thread(target=_bg, daemon=True).start()

    def _unblock_sync(self):
        self._block_sync = False
        return False

    def _on_win_lock_toggled(self, switch, state):
        """Toggle Windows Key Lock by writing to the hp-wmi/hp-rgb-lighting hardware register."""
        def _bg():
            # 1. Direct hardware sysfs write
            try:
                for base in ("/sys/devices/platform/hp-rgb-lighting", "/sys/devices/platform/hp_rgb_lighting"):
                    lock_p = f"{base}/win_lock"
                    if os.path.exists(lock_p):
                        with open(lock_p, "w") as f:
                            f.write("1" if state else "0")
                            break
            except Exception as e:
                print(f"⚠ Direct sysfs WinLock write failed: {e}")

            # 2. Sync via D-Bus daemon if available
            if self._rgb_svc:
                try:
                    _dbus_call(self._rgb_svc.SetWinLock, bool(state))
                except Exception as ex:
                    print(f"⚠ D-Bus WinLock call failed: {ex}")
        threading.Thread(target=_bg, daemon=True).start()
        return True





    def _on_clean_ram_clicked(self, _btn):
        if self._platform_svc:
            def _bg():
                try:
                    _dbus_call(self._platform_svc.CleanMemory)
                except: pass
            threading.Thread(target=_bg, daemon=True).start()

    def _on_curve_changed(self, points):
        if self.fan_control_mode == "custom":
            self.custom_points = points
            if self.fan_curve_editor_open:
                if getattr(self, "_curve_timer", None):
                    GLib.source_remove(self._curve_timer)
                self._curve_timer = GLib.timeout_add(200, self._apply_fan_curve_debounced)

    def _apply_fan_curve_debounced(self):
        self._apply_fan_curve()
        self._curve_timer = None
        return False

    def _apply_fan_curve(self, points=None):
        if self.fan_control_mode not in ("custom", "performance"):
            return
        if not self.temp_history:
            return

        # Initialize last_applied_temp if not present
        if not hasattr(self, "last_applied_temp"):
            self.last_applied_temp = 0.0

        avg_temp = sum(self.temp_history) / len(self.temp_history)

        # Apply Hysteresis:
        # If temperature is cooling down, don't reduce fan speed unless it cools by at least 4.0°C.
        # This prevents annoying pulsing / rapid fluctuation sounds of the fans.
        if avg_temp < self.last_applied_temp:
            if self.last_applied_temp - avg_temp < 4.0:
                effective_temp = self.last_applied_temp
            else:
                effective_temp = avg_temp
                self.last_applied_temp = avg_temp
        else:
            effective_temp = avg_temp
            self.last_applied_temp = avg_temp

        if points:
            active_points = points
        elif self.fan_control_mode == "performance":
            active_points = self.performance_points
        elif self.fan_control_mode == "auto":
            active_points = getattr(self, "auto_points", [(40, 0), (55, 30), (65, 45), (75, 65), (85, 100)])
        else:
            active_points = self.custom_points

        rpm_floor = 2000 if self.fan_control_mode == "performance" else None
        fan_max = None

        if self.service:
            try:
                data = self.monitor.get_data()
                info = data.get("fan_info", {})
                
                # Check availability first to avoid flooding
                if not info.get("available", False):
                    return
                    
                # Ensure daemon is in the correct curve-based mode
                # For software fan curves, the daemon must be in 'custom' or 'performance' (pwm1_enable=1)
                expected_mode = self.fan_control_mode
                if expected_mode == "auto":
                    expected_mode = "custom" # Force daemon to manual mode so we can write targets

                current_mode = info.get("mode", "")
                if current_mode != expected_mode:
                    self._set_daemon_fan_mode(expected_mode)
                    
                fans = info.get("fans", {})

                for fn, fd in fans.items():
                    max_rpm = fd.get("max", 5800)
                    if max_rpm <= 0:
                        max_rpm = 5800

                    fan_max = max_rpm
                    fan_pct = self._curve_fan_pct_for_temp(active_points, effective_temp, rpm_floor=rpm_floor, fan_max=fan_max)

                    ideal_target_rpm = int(max_rpm * fan_pct / 100)
                    
                    # Anti-Stall Protection: Prevent fan from pulsing at unspinnable low RPMs
                    MIN_SPIN_RPM = 2000
                    if 0 < ideal_target_rpm < MIN_SPIN_RPM:
                        ideal_target_rpm = MIN_SPIN_RPM
                        
                    last = self.last_applied_rpm.get(str(fn), -1)
                    
                    if last < 0:
                        # Initial state, set directly
                        target_rpm = ideal_target_rpm
                    else:
                        # Smooth transition (step by max 150 RPM per 1.5s tick)
                        STEP_SIZE = 150
                        if ideal_target_rpm > last + STEP_SIZE:
                            target_rpm = last + STEP_SIZE
                        elif ideal_target_rpm < last - STEP_SIZE:
                            target_rpm = last - STEP_SIZE
                        else:
                            target_rpm = ideal_target_rpm
                            
                    # Deadband threshold to filter small jitter
                    if last >= 0 and abs(target_rpm - last) < 50:
                        continue

                    self.last_applied_rpm[str(fn)] = target_rpm
                    
                    def _apply_async(fidx, rpm):
                        try: _dbus_call(self.service.SetFanTarget, fidx, rpm)
                        except: pass
                    threading.Thread(target=_apply_async, args=(int(str(fn)), target_rpm), daemon=True).start()
            except Exception as e:
                print(f"Fan curve set error: {e}")

    def _refresh(self):
        if not self.get_mapped():
            return True

        data = self.monitor.get_data()
        cpu_t = data.get("cpu_temp", 0.0)
        gpu_t = data.get("gpu_temp", 0.0)
        cpu_pct = data.get("cpu_pct", 0.0)
        gpu_pct = data.get("gpu_pct", 0.0)
        cpu_freq = data.get("cpu_freq", "0.00GHz")
        gpu_freq = data.get("gpu_freq", "0.00GHz")
        ram_pct = data.get("ram_pct", 0.0)
        ram_text = data.get("ram_text", "RAM 0% 0.0GB")
        fan_info = data.get("fan_info", {})
        power_profile = data.get("power_profile", {})
        rgb_state = data.get("rgb_state", {})
        gamemode = data.get("gamemode", "Inactive")
        sensors = data.get("all_sensors", [])
        gpu_tgp_state = data.get("gpu_tgp_state", False)
        gpu_ppab_state = data.get("gpu_ppab_state", False)

        # Update Fan Control Status Box
        if fan_info.get("available", False):
            self.fc_status_lbl.set_label(T("fan_active") if "fan_active" in globals() else "Fan Control: Active")
            self.fc_status_lbl.set_css_classes(["caption", "success"])
        else:
            self.fc_status_lbl.set_label(T("fan_inactive") if "fan_inactive" in globals() else "Fan Control: Inactive")
            self.fc_status_lbl.set_css_classes(["caption", "error"])

        # On first refresh, sync fan control mode from daemon's actual state
        if not self._fan_mode_synced and fan_info:
            daemon_mode = fan_info.get("mode", "auto")
            if daemon_mode == "auto":
                self.fan_control_level = 0
                self.fan_control_mode = "auto"
                self._sync_fan_control_buttons(0)
                self._set_custom_button_active(False)
            elif daemon_mode == "max":
                self.fan_control_level = 2
                self.fan_control_mode = "max"
                self._sync_fan_control_buttons(2)
                self._set_custom_button_active(False)
            elif daemon_mode == "custom":
                saved_curve_json = fan_info.get("custom_curve", "[]")
                try:
                    import json as _json
                    saved_curve = _json.loads(saved_curve_json)
                    if saved_curve and len(saved_curve) > 0:
                        self.custom_points = [(p[0], p[1]) for p in saved_curve]
                except Exception:
                    pass
                self.fan_control_level = 3
                self.fan_control_mode = "custom"
                self._sync_fan_control_buttons(3)
                self._set_custom_button_active(True)
            elif daemon_mode == "performance":
                self.fan_control_level = 1
                self.fan_control_mode = "performance"
                self._sync_fan_control_buttons(1)
                self._set_custom_button_active(False)
            self._fan_mode_synced = True
            print(f"Fan mode synced from daemon: {daemon_mode} (level={self.fan_control_level})")

        if not getattr(self, "_custom_curve_loaded", False):
            saved_curve_json = fan_info.get("custom_curve", "[]")
            try:
                import json
                saved_curve = json.loads(saved_curve_json)
                if saved_curve and len(saved_curve) > 0:
                    self.custom_points = [(p[0], p[1]) for p in saved_curve]
                    if hasattr(self, "fan_curve") and self.fan_curve is not None:
                        self.fan_curve.set_points(self.custom_points)
                self._custom_curve_loaded = True
            except Exception:
                pass

        # Sync temp history and slider marker using max of CPU and GPU temp to ensure proper cooling response for both
        max_t = max(cpu_t, gpu_t)
        self.temp_history.append(max_t)
        # Increased moving average history size to 15 to smooth out short CPU spikes
        if len(self.temp_history) > 15:
            self.temp_history.pop(0)
        self.fan_curve.set_current_temp(max_t)

        # Sync Gauges & RAM Bridge
        fans = fan_info.get("fans", {})
        fan_keys = sorted(fans.keys(), key=lambda x: int(x))
        
        f1_rpm = fans[fan_keys[0]].get("current", 0) if len(fan_keys) > 0 else 0
        f2_rpm = fans[fan_keys[1]].get("current", 0) if len(fan_keys) > 1 else 0
        
        disk_pct = data.get("disk_pct", 0.0)
        disk_text = data.get("disk_text", "")
        bat_pct = data.get("bat_pct", 0.0)
        bat_text = data.get("bat_text", "")

        self.fan1_gauge.set_val(cpu_pct, cpu_t, cpu_freq, f1_rpm)
        self.fan2_gauge.set_val(gpu_pct, gpu_t, gpu_freq, f2_rpm)
        self.ram_bridge.set_val(ram_pct, ram_text)
        self.disk_bridge.set_val(disk_pct, disk_text)
        self.bat_bridge.set_val(bat_pct, bat_text)

        # Apply fan curve if manual custom fan mode is enabled
        if self.fan_control_mode in ("custom", "performance", "auto"):
            self._apply_fan_curve()

        # Rebuild mode selector dynamically matching available WMI/ACPI profiles
        profiles = power_profile.get("profiles", [])
        if profiles:
            self._rebuild_mode_selector(profiles)

        # Sync Segmented Bar with active Profile, but keep a recent selection sticky
        if not self._block_sync:
            pending_mode = self._pending_power_mode
            pending_valid = False
            if pending_mode is not None:
                if self._power_mode_confirmed(power_profile, fan_info, pending_mode):
                    self._clear_pending_power_mode()
                else:
                    elapsed = time.monotonic() - self._pending_power_started
                    if elapsed < 6.0:
                        pending_valid = True
                    else:
                        self._clear_pending_power_mode()

            if pending_valid:
                ui_mode = pending_mode
            else:
                active_p = power_profile.get("active", "")
                
                if active_p in self.selector_buttons:
                    ui_mode = active_p
                else:
                    # Dynamic fallbacks
                    if active_p == "power-saver":
                        ui_mode = "quiet" if "quiet" in self.selector_buttons else "low-power" if "low-power" in self.selector_buttons else "power-saver"
                    elif active_p == "performance":
                        ui_mode = "performance"
                    else:
                        ui_mode = "balanced"

            self._sync_mode_buttons(ui_mode)
            self.active_mode = ui_mode

        if self.fan_control_mode == "custom":
            self._set_custom_button_active(True)
            if self.fan_curve_editor_open and hasattr(self, "curve_card") and self.curve_card is not None:
                self.curve_card.set_reveal_child(True)
            elif hasattr(self, "curve_card") and self.curve_card is not None:
                self.curve_card.set_reveal_child(False)
        else:
            self._set_custom_button_active(False)
            self._sync_fan_control_buttons(self.fan_control_level)

        # Sync Win Lock Switch
        if not self._block_sync and rgb_state:
            locked = rgb_state.get("win_lock", False)
            if self.win_lock_switch.get_active() != locked:
                self.win_lock_switch.set_active(locked)

        # Sync GameMode badge
        is_gm_active = gamemode == "Active"
        if is_gm_active:
            self.gamemode_status_label.set_label(T("active"))
            self.gamemode_status_label.set_css_classes(["gamemode-badge-active"])
        else:
            self.gamemode_status_label.set_label(T("inactive"))
            self.gamemode_status_label.set_css_classes(["gamemode-badge-inactive"])

        # Sync cTGP & PPAB hardware state switches
        # Fallback to profile states if sysfs not writable/present
        if not self._block_sync:
            active_p = power_profile.get("active", "")
            if active_p == "performance":
                tgp_target = True
                ppab_target = True
            elif active_p == "balanced":
                tgp_target = False
                ppab_target = True
            else:
                tgp_target = False
                ppab_target = False

            current_tgp = gpu_tgp_state if gpu_tgp_state else tgp_target
            current_ppab = gpu_ppab_state if gpu_ppab_state else ppab_target

            if current_tgp:
                self.ctgp_status_label.set_label(T("active"))
                self.ctgp_status_label.set_css_classes(["gamemode-badge-active"])
            else:
                self.ctgp_status_label.set_label(T("inactive"))
                self.ctgp_status_label.set_css_classes(["gamemode-badge-inactive"])

            if current_ppab:
                self.ppab_status_label.set_label(T("active"))
                self.ppab_status_label.set_css_classes(["gamemode-badge-active"])
            else:
                self.ppab_status_label.set_label(T("inactive"))
                self.ppab_status_label.set_css_classes(["gamemode-badge-inactive"])

        # Sync Sensors List (Left Card)
        self._update_sensor_list(sensors)

        # TLP / Auto-cpufreq conflicts
        conflict = data.get("power_conflict")
        if conflict:
            self.selector_capsule.set_sensitive(True)
            self._pp_conflict_lbl.set_label(
                f"<span color='#ef5b4a'>{T('power_managed_by').format(tool=conflict.upper())}</span>")
            self._pp_conflict_lbl.set_visible(True)
        else:
            self.selector_capsule.set_sensitive(True)
            self._pp_conflict_lbl.set_visible(False)

        # Fan service warning
        available = fan_info.get("available", False)
        self.fan_warning.set_visible(not available)

        # Check custom mode support
        supports_custom = fan_info.get("supports_custom", True)
        self.fan_control_custom_btn.set_visible(supports_custom)

        return True

    def _update_sensor_list(self, sensors):
        """Populate the left bottom card with a beautifully formatted list of real-time temperatures."""
        if len(sensors) != len(self._sensor_labels):
            while child := self.sensor_list_box.get_first_child():
                self.sensor_list_box.remove(child)
            self._sensor_labels.clear()

        for s in sensors:
            key = f"{s['driver']}_{s['label']}"
            val_str = f"{int(s['temp'])}°C"

            # Temperature color coding
            is_dark = getattr(self, "is_dark", True)
            if is_dark:
                color = "#a0aec0"
                if s["temp"] >= 78.0:
                    color = "#ef5b4a"
                elif s["temp"] >= 62.0:
                    color = "#f6ad55"
                elif s["temp"] > 0:
                    color = "#00f0ff"
            else:
                color = "#475569"
                if s["temp"] >= 78.0:
                    color = "#d93025"
                elif s["temp"] >= 62.0:
                    color = "#b06000"
                elif s["temp"] > 0:
                    color = "#0066cc"

            if key in self._sensor_labels:
                _lbl_name, lbl_temp = self._sensor_labels[key]
                lbl_temp.set_markup(f"<span color='{color}'><b>{val_str}</b></span>")
            else:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.add_css_class("sensor-row")
                
                bullet = Gtk.Label(label="• ")
                bullet.set_opacity(0.4)
                row.append(bullet)

                lbl_name = Gtk.Label(label=s["label"], xalign=0, css_classes=["dim-label"])
                lbl_name.set_hexpand(True)
                row.append(lbl_name)

                lbl_temp = Gtk.Label(xalign=1)
                lbl_temp.add_css_class("sensor-temp-val")
                lbl_temp.set_markup(f"<span color='{color}'><b>{val_str}</b></span>")
                row.append(lbl_temp)

                self._sensor_list_box_row = row
                self.sensor_list_box.append(row)
                self._sensor_labels[key] = (lbl_name, lbl_temp)

        if not sensors:
            if not self.sensor_list_box.get_first_child():
                lbl_empty = Gtk.Label(label=T("no_sensor"), css_classes=["dim-label"])
                lbl_empty.set_opacity(0.6)
                self.sensor_list_box.append(lbl_empty)

    def cleanup(self):
        self._stop_timers()
        self.monitor.stop()
