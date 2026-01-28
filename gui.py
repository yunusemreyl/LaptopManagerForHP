#!/usr/bin/env python3
import sys, os, json, subprocess, shutil, datetime, math, colorsys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk

# Psutil Check
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# --- PATH CONFIGURATION ---
INSTALL_DIR = "/opt/omen-control"
CONFIG_DIR = "/etc/omen-control"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# Dev Mode vs Installed Mode
if not os.path.exists(INSTALL_DIR) or os.path.dirname(os.path.abspath(__file__)) != INSTALL_DIR:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    IMAGES_DIR = os.path.join(BASE_DIR, "images")
    if not os.path.exists(CONFIG_PATH):
        CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
else:
    IMAGES_DIR = os.path.join(INSTALL_DIR, "images")

# --- LANGUAGE SUPPORT ---
TR = {
    "app_title": "OMEN KONTROL v2.1 (Wave)",
    "monitor_temp": "SICAKLIK", "monitor_ram": "BELLEK", "monitor_disk": "DİSK",
    "power_title": "GÜÇ PROFİLİ",
    "perf_eco": "ECO", "perf_bal": "DENGELİ", "perf_max": "PERF.",
    "kb_title": "KLAVYE IŞIKLARI",
    "zone_all": "TÜMÜ",
    "color_title": "RENK SEÇİMİ",
    "effect_title": "EFEKT AYARLARI",
    "mode_static": "Statik", "mode_breath": "Nefes", "mode_cycle": "Döngü",
    "mode_wave_r": "Dalga (Soldan Sağa)", "mode_wave_l": "Dalga (Sağdan Sola)",
    "lbl_mode": "Efekt Modu", "lbl_bri": "Parlaklık", "lbl_spd": "Hız",
    "sys_title": "SİSTEM & AYARLAR",
    "lbl_lang": "Dil / Language", "lbl_auto": "Başlangıçta Çalıştır",
    "btn_logs": "Hata Ayıklama (Logs)", "win_logs": "Sistem Kayıtları",
    "sect_about": "HAKKINDA", "dev_name": "Geliştirici: Yunus Emre"
}
EN = {
    "app_title": "OMEN CONTROL v2.1 (Wave)",
    "monitor_temp": "TEMP", "monitor_ram": "RAM", "monitor_disk": "DISK",
    "power_title": "POWER PROFILE",
    "perf_eco": "ECO", "perf_bal": "BALANCED", "perf_max": "PERF.",
    "kb_title": "KEYBOARD LIGHTS",
    "zone_all": "ALL",
    "color_title": "COLOR SELECTION",
    "effect_title": "EFFECT SETTINGS",
    "mode_static": "Static", "mode_breath": "Breath", "mode_cycle": "Cycle",
    "mode_wave_r": "Wave (Left to Right)", "mode_wave_l": "Wave (Right to Left)",
    "lbl_mode": "Effect Mode", "lbl_bri": "Brightness", "lbl_spd": "Speed",
    "sys_title": "SYSTEM & SETTINGS",
    "lbl_lang": "Language", "lbl_auto": "Run on Startup",
    "btn_logs": "Debug Logs", "win_logs": "System Logs",
    "sect_about": "ABOUT", "dev_name": "Developer: Yunus Emre"
}
LANGS = {"tr": TR, "en": EN}

