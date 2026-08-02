import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import math
import cairo
import concurrent.futures

class TemperatureRing(Gtk.Box):
    """Circular temperature indicator with emphasized value and muted unit."""

    def __init__(self, name: str, base_color: str = "blue"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_halign(Gtk.Align.CENTER)

        self._progress = 0.0
        self._base_color = (0.25, 0.52, 0.95) if base_color == "blue" else (0.90, 0.30, 0.30)
        self._color = self._base_color
        self._last_valid = False

        self._ring = Gtk.DrawingArea()
        self._ring.set_content_width(146)
        self._ring.set_content_height(146)
        self._ring.set_draw_func(self._draw_ring)

        overlay = Gtk.Overlay()
        overlay.set_child(self._ring)

        center = Gtk.Box(spacing=2)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        self._value_lbl = Gtk.Label(label="--")
        self._value_lbl.add_css_class("temp-value")
        self._unit_lbl = Gtk.Label(label="°C")
        self._unit_lbl.add_css_class("temp-unit")
        center.append(self._value_lbl)
        center.append(self._unit_lbl)
        overlay.add_overlay(center)

        self.append(overlay)

        name_lbl = Gtk.Label(label=name)
        name_lbl.add_css_class("dim-label")
        name_lbl.add_css_class("sensor-name")
        self.append(name_lbl)

    def set_diameter(self, size: int):
        s = max(96, int(size))
        self._ring.set_content_width(s)
        self._ring.set_content_height(s)

    def _temp_to_color(self, progress: float):
        if progress >= 0.80:
            return (0.96, 0.24, 0.24)
        if progress <= 0.12:
            return (0.95, 0.95, 0.95)
        return self._base_color

    def set_temperature(self, celsius: float, unit: str):
        try:
            celsius = float(celsius)
        except Exception:
            celsius = 0.0

        use_f = unit == "F"
        disp = int(celsius * 9 / 5 + 32) if use_f else int(celsius)
        unit_str = "°F" if use_f else "°C"

        if celsius and celsius > 0:
            self._value_lbl.set_label(str(disp))
            self._unit_lbl.set_label(unit_str)
            self._last_valid = True
            # Normalize around typical laptop thermal envelope.
            self._progress = max(0.0, min(1.0, (celsius - 25.0) / 75.0))
            self._color = self._temp_to_color(self._progress)
        else:
            self._value_lbl.set_label("--")
            self._unit_lbl.set_label(unit_str)
            self._last_valid = False
            self._progress = 0.0
            self._color = (0.95, 0.95, 0.95)

        self._ring.queue_draw()

    def _draw_ring(self, _area, cr, w, h):
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 10

        cr.set_line_width(8)
        cr.set_source_rgba(1, 1, 1, 0.09)
        cr.arc(cx, cy, radius, 0, _TWO_PI)
        cr.stroke()

        if self._progress > 0:
            cr.set_line_width(8)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(*self._color, 0.95)
            cr.arc(cx, cy, radius, -math.pi / 2, -math.pi / 2 + (_TWO_PI * self._progress))
            cr.stroke()

        if self._last_valid:
            cr.set_line_width(1.5)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.42)
            cr.arc(cx, cy, radius - 8, 0, _TWO_PI)
            cr.stroke()


class CPUSparkline(Gtk.DrawingArea):
    """Compact sparkline for recent CPU usage."""

    def __init__(
        self,
        capacity: int = 30,
        line_color=(0.45, 0.69, 0.96),
        fill_alpha: float = 0.20,
        dot_color=(0.84, 0.91, 1.0),
    ):
        super().__init__()
        self._capacity = capacity
        self._values = [0.0] * capacity
        self._line_color = line_color
        self._fill_alpha = fill_alpha
        self._dot_color = dot_color
        self.set_content_height(62)
        self.set_draw_func(self._draw)
        self.add_css_class("cpu-sparkline")

    def push_value(self, value: float):
        v = max(0.0, min(100.0, float(value)))
        self._values.append(v)
        self._values = self._values[-self._capacity :]
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        if w <= 2 or h <= 2:
            return

        points = self._values
        step = w / max(1, len(points) - 1)

        cr.set_source_rgba(1, 1, 1, 0.06)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.10)
        cr.set_line_width(1)
        for y in (0.25, 0.50, 0.75):
            yy = h * y
            cr.move_to(0, yy)
            cr.line_to(w, yy)
            cr.stroke()

        cr.set_source_rgba(*self._line_color, self._fill_alpha)
        cr.move_to(0, h)
        for i, val in enumerate(points):
            x = i * step
            y = h - (val / 100.0) * h
            cr.line_to(x, y)
        cr.line_to((len(points) - 1) * step, h)
        cr.close_path()
        cr.fill()

        cr.set_source_rgba(*self._line_color, 0.95)
        cr.set_line_width(2)
        for i, val in enumerate(points):
            x = i * step
            y = h - (val / 100.0) * h
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()

        last = points[-1] if points else 0
        dot_x = (len(points) - 1) * step
        dot_y = h - (last / 100.0) * h
        cr.set_source_rgba(*self._dot_color, 1.0)
        cr.arc(dot_x, dot_y, 3, 0, _TWO_PI)
        cr.fill()

