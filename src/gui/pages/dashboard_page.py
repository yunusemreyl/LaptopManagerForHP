#!/usr/bin/env python3
"""
Dashboard Page — OMEN Command Center for Linux
Provides system-monitor-only overview: temperatures, fan, battery, and usage.
All heavy I/O runs in a background thread.
"""

import gi, math, json, subprocess, os, shutil, threading, concurrent.futures

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk
from components.custom_widgets import TemperatureRing, CPUSparkline, ResourceBox
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

_NVIDIA_SMI = None
_DBUS_TIMEOUT = 5
_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dash-dbus")

def _dbus_call(fn, *args, timeout=_DBUS_TIMEOUT):
    fut = _dbus_pool.submit(fn, *args)
    try:
        return fut.result(timeout=timeout)
    except Exception as e:
        print(f"⚠ Dash D-Bus call failed: {e}")
        return None
class DashboardPage(Gtk.Box):
    """Main dashboard: 4-pane grid with info bar."""

    def __init__(self, services=None, on_navigate=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self.services = services or {}
        self.on_navigate = on_navigate
        self._timer_id = None
        self._cpu_prev = None       # (total, idle) for delta calc
        self._cpu_smooth = 0.0      # EMA-smoothed CPU %
        self._data = {}             # latest bg-fetched snapshot
        self._busy = False          # guard against overlapping bg threads
        self._temp_unit = "C"       # temperature unit preference
        self._gpu_runtime_status_path = None
        self._gpu_runtime_status_scanned = False

        global _NVIDIA_SMI
        if _NVIDIA_SMI is None:
            _NVIDIA_SMI = shutil.which("nvidia-smi") or ""

        self._build()
        # Delay the first tick to avoid resource contention during app startup
        GLib.timeout_add(1500, self._initial_start)

    def _initial_start(self):
        self._tick()
        self._timer_id = GLib.timeout_add(_REFRESH_MS, self._tick)
        return False

    def refresh(self):
        """Public refresh to force a data update on navigation."""
        if not self._busy:
            self._busy = True
            threading.Thread(target=self._fetch, daemon=True).start()
        # Also update theme for donut charts
        # Update resources if needed
        for box in (self._disk_chart, self._ram_chart):
            if hasattr(box, "refresh"): box.refresh()

    # ── public ────────────────────────────────────────────────────────────
    def set_services(self, svcs):
        self.services = svcs

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
        self._root_box = root

        heading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        heading_box.append(self._heading(T("sys_info")))
        heading_box.append(Gtk.Separator())
        root.append(heading_box)

        top_row = Gtk.Box(spacing=18, homogeneous=True)
        top_row.append(self._mk_quick_status(embedded=False))
        top_row.append(self._mk_resources(embedded=False))
        self._top_row = top_row
        root.append(top_row)

    def set_ui_scale(self, bucket, _width=0, _height=0):
        root = getattr(self, "_root_box", None)
        if root is not None:
            if bucket == "compact":
                root.set_spacing(12)
                root.set_margin_top(10)
                root.set_margin_start(12)
                root.set_margin_end(12)
                root.set_margin_bottom(12)
            elif bucket == "spacious":
                root.set_spacing(20)
                root.set_margin_top(20)
                root.set_margin_start(30)
                root.set_margin_end(30)
                root.set_margin_bottom(22)
            else:
                root.set_spacing(18)
                root.set_margin_top(16)
                root.set_margin_start(24)
                root.set_margin_end(24)
                root.set_margin_bottom(20)

        row = getattr(self, "_top_row", None)
        if row is not None:
            row.set_spacing(12 if bucket == "compact" else 22 if bucket == "spacious" else 18)

        ring_size = 124 if bucket == "compact" else 160 if bucket == "spacious" else 146
        for ring in (getattr(self, "_cpu_temp", None), getattr(self, "_gpu_temp", None)):
            if ring is not None and hasattr(ring, "set_diameter"):
                ring.set_diameter(ring_size)

        for box in (getattr(self, "_disk_chart", None), getattr(self, "_ram_chart", None)):
            if box is not None and hasattr(box, "set_ui_scale"):
                box.set_ui_scale(bucket)

        if hasattr(self, "_max_fan_btn") and self._max_fan_btn is not None:
            h = 44 if bucket == "compact" else 54 if bucket == "spacious" else 50
            self._max_fan_btn.set_size_request(-1, h)

    # ── Quick Status ──────────────────────────────────────────────────────
    def _mk_quick_status(self, embedded=False):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        if embedded:
            card.add_css_class("inner-panel")
        else:
            card.add_css_class("card")

        card.append(self._heading(T("quick_status")))
        card.append(Gtk.Separator())

        # Temperature boxes side-by-side
        temps = Gtk.Box(spacing=14, homogeneous=True)
        card.append(temps)
        self._cpu_temp = self._mk_sensor(temps, "CPU")
        self._gpu_temp = self._mk_sensor(temps, "GPU")

        shortcut_box = Gtk.Box()
        shortcut_box.set_halign(Gtk.Align.CENTER)
        self._perf_shortcut_btn = Gtk.Button(label=T("go_performance"))
        self._perf_shortcut_btn.add_css_class("dashboard-link-btn")
        self._perf_shortcut_btn.connect("clicked", self._on_open_performance)
        shortcut_box.append(self._perf_shortcut_btn)
        card.append(shortcut_box)

        card.append(Gtk.Separator())

        fan_row = Gtk.Box(spacing=8)
        fan_row.append(Gtk.Label(label=T("fan_metric"), xalign=0, css_classes=["dim-label"]))
        fan_row.append(Gtk.Label(hexpand=True))
        self._fan_lbl = Gtk.Label(label="-- RPM", xalign=1, css_classes=["title-4"])
        fan_row.append(self._fan_lbl)
        card.append(fan_row)

        bat_hdr = Gtk.Box(spacing=8)
        bat_lbl = Gtk.Label(label=T("battery"), xalign=0, css_classes=["dim-label"])
        bat_hdr.append(bat_lbl)
        bat_hdr.append(Gtk.Label(hexpand=True))
        self._bat_pct_lbl = Gtk.Label(label="--%", xalign=1, css_classes=["title-4"])
        bat_hdr.append(self._bat_pct_lbl)
        card.append(bat_hdr)

        self._bat_chart = CPUSparkline(
            capacity=30,
            line_color=(0.18, 0.76, 0.49),
            fill_alpha=0.26,
            dot_color=(0.84, 1.0, 0.90),
        )
        self._bat_chart.add_css_class("battery-sparkline-frame")
        card.append(self._bat_chart)
        
        self._bat_status_lbl = Gtk.Label(label="", xalign=0.5, css_classes=["dim-label"])
        self._bat_health_lbl = Gtk.Label(label="", xalign=0.5, css_classes=["dim-label"])
        card.append(self._bat_status_lbl)
        card.append(self._bat_health_lbl)

        return card

    # ── Hardware Profile ──────────────────────────────────────────────────
    def _mk_hw_profile(self, embedded=False):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        if embedded:
            card.add_css_class("inner-panel")
        else:
            card.add_css_class("card")

        card.append(self._heading(T("hardware_profile")))
        card.append(Gtk.Separator())

        strips = Gtk.Box(spacing=10, homogeneous=True)
        card.append(strips)

        self._pills = {}
        self._pill_frames = {}
        for key, icon_name, caption in (
            ("power", "battery-symbolic",        T("power_profile_label")),
            ("fan",   "weather-tornado-symbolic", T("fan_mode_label")),
            ("mux",   "video-display-symbolic",   T("gpu_mux_label")),
        ):
            frame = Gtk.Frame()
            frame.add_css_class("pill-frame")
            frame.add_css_class("profile-strip")
            frame.add_css_class("profile-tile")

            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            row.set_halign(Gtk.Align.CENTER)
            row.set_valign(Gtk.Align.CENTER)
            row.set_margin_top(10)
            row.set_margin_bottom(10)
            row.set_margin_start(12)
            row.set_margin_end(12)

            ic = Gtk.Image.new_from_icon_name(icon_name)
            ic.set_pixel_size(20)
            ic.set_halign(Gtk.Align.CENTER)
            row.append(ic)

            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            col.set_halign(Gtk.Align.CENTER)
            cap_lbl = Gtk.Label(label=caption, xalign=0.5,
                                css_classes=["dim-label", "profile-caption"])
            col.append(cap_lbl)
            val = Gtk.Label(label="—", xalign=0.5, css_classes=["title-4", "profile-value"])
            col.append(val)
            row.append(col)

            frame.set_child(row)
            
            nav_target = "mux" if key == "mux" else "fan"
            gesture = Gtk.GestureClick.new()
            gesture.connect("pressed", lambda g, n, x, y, t=nav_target: self.on_navigate(t) if self.on_navigate else None)
            frame.add_controller(gesture)
            frame.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            
            strips.append(frame)
            self._pills[key] = val
            self._pill_frames[key] = frame

        return card

    # ── Resources ─────────────────────────────────────────────────────────
    def _mk_resources(self, embedded=False):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        if embedded:
            card.add_css_class("inner-panel")
        else:
            card.add_css_class("card")

        card.append(self._heading(T("resources")))
        card.append(Gtk.Separator())

        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        spark_hdr = Gtk.Box(spacing=8)
        spark_lbl = Gtk.Label(label=T("cpu_load_30s"), xalign=0, css_classes=["dim-label"])
        spark_hdr.append(spark_lbl)
        spark_hdr.append(Gtk.Label(hexpand=True))
        self._cpu_pct_lbl = Gtk.Label(label="0%", xalign=1, css_classes=["title-4"])
        spark_hdr.append(self._cpu_pct_lbl)
        column.append(spark_hdr)

        self._cpu_spark = CPUSparkline()
        self._cpu_spark.add_css_class("cpu-sparkline-frame")
        column.append(self._cpu_spark)

        self._disk_chart = ResourceBox("#9d65ff", T("disk"))
        self._ram_chart = ResourceBox("#2ec27e", T("ram"))
        column.append(self._disk_chart)
        column.append(self._ram_chart)
        card.append(column)
        return card

    # ── Quick Actions ─────────────────────────────────────────────────────
    def _mk_quick_actions(self, embedded=False):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       vexpand=True)
        if embedded:
            card.add_css_class("inner-panel")
        else:
            card.add_css_class("card")

        card.append(self._heading(T("quick_actions")))
        card.append(Gtk.Separator())

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.append(vbox)
        
        row1 = Gtk.Box(spacing=10, homogeneous=True)
        vbox.append(row1)
        # Squeeze height for secondary actions
        self._max_fan_btn = self._mk_action_button(
            T("max_fan"), "weather-tornado-symbolic", "max_fan", "max-fan-action"
        )
        self._max_fan_btn.set_size_request(-1, 50)
        row1.append(self._max_fan_btn)
        
        clean_ram_btn = self._mk_action_button(
            T("clean_memory"), "edit-clear-all-symbolic", "clean_ram", "clean-ram-action"
        )
        clean_ram_btn.set_size_request(-1, 50)
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

        self._conflict_lbl = Gtk.Label(label="", use_markup=True, xalign=0.5, wrap=True)
        self._conflict_lbl.add_css_class("warning-text")
        self._conflict_lbl.set_visible(False)
        vbox.append(self._conflict_lbl)

        return card

    # ── tiny helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _heading(text):
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class("heading")
        return lbl

    @staticmethod
    def _mk_sensor(parent, name):
        base_color = "blue" if name.upper() == "CPU" else "red"
        ring = TemperatureRing(name, base_color)
        parent.append(ring)
        return ring

    def _on_open_performance(self, *_args):
        if self.on_navigate:
            self.on_navigate("fan")

    def _mk_action_button(self, text, icon_name, action_id, css_class):
        btn = Gtk.Button(hexpand=True, vexpand=False)
        btn.add_css_class(css_class)

        row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        ic = Gtk.Image.new_from_icon_name(icon_name)
        ic.set_pixel_size(16)
        row.append(ic)

        lbl = Gtk.Label(label=text)
        lbl.add_css_class("action-btn-label")
        row.append(lbl)

        row.add_css_class("action-btn-content")
        btn.set_child(row)
        btn.connect("clicked", self._on_action, action_id)
        return btn

    # ═════════════════════════════════════════════════════════════════════════
    #  ACTIONS
    # ═════════════════════════════════════════════════════════════════════════
    def _on_perf_toggled(self, btn, mode):
        if not btn.get_active() or getattr(self, "_block_perf_sync", False):
            return
        self._on_action(None, mode)

    def _on_action(self, _btn, action_id):
        """Dispatch D-Bus action to a background thread to avoid UI freezing."""
        def _bg():
            try:
                if action_id == "max_fan":
                    if "fan" in self.services and self.services["fan"]:
                        fan_data = self._data.get("fan", {})
                        current_mode = fan_data.get("mode", "auto")
                        if current_mode == "max":
                            _dbus_call(self.services["fan"].SetFanMode, "auto")
                        else:
                            _dbus_call(self.services["fan"].SetFanMode, "max")
                elif action_id == "balanced" or action_id == "eco":
                    if "power" in self.services and self.services["power"]:
                        _dbus_call(self.services["power"].SetPowerProfile, action_id if action_id == "balanced" else "power-saver")
                elif action_id == "performance" or action_id == "perf":
                    if "power" in self.services and self.services["power"]:
                        _dbus_call(self.services["power"].SetPowerProfile, "performance")
                elif action_id == "clean_ram":
                    if "platform" in self.services and self.services["platform"]:
                        _dbus_call(self.services["platform"].CleanMemory)
            except Exception as e:
                print(f"[Dashboard] action '{action_id}' failed: {e}")
        threading.Thread(target=_bg, daemon=True).start()

    # ═════════════════════════════════════════════════════════════════════════
    #  BACKGROUND DATA FETCH  –  keeps UI thread free
    # ═════════════════════════════════════════════════════════════════════════
    def _tick(self):
        # Eğer bu fonksiyon yanlışlıkla idle_add ile çağrılırsa sonsuz döngüye girmesin.
        if not self.get_mapped() or self._busy:
            return GLib.SOURCE_CONTINUE
            
        self._busy = True
        threading.Thread(target=self._fetch, daemon=True).start()
        return GLib.SOURCE_CONTINUE

    def _fetch(self):
        """Run ALL blocking I/O here (daemon D-Bus, /proc, nvidia-smi)."""
        d = {}

        if self.services:
            try:
                if "platform" in self.services and self.services["platform"]:
                    raw = _dbus_call(self.services["platform"].GetSystemInfo)
                    if raw is not None:
                        d["sys"] = json.loads(raw)
            except Exception: pass
            
            try:
                if "fan" in self.services and self.services["fan"]:
                    raw = _dbus_call(self.services["fan"].GetFanInfo)
                    if raw is not None:
                        d["fan"] = json.loads(raw)
            except Exception: pass

            try:
                if "power" in self.services and self.services["power"]:
                    raw = _dbus_call(self.services["power"].GetPowerProfile)
                    if raw is not None:
                        d["power"] = json.loads(raw)
            except Exception: pass

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
                cpu = f.readline().strip().split()
            vals = [int(x) for x in cpu[1:9]]
            user, nice, system, idle, iowait, irq, softirq, steal = vals
            idle_all = idle + iowait
            total = sum(vals)
            pct = self._cpu_smooth

            if self._cpu_prev is not None:
                prev_total, prev_idle = self._cpu_prev
                total_delta = total - prev_total
                idle_delta = idle_all - prev_idle
                if total_delta > 0:
                    pct = (1.0 - (idle_delta / total_delta)) * 100.0

            self._cpu_prev = (total, idle_all)

            if self._cpu_smooth <= 0.0:
                self._cpu_smooth = max(0.0, min(100.0, pct))
            else:
                self._cpu_smooth = (self._cpu_smooth * 0.62) + (max(0.0, min(100.0, pct)) * 0.38)
            d["cpu_pct"] = self._cpu_smooth
        except Exception:
            pass

        # ── Disk % from shutil ────────────────────────────────────────────
        try:
            usage = shutil.disk_usage("/")
            d["disk_pct"] = (usage.used / usage.total) * 100
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
            pci_path = self._get_nvidia_runtime_status_path()

            if pci_path is not None and os.path.exists(pci_path):
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
                        stderr=subprocess.DEVNULL, timeout=2
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

        # ── Power conflict check ──────────────────────────────────────────
        conflict = None
        for tool in ("tlp", "auto-cpufreq"):
            try:
                res = subprocess.run(["systemctl", "is-active", f"{tool}.service"],
                                     capture_output=True, text=True, timeout=1.0)
                if res.stdout.strip() == "active":
                    conflict = tool
                    break
            except Exception: pass
        d["power_conflict"] = conflict

        self._data = d
        GLib.idle_add(self._apply)

    # ── Apply data to widgets (main thread) ───────────────────────────────
    def _apply(self):
        d = self._data
        self._busy = False

        # Temps
        self._cpu_temp.set_temperature(d.get("cpu_temp", 0), self._temp_unit)
        self._gpu_temp.set_temperature(d.get("gpu_temp", 0), self._temp_unit)

        # Battery
        cap = d.get("bat_cap")
        if cap is not None:
            self._bat_chart.push_value(cap)
            self._bat_pct_lbl.set_label(f"{int(cap)}%")
            self._bat_status_lbl.set_label(f"{cap}% • {d.get('bat_stat', '')}")
            health = d.get("bat_health")
            if health is not None:
                self._bat_health_lbl.set_label(f"{T('health')}: {health}%")
            else:
                self._bat_health_lbl.set_label("")
        else:
            self._bat_chart.push_value(100)
            self._bat_pct_lbl.set_label("100%")
            self._bat_status_lbl.set_label(T("ac_power"))
            self._bat_health_lbl.set_label("")

        # Resources
        cpu_pct = d.get("cpu_pct")
        if cpu_pct is not None:
            self._cpu_spark.push_value(cpu_pct)
            self._cpu_pct_lbl.set_label(f"{int(cpu_pct)}%")
        self._disk_chart.set_value(d.get("disk_pct", 0.0))
        self._ram_chart.set_value(d.get("ram_pct", 0.0))

        # Performance Mode Sync
        power_profile = d.get("power", {})
        active_p = power_profile.get("active", "")
        if active_p:
            ui_mode = "balanced"
            if active_p == "power-saver":
                ui_mode = "eco"
            elif active_p == "performance":
                ui_mode = "performance"
            
            if ui_mode in self._perf_btns:
                btn = self._perf_btns[ui_mode]
                if not btn.get_active():
                    self._block_perf_sync = True
                    btn.set_active(True)
                    self._block_perf_sync = False

        # Conflict check
        conflict = d.get("power_conflict")
        if conflict:
            self._conflict_lbl.set_markup(f"⚠️ <b>Conflict Detected:</b> {conflict}.service is running, which may override OmenCtl.")
            self._conflict_lbl.set_visible(True)
        else:
            self._conflict_lbl.set_visible(False)

        fan = d.get("fan", {})
        fm = fan.get("mode", "auto").capitalize()
        fans = fan.get("fans", {})
        rpms = []
        for fid in sorted(fans.keys()):
            r = fans[fid].get("current", 0)
            if r > 0:
                rpms.append(str(r))
        rpm_str = "/".join(rpms) if rpms else "0"
        self._fan_lbl.set_label(f"{fm} • {rpm_str} RPM")

        return False  # idle_add one-shot

    # ── Temp helpers (same logic as fan page) ─────────────────────────────
    def _get_nvidia_runtime_status_path(self):
        if self._gpu_runtime_status_scanned:
            return self._gpu_runtime_status_path

        self._gpu_runtime_status_scanned = True
        try:
            for dev in os.listdir("/sys/bus/pci/devices"):
                vendor_file = f"/sys/bus/pci/devices/{dev}/vendor"
                if not os.path.exists(vendor_file):
                    continue
                try:
                    with open(vendor_file) as f:
                        if f.read().strip() == "0x10de":
                            path = f"/sys/bus/pci/devices/{dev}/power/runtime_status"
                            self._gpu_runtime_status_path = path if os.path.exists(path) else None
                            break
                except Exception:
                    continue
        except Exception:
            pass
        return self._gpu_runtime_status_path

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