# --- CSS ---
CSS_DATA = """
.main-window { background-color: #101010; color: #eeeeee; }
.main-content { padding: 20px; }
.section-title { font-weight: 900; opacity: 0.6; font-size: 11px; margin-bottom: 5px; margin-top: 15px; letter-spacing: 1px; }
.control-card { background-color: #181818; border-radius: 12px; padding: 15px; border: 1px solid alpha(white, 0.08); }
.monitor-card { padding: 10px; background-color: alpha(white, 0.03); border-radius: 12px; border: 1px solid alpha(white, 0.05); }
.monitor-val { font-family: monospace; font-size: 16px; font-weight: 800; margin-top: 5px; }
.monitor-lbl { font-size: 9px; font-weight: 900; opacity: 0.6; letter-spacing: 1px; }
.critical { color: #ff5555; }
.perf-btn { padding: 15px; border-radius: 12px; font-weight: 800; transition: all 0.2s; background-color: alpha(currentColor, 0.05); color: inherit; }
.perf-btn:checked { background-color: alpha(@accent_color, 0.2); border: 1px solid @accent_color; color: @accent_color; }
.kb-card { background-color: #050505; border-radius: 16px; border: 1px solid alpha(white, 0.1); margin-top: 10px; overflow: hidden; }
.kb-header { padding: 15px; background: alpha(white, 0.05); }
.kb-overlay { min-height: 180px; }
.kb-glow-layer { opacity: 1.0; transition: background 0.2s ease; }
.kb-image-layer { opacity: 0.9; }
.zone-box { padding: 10px; background-color: alpha(white, 0.02); }
.zone-btn { min-height: 40px; font-weight: bold; border-radius: 8px; margin: 0 4px; background: transparent; border: 1px solid alpha(white, 0.2); }
.zone-btn:checked { background-color: @accent_color; color: black; border-color: @accent_color; }
.color-preset-btn { border-radius: 50%; padding: 0; margin: 5px; min-width: 40px; min-height: 40px; border: 2px solid transparent; }
.color-preset-btn:checked { border-color: white; box-shadow: 0 0 8px white; transform: scale(1.1); }
.color-picker-btn { border-radius: 50%; padding: 0; margin: 5px; min-width: 40px; min-height: 40px; background: linear-gradient(135deg, red, yellow, green, blue, purple); border: 1px solid alpha(white, 0.3); }
.slider-label { font-weight: bold; font-size: 13px; opacity: 0.8; margin-right: 15px; }
.log-view { font-family: Monospace; font-size: 12px; background-color: #111; color: #0f0; padding: 10px; }
"""

class LogWindow(Gtk.Window):
    def __init__(self, parent, logs, title):
        super().__init__(title=title)
        self.set_transient_for(parent); self.set_modal(True); self.set_default_size(600, 400)
        s = Gtk.ScrolledWindow(); t = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD)
        t.add_css_class("log-view"); t.get_buffer().set_text("\n".join(logs))
        s.set_child(t); self.set_child(s)

