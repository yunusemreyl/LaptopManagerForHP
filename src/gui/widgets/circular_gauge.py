#!/usr/bin/env python3
"""Circular gauge widget using Cairo — theme-aware text color."""
import os
import math
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango, PangoCairo
import cairo

class CircularGauge(Gtk.DrawingArea):
    def __init__(self, label, color, size=140):
        super().__init__()
        self.set_size_request(size, size)
        self.label = label
        self.color = color
        self.val = 0
        self.txt = "0"
        self._dark = True  # default assume dark
        
        self.rotation = 0.0
        self.fan_surface = None
        
        img_path = os.path.join(os.path.dirname(__file__), "..", "..", "images", "fanpage.png")
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
            # Parse RPM from text if available (e.g. "3400 RPM" -> 3400)
            rpm = int(''.join(c for c in self.txt if c.isdigit()))
        except ValueError:
            rpm = (self.val / 100) * max_rpm
            
        if rpm > 0:
            # Base rotation increment on RPM
            base_increment = 0.1
            scale = rpm / max_rpm
            self.rotation += base_increment + (0.3 * scale)
            if self.rotation >= 2 * math.pi:
                self.rotation -= 2 * math.pi
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

        # Rotating fan image
        if self.fan_surface:
            cr.save()
            cr.translate(cx, cy)
            cr.rotate(self.rotation)
            
            # Scale image to fit inside the inner ring
            if self.fan_surface is not None:
                img_w = self.fan_surface.get_width()
                img_h = self.fan_surface.get_height()
                
                # Target radius is inner radius minus a small gap
                target_r = r - 15
                scale_x = (target_r * 2) / img_w
                scale_y = (target_r * 2) / img_h
                scale = min(scale_x, scale_y)
                
                cr.scale(scale, scale)
                cr.set_source_surface(self.fan_surface, -img_w / 2, -img_h / 2)
                
                # Change opacity based on speed (looks better)
                opacity = 0.3 if self.val == 0 else 0.5 + (0.5 * (self.val / 100))
                if self._dark:
                    cr.paint_with_alpha(opacity)
                else:
                    # Tint the image blackish for light theme 
                    # Source ATOP to recolor
                    cr.save()
                    cr.paint()
                    cr.set_source_rgba(0, 0, 0, 0.7)
                    cr.set_operator(14) # CAIRO_OPERATOR_SOURCE_ATOP 
                    cr.paint()
                    cr.restore()
                
            cr.restore()

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
        
        # Draw a semi-transparent text background pill for legibility over the fan
        bg_w = log_ext.width / Pango.SCALE + 16
        bg_h = log_ext.height / Pango.SCALE + 8
        cr.save()
        if self._dark:
            cr.set_source_rgba(0.1, 0.1, 0.1, 0.7)
        else:
            cr.set_source_rgba(0.9, 0.9, 0.9, 0.7)
        cr.rectangle(cx - bg_w / 2, cy - bg_h / 2 - 6, bg_w, bg_h)
        cr.fill()
        cr.restore()
        
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
