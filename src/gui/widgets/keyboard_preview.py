
#!/usr/bin/env python3
"""Keyboard glow preview widget using Cairo."""
import math, time, colorsys, cairo, os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

# Fix path to images
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check relative to source (3 levels up)
IMG_SRC = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "..", "images"))

# Check relative to installed location (2 levels up)
IMG_INSTALLED = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "images"))

if os.path.exists(os.path.join(IMG_SRC, "keyboard.png")):
    IMAGES_DIR = IMG_SRC
elif os.path.exists(os.path.join(IMG_INSTALLED, "keyboard.png")):
    IMAGES_DIR = IMG_INSTALLED
else:
    # Final fallback
    IMAGES_DIR = "/usr/share/hp-manager/images"


class KeyboardPreview(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_size_request(600, 240)  # Slightly taller for image
        self.power = True
        self.mode = "static"
        self.speed = 50
        self.brightness = 100
        self.direction = "ltr"
        self.zone_colors = [(1, 0, 0)] * 4  # RGBA tuples
        self.set_draw_func(self._draw)
        self._anim_id = GLib.timeout_add(33, self._tick)
        
        # Load background image
        self.bg_surf = None
        img_path = os.path.join(IMAGES_DIR, "keyboard.png")
        if os.path.exists(img_path):
            try:
                self.bg_surf = cairo.ImageSurface.create_from_png(img_path)
            except Exception as e:
                print(f"Failed to load keyboard image: {e}")

    def _tick(self):
        if self.power and self.mode != "static":
            self.queue_draw()
        return True

    def set_zone_color(self, zone, r, g, b):
        if 0 <= zone < 4:
            self.zone_colors[zone] = (r, g, b)
        self.queue_draw()

    def set_all_zones(self, r, g, b):
        self.zone_colors = [(r, g, b)] * 4
        self.queue_draw()

    def _draw(self, _, cr, w, h):
        # 1. Draw Background Image (scaled to fit width)
        if self.bg_surf:
            img_w = self.bg_surf.get_width()
            img_h = self.bg_surf.get_height()
            scale = w / img_w
            # Center vertically
            y_off = (h - (img_h * scale)) / 2
            
            cr.save()
            cr.translate(0, y_off)
            cr.scale(scale, scale)
            cr.set_source_surface(self.bg_surf, 0, 0)
            cr.paint()
            cr.restore()
        else:
            # Fallback
            cr.set_source_rgba(0.1, 0.1, 0.1, 1)
            self._rounded_rect(cr, 0, 0, w, h, 16)
            cr.fill()

        if not self.power:
            # Dim if off
            cr.set_source_rgba(0, 0, 0, 0.6)
            cr.paint()
            return

        # 2. Draw Glow Overlay
        # Use simple ADD for glow effect
        cr.set_operator(cairo.Operator.ADD)
        bri = self.brightness / 100.0
        t = time.time()
        
        # Approximate key zone centers based on image
        # Zones: Left, WASD/Mid-Left, Mid-Right, Numpad/Right
        centers = [
            (w * 0.15, h * 0.5), # Zone 1
            (w * 0.38, h * 0.5), # Zone 2
            (w * 0.62, h * 0.5), # Zone 3
            (w * 0.85, h * 0.5)  # Zone 4
        ]

        for i, (cx, cy) in enumerate(centers):
            r, g, b = self.zone_colors[i]

            if self.mode == "breathing":
                period = 8.0 - (self.speed * 0.06)
                f = (math.sin(2 * math.pi * t / period) + 1) / 2
                f = 0.3 + (f * 0.7) # Min brightness floor
                r, g, b = r * f, g * f, b * f
            elif self.mode == "cycle":
                hue = (t * (self.speed * 0.003)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            elif self.mode == "wave":
                speed_factor = self.speed * 0.007
                # ltr: wave flows left→right (zone 0 leads), rtl: right→left (zone 3 leads)
                offset = ((3 - i) * 0.15) if self.direction == "ltr" else (i * 0.15)
                hue = (t * speed_factor + offset) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)

            # Radial gradient for soft glow
            pat = cairo.RadialGradient(cx, cy, 0, cx, cy, w * 0.25)
            pat.add_color_stop_rgba(0, r, g, b, 0.4 * bri) # Inner intense
            pat.add_color_stop_rgba(0.6, r, g, b, 0.1 * bri) # Middle soft
            pat.add_color_stop_rgba(1, r, g, b, 0) # Outer transparent
            cr.set_source(pat)
            cr.paint()

    def _rounded_rect(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def cleanup(self):
        if self._anim_id:
            GLib.source_remove(self._anim_id)
            self._anim_id = None