class ResourceBox(Gtk.Box):
    """Linear percentage gauge inside a styled box."""
    def __init__(self, color_hex: str, label: str):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(8)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.CENTER)
        self.add_css_class("card")
        self.set_margin_start(5)
        self.set_margin_end(5)

        # Header: Label (Top Left) & Value (Top Right)
        header = Gtk.Box()
        header.set_spacing(10)
        lbl = Gtk.Label(label=label, xalign=0, css_classes=["dim-label"])
        header.append(lbl)
        header.append(Gtk.Label(hexpand=True)) # Spacer
        self.val_lbl = Gtk.Label(label="0%", xalign=1, css_classes=["title-4"])
        header.append(self.val_lbl)
        self.append(header)

        # Level Bar
        self.bar = Gtk.LevelBar()
        self.bar.set_min_value(0.0)
        self.bar.set_max_value(100.0)
        self.bar.set_value(0.0)
        self.bar.set_size_request(-1, 8)
        self.append(self.bar)

        # Custom CSS for the bar color
        css = f"levelbar block {{ background-color: {color_hex}; border-radius: 4px; }}"
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        self.bar.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_ui_scale(self, bucket: str):
        if bucket == "compact":
            self.set_margin_start(2)
            self.set_margin_end(2)
            self.bar.set_size_request(-1, 6)
        elif bucket == "spacious":
            self.set_margin_start(6)
            self.set_margin_end(6)
            self.bar.set_size_request(-1, 9)
        else:
            self.set_margin_start(5)
            self.set_margin_end(5)
            self.bar.set_size_request(-1, 8)

    def set_value(self, val: float):
        v = max(0.0, min(100.0, val))
        self.val_lbl.set_label(f"{int(v)}%")
        self.bar.set_value(v)


# ═════════════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE
# ═════════════════════════════════════════════════════════════════════════════
_REFRESH_MS = 7000          # background fetch period
_NVIDIA_SMI = None          # cached shutil.which result
_DBUS_TIMEOUT = 5           # seconds — prevents D-Bus hangs from freezing app
_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dash-dbus")


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


