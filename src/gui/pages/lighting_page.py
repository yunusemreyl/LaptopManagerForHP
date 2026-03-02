#!/usr/bin/env python3
"""Lighting Page - 4-zone RGB keyboard backlight control — i18n via T().
Victus: single zone, Omen: 4 zones (auto-detected via DMI)."""
import os, json, colorsys, threading
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from widgets.keyboard_preview import KeyboardPreview

PRESETS = ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#FFFF00", "#00FFFF", "#FF00FF", "#FF6600", "#7B00FF"]


def T(k):
    from i18n import T as _T
    return _T(k)


def _detect_model_type():
    for dmi_file in ("/sys/devices/virtual/dmi/id/product_name",
                     "/sys/devices/virtual/dmi/id/product_family"):
        try:
            with open(dmi_file) as f:
                name = f.read().strip().lower()
                if "victus" in name:
                    return "victus"
                if "omen" in name:
                    return "omen"
        except Exception: pass
    return "omen"


class LightingPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.service = service
        self.set_margin_top(30)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.set_margin_bottom(30)

        self.model_type = _detect_model_type()
        self.num_zones = 1 if self.model_type == "victus" else 4

        self.power = True
        self.mode = "static"
        self.speed = 50
        self.brightness = 100
        self.direction = "ltr"
        self.zone_rgba = [Gdk.RGBA() for _ in range(4)]
        for c in self.zone_rgba:
            c.parse("red")
        self.selected_zone = 4 if self.num_zones == 4 else 0

        self._speed_timer = None
        self._bri_timer = None

        self._build_ui()
        self._sync_state()
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def _on_map(self, *args):
        GLib.timeout_add(300, self._start_preview_anim)
        
    def _start_preview_anim(self):
        self.kb_preview.resume_animation()
        return False
        
    def _on_unmap(self, *args):
        self.kb_preview.pause_animation()

    def set_service(self, service):
        self.service = service
        self._sync_state()

    def _sync_state(self):
        if not self.service:
            return
        
        # Run DBus call in background to avoid freezing the UI transition
        def _fetch():
            try:
                st = json.loads(self.service.GetState())
                GLib.idle_add(self._apply_state, st)
            except Exception:
                pass
        
        threading.Thread(target=_fetch, daemon=True).start()

    def _apply_state(self, st):
        try:
            self.power = st.get("power", True)
            self.mode = st.get("mode", "static")
            self.speed = st.get("speed", 50)
            self.brightness = st.get("brightness", 100)
            self.direction = st.get("direction", "ltr")

            self.sw.set_active(self.power)
            self.brightness_scale.set_value(self.brightness)
            self.speed_scale.set_value(self.speed)

            modes = ["static", "breathing", "wave", "cycle"]
            if self.mode in modes:
                self.mode_dd.set_selected(modes.index(self.mode))

            self.dir_dd.set_selected(0 if self.direction == "ltr" else 1)

            colors = st.get("colors", ["FF0000"] * 4)
            for i in range(4):
                c = Gdk.RGBA()
                c.parse(f"#{colors[i]}")
                self.zone_rgba[i] = c
                self.kb_preview.set_zone_color(i, c.red, c.green, c.blue)

            self.kb_preview.power = self.power
            self.kb_preview.mode = self.mode
            self.kb_preview.speed = self.speed
            self.kb_preview.brightness = self.brightness
            self.kb_preview.direction = self.direction
            self.kb_preview.queue_draw()
        except Exception: pass
        return False

    def _build_ui(self):
        title = Gtk.Label(label=T("keyboard_lighting"), xalign=0)
        title.add_css_class("page-title")
        self.append(title)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        # Keyboard Preview
        preview_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        preview_frame.add_css_class("kb-frame")
        self.kb_preview = KeyboardPreview()
        preview_frame.append(self.kb_preview)
        content.append(preview_frame)

        # Zone Selection (Omen only)
        if self.num_zones == 4:
            zone_box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
            self.zone_group = None
            zones = [f"{T('zone')} 1", f"{T('zone')} 2", f"{T('zone')} 3", f"{T('zone')} 4", T("all_zones")]
            for i, label in enumerate(zones):
                btn = Gtk.ToggleButton(label=label)
                btn.add_css_class("zone-btn")
                if self.zone_group:
                    btn.set_group(self.zone_group)
                else:
                    self.zone_group = btn
                if i == 4:
                    btn.set_active(True)
                btn.connect("toggled", lambda w, idx=i: self._on_zone_select(idx) if w.get_active() else None)
                zone_box.append(btn)
            content.append(zone_box)

        # Controls Card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        card.add_css_class("card")

        row1 = Gtk.Box(spacing=15, halign=Gtk.Align.CENTER)

        power_box = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
        power_box.append(Gtk.Label(label=T("keyboard_light"), css_classes=["section-title"]))
        self.sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.sw.set_active(True)
        self.sw.connect("state-set", self._on_power)
        power_box.append(self.sw)
        row1.append(power_box)

        row1.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        color_box = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        
        # We need a CSS provider to inject dynamic CSS for glows
        self.preset_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), 
            self.preset_css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        dyn_css = ""
        for i, hex_color in enumerate(PRESETS):
            btn = Gtk.Button()
            css_class = f"neon-preset-{i}"
            btn.add_css_class("color-preset-btn")
            btn.add_css_class(css_class)
            btn.set_size_request(32, 32)
            btn.connect("clicked", lambda w, c=hex_color: self._on_color(c))
            color_box.append(btn)
            
            # Dynamic CSS for the specific color glow
            dyn_css += f"""
            .{css_class} {{
                background-color: {hex_color};
                border-radius: 50%;
                box-shadow: 0px 0px 8px {hex_color}, inset 0px 0px 2px rgba(255,255,255,0.4);
            }}
            .{css_class}:hover {{
                box-shadow: 0px 0px 14px {hex_color}, inset 0px 0px 4px rgba(255,255,255,0.6);
            }}
            """
            
        self.preset_css_provider.load_from_data(dyn_css.encode('utf-8'))

        pick_btn = Gtk.Button(label="+")
        pick_btn.add_css_class("color-picker-btn")
        pick_btn.set_size_request(32, 32)
        pick_btn.connect("clicked", self._open_picker)
        color_box.append(pick_btn)
        row1.append(color_box)
        card.append(row1)

        card.append(Gtk.Separator())

        # Effect controls
        grid = Gtk.Grid(column_spacing=30, row_spacing=15, halign=Gtk.Align.CENTER)

        grid.attach(Gtk.Label(label=T("effect"), xalign=1, css_classes=["section-title"]), 0, 0, 1, 1)
        self.mode_dd = Gtk.DropDown(model=Gtk.StringList.new([T("static_eff"), T("breathing"), T("wave"), T("cycle")]))
        self.mode_dd.connect("notify::selected", self._on_mode)
        grid.attach(self.mode_dd, 1, 0, 1, 1)

        self.dir_label = Gtk.Label(label=T("direction"), xalign=1, css_classes=["section-title"])
        grid.attach(self.dir_label, 2, 0, 1, 1)
        self.dir_dd = Gtk.DropDown(model=Gtk.StringList.new([T("ltr"), T("rtl")]))
        self.dir_dd.connect("notify::selected", self._on_direction)
        grid.attach(self.dir_dd, 3, 0, 1, 1)

        grid.attach(Gtk.Label(label=T("speed"), xalign=1, css_classes=["section-title"]), 0, 1, 1, 1)
        self.speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.speed_scale.set_value(50)
        self.speed_scale.set_draw_value(False)
        self.speed_scale.set_size_request(160, -1)
        self.speed_scale.connect("value-changed", self._on_speed)
        grid.attach(self.speed_scale, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=T("brightness"), xalign=1, css_classes=["section-title"]), 2, 1, 1, 1)
        self.brightness_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.brightness_scale.set_value(100)
        self.brightness_scale.set_draw_value(False)
        self.brightness_scale.set_size_request(160, -1)
        self.brightness_scale.connect("value-changed", self._on_brightness)
        grid.attach(self.brightness_scale, 3, 1, 1, 1)

        card.append(grid)
        content.append(card)

        scroll.set_child(content)
        self.append(scroll)

    def _on_zone_select(self, zone):
        self.selected_zone = zone

    def _on_power(self, sw, state):
        self.power = state
        self.kb_preview.power = state
        self.kb_preview.queue_draw()
        if self.service:
            try:
                self.service.SetGlobal(state, int(self.brightness_scale.get_value()), self.direction)
            except Exception: pass

    def _on_color(self, hex_color):
        c = Gdk.RGBA()
        c.parse(hex_color)

        # Auto-switch to static
        if self.mode != "static":
            self.mode = "static"
            self.mode_dd.set_selected(0)
            self.kb_preview.mode = "static"
            if self.service:
                try: self.service.SetMode("static", self.speed)
                except Exception: pass

        if self.num_zones == 1 or self.selected_zone == 4:
            for i in range(4):
                self.zone_rgba[i] = c
                self.kb_preview.set_zone_color(i, c.red, c.green, c.blue)
            if self.service:
                try:
                    self.service.SetColor(4, hex_color)
                except Exception: pass
        else:
            self.zone_rgba[self.selected_zone] = c
            self.kb_preview.set_zone_color(self.selected_zone, c.red, c.green, c.blue)
            if self.service:
                try: self.service.SetColor(self.selected_zone, hex_color)
                except Exception: pass
        self.kb_preview.queue_draw()

    def _open_picker(self, btn):
        dialog = Gtk.ColorDialog()
        dialog.choose_rgba(self.get_root(), None, None, self._on_color_picked)

    def _on_color_picked(self, dialog, result):
        try:
            c = dialog.choose_rgba_finish(result)
            hex_color = f"#{int(c.red * 255):02X}{int(c.green * 255):02X}{int(c.blue * 255):02X}"
            self._on_color(hex_color)
        except Exception: pass

    def _on_mode(self, dd, _):
        modes = ["static", "breathing", "wave", "cycle"]
        self.mode = modes[dd.get_selected()]
        self.kb_preview.mode = self.mode
        self.kb_preview.queue_draw()
        if self.service:
            try: self.service.SetMode(self.mode, int(self.speed_scale.get_value()))
            except Exception: pass

    def _on_direction(self, dd, _):
        self.direction = "ltr" if dd.get_selected() == 0 else "rtl"
        self.kb_preview.direction = self.direction
        if self.service:
            try: self.service.SetGlobal(self.power, int(self.brightness_scale.get_value()), self.direction)
            except Exception: pass

    def _on_speed(self, scale):
        self.speed = int(scale.get_value())
        self.kb_preview.speed = self.speed
        if self._speed_timer:
            GLib.source_remove(self._speed_timer)
        self._speed_timer = GLib.timeout_add(200, self._send_mode_update)

    def _send_mode_update(self):
        if self.service:
            try: self.service.SetMode(self.mode, self.speed)
            except Exception: pass
        self._speed_timer = None
        return False

    def _on_brightness(self, scale):
        self.brightness = int(scale.get_value())
        self.kb_preview.brightness = self.brightness
        if self._bri_timer:
            GLib.source_remove(self._bri_timer)
        self._bri_timer = GLib.timeout_add(200, self._send_global_update)

    def _send_global_update(self):
        if self.service:
            try: self.service.SetGlobal(self.power, self.brightness, self.direction)
            except Exception: pass
        self._bri_timer = None
        return False

    def cleanup(self):
        self.kb_preview.cleanup()
        if self._speed_timer:
            GLib.source_remove(self._speed_timer)
        if self._bri_timer:
            GLib.source_remove(self._bri_timer)
