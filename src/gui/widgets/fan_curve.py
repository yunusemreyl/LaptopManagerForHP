#!/usr/bin/env python3
"""
Fan Curve Widget - Draggable temperature/speed line graph.
X axis: Temperature (°C)  30-100
Y axis: Fan Speed (%)      0-100
"""
import math
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib


# Default curve points (temp_C, fan_pct)
DEFAULT_POINTS = [
    (35, 0),
    (50, 20),
    (65, 50),
    (80, 80),
    (95, 100),
]

TEMP_MIN = 30
TEMP_MAX = 100
FAN_MIN = 0
FAN_MAX = 100

# Drawing constants
PAD_L = 55
PAD_R = 20
PAD_T = 20
PAD_B = 45
POINT_RADIUS = 8
SNAP_DIST = 20


class FanCurveWidget(Gtk.DrawingArea):
    """Interactive fan curve editor with draggable control points."""

    def __init__(self):
        super().__init__()
        self.set_content_width(500)
        self.set_content_height(260)

        self.points = [list(p) for p in DEFAULT_POINTS]
        self.dragging = -1  # index of point being dragged
        self.hover = -1
        self.current_temp = 0.0  # live CPU temp marker
        self.on_curve_changed = None  # callback

        self.set_draw_func(self._draw)

        self.interactive = True

        # Mouse events
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def set_interactive(self, interactive):
        self.interactive = interactive
        if not interactive:
            self.set_cursor(None)
            self.hover = -1
            self.dragging = -1
            self.queue_draw()

    def set_points(self, pts):
        self.points = [list(p) for p in pts]
        self.queue_draw()

    def get_points(self):
        return [tuple(p) for p in self.points]

    def get_fan_pct_for_temp(self, temp):
        """Interpolate fan % for a given temperature."""
        if not self.points:
            return 0
        if temp <= self.points[0][0]:
            return self.points[0][1]
        if temp >= self.points[-1][0]:
            return self.points[-1][1]
        for i in range(len(self.points) - 1):
            t0, f0 = self.points[i]
            t1, f1 = self.points[i + 1]
            if t0 <= temp <= t1:
                ratio = (temp - t0) / (t1 - t0) if t1 != t0 else 0
                return f0 + (f1 - f0) * ratio
        return 0

    def set_current_temp(self, temp):
        self.current_temp = temp
        self.queue_draw()

    def _temp_to_x(self, temp, w):
        graph_w = w - PAD_L - PAD_R
        return PAD_L + (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN) * graph_w

    def _fan_to_y(self, fan, h):
        graph_h = h - PAD_T - PAD_B
        return PAD_T + graph_h - (fan - FAN_MIN) / (FAN_MAX - FAN_MIN) * graph_h

    def _x_to_temp(self, x, w):
        graph_w = w - PAD_L - PAD_R
        return TEMP_MIN + (x - PAD_L) / graph_w * (TEMP_MAX - TEMP_MIN)

    def _y_to_fan(self, y, h):
        graph_h = h - PAD_T - PAD_B
        return FAN_MAX - (y - PAD_T) / graph_h * (FAN_MAX - FAN_MIN)

    def _draw(self, _, cr, w, h):
        graph_w = w - PAD_L - PAD_R
        graph_h = h - PAD_T - PAD_B

        # Background
        cr.set_source_rgba(0.117, 0.117, 0.141, 1.0)
        cr.rectangle(PAD_L, PAD_T, graph_w, graph_h)
        cr.fill()

        # Grid lines
        cr.set_line_width(0.5)
        cr.set_source_rgba(1, 1, 1, 0.15)
        for t in range(TEMP_MIN, TEMP_MAX + 1, 10):
            x = self._temp_to_x(t, w)
            cr.move_to(x, PAD_T)
            cr.line_to(x, PAD_T + graph_h)
            cr.stroke()
        for f in range(FAN_MIN, FAN_MAX + 1, 20):
            y = self._fan_to_y(f, h)
            cr.move_to(PAD_L, y)
            cr.line_to(PAD_L + graph_w, y)
            cr.stroke()

        # Axis labels
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.select_font_face("sans-serif", 0, 0)
        cr.set_font_size(10)

        for t in range(TEMP_MIN, TEMP_MAX + 1, 10):
            x = self._temp_to_x(t, w)
            cr.move_to(x - 8, h - PAD_B + 20)
            cr.show_text(f"{t}°")

        for f in range(FAN_MIN, FAN_MAX + 1, 20):
            y = self._fan_to_y(f, h)
            cr.move_to(PAD_L - 30, y + 4)
            cr.show_text(f"{f}%")

        # Axis titles
        cr.set_font_size(10)
        cr.set_source_rgba(1, 1, 1, 0.35)
        cr.move_to(PAD_L + graph_w / 2 - 25, h - 3)
        cr.show_text("Sıcaklık (°C)")

        cr.save()
        cr.move_to(12, PAD_T + graph_h / 2 + 25)
        cr.rotate(-math.pi / 2)
        cr.show_text("Fan Hızı (%)")
        cr.restore()

        # Fill under curve
        if len(self.points) >= 2:
            cr.move_to(self._temp_to_x(self.points[0][0], w), self._fan_to_y(0, h))
            for t, f in self.points:
                cr.line_to(self._temp_to_x(t, w), self._fan_to_y(f, h))
            cr.line_to(self._temp_to_x(self.points[-1][0], w), self._fan_to_y(0, h))
            cr.close_path()
            cr.set_source_rgba(0.486, 0.702, 0.259, 0.12)
            cr.fill()

        # Curve line
        if len(self.points) >= 2:
            cr.set_line_width(2.5)
            cr.set_source_rgba(0.486, 0.702, 0.259, 0.9)
            first = True
            for t, f in self.points:
                x, y = self._temp_to_x(t, w), self._fan_to_y(f, h)
                if first:
                    cr.move_to(x, y)
                    first = False
                else:
                    cr.line_to(x, y)
            cr.stroke()

        # Control points
        for i, (t, f) in enumerate(self.points):
            x, y = self._temp_to_x(t, w), self._fan_to_y(f, h)
            r = POINT_RADIUS + (2 if i == self.hover else 0)

            # Outer glow
            cr.set_source_rgba(0.486, 0.702, 0.259, 0.3 if i == self.hover else 0.15)
            cr.arc(x, y, r + 4, 0, 2 * math.pi)
            cr.fill()

            # Point
            if i == self.dragging:
                cr.set_source_rgba(0.486, 0.702, 0.259, 1.0)
            elif i == self.hover:
                cr.set_source_rgba(0.6, 0.85, 0.35, 1.0)
            else:
                cr.set_source_rgba(0.486, 0.702, 0.259, 0.85)
            cr.arc(x, y, r, 0, 2 * math.pi)
            cr.fill()

            # Inner dot
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.arc(x, y, 3, 0, 2 * math.pi)
            cr.fill()

            # Value tooltip on hover
            if i == self.hover or i == self.dragging:
                cr.set_font_size(10)
                cr.set_source_rgba(1, 1, 1, 0.9)
                label = f"{int(t)}° → {int(f)}%"
                cr.move_to(x - 20, y - r - 8)
                cr.show_text(label)

        # Current temperature marker
        if TEMP_MIN <= self.current_temp <= TEMP_MAX:
            tx = self._temp_to_x(self.current_temp, w)
            fan_pct = self.get_fan_pct_for_temp(self.current_temp)
            ty = self._fan_to_y(fan_pct, h)

            # Vertical line
            cr.set_line_width(1)
            cr.set_source_rgba(1, 0.4, 0.2, 0.4)
            cr.set_dash([4, 4])
            cr.move_to(tx, PAD_T)
            cr.line_to(tx, PAD_T + graph_h)
            cr.stroke()
            cr.set_dash([])

            # Marker dot
            cr.set_source_rgba(1, 0.4, 0.2, 1.0)
            cr.arc(tx, ty, 5, 0, 2 * math.pi)
            cr.fill()

            # Label
            cr.set_font_size(10)
            cr.set_source_rgba(1, 0.4, 0.2, 1.0)
            cr.move_to(tx + 8, ty - 6)
            cr.show_text(f"{int(self.current_temp)}°C → {int(fan_pct)}%")

    def _find_point_at(self, x, y, w, h):
        for i, (t, f) in enumerate(self.points):
            px = self._temp_to_x(t, w)
            py = self._fan_to_y(f, h)
            dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
            if dist < SNAP_DIST:
                return i
        return -1

    def _on_drag_begin(self, gesture, start_x, start_y):
        if not self.interactive:
            return
        w = self.get_width()
        h = self.get_height()
        idx = self._find_point_at(start_x, start_y, w, h)
        if idx >= 0:
            self.dragging = idx
            self._drag_start_x = start_x
            self._drag_start_y = start_y

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if self.dragging < 0:
            return
        w = self.get_width()
        h = self.get_height()
        x = self._drag_start_x + offset_x
        y = self._drag_start_y + offset_y

        new_temp = self._x_to_temp(x, w)
        new_fan = self._y_to_fan(y, h)

        # Clamp
        new_temp = max(TEMP_MIN, min(TEMP_MAX, new_temp))
        new_fan = max(FAN_MIN, min(FAN_MAX, new_fan))

        # Prevent crossing neighbors
        if self.dragging > 0:
            new_temp = max(new_temp, self.points[self.dragging - 1][0] + 1)
        if self.dragging < len(self.points) - 1:
            new_temp = min(new_temp, self.points[self.dragging + 1][0] - 1)

        self.points[self.dragging] = [new_temp, new_fan]
        self.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        if self.dragging >= 0:
            self.dragging = -1
            if self.on_curve_changed:
                self.on_curve_changed(self.get_points())
            self.queue_draw()

    def _on_motion(self, controller, x, y):
        if not self.interactive:
            return
        w = self.get_width()
        h = self.get_height()
        new_hover = self._find_point_at(x, y, w, h)
        if new_hover != self.hover:
            self.hover = new_hover
            self.set_cursor(Gdk.Cursor.new_from_name("pointer") if new_hover >= 0 else None)
            self.queue_draw()

    def _on_leave(self, controller):
        self.hover = -1
        self.set_cursor(None)
        self.queue_draw()
