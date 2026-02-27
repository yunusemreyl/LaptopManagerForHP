#!/usr/bin/env python3
"""
HP Laptop Manager - Main Window
Sidebar navigation ile 5 sekme + ayarlar.
"""
import sys, os, json
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # fallback
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio

# Add parent path for imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check relative to source (2 levels up -> src/LaptopManagerForHP)
PROJ_SRC = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

# Check relative to installed location (1 level up -> /usr/share/hp-manager)
PROJ_INSTALLED = os.path.abspath(os.path.join(BASE_DIR, ".."))

if os.path.exists(os.path.join(PROJ_SRC, "images", "hp_logo.png")):
    IMAGES_DIR = os.path.join(PROJ_SRC, "images")
    PROJECT_DIR = PROJ_SRC
elif os.path.exists(os.path.join(PROJ_INSTALLED, "images", "hp_logo.png")):
    IMAGES_DIR = os.path.join(PROJ_INSTALLED, "images")
    PROJECT_DIR = PROJ_INSTALLED
else:
    # Final fallback
    IMAGES_DIR = "/usr/share/hp-manager/images"
    PROJECT_DIR = "/usr/share/hp-manager"

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))

from pages.games_page import GamesPage
from pages.tools_page import ToolsPage
from pages.fan_page import FanPage
from pages.lighting_page import LightingPage
from pages.mux_page import MUXPage
from pages.settings_page import SettingsPage

APP_VERSION = "4.5"
CONFIG_FILE = os.path.expanduser("~/.config/hp-manager.toml")
CONFIG_FILE_JSON = os.path.expanduser("~/.config/hp-manager.json")

# ── TRANSLATIONS (centralized in i18n.py to avoid __main__ double-import) ──
from i18n import T, set_lang, get_lang


class HPManagerWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("HP Laptop Manager")
        self.set_default_size(1100, 750)

        # Add local icons to theme
        display = Gdk.Display.get_default()
        icon_theme = Gtk.IconTheme.get_for_display(display)
        if IMAGES_DIR not in icon_theme.get_search_path():
            icon_theme.add_search_path(IMAGES_DIR)
        
        self.set_icon_name("hp_logo")

        self.app_theme = "dark"
        self.temp_unit = "C"
        self.service = None
        self.ready = False
        self._rebuilding = False

        self._load_config()
        self._apply_css()
        self._build_ui()
        self._connect_daemon()

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "rb") as f:
                    data = tomllib.load(f)
                self.app_theme = data.get("theme", "dark")
                self.temp_unit = data.get("temp_unit", "C")
                set_lang(data.get("lang", "tr"))
            elif os.path.exists(CONFIG_FILE_JSON):
                # Auto-migrate from old JSON config
                data = json.load(open(CONFIG_FILE_JSON))
                self.app_theme = data.get("theme", "dark")
                self.temp_unit = data.get("temp_unit", "C")
                set_lang(data.get("lang", "tr"))
                self._save_config()  # write TOML
        except:
            pass

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                f.write(f'theme = "{self.app_theme}"\n')
                f.write(f'lang = "{get_lang()}"\n')
                f.write(f'temp_unit = "{self.temp_unit}"\n')
        except:
            pass

    def _get_system_accent(self):
        """Try to read the system/GTK accent color."""
        try:
            sm = Adw.StyleManager.get_default()
            ac = sm.get_accent_color()
            rgba = ac.to_rgba()
            r, g, b = int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
            if r or g or b:
                return f"#{r:02X}{g:02X}{b:02X}"
        except:
            pass
        # Fallback: default blue accent
        return "#3584e4"

    @staticmethod
    def _hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _lighten(hex_color, amount=30):
        r, g, b = HPManagerWindow._hex_to_rgb(hex_color)
        r = min(255, r + amount)
        g = min(255, g + amount)
        b = min(255, b + amount)
        return f"#{r:02X}{g:02X}{b:02X}"

    @staticmethod
    def _darken(hex_color, amount=30):
        r, g, b = HPManagerWindow._hex_to_rgb(hex_color)
        r = max(0, r - amount)
        g = max(0, g - amount)
        b = max(0, b - amount)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _apply_css(self):
        # ── HP Victus / Omen style theme with system accent ──
        accent = self._get_system_accent()
        accent_hover = self._lighten(accent, 20)
        ar, ag, ab = self._hex_to_rgb(accent)
        accent_dim = f"rgba({ar}, {ag}, {ab}, 0.15)"
        accent_shadow = f"rgba({ar}, {ag}, {ab}, 0.3)"
        accent_shadow_strong = f"rgba({ar}, {ag}, {ab}, 0.35)"
        accent_glow = f"rgba({ar}, {ag}, {ab}, 0.08)"
        accent_border_hover = f"rgba({ar}, {ag}, {ab}, 0.3)"
        accent_dark = self._darken(accent, 60)

        if self.app_theme == "dark":
            bg = "#1e1e24"
            sidebar_bg = "#16161c"
            card_bg = "#2a2a32"
            card_border = "rgba(255,255,255,0.08)"
            fg = "#ffffff"
            fg_dim = "#cccccc"
            fg_very_dim = "#999999"
            input_bg = "rgba(255,255,255,0.08)"
        else:
            bg = "#f0f0f4"
            sidebar_bg = "#e8e8ee"
            card_bg = "#ffffff"
            card_border = "rgba(0,0,0,0.12)"
            fg = "#121212"
            fg_dim = "#444444"
            fg_very_dim = "#666666"
            input_bg = "rgba(0,0,0,0.06)"
            accent = self._darken(accent, 20)
            accent_hover = self._darken(accent, 10)
            ar, ag, ab = self._hex_to_rgb(accent)
            accent_dim = f"rgba({ar}, {ag}, {ab}, 0.15)"
            accent_shadow = f"rgba({ar}, {ag}, {ab}, 0.3)"
            accent_shadow_strong = f"rgba({ar}, {ag}, {ab}, 0.35)"
            accent_glow = f"rgba({ar}, {ag}, {ab}, 0.08)"
            accent_border_hover = f"rgba({ar}, {ag}, {ab}, 0.3)"
            accent_dark = self._darken(accent, 60)

        # Color preset CSS
        presets_css = ""
        preset_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#FFFF00", "#00FFFF", "#FF00FF", "#FF6600", "#7B00FF"]
        for i, c in enumerate(preset_colors):
            presets_css += f"""
            .preset-{i} {{
                background-color: {c}; border-radius: 50%;
                min-width: 28px; min-height: 28px; padding: 0;
                border: 2px solid rgba(255,255,255,0.1);
                transition: all 0.2s ease;
            }}
            .preset-{i}:hover {{ border-color: white; transform: scale(1.15); }}
            """

        css = f"""
        /* ── Window ── */
        window {{ background-color: {bg}; color: {fg}; }}

        /* ── Sidebar ── */
        .sidebar {{
            background-color: {sidebar_bg};
            border-right: 1px solid {card_border};
        }}
        .sidebar-logo {{
            padding: 15px 0 10px 0;
        }}
        .sidebar-logo image {{
            opacity: 0.9;
        }}
        .logo-img {{
            max-width: 48px;
            max-height: 48px;
            margin-bottom: 4px;
        }}

        /* ── Nav Items ── */
        .nav-item {{
            padding: 10px 8px;
            margin: 2px 8px;
            border-radius: 12px;
            transition: all 0.2s ease;
            background: transparent;
            border: none;
            min-height: 0;
        }}
        .nav-item:hover {{
            background: {accent_dim};
        }}
        .nav-item.active {{
            background: {accent_dim};
        }}
        .nav-item.active image,
        .nav-item.active label {{
            color: {accent};
        }}
        .nav-label {{
            font-size: 10px;
            font-weight: 600;
            color: {fg_dim};
            margin-top: 4px;
        }}
        .nav-item.active .nav-label {{
            color: {accent};
        }}
        .nav-icon {{
            color: {fg_dim};
        }}
        .nav-item.active .nav-icon {{
            color: {accent};
        }}

        /* ── Pages ── */
        .page-title {{
            font-size: 22px;
            font-weight: 800;
            color: {fg};
            margin-bottom: 5px;
        }}
        .section-title {{
            font-size: 11px;
            font-weight: 700;
            color: {fg_dim};
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }}
        .stat-big {{
            font-size: 18px;
            font-weight: 700;
            color: {fg};
        }}
        .stat-lbl {{
            font-size: 12px;
            color: {fg_dim};
            font-weight: 500;
        }}

        /* ── Cards ── */
        .card {{
            background-color: {card_bg};
            border-radius: 16px;
            border: 1px solid {card_border};
            padding: 22px;
        }}

        /* ── Buttons ── */
        .zone-btn {{
            background: {input_bg};
            color: {fg};
            border: 1px solid {card_border};
            border-radius: 20px;
            padding: 8px 16px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        .zone-btn:checked {{
            background: {accent};
            color: white;
            border-color: {accent};
        }}

        .profile-btn {{
            background: {input_bg};
            border: 2px solid {card_border};
            border-radius: 18px;
            transition: all 0.2s ease;
            min-width: 120px;
            min-height: 100px;
        }}
        .profile-btn:checked {{
            background: {accent_dim};
            border-color: {accent};
        }}
        .profile-emoji {{
            font-size: 32px;
        }}
        .profile-label {{
            font-size: 13px;
            font-weight: 600;
            color: {fg};
        }}

        .mux-btn {{
            background: {input_bg};
            border: 2px solid {card_border};
            border-radius: 20px;
            transition: all 0.2s ease;
            color: {fg};
        }}
        .mux-btn:checked {{
            background: linear-gradient(135deg, {accent}, {accent_dark});
            border-color: {accent_hover};
            box-shadow: 0 6px 20px {accent_shadow};
            color: white;
        }}

        /* ── Fan mode buttons (pill segmented) ── */
        .mode-selector-strip {{
            background: {input_bg};
            border-radius: 25px;
            border: 1px solid {card_border};
            padding: 4px;
        }}
        .fan-mode-btn {{
            background: transparent;
            color: {fg};
            border: none;
            border-radius: 22px;
            padding: 10px 28px;
            font-weight: 600;
            font-size: 13px;
            transition: all 0.2s ease;
            min-height: 0;
        }}
        .fan-mode-btn:checked {{
            background: {accent};
            color: white;
            box-shadow: 0 4px 12px {accent_shadow_strong};
        }}

        /* ── Tool cards ── */
        .tool-card {{
            background: {card_bg};
            border-radius: 14px;
            border: none;
            padding: 18px 22px;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .tool-card:hover {{
            box-shadow: 0 2px 8px {accent_shadow};
        }}
        .tool-name {{
            font-size: 14px;
            font-weight: 700;
            color: {fg};
        }}
        .tool-desc {{
            font-size: 11px;
            color: {fg_dim};
        }}
        .tool-status {{
            font-size: 12px;
            font-weight: 600;
        }}
        .tool-installed {{
            color: {accent};
        }}
        .tool-not-installed {{
            color: #ef5350;
        }}
        .tool-install-btn {{
            background: {accent};
            color: white;
            border: none;
            border-radius: 10px;
            padding: 6px 16px;
            font-weight: 700;
            font-size: 12px;
        }}
        .tool-install-btn:hover {{
            background: {accent_hover};
        }}

        /* ── Game cards ── */
        .game-card {{
            background: {card_bg};
            border-radius: 14px;
            border: 1px solid {card_border};
            padding: 12px;
            transition: all 0.2s ease;
        }}
        .game-card:hover {{
            border-color: {accent_border_hover};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .game-icon-box {{
            background: {accent_glow};
            border-radius: 10px;
        }}
        .game-name {{
            font-size: 13px;
            font-weight: 700;
            color: {fg};
        }}
        .game-source {{
            font-size: 10px;
            font-weight: 600;
            color: {accent};
            background: {accent_dim};
            padding: 2px 8px;
            border-radius: 8px;
        }}
        .game-launch-btn {{
            background: {accent};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 4px 12px;
            font-weight: 600;
            font-size: 11px;
        }}

        /* ── Search ── */
        .search-entry {{
            background: {input_bg};
            border: 1px solid {card_border};
            border-radius: 12px;
            padding: 8px 15px;
            color: {fg};
        }}

        /* ── KB Frame ── */
        .kb-frame {{
            background: rgba(0,0,0,0.25);
            border: 1px solid {card_border};
            border-radius: 18px;
            padding: 12px;
        }}

        /* ── Color picker ── */
        .color-picker-btn {{
            background: {input_bg};
            border: 2px dashed {fg_very_dim};
            border-radius: 50%;
            min-width: 28px;
            min-height: 28px;
            padding: 0;
            font-weight: 700;
            color: {fg_dim};
        }}

        /* ── Warning ── */
        .warning-box {{
            background: rgba(255, 200, 0, 0.06);
            border: 1px solid rgba(255, 200, 0, 0.2);
            border-radius: 12px;
            padding: 20px;
        }}
        .warning-text {{
            color: #ffcc00;
            font-weight: 700;
            font-size: 16px;
        }}
        .warning-sub {{
            color: #e6b800;
            font-weight: 500;
            font-size: 12px;
        }}

        /* ── Empty state ── */
        .empty-state {{
            padding: 40px;
        }}

        /* ── Inputs ── */
        scale trough {{
            background: {input_bg};
            border-radius: 4px;
        }}
        scale highlight {{
            background: {accent};
            border-radius: 4px;
        }}
        scale value {{
            background: {card_bg};
            color: {fg};
            border: none;
            border-radius: 6px;
            padding: 2px 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        }}
        dropdown > button {{
            background: {input_bg};
            border: none;
            outline: none;
            box-shadow: none;
            border-radius: 10px;
            color: {fg};
            min-height: 0;
        }}
        dropdown > button:focus {{
            outline: none;
            box-shadow: none;
            border: none;
        }}
        popover, popover.background {{
            background: transparent;
            border: none;
            box-shadow: none;
        }}
        popover > contents, popover.background > contents {{
            background: {card_bg};
            border: none;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
            padding: 4px 0;
        }}
        popover modelbutton, popover label {{
            color: {fg};
        }}
        popover modelbutton:hover {{
            background: {accent_dim};
        }}
        popover row {{
            color: {fg};
        }}
        popover row:selected {{
            background: {accent_dim};
        }}

        /* ── Update button ── */
        .update-btn {{
            background: {accent};
            color: white;
            border: none;
            border-radius: 10px;
            padding: 8px 20px;
            font-weight: 700;
            font-size: 12px;
        }}
        .update-btn:hover {{
            background: {accent_hover};
        }}
        .update-available {{
            color: {accent};
            font-weight: 600;
        }}

        {presets_css}
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        # Main horizontal layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_child(main_box)

        # ── Sidebar ──
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.add_css_class("sidebar")
        sidebar.set_size_request(82, -1)

        # Logo at top
        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER)
        logo_box.add_css_class("sidebar-logo")
        logo_path = os.path.join(IMAGES_DIR, "hp_logo.png")
        if os.path.exists(logo_path):
            from gi.repository import GdkPixbuf
            # Load larger for high DPI
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(logo_path, 48, 48, True)
            logo_icon = Gtk.Image.new_from_pixbuf(pixbuf)
            logo_icon.set_pixel_size(48)
            logo_icon.add_css_class("logo-img")
        else:
            logo_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
            logo_icon.set_pixel_size(48)
        logo_box.append(logo_icon)
        sidebar.append(logo_box)

        sidebar.append(Gtk.Separator())

        # Navigation items
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.nav_labels = {}  # track nav labels for language update
        self.stack.set_transition_duration(200)

        self.nav_buttons = {}

        nav_items = [
            ("games", "Oyunlar", "applications-games-symbolic"),
            ("fan", "Fan", "weather-tornado-symbolic"),
            ("lighting", "Aydınlatma", "weather-clear-night-symbolic"),
            ("mux", "MUX", "video-display-symbolic"),
        ]

        nav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8)
        for page_id, label, icon_name in nav_items:
            btn = self._make_nav_button(page_id, label, icon_name)
            nav_box.append(btn)
        sidebar.append(nav_box)

        # Spacer
        sidebar.append(Gtk.Label(vexpand=True))

        # Tools at bottom (above settings)
        tools_btn = self._make_nav_button("tools", "Araçlar", "emblem-system-symbolic")
        sidebar.append(tools_btn)

        # Settings at bottom
        settings_btn = self._make_nav_button("settings", "Ayarlar", "emblem-system-symbolic")
        sidebar.append(settings_btn)
        sidebar.append(Gtk.Box(margin_bottom=10))

        main_box.append(sidebar)

        # ── Content Area ──
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        content.append(self.stack)
        main_box.append(content)

        # ── Create pages ──
        self.games_page = GamesPage()
        self.tools_page = ToolsPage(service=self.service)
        self.fan_page = FanPage(service=self.service)
        self.lighting_page = LightingPage(service=self.service)
        self.mux_page = MUXPage(service=self.service)
        self.settings_page = SettingsPage(
            on_theme_change=self._on_theme_change,
            on_lang_change=self._on_lang_change,
            on_temp_unit_change=self._on_temp_unit_change
        )

        self.stack.add_named(self.games_page, "games")
        self.stack.add_named(self.tools_page, "tools")
        self.stack.add_named(self.fan_page, "fan")
        self.stack.add_named(self.lighting_page, "lighting")
        self.stack.add_named(self.mux_page, "mux")
        self.stack.add_named(self.settings_page, "settings")

        # Sync initial theme to gauges
        self.fan_page.set_dark(self.app_theme == "dark")
        self.fan_page.set_temp_unit(self.temp_unit)

        # Sync settings dropdowns to saved config
        self._rebuilding = True
        self.settings_page.set_theme_index(0 if self.app_theme == "dark" else 1)
        self.settings_page.set_lang_index(0 if get_lang() == "tr" else 1)
        self.settings_page.set_temp_unit_index(0 if self.temp_unit == "C" else 1)
        self._rebuilding = False

        # Select first page
        self._navigate("games")

    def _make_nav_button(self, page_id, label, icon_name):
        btn = Gtk.Button()
        btn.add_css_class("nav-item")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, halign=Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(22)
        icon.add_css_class("nav-icon")
        box.append(icon)

        lbl = Gtk.Label(label=label)
        lbl.add_css_class("nav-label")
        self.nav_labels[page_id] = lbl
        box.append(lbl)

        btn.set_child(box)
        btn.connect("clicked", lambda w, pid=page_id: self._navigate(pid))

        self.nav_buttons[page_id] = btn
        return btn

    def _navigate(self, page_id):
        self.stack.set_visible_child_name(page_id)

        # Update active states
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.add_css_class("active")
            else:
                if "active" in btn.get_css_classes():
                    btn.remove_css_class("active")

    def _connect_daemon(self):
        try:
            from pydbus import SystemBus
            bus = SystemBus()
            self.service = bus.get("com.yyl.hpmanager")
            self.ready = True

            # Pass service to pages
            self.fan_page.set_service(self.service)
            self.lighting_page.set_service(self.service)
            self.mux_page.set_service(self.service)

            print("✓ Daemon bağlantısı kuruldu")
        except Exception as e:
            print(f"⚠ Daemon bağlantısı kurulamadı: {e}")
            print("  Uygulama daemon olmadan çalışmaya devam edecek.")

    def _on_theme_change(self, theme):
        if self._rebuilding:
            return
        self.app_theme = theme
        self._save_config()
        self._apply_css()
        # Update fan gauges theme
        is_dark = theme == "dark"
        if hasattr(self, 'fan_page'):
            self.fan_page.set_dark(is_dark)

    def _on_lang_change(self, lang):
        if self._rebuilding:
            return
        if get_lang() == lang:
            return  # No change needed
        set_lang(lang)
        self._save_config()
        # Live-update nav labels
        label_map = {
            "games": T("games"), "fan": T("fan"), "lighting": T("lighting"),
            "mux": T("mux"), "tools": T("tools"), "settings": T("settings"),
        }
        for pid, lbl in self.nav_labels.items():
            if pid in label_map:
                lbl.set_label(label_map[pid])
        # Defer rebuild to next idle — we can't destroy the settings page
        # while still inside the dropdown's signal handler
        GLib.idle_add(self._rebuild_pages)

    def _on_temp_unit_change(self, unit):
        if self._rebuilding:
            return
        self.temp_unit = unit
        self._save_config()
        if hasattr(self, 'fan_page'):
            self.fan_page.set_temp_unit(unit)

    def _rebuild_pages(self):
        """Destroy and recreate all pages so T() picks up the new language."""
        self._rebuilding = True
        try:
            current_page = self.stack.get_visible_child_name()

            # Cleanup old pages
            if hasattr(self, 'fan_page'):
                self.fan_page.cleanup()
            if hasattr(self, 'lighting_page'):
                self.lighting_page.cleanup()

            # Remove old pages from stack
            for name in ("games", "tools", "fan", "lighting", "mux", "settings"):
                child = self.stack.get_child_by_name(name)
                if child:
                    self.stack.remove(child)

            # Recreate pages
            self.games_page = GamesPage()
            self.tools_page = ToolsPage(service=self.service)
            self.fan_page = FanPage(service=self.service)
            self.lighting_page = LightingPage(service=self.service)
            self.mux_page = MUXPage(service=self.service)
            self.settings_page = SettingsPage(
                on_theme_change=self._on_theme_change,
                on_lang_change=self._on_lang_change,
                on_temp_unit_change=self._on_temp_unit_change
            )

            self.stack.add_named(self.games_page, "games")
            self.stack.add_named(self.tools_page, "tools")
            self.stack.add_named(self.fan_page, "fan")
            self.stack.add_named(self.lighting_page, "lighting")
            self.stack.add_named(self.mux_page, "mux")
            self.stack.add_named(self.settings_page, "settings")

            # Restore theme + temp_unit state
            self.fan_page.set_dark(self.app_theme == "dark")
            self.fan_page.set_temp_unit(self.temp_unit)

            # Restore settings dropdowns
            self.settings_page.set_theme_index(0 if self.app_theme == "dark" else 1)
            self.settings_page.set_lang_index(0 if get_lang() == "tr" else 1)
            self.settings_page.set_temp_unit_index(0 if self.temp_unit == "C" else 1)

            # Restore page
            self._navigate(current_page or "settings")
        finally:
            self._rebuilding = False
        return False  # Don't repeat GLib.idle_add

    def do_close_request(self):
        """Cleanup on close."""
        if hasattr(self, 'lighting_page'):
            self.lighting_page.cleanup()
        if hasattr(self, 'fan_page'):
            self.fan_page.cleanup()
        return False


class HPManagerApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self._on_activate)

    def _on_activate(self, app):
        print("Activating application window...", flush=True)
        win = HPManagerWindow(application=app)
        win.present()


def main():
    print("Initializing Application...", flush=True)
    # Use a distinct ID for the GUI to avoid conflict with the daemon service name
    # and use NON_UNIQUE to ensure it always launches a new instance for now
    app = HPManagerApp(application_id="com.yyl.hpmanager.gui", flags=Gio.ApplicationFlags.FLAGS_NONE)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
