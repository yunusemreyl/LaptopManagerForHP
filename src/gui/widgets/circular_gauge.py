#!/usr/bin/env python3
"""Circular gauge widget using Cairo — theme-aware text color."""
import math
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango, PangoCairo


class CircularGauge(Gtk.DrawingArea):
    def __init__(self, label, color, size=140):
        super().__init__()
        self.set_size_request(size, size)
        self.label = label
        self.color = color
        self.val = 0
        self.txt = "0"
        self._dark = True  # default assume dark
        self.set_draw_func(self._draw)

    def set_val(self, value, text):
        self.val = value
        self.txt = text
        self.queue_draw()

    def set_dark(self, is_dark):
        self._dark = is_dark
        self.queue_draw()

    def _draw(self, _, cr, w, h):
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 12

        # Background arc
        cr.set_line_width(6)
        if self._dark:
            cr.set_source_rgba(1, 1, 1, 0.08)
        else:
            cr.set_source_rgba(0, 0, 0, 0.08)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

        # Value arc
        if self.val > 0:
            cr.set_line_width(6)
            cr.set_line_cap(1)  # ROUND
            cr.set_source_rgb(*self.color)
            angle = 2 * math.pi * min(self.val, 100) / 100
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + angle)
            cr.stroke()

        # Value text — adapt to theme
        if self._dark:
            cr.set_source_rgb(1, 1, 1)
        else:
            cr.set_source_rgb(0.12, 0.12, 0.14)
        layout = PangoCairo.create_layout(cr)
        layout.set_text(self.txt, -1)
        layout.set_font_description(Pango.FontDescription("Sans Bold 18"))
        _, log_ext = layout.get_extents()
        cr.move_to(cx - log_ext.width / Pango.SCALE / 2, cy - log_ext.height / Pango.SCALE / 2 - 6)
        PangoCairo.show_layout(cr, layout)

        # Label text
        if self._dark:
            cr.set_source_rgba(1, 1, 1, 0.5)
        else:
            cr.set_source_rgba(0, 0, 0, 0.5)
        layout2 = PangoCairo.create_layout(cr)
        layout2.set_text(self.label, -1)
        layout2.set_font_description(Pango.FontDescription("Sans Bold 9"))
        _, log_ext2 = layout2.get_extents()
        cr.move_to(cx - log_ext2.width / Pango.SCALE / 2, cy + r * 0.45)
        PangoCairo.show_layout(cr, layout2)
