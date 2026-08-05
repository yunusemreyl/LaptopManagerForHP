"""Theme-aware Cairo graph used by the dashboard telemetry card."""

import math
import cairo

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class TelemetryGraph(Gtk.DrawingArea):
    def __init__(self, history, series, kind="temperature", past_label="10m", now_label="0m"):
        super().__init__()
        self.history = history
        self.series = tuple(series)
        self.kind = kind
        self.past_label = past_label
        self.now_label = now_label
        self._dark = False
        self._temp_unit = "C"
        self.set_content_height(160)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_dark(self, is_dark):
        self._dark = bool(is_dark)
        self.queue_draw()

    def set_temp_unit(self, unit):
        self._temp_unit = "F" if unit == "F" else "C"
        self.queue_draw()

    def refresh(self):
        self.queue_draw()

    def _display_value(self, value):
        if value is None:
            return None
        if self.kind == "temperature" and self._temp_unit == "F":
            return value * 9.0 / 5.0 + 32.0
        return value

    def _bounds(self):
        if self.kind == "temperature":
            if self._temp_unit == "F":
                return 68.0, 230.0
            return 20.0, 110.0

        maximum = 0.0
        for key, _label, _color in self.series:
            values = [value for value in self.history.values(key) if value is not None]
            if values:
                maximum = max(maximum, max(values))
        return 0.0, max(4000.0, math.ceil(maximum / 1000.0) * 1000.0)

    def _draw(self, _area, cr, width, height):
        if width < 100 or height < 70:
            return

        text = (0.78, 0.76, 0.84, 0.88) if self._dark else (0.28, 0.25, 0.34, 0.80)
        grid = (0.72, 0.68, 0.80, 0.16) if self._dark else (0.28, 0.22, 0.38, 0.12)
        left, right, top, bottom = 48.0, 12.0, 10.0, 25.0
        plot_w = max(1.0, width - left - right)
        plot_h = max(1.0, height - top - bottom)
        y_min, y_max = self._bounds()

        cr.set_line_width(1.0)
        cr.select_font_face("Sans")
        cr.set_font_size(10.0)
        for index in range(5):
            ratio = index / 4.0
            y = top + plot_h * ratio
            cr.set_source_rgba(*grid)
            cr.move_to(left, y)
            cr.line_to(left + plot_w, y)
            cr.stroke()

            value = y_max - (y_max - y_min) * ratio
            suffix = "°F" if self.kind == "temperature" and self._temp_unit == "F" else "°C" if self.kind == "temperature" else ""
            label = f"{int(value)}{suffix}"
            cr.set_source_rgba(*text)
            extents = cr.text_extents(label)
            cr.move_to(left - extents.width - 7, y + extents.height / 2)
            cr.show_text(label)

        cr.set_source_rgba(*text)
        cr.move_to(left, height - 6)
        cr.show_text(self.past_label)
        now_extents = cr.text_extents(self.now_label)
        cr.move_to(left + plot_w - now_extents.width, height - 6)
        cr.show_text(self.now_label)

        x_step = plot_w / max(1, self.history.capacity - 1)
        for key, _label, color in self.series:
            values = self.history.values(key)
            if not values:
                continue
            x_start = left + plot_w - (len(values) - 1) * x_step
            active_path = False
            last_point = None
            cr.set_line_width(2.2)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(color[0], color[1], color[2], 0.96)
            for index, raw_value in enumerate(values):
                value = self._display_value(raw_value)
                if value is None:
                    if active_path:
                        cr.stroke()
                        active_path = False
                    continue
                clamped = max(y_min, min(y_max, value))
                x = x_start + index * x_step
                y = top + (y_max - clamped) / (y_max - y_min) * plot_h
                last_point = (x, y)
                if not active_path:
                    cr.move_to(x, y)
                    active_path = True
                else:
                    cr.line_to(x, y)
            if active_path:
                cr.stroke()
            if last_point is not None:
                cr.set_source_rgba(color[0], color[1], color[2], 1.0)
                cr.arc(last_point[0], last_point[1], 3.0, 0, 2 * math.pi)
                cr.fill()
