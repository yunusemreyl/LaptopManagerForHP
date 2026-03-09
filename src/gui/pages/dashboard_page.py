#!/usr/bin/env python3
"""
Dashboard Page — HP Laptop Manager
Provides system overview: temps, battery, hardware profile, resource usage,
and quick actions.  All heavy I/O runs in a background thread.
"""

import gi, math, json, subprocess, os, shutil, threading

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk
from widgets.smooth_scroll import SmoothScrolledWindow
import cairo

# ── Lazy i18n import ─────────────────────────────────────────────────────────
def T(key):
    from i18n import T as _T
    return _T(key)

# ═════════════════════════════════════════════════════════════════════════════
#  DONUT CHART  –  lightweight Cairo ring gauge
# ═════════════════════════════════════════════════════════════════════════════
_TWO_PI = 2 * math.pi

class DonutChart(Gtk.DrawingArea):
    """Reusable ring-style percentage gauge drawn via Cairo."""

    __slots__ = ("value", "color", "label", "_rgb")

    def __init__(self, color_hex: str, label: str, size: int = 90):
        super().__init__()
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.value = 0.0
        self.color = color_hex
        self.label = label
        self._rgb = self._parse_hex(color_hex)
        self.set_draw_func(self._draw)

    # ── public ────────────────────────────────────────────────────────────
    def set_value(self, val: float):
        v = max(0.0, min(100.0, val))
        if abs(v - self.value) < 0.5:
            return
        self.value = v
        self.queue_draw()

    # ── internal ──────────────────────────────────────────────────────────
    @staticmethod
    def _parse_hex(h: str):
        h = h.lstrip("#")
        if len(h) != 6:
            return (1.0, 1.0, 1.0)
        return (int(h[0:2], 16) / 255.0,
                int(h[2:4], 16) / 255.0,
                int(h[4:6], 16) / 255.0)

    def _draw(self, _area, cr, w, h):
        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) / 2.0 - 5
        cr.set_line_width(8)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)

        # Detect theme once
        try:
            from gi.repository import Adw as _Adw
            _dark = _Adw.StyleManager.get_default().get_dark()
        except Exception:
            _dark = True

        # background track
        track_alpha = 0.25 if _dark else 0.15
        cr.set_source_rgba(0.4, 0.4, 0.4, track_alpha)
        cr.arc(cx, cy, radius, 0, _TWO_PI)
        cr.stroke()

        # foreground arc
        if self.value > 0:
            cr.set_source_rgba(*self._rgb, 0.9)
            start = -math.pi / 2
            cr.arc(cx, cy, radius, start,
                   start + (self.value / 100.0) * _TWO_PI)
            cr.stroke()

        # filled center circle — contrasting to theme
        inner_r = radius - 6
        if _dark:
            cr.set_source_rgba(0.12, 0.12, 0.14, 0.85)
        else:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
        cr.arc(cx, cy, inner_r, 0, _TWO_PI)
        cr.fill()

        # center text — inverted contrast
        _lum = 0.92 if _dark else 0.12
        cr.set_source_rgba(_lum, _lum, _lum, 1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        pct = f"{int(self.value)}%"
        ext = cr.text_extents(pct)
        cr.move_to(cx - ext.width / 2, cy + 5)
        cr.show_text(pct)

        cr.set_font_size(9)
        ext2 = cr.text_extents(self.label)
        cr.move_to(cx - ext2.width / 2, cy + 18)
        cr.show_text(self.label)

# ═════════════════════════════════════════════════════════════════════════════
#  PERF SLIDER  –  Animated segmented control
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
#  PERF SLIDER  –  (Removed in favor of Fan Page Native Toggle Layout)
# ═════════════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE
# ═════════════════════════════════════════════════════════════════════════════
_REFRESH_MS = 5000          # background fetch period
_NVIDIA_SMI = None          # cached shutil.which result

class DashboardPage(Gtk.Box):
    """Main dashboard: 4-pane grid with info bar."""

    def __init__(self, service=None, on_navigate=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.service = service
        self.on_navigate = on_navigate
        self._timer_id = None
        self._cpu_prev = None       # (total, idle) for delta calc
        self._cpu_smooth = 0.0      # EMA-smoothed CPU %
        self._data = {}             # latest bg-fetched snapshot
        self._busy = False          # guard against overlapping bg threads
        self._temp_unit = "C"       # temperature unit preference

        global _NVIDIA_SMI
        if _NVIDIA_SMI is None:
            _NVIDIA_SMI = shutil.which("nvidia-smi") or ""

        self._build()
        self._timer_id = GLib.timeout_add(_REFRESH_MS, self._tick)
        GLib.idle_add(self._tick)

    # ── public ────────────────────────────────────────────────────────────
    def set_service(self, svc):
        self.service = svc

    def set_temp_unit(self, unit):
        self._temp_unit = unit

    def _format_temp(self, celsius):
        """Format temperature value for display in the user's preferred unit."""
        if self._temp_unit == "F":
            return f"{int(celsius * 9 / 5 + 32)}°F"
        return f"{int(celsius)}°C"

    def cleanup(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    # ═════════════════════════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ═════════════════════════════════════════════════════════════════════════
    def _build(self):
        scroll = SmoothScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True, hexpand=True)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(16)
        root.set_margin_start(24)
        root.set_margin_end(24)
        root.set_margin_bottom(20)
        scroll.set_child(root)
        self.append(scroll)

        root.append(self._mk_info_bar())

        grid = Gtk.Grid(column_spacing=18, row_spacing=18,
                        column_homogeneous=True)
        root.append(grid)

        grid.attach(self._mk_quick_status(), 0, 0, 1, 1)
        grid.attach(self._mk_hw_profile(),   1, 0, 1, 1)
        grid.attach(self._mk_resources(),    0, 1, 1, 1)
        grid.attach(self._mk_quick_actions(),1, 1, 1, 1)

    # ── Info Bar ──────────────────────────────────────────────────────────
    def _mk_info_bar(self):
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("card")

        ic = Gtk.Image.new_from_icon_name("computer-symbolic")
        ic.set_pixel_size(28)
        bar.append(ic)

        lbl = Gtk.Label(label="Victus by HP")
        lbl.add_css_class("heading")
        bar.append(lbl)

        bar.append(Gtk.Label(hexpand=True))  # spacer

        self._os_lbl = Gtk.Label(label="—", css_classes=["dim-label"])
        bar.append(self._os_lbl)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self._kern_lbl = Gtk.Label(label="—", css_classes=["dim-label"])
        bar.append(self._kern_lbl)
        return bar

    # ── Quick Status ──────────────────────────────────────────────────────
    def _mk_quick_status(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        card.add_css_class("card")

        card.append(self._heading(T("quick_status")))
        card.append(Gtk.Separator())

        # Temperature boxes side-by-side
        temps = Gtk.Box(spacing=0, homogeneous=True)
        card.append(temps)
        self._cpu_temp = self._mk_sensor(temps, "CPU")
        self._gpu_temp = self._mk_sensor(temps, "GPU")

        card.append(Gtk.Separator())

        # Battery — large donut + textual details
        bat_box = Gtk.Box(spacing=14, halign=Gtk.Align.CENTER,
                          vexpand=True, valign=Gtk.Align.CENTER)
        card.append(bat_box)

        self._bat_donut = DonutChart("#57e389", "BAT", size=80)
        bat_box.append(self._bat_donut)

        bat_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                           valign=Gtk.Align.CENTER)
        self._bat_pct_lbl = Gtk.Label(label="—", xalign=0,
                                      css_classes=["title-2"])
        self._bat_status_lbl = Gtk.Label(label="", xalign=0,
                                         css_classes=["dim-label"])
        self._bat_health_lbl = Gtk.Label(label="", xalign=0,
                                          css_classes=["dim-label"])
        bat_info.append(self._bat_pct_lbl)
        bat_info.append(self._bat_status_lbl)
        bat_info.append(self._bat_health_lbl)
        bat_box.append(bat_info)

        return card

    # ── Hardware Profile ──────────────────────────────────────────────────
    def _mk_hw_profile(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        card.add_css_class("card")

        card.append(self._heading(T("hardware_profile")))
        card.append(Gtk.Separator())

        self._pills = {}
        for key, icon_name, caption in (
            ("power", "battery-symbolic",        T("power_profile_label")),
            ("fan",   "weather-tornado-symbolic", T("fan_mode_label")),
            ("mux",   "video-display-symbolic",   T("gpu_mux_label")),
        ):
            frame = Gtk.Frame()
            frame.add_css_class("pill-frame")

            row = Gtk.Box(spacing=10)
            row.set_margin_top(8)
            row.set_margin_bottom(8)
            row.set_margin_start(12)
            row.set_margin_end(12)

            ic = Gtk.Image.new_from_icon_name(icon_name)
            ic.set_pixel_size(18)
            row.append(ic)

            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            col.append(Gtk.Label(label=caption, xalign=0,
                                 css_classes=["dim-label"]))
            val = Gtk.Label(label="—", xalign=0, css_classes=["title-3"])
            col.append(val)
            row.append(col)

            frame.set_child(row)
            
            nav_target = "mux" if key == "mux" else "fan"
            gesture = Gtk.GestureClick.new()
            gesture.connect("pressed", lambda g, n, x, y, t=nav_target: self.on_navigate(t) if self.on_navigate else None)
            frame.add_controller(gesture)
            frame.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            
            card.append(frame)
            self._pills[key] = val

        return card

    # ── Resources ─────────────────────────────────────────────────────────
    def _mk_resources(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        card.add_css_class("card")

        card.append(self._heading(T("resources")))
        card.append(Gtk.Separator())

        row = Gtk.Box(spacing=12, homogeneous=True, halign=Gtk.Align.CENTER,
                      vexpand=True, valign=Gtk.Align.CENTER)
        self._cpu_chart = DonutChart("#3584e4", "CPU", size=130)
        self._ram_chart = DonutChart("#2ec27e", "RAM", size=130)
        self._gpu_chart = DonutChart("#e66100", "GPU", size=130)
        row.append(self._cpu_chart)
        row.append(self._ram_chart)
        row.append(self._gpu_chart)
        card.append(row)
        return card

    # ── Quick Actions ─────────────────────────────────────────────────────
    def _mk_quick_actions(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        card.add_css_class("card")

        card.append(self._heading(T("quick_actions")))
        card.append(Gtk.Separator())

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.append(vbox)
        
        row1 = Gtk.Box(spacing=10, homogeneous=True)
        vbox.append(row1)
        # Squeeze height for secondary actions
        self._max_fan_btn = Gtk.Button(label=T("max_fan"), hexpand=True, vexpand=False)
        self._max_fan_btn.set_size_request(-1, 50)
        self._max_fan_btn.add_css_class("clean-ram-action")
        self._max_fan_btn.connect("clicked", self._on_action, "max_fan")
        row1.append(self._max_fan_btn)
        
        clean_ram_btn = Gtk.Button(label=T("clean_memory"), hexpand=True, vexpand=False)
        clean_ram_btn.set_size_request(-1, 50)
        clean_ram_btn.add_css_class("clean-ram-action")
        clean_ram_btn.connect("clicked", self._on_action, "clean_ram")
        row1.append(clean_ram_btn)
        
        # Performance Slider
        lbl_perf = Gtk.Label(label=f"<b>{T('performance_lbl')}</b>", use_markup=True, xalign=0)
        vbox.append(lbl_perf)
        
        self._perf_strip = Gtk.Box(spacing=0, halign=Gtk.Align.CENTER)
        self._perf_strip.add_css_class("mode-selector-strip")
        self._perf_group = None
        self._perf_btns = {}
        
        for mode_id, label in [
            ("eco", T('eco_mode')), 
            ("balanced", T('balanced')), 
            ("performance", T('performance'))
        ]:
            btn = Gtk.ToggleButton()
            btn.add_css_class("fan-mode-btn")
            btn.add_css_class(f"perf-{mode_id}")
            btn.set_child(Gtk.Label(label=label))
            
            if self._perf_group:
                btn.set_group(self._perf_group)
            else:
                self._perf_group = btn
                
            btn.connect("toggled", lambda w, m=mode_id: self._on_perf_toggled(w, m))
            self._perf_strip.append(btn)
            self._perf_btns[mode_id] = btn

        vbox.append(self._perf_strip)

        return card

    # ── tiny helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _heading(text):
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class("heading")
        return lbl

    @staticmethod
    def _mk_sensor(parent, name):
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                      halign=Gtk.Align.CENTER)
        ic = Gtk.Image.new_from_icon_name("weather-clear-symbolic")
        ic.set_pixel_size(24)
        col.append(ic)
        lbl = Gtk.Label(label="-- °C", css_classes=["title-2"])
        col.append(lbl)
        col.append(Gtk.Label(label=name, css_classes=["dim-label"]))
        parent.append(col)
        return lbl

    # ═════════════════════════════════════════════════════════════════════════
    #  ACTIONS
    # ═════════════════════════════════════════════════════════════════════════
    def _on_perf_toggled(self, btn, mode):
        if not btn.get_active() or getattr(self, "_block_perf_sync", False):
            return
        self._on_action(None, mode)

    def _on_action(self, _btn, action_id):
        if not self.service:
            return
        try:
            if action_id == "max_fan":
                fan_data = self._data.get("fan", {})
                current_mode = fan_data.get("mode", "auto")
                if current_mode == "max":
                    self.service.SetFanMode("auto")
                else:
                    self.service.SetFanMode("max")
            elif action_id == "balanced" or action_id == "eco":
                # Only pass the exact strings expected by daemon
                self.service.SetPowerProfile(action_id if action_id == "balanced" else "power-saver")
            elif action_id == "performance" or action_id == "perf":
                self.service.SetPowerProfile("performance")
            elif action_id == "clean_ram":
                self.service.CleanMemory()
        except Exception as e:
            print(f"[Dashboard] action '{action_id}' failed: {e}")

    # ═════════════════════════════════════════════════════════════════════════
    #  BACKGROUND DATA FETCH  –  keeps UI thread free
    # ═════════════════════════════════════════════════════════════════════════
    def _tick(self):
        if self._busy:
            return True
        if not self.get_mapped():
            return True
        self._busy = True
        threading.Thread(target=self._fetch, daemon=True).start()
        return True

    def _fetch(self):
        """Run ALL blocking I/O here (daemon D-Bus, /proc, nvidia-smi)."""
        d = {}
        svc = self.service

        # ── Daemon calls ──────────────────────────────────────────────────
        if svc:
            for key, method in (("sys", "GetSystemInfo"),
                                ("fan", "GetFanInfo"),
                                ("pp",  "GetPowerProfile"),
                                ("gpu", "GetGpuInfo")):
                try:
                    d[key] = json.loads(getattr(svc, method)())
                except Exception:
                    pass

        # ── CPU/GPU temp — prefer daemon values for consistency with fan page ─
        si = d.get("sys", {})
        d["cpu_temp"] = si.get("cpu_temp", 0)
        d["gpu_temp"] = si.get("gpu_temp", 0)
        # Fallback to direct hwmon only if daemon didn't provide temps
        if not d["cpu_temp"]:
            d["cpu_temp"] = self._get_cpu_temp()
        if not d["gpu_temp"]:
            d["gpu_temp"] = self._get_gpu_temp()

        # ── CPU % from /proc/stat ─────────────────────────────────────────
        try:
            with open("/proc/stat") as f:
                parts = f.readline().split()
            times = list(map(int, parts[1:]))
            total = sum(times)
            idle = times[3] + (times[4] if len(times) > 4 else 0)
            if self._cpu_prev:
                dt = total - self._cpu_prev[0]
                di = idle  - self._cpu_prev[1]
                raw = (1 - di / dt) * 100 if dt else 0
                # EMA smoothing (α=0.3) to reduce jitter
                alpha = 0.3
                self._cpu_smooth = alpha * raw + (1 - alpha) * self._cpu_smooth
                d["cpu_pct"] = self._cpu_smooth
            self._cpu_prev = (total, idle)
        except Exception:
            pass

        # ── RAM % from /proc/meminfo ──────────────────────────────────────
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.split()[0])
            mt = mem.get("MemTotal", 1)
            ma = mem.get("MemAvailable", mt)
            d["ram_pct"] = (1 - ma / mt) * 100
        except Exception:
            pass

        # ── GPU % from nvidia-smi ─────────────────────────────────────────
        if _NVIDIA_SMI:
            # Check if dGPU is suspended to avoid waking it
            is_awake = True
            pci_path = None
            try:
                for dev in os.listdir("/sys/bus/pci/devices"):
                    vendor_file = f"/sys/bus/pci/devices/{dev}/vendor"
                    if os.path.exists(vendor_file):
                        with open(vendor_file) as f:
                            if f.read().strip() == "0x10de":
                                pci_path = f"/sys/bus/pci/devices/{dev}/power/runtime_status"
                                break
            except Exception:
                pass

            if pci_path and os.path.exists(pci_path):
                try:
                    with open(pci_path) as f:
                        if f.read().strip() == "suspended":
                            is_awake = False
                except Exception:
                    pass

            if is_awake:
                try:
                    out = subprocess.check_output(
                        [_NVIDIA_SMI, "--query-gpu=utilization.gpu",
                         "--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL, timeout=3
                    ).decode().strip()
                    d["gpu_pct"] = float(out)
                except Exception:
                    pass
            else:
                d["gpu_pct"] = 0.0

        # ── Battery from sysfs ────────────────────────────────────────────
        for name in ("BAT0", "BAT1", "BATT"):
            bp = f"/sys/class/power_supply/{name}"
            if not os.path.isdir(bp):
                continue
            try:
                d["bat_cap"] = self._read_int(bp, "capacity")
                d["bat_stat"] = self._read_str(bp, "status")
                # health = energy_full_design vs energy_full
                efd = self._read_int(bp, "energy_full_design")
                ef  = self._read_int(bp, "energy_full")
                if efd and ef:
                    d["bat_health"] = round(ef / efd * 100)
                break
            except Exception:
                pass

        self._data = d
        GLib.idle_add(self._apply)

    # ── Apply data to widgets (main thread) ───────────────────────────────
    def _apply(self):
        d = self._data
        self._busy = False

        # Info bar
        si = d.get("sys", {})
        self._os_lbl.set_label(si.get("os_name", "Linux"))
        self._kern_lbl.set_label(f"Kernel {si.get('kernel', '')}")

        # Temps — from direct hwmon reading
        self._cpu_temp.set_label(self._format_temp(d.get('cpu_temp', 0)))
        self._gpu_temp.set_label(self._format_temp(d.get('gpu_temp', 0)))

        # Battery
        cap = d.get("bat_cap")
        if cap is not None:
            self._bat_donut.set_value(cap)
            self._bat_pct_lbl.set_label(f"{cap}%")
            self._bat_status_lbl.set_label(d.get("bat_stat", ""))
            health = d.get("bat_health")
            if health is not None:
                self._bat_health_lbl.set_label(f"{T('health')}: {health}%")
            else:
                self._bat_health_lbl.set_label("")
        else:
            self._bat_donut.set_value(100)
            self._bat_pct_lbl.set_label("AC")
            self._bat_status_lbl.set_label(T("ac_power"))
            self._bat_health_lbl.set_label("")

        # Resources
        self._cpu_chart.set_value(d.get("cpu_pct", 0))
        self._ram_chart.set_value(d.get("ram_pct", 0))
        self._gpu_chart.set_value(d.get("gpu_pct", 0))

        # Hardware profile pills
        pp = d.get("pp", {})
        active = pp.get("active", "balanced")
        _PWR = {"power-saver": T("power_saver_lbl"),
                "balanced": T("balanced_lbl"),
                "performance": T("performance_lbl")}
        self._pills["power"].set_label(_PWR.get(active, active.capitalize()))

        # Update perf slider if it exists
        if hasattr(self, "_perf_strip"):
            mapped_active = "eco" if active == "power-saver" else active
            if mapped_active in self._perf_btns:
                btn = self._perf_btns[mapped_active]
                if not btn.get_active():
                    self._block_perf_sync = True
                    btn.set_active(True)
                    self._block_perf_sync = False

        fan = d.get("fan", {})
        fm = fan.get("mode", "auto").capitalize()
        fans = fan.get("fans", {})
        rpms = []
        for fid in sorted(fans.keys()):
            r = fans[fid].get("current", 0)
            if r > 0:
                rpms.append(str(r))
        rpm_str = "/".join(rpms) if rpms else "0"
        self._pills["fan"].set_label(f"{fm} @ {rpm_str} RPM")

        if hasattr(self, "_max_fan_btn"):
            if fm.lower() == "max":
                self._max_fan_btn.remove_css_class("clean-ram-action")
                self._max_fan_btn.add_css_class("destructive-action")
            else:
                self._max_fan_btn.remove_css_class("destructive-action")
                self._max_fan_btn.add_css_class("clean-ram-action")

        gi_d = d.get("gpu", {})
        self._pills["mux"].set_label(
            gi_d.get("mode", "unknown").capitalize())

        return False  # idle_add one-shot

    # ── Temp helpers (same logic as fan page) ─────────────────────────────
    @staticmethod
    def _find_hwmon(name):
        base = "/sys/class/hwmon"
        try:
            for d in sorted(os.listdir(base)):
                nf = os.path.join(base, d, "name")
                try:
                    with open(nf) as f:
                        if f.read().strip().lower() == name:
                            return os.path.join(base, d)
                except Exception:
                    pass
        except Exception:
            pass
        return None

    @classmethod
    def _get_cpu_temp(cls):
        for drv in ("coretemp", "k10temp"):
            hp = cls._find_hwmon(drv)
            if hp:
                try:
                    with open(os.path.join(hp, "temp1_input")) as f:
                        return int(f.read().strip()) / 1000
                except Exception:
                    pass
        hp = cls._find_hwmon("acpitz")
        if hp:
            try:
                with open(os.path.join(hp, "temp1_input")) as f:
                    return int(f.read().strip()) / 1000
            except Exception:
                pass
        return 0

    @classmethod
    def _get_gpu_temp(cls):
        if _NVIDIA_SMI:
            try:
                return float(subprocess.check_output(
                    [_NVIDIA_SMI, "--query-gpu=temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    stderr=subprocess.DEVNULL, timeout=3
                ).decode().strip())
            except Exception:
                pass
        hp = cls._find_hwmon("amdgpu")
        if hp:
            try:
                with open(os.path.join(hp, "temp1_input")) as f:
                    return int(f.read().strip()) / 1000
            except Exception:
                pass
        return 0

    # ── File read helpers ─────────────────────────────────────────────────
    @staticmethod
    def _read_int(base, name):
        path = os.path.join(base, name)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return int(f.read().strip())

    @staticmethod
    def _read_str(base, name):
        path = os.path.join(base, name)
        if not os.path.exists(path):
            return ""
        with open(path) as f:
            return f.read().strip()