class OmenGUI(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(540, 950)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        self.config = {"enabled": True, "mode": 0, "lang": "tr", "zone_colors": ["#FF0000"]*4, "bri": 1.0, "spd": 50, "power": "balanced", "autostart": False}
        self.logs = []
        self.active_zone_idx = 4
        self.animation_timer = None
        self.anim_tick = 0.0

        self.load_config()
        self.log(f"GUI Başlatıldı - Dil: {self.config.get('lang')}")
        self.setup_ui()
        self.update_visuals()

        GLib.timeout_add(2000, self.update_system_stats)
        GLib.timeout_add(1000, self.load_config)

    def t(self, key): return LANGS.get(self.config.get("lang", "tr"), TR).get(key, key)
    def log(self, msg): self.logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    def setup_ui(self):
        if self.get_content(): self.set_content(None)
        self.set_title(self.t("app_title"))
        p = Gtk.CssProvider(); p.load_from_data(CSS_DATA.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        tb_view = Adw.ToolbarView(); self.set_content(tb_view)
        header = Adw.HeaderBar(); tb_view.add_top_bar(header)
        if os.path.exists(os.path.join(IMAGES_DIR, "omen_logo.png")):
            img = Gtk.Image.new_from_file(os.path.join(IMAGES_DIR, "omen_logo.png"))
            img.set_pixel_size(32); img.set_margin_end(10); header.pack_start(img)

        scroll = Gtk.ScrolledWindow()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["main-content"])
        scroll.set_child(main_box); tb_view.set_content(scroll)

        # 0. SYSTEM MONITOR
        monitor_grid = Gtk.Box(spacing=10, homogeneous=True, margin_bottom=20)
        self.lbl_temp = Gtk.Label(label="--°C", css_classes=["monitor-val"])
        self.lbl_ram = Gtk.Label(label="%--", css_classes=["monitor-val"])
        self.lbl_disk = Gtk.Label(label="%--", css_classes=["monitor-val"])
        for l, k in [(self.lbl_temp, "monitor_temp"), (self.lbl_ram, "monitor_ram"), (self.lbl_disk, "monitor_disk")]:
            c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["monitor-card"])
            c.append(Gtk.Label(label=self.t(k), css_classes=["monitor-lbl"])); c.append(l); monitor_grid.append(c)
        main_box.append(monitor_grid)

        # 1. POWER PROFILE
        main_box.append(Gtk.Label(label=self.t("power_title"), xalign=0, css_classes=["section-title"]))
        perf_box = Gtk.Box(spacing=10, homogeneous=True)
        modes = [("eco", "perf_eco", "weather-clear-night-symbolic"), ("balanced", "perf_bal", "preferences-system-symbolic"), ("perf", "perf_max", "speedometer-symbolic")]
        self.perf_btns = {}
        grp = None
        for p_key, t_key, icon in modes:
            btn = Gtk.ToggleButton(css_classes=["perf-btn"])
            if not grp: grp = btn
            else: btn.set_group(grp)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            box.append(Gtk.Image.new_from_icon_name(icon)); box.append(Gtk.Label(label=self.t(t_key), css_classes=["small-label"]))
            btn.set_child(box); btn.connect("toggled", self.on_perf_change, p_key)
            perf_box.append(btn); self.perf_btns[p_key] = btn
        main_box.append(perf_box)
        if self.config.get("power") in self.perf_btns: self.perf_btns[self.config["power"]].set_active(True)

        # 2. KEYBOARD
        kb_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["kb-card"])
        sw_box = Gtk.Box(spacing=10, css_classes=["kb-header"])
        sw_lbl = Gtk.Label(label=self.t("kb_title"), hexpand=True, xalign=0, css_classes=["switch-label"])
        self.sw_master = Gtk.Switch(); self.sw_master.set_active(self.config.get("enabled", True)); self.sw_master.connect("notify::active", self.on_master_toggle)
        sw_box.append(sw_lbl); sw_box.append(self.sw_master); kb_card.append(sw_box)

        overlay = Gtk.Overlay(css_classes=["kb-overlay"])
        overlay.set_size_request(-1, 190); overlay.set_overflow(Gtk.Overflow.HIDDEN)
        self.glow_layer = Gtk.Box(css_classes=["kb-glow-layer"]); overlay.set_child(self.glow_layer)
        if os.path.exists(os.path.join(IMAGES_DIR, "keyboard.png")):
            kb_pic = Gtk.Picture.new_for_filename(os.path.join(IMAGES_DIR, "keyboard.png")); kb_pic.set_content_fit(Gtk.ContentFit.COVER)
            kb_pic.add_css_class("kb-image-layer"); overlay.add_overlay(kb_pic)
        kb_card.append(overlay)

        zone_box = Gtk.Box(homogeneous=True, css_classes=["zone-box"])
        z_grp = None
        for i in range(5):
            lbl = f"ZONE {i+1}" if i < 4 else self.t("zone_all")
            btn = Gtk.ToggleButton(label=lbl, css_classes=["zone-btn"])
            if not z_grp: z_grp = btn
            else: btn.set_group(z_grp)
            if i == 4: btn.set_active(True)
            btn.connect("toggled", self.on_zone_select, i); zone_box.append(btn)
        kb_card.append(zone_box); main_box.append(kb_card)

        # 3. COLOR
        main_box.append(Gtk.Label(label=self.t("color_title"), xalign=0, css_classes=["section-title"], margin_top=20))
        color_card = Gtk.Box(css_classes=["control-card"])
        color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5, halign=Gtk.Align.CENTER)
        self.preset_btns = []; c_grp = None
        for c in ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#00FFFF", "#FF00FF", "#FFFFFF"]:
            btn = Gtk.ToggleButton(css_classes=["color-preset-btn"])
            prov = Gtk.CssProvider(); prov.load_from_data(f"button {{ background-color: {c}; }}".encode())
            btn.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            if not c_grp: c_grp = btn
            else: btn.set_group(c_grp)
            btn.connect("toggled", self.on_preset_toggled, c); color_row.append(btn); self.preset_btns.append(btn)
        self.color_dialog = Gtk.ColorDialog()
        custom = Gtk.Button(icon_name="color-select-symbolic", css_classes=["color-picker-btn"])
        custom.connect("clicked", self.on_custom_picker_clicked); color_row.append(custom)
        color_card.append(color_row); main_box.append(color_card)

        # 4. EFFECT
        main_box.append(Gtk.Label(label=self.t("effect_title"), xalign=0, css_classes=["section-title"]))
        fx_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["control-card"])
        grid = Gtk.Grid(column_spacing=20, row_spacing=15)

        effect_list = [self.t("mode_static"), self.t("mode_breath"), self.t("mode_cycle"), self.t("mode_wave_r"), self.t("mode_wave_l")]
        row_mode = Gtk.DropDown.new_from_strings(effect_list)
        row_mode.set_selected(self.config.get("mode", 0)); row_mode.connect("notify::selected", self.on_mode_change)
        row_mode.set_hexpand(True)
        grid.attach(Gtk.Label(label=self.t("lbl_mode"), xalign=0, css_classes=["slider-label"]), 0, 0, 1, 1); grid.attach(row_mode, 1, 0, 1, 1)

        self.scale_bri = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self.scale_bri.set_value(self.config.get("bri", 1.0) * 100); self.scale_bri.set_hexpand(True)
        self.scale_bri.connect("value-changed", self.on_slider_change)
        grid.attach(Gtk.Label(label=self.t("lbl_bri"), xalign=0, css_classes=["slider-label"]), 0, 1, 1, 1); grid.attach(self.scale_bri, 1, 1, 1, 1)

        self.scale_spd = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 5)
        self.scale_spd.set_value(self.config.get("spd", 50)); self.scale_spd.set_hexpand(True)
        self.scale_spd.connect("value-changed", self.on_slider_change)
        grid.attach(Gtk.Label(label=self.t("lbl_spd"), xalign=0, css_classes=["slider-label"]), 0, 2, 1, 1); grid.attach(self.scale_spd, 1, 2, 1, 1)
        fx_card.append(grid); main_box.append(fx_card)

        # 5. SYSTEM & ABOUT
        main_box.append(Gtk.Label(label=self.t("sys_title"), xalign=0, css_classes=["section-title"]))
        sys_grp = Adw.PreferencesGroup()
        row_lang = Adw.ComboRow(title=self.t("lbl_lang"))
        row_lang.set_model(Gtk.StringList.new(["Türkçe", "English"]))
        row_lang.set_selected(0 if self.config.get("lang") == "tr" else 1)
        row_lang.connect("notify::selected", self.on_lang_change); sys_grp.add(row_lang)
        sw_auto = Adw.SwitchRow(title=self.t("lbl_auto")); sw_auto.set_active(True); sw_auto.set_sensitive(False); sys_grp.add(sw_auto)
        row_logs = Adw.ActionRow(title=self.t("btn_logs"))
        btn_log = Gtk.Button(icon_name="text-x-generic-symbolic", valign=Gtk.Align.CENTER)
        btn_log.connect("clicked", self.on_show_logs); row_logs.add_suffix(btn_log); sys_grp.add(row_logs); main_box.append(sys_grp)

        about_grp = Adw.PreferencesGroup(title=self.t("sect_about"))
        row_dev = Adw.ActionRow(title=self.t("dev_name"), subtitle="GitHub: @yunusemreyl")
        btn_link = Gtk.Button(icon_name="web-browser-symbolic", valign=Gtk.Align.CENTER)
        btn_link.connect("clicked", lambda _: subprocess.run(["xdg-open", "https://github.com/yunusemreyl"])); row_dev.add_suffix(btn_link); about_grp.add(row_dev); main_box.append(about_grp)

    # --- VISUAL ANIMATION LOGIC ---
    def animate_preview(self):
        if not self.config.get("enabled", True): return False

        mode = self.config.get("mode", 0)
        if mode == 0: return False # Static mode, no animation needed

        # Calculate speed from slider (1-100) -> factor
        spd = self.config.get("spd", 50)
        speed_factor = (spd / 100.0) * 0.05
        self.anim_tick += speed_factor

        colors = []

        if mode == 1: # Breath
            bri = 0.3 + (0.7 * ((math.sin(self.anim_tick * 5) + 1) / 2))
            c = self.config.get("zone_colors")[0] # Base color
            # Just dim the existing color visually (simple approximation)
            # For GUI preview, we will just use the base color but maybe slightly adjust opacity?
            # CSS linear-gradient doesn't support easy brightness adjustment without parsing HEX.
            # So for breath, we might just skip complex animation or implement HEX parsing.
            pass

        elif mode == 2: # Cycle
            hue = (self.anim_tick * 2) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            hex_c = "#{:02X}{:02X}{:02X}".format(int(r*255), int(g*255), int(b*255))
            colors = [hex_c] * 4

        elif mode == 3: # Wave Right
            for i in range(4):
                hue = (self.anim_tick + (i * 0.1)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                colors.append("#{:02X}{:02X}{:02X}".format(int(r*255), int(g*255), int(b*255)))

        elif mode == 4: # Wave Left
            for i in range(4):
                hue = (self.anim_tick + ((3-i) * 0.1)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                colors.append("#{:02X}{:02X}{:02X}".format(int(r*255), int(g*255), int(b*255)))

        if colors:
            css = f".kb-glow-layer {{ background: linear-gradient(90deg, {colors[0]}, {colors[1]}, {colors[2]}, {colors[3]}); }}"
            self.apply_css(css)

        return True

    def apply_css(self, css):
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def start_animation(self):
        if self.animation_timer:
            GLib.source_remove(self.animation_timer)
        # Start a 30 FPS timer for smooth UI update
        self.animation_timer = GLib.timeout_add(33, self.animate_preview)

    def update_visuals(self):
        # Update static visuals immediately
        c = self.config.get("zone_colors", ["#FF0000"]*4)
        css = f".kb-glow-layer {{ background: linear-gradient(90deg, {c[0]}, {c[1]}, {c[2]}, {c[3]}); }}"
        self.apply_css(css)

        # If dynamic mode, start animation loop
        mode = self.config.get("mode", 0)
        if mode >= 2: # Cycle or Waves
            self.start_animation()
        else:
            if self.animation_timer:
                GLib.source_remove(self.animation_timer)
                self.animation_timer = None

    # --- SYSTEM LOGIC ---
    def update_system_stats(self):
        if not PSUTIL_AVAILABLE: self.lbl_temp.set_label("N/A"); return True
        try:
            t = 0; temps = psutil.sensors_temperatures()
            if "coretemp" in temps: t = temps["coretemp"][0].current
            elif "k10temp" in temps: t = temps["k10temp"][0].current
            elif "zenpower" in temps: t = temps["zenpower"][0].current
            else:
                max_t = 0
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current > max_t: max_t = entry.current
                t = max_t
            self.lbl_temp.set_label(f"{int(t)}°C")
            self.lbl_ram.set_label(f"%{int(psutil.virtual_memory().percent)}")
            self.lbl_disk.set_label(f"%{int(psutil.disk_usage('/').percent)}")
        except: pass
        return True

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.config.update(data)
            except: pass
        return True

    def save_config(self):
        if os.path.exists(CONFIG_DIR):
            try:
                with open(CONFIG_PATH, "w") as f: json.dump(self.config, f)
                os.chmod(CONFIG_PATH, 0o666)
            except Exception as e: self.log(f"Kayıt Hatası: {e}")
        self.update_visuals()

    def on_lang_change(self, combo, _):
        new_lang = "tr" if combo.get_selected() == 0 else "en"
        if new_lang != self.config.get("lang"):
            self.config["lang"] = new_lang; self.save_config(); self.setup_ui()

    def on_perf_change(self, btn, p_key):
        if btn.get_active(): self.config["power"] = p_key; self.save_config()
    def on_master_toggle(self, sw, _): self.config["enabled"] = sw.get_active(); self.save_config()
    def on_mode_change(self, c, _): self.config["mode"] = c.get_selected(); self.save_config()
    def on_slider_change(self, _):
        self.config["bri"] = self.scale_bri.get_value() / 100.0
        self.config["spd"] = int(self.scale_spd.get_value()); self.save_config()
    def on_preset_toggled(self, btn, c):
        if btn.get_active(): self.apply_col(c)
    def on_custom_picker_clicked(self, btn):
        self.color_dialog.choose_rgba(self, None, None, self.on_color_picked, None)
    def on_color_picked(self, d, r, _):
        try:
            c = d.choose_rgba_finish(r)
            hex_c = f"#{int(c.red*255):02X}{int(c.green*255):02X}{int(c.blue*255):02X}"
            for b in self.pbs: b.set_active(False)
            self.apply_col(hex_c)
        except: pass
    def apply_col(self, c):
        if self.active_zone_idx == 4:
            for i in range(4): self.config["zone_colors"][i] = c
        else: self.config["zone_colors"][self.active_zone_idx] = c
        self.save_config()
    def on_zone_select(self, b, i):
        if b.get_active(): self.active_zone_idx = i; self.update_visuals()
    def on_show_logs(self, _): Win = LogWindow(self, self.logs, self.t("win_logs")); Win.present()

if __name__ == "__main__":
    app = Adw.Application(application_id="com.victus.gui")
    app.connect("activate", lambda a: OmenGUI(application=a).present())
    app.run(sys.argv)