class OmenHighTechGauge(Gtk.DrawingArea):
    """Circular gauge replicating the OMEN speedometer design, scaled up."""

    def __init__(self, label="CPU", is_left=True, active_color=(0.66, 0.33, 0.97)):
        super().__init__()
        self.label = label
        self.is_left = is_left  # True for Left Gauge (CPU), False for Right (GPU)
        self.active_color = active_color
        
        self.usage = 0.0
        self.temp = 0.0
        self.speed = "0.00GHz"
        self.rpm = 0
        self.rotation = 0.0
        self.is_dark = True
        
        self.set_size_request(260, 260)
        self.set_draw_func(self._draw)

    def set_dark(self, is_dark):
        self.is_dark = is_dark
        self.queue_draw()

    def set_val(self, usage, temp, speed, rpm):
        self.usage = float(usage)
        self.temp = float(temp)
        self.speed = str(speed)
        self.rpm = int(rpm)
        self.queue_draw()

    def tick_rotation(self):
        if self.rpm > 0:
            speed = 0.03 + (self.rpm / 6000.0) * 0.15
            self.rotation += speed
            if self.rotation >= 2 * math.pi:
                self.rotation -= 2 * math.pi
            self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2 - 12
        r_main = 94
        r_tick_out = 85
        r_tick_in = 75
        
        # ── 1. Outer Temperature Arc & Ticks (Thicker and Offset) ──
        cr.set_line_width(5.5) # Even thicker temperature curves as requested
        
        if self.is_left:
            # CPU Temp Arc: Top-Left from 125° to 215°
            start_angle = 125 * math.pi / 180
            end_angle = 215 * math.pi / 180
            temp_pct = max(0.0, min(100.0, self.temp)) / 100.0
            fill_angle = start_angle + temp_pct * (end_angle - start_angle)
            
            # Base track
            if self.is_dark:
                cr.set_source_rgba(255, 255, 255, 0.05)
            else:
                cr.set_source_rgba(0, 0, 0, 0.06)
            cr.arc(cx, cy, r_main + 16, start_angle, end_angle)
            cr.stroke()
            
            # Fill track
            cr.set_source_rgba(*self.active_color, 0.85)
            cr.arc(cx, cy, r_main + 16, start_angle, fill_angle)
            cr.stroke()
            
            # Label temperature e.g. "51°C" bold, italic, and exactly ON TOP of the curve
            cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(18)
            if self.is_dark:
                cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
            else:
                cr.set_source_rgba(0.1, 0.11, 0.15, 0.95)
            cr.move_to(cx - 100, cy - 76) # Slightly larger label for clearer visibility
            cr.show_text(f"{int(self.temp)}°C")
        else:
            # GPU Temp Arc: Top-Right from 325° to 415°
            start_angle = 325 * math.pi / 180
            end_angle = 415 * math.pi / 180
            temp_pct = max(0.0, min(100.0, self.temp)) / 100.0
            fill_angle = start_angle + temp_pct * (end_angle - start_angle)
            
            # Base track
            if self.is_dark:
                cr.set_source_rgba(255, 255, 255, 0.05)
            else:
                cr.set_source_rgba(0, 0, 0, 0.06)
            cr.arc(cx, cy, r_main + 16, start_angle, end_angle)
            cr.stroke()
            
            # Fill track
            cr.set_source_rgba(*self.active_color, 0.85)
            cr.arc(cx, cy, r_main + 16, start_angle, fill_angle)
            cr.stroke()
            
            # Label temperature e.g. "0°C" bold, italic, and exactly ON TOP of the curve
            cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(18)
            if self.is_dark:
                cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
            else:
                cr.set_source_rgba(0.1, 0.11, 0.15, 0.95)
            cr.move_to(cx + 62, cy - 76) # Slightly larger label for clearer visibility
            cr.show_text(f"{int(self.temp)}°C")

        # ── 2. Speedometer Radial Ticks (Thicker) ──
        num_ticks = 72
        angle_step = 2 * math.pi / num_ticks
        
        for i in range(num_ticks):
            angle = -math.pi / 2 + i * angle_step
            is_active = (i / num_ticks) <= (self.usage / 100.0)
            
            cr.save()
            if is_active:
                cr.set_source_rgba(self.active_color[0], self.active_color[1], self.active_color[2], 0.9)
                cr.set_line_width(4.5) # Even thicker active ticks as requested
            else:
                if self.is_dark:
                    cr.set_source_rgba(255, 255, 255, 0.06)
                else:
                    cr.set_source_rgba(0, 0, 0, 0.08)
                cr.set_line_width(2.4) # Even thicker inactive ticks as requested
                
            x_in = cx + r_tick_in * math.cos(angle)
            y_in = cy + r_tick_in * math.sin(angle)
            x_out = cx + r_tick_out * math.cos(angle)
            y_out = cy + r_tick_out * math.sin(angle)
            
            cr.move_to(x_in, y_in)
            cr.line_to(x_out, y_out)
            cr.stroke()
            cr.restore()

        # Outer thick frame boundary line (Thicker)
        cr.set_line_width(3.0) # Even thicker boundary line as requested
        if self.is_dark:
            cr.set_source_rgba(255, 255, 255, 0.04)
        else:
            cr.set_source_rgba(0, 0, 0, 0.05)
        cr.arc(cx, cy, r_main, 0, 2 * math.pi)
        cr.stroke()

        # ── 3. Central Details ──
        # Label (CPU / GPU) - Italic and Bold using Sans and a forced shear slant matrix
        cr.save()
        cr.select_font_face("Sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        cr.set_source_rgba(self.active_color[0], self.active_color[1], self.active_color[2], 0.85)
        
        # Mathematically shear/slant font matrix to guarantee beautiful italic slant on all systems
        font_matrix = cr.get_font_matrix()
        font_matrix.xy = -0.25 * font_matrix.xx
        cr.set_font_matrix(font_matrix)
        
        te = cr.text_extents(self.label)
        cr.move_to(cx - te.width / 2, cy - r_tick_in * 0.35)
        cr.show_text(self.label)
        cr.restore()
        
        # Usage Value
        val_txt = f"{int(self.usage)}%"
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(32)
        if self.is_dark:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        else:
            cr.set_source_rgba(0.09, 0.11, 0.16, 0.95)
        te = cr.text_extents(val_txt)
        cr.move_to(cx - te.width / 2, cy + te.height / 2 - 3)
        cr.show_text(val_txt)
        
        # Clock Speed
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        if self.is_dark:
            cr.set_source_rgba(0.55, 0.60, 0.68, 0.7)
        else:
            cr.set_source_rgba(0.27, 0.33, 0.41, 0.8)
        te = cr.text_extents(self.speed)
        cr.move_to(cx - te.width / 2, cy + r_tick_in * 0.52)
        cr.show_text(self.speed)

        # ── 4. Fan Speed RPM text centered under dial (whiter, larger, italic, and bold) ──
        cr.select_font_face("Inter", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        if self.is_dark:
            cr.set_source_rgba(0.9, 0.94, 1.0, 0.95)
        else:
            cr.set_source_rgba(0.1, 0.11, 0.15, 0.95)
        rpm_txt = f"{self.rpm} RPM"
        te = cr.text_extents(rpm_txt)
        cr.move_to(cx - te.width / 2, cy + r_main + 26)
        cr.show_text(rpm_txt)


class OmenSpecsBridge(Gtk.DrawingArea):
    """Compact bridging bar for RAM, Disk, and Battery metrics."""

    def __init__(self, size_w=160, size_h=52, color=(0.24, 0.60, 1.0)):
        super().__init__()
        self.set_size_request(size_w, size_h)
        self.pct = 0.0
        self.text = ""
        self.color = color
        self.is_dark = True
        self.set_draw_func(self._draw)

    def set_dark(self, is_dark):
        self.is_dark = is_dark
        self.queue_draw()

    def set_val(self, pct, text):
        self.pct = float(pct)
        self.text = str(text)
        self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2
        bar_w = w * 0.90
        bar_h = 6
        bar_x = cx - bar_w / 2
        
        # ── 1. Thin Translucent Bridge line ──
        cr.set_line_width(1.0)
        if self.is_dark:
            cr.set_source_rgba(255, 255, 255, 0.03)
        else:
            cr.set_source_rgba(0, 0, 0, 0.04)
        cr.move_to(0, cy)
        cr.line_to(w, cy)
        cr.stroke()
        
        # ── 2. Background Capsule Tube ──
        if self.is_dark:
            cr.set_source_rgba(22, 25, 30, 0.95)
        else:
            cr.set_source_rgba(0, 0, 0, 0.06)
        cr.set_line_width(bar_h)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(bar_x, cy)
        cr.line_to(bar_x + bar_w, cy)
        cr.stroke()
        
        # Outer border
        if self.is_dark:
            cr.set_source_rgba(255, 255, 255, 0.08)
        else:
            cr.set_source_rgba(0, 0, 0, 0.04)
        cr.set_line_width(bar_h + 1.2)
        cr.move_to(bar_x, cy)
        cr.line_to(bar_x + bar_w, cy)
        cr.stroke()

        # ── 3. Glowing Fill ──
        fill_w = bar_w * (max(0.0, min(100.0, self.pct)) / 100.0)
        if fill_w > 0:
            cr.set_source_rgba(self.color[0], self.color[1], self.color[2], 0.95)
            cr.set_line_width(bar_h)
            cr.move_to(bar_x, cy)
            cr.line_to(bar_x + fill_w, cy)
            cr.stroke()
            
            # Subtle radial shadow/glow
            cr.set_source_rgba(self.color[0], self.color[1], self.color[2], 0.22)
            cr.set_line_width(bar_h + 3)
            cr.move_to(bar_x, cy)
            cr.line_to(bar_x + fill_w, cy)
            cr.stroke()
            
        # ── 4. Small Pointer Indicator Triangle on top ──
        px = bar_x + fill_w
        py = cy - bar_h / 2 - 3
        if self.is_dark:
            cr.set_source_rgb(1.0, 1.0, 1.0)
        else:
            cr.set_source_rgb(self.color[0], self.color[1], self.color[2])
        cr.move_to(px, py)
        cr.line_to(px - 3, py - 4)
        cr.line_to(px + 3, py - 4)
        cr.close_path()
        cr.fill()
        
        # ── 5. Details Text under the bar ──
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        if self.is_dark:
            cr.set_source_rgba(0.82, 0.86, 0.92, 0.8)
        else:
            cr.set_source_rgba(0.2, 0.25, 0.33, 0.85)
        te = cr.text_extents(self.text)
        cr.move_to(cx - te.width / 2, cy + bar_h + 14)
        cr.show_text(self.text)

# ═════════════════════════════════════════════════════════════════════════════
#  SYSTEM MONITOR DATA WORKER
# ═════════════════════════════════════════════════════════════════════════════

