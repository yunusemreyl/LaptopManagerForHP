#!/usr/bin/env python3
"""
OMEN Command Center for Linux - Main Window
Launcher-style home menu with page selection cards.
"""
import sys, os, json, math, subprocess, shutil, threading, concurrent.futures

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback for Python ≤3.10
    except ImportError:
        tomllib = None  # No TOML support — will use JSON config only

import gi
gi.require_version('Gtk', '4.0')
try:
    gi.require_version('Adw', '1')
    from gi.repository import Adw
    HAS_ADW = True
except ValueError:
    Adw = None
    HAS_ADW = False

from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf, Pango
import cairo

# Add parent path for imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check relative to source (2 levels up -> src/OmenCtl)
PROJ_SRC = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

# Check relative to installed location (1 level up -> /usr/share/hp-manager)
PROJ_INSTALLED = os.path.abspath(os.path.join(BASE_DIR, ".."))

if os.path.exists(os.path.join(PROJ_SRC, "images", "omenctl.png")):
    IMAGES_DIR = os.path.join(PROJ_SRC, "images")
    PROJECT_DIR = PROJ_SRC
elif os.path.exists(os.path.join(PROJ_INSTALLED, "images", "omenctl.png")):
    IMAGES_DIR = os.path.join(PROJ_INSTALLED, "images")
    PROJECT_DIR = PROJ_INSTALLED
else:
    IMAGES_DIR = "/usr/share/hp-manager/images"
    PROJECT_DIR = "/usr/share/hp-manager"

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))

from pages.fan_page import FanPage
from pages.lighting_page import LightingPage
from pages.mux_page import MUXPage
from pages.settings_page import SettingsPage
from pages.keyboard_page import KeyboardPage
from pages.app_profiles_page import AppProfilesPage
from pages.power_page import PowerPage

APP_VERSION = "1.6.6"
CONFIG_FILE      = os.path.expanduser("~/.config/hp-manager.toml")
CONFIG_FILE_JSON = os.path.expanduser("~/.config/hp-manager.json")
_LAUNCHER_REFRESH_MS = 5000
_DBUS_TIMEOUT = 5  # seconds — prevents D-Bus hangs from freezing app
_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mw-dbus")


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

# ── Translations (centralised in i18n.py) ────────────────────────────────────
from i18n import T, set_lang, get_lang


def get_model_branding():
    """Return 'OMEN', 'Victus', or 'HP Laptop' based on DMI product name."""
    try:
        for dmi_file in ("/sys/class/dmi/id/product_name",
                         "/sys/class/dmi/id/product_family"):
            if os.path.exists(dmi_file):
                with open(dmi_file, "r") as f:
                    name = f.read().lower()
                if "omen" in name:
                    return "OMEN"
                if "victus" in name:
                    return "Victus"
    except Exception:
        pass
    return "HP Laptop"


def get_device_model_name():
    """Return concrete device model name from DMI, fallback to branding."""
    invalid = {
        "",
        "to be filled by o.e.m.",
        "not applicable",
        "default string",
        "system product name",
        "unknown",
        "hp laptop",
    }
    try:
        for dmi_file in (
            "/sys/class/dmi/id/product_name",
            "/sys/class/dmi/id/product_family",
            "/sys/class/dmi/id/board_name",
        ):
            if os.path.exists(dmi_file):
                with open(dmi_file, "r") as f:
                    name = " ".join(f.read().strip().split())
                if name.lower() not in invalid:
                    return name
    except Exception:
        pass
    return get_model_branding()


class FixedMenuIcon(Gtk.DrawingArea):
    """Theme-pack-independent line icons for launcher/menu UI."""

    def __init__(self, kind, size=74, rgb=(0.92, 0.94, 0.97), line_width=3.0):
        super().__init__()
        self.kind = kind
        self.rgb = rgb
        self._line_width = line_width
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self._draw)

    def _setup_pen(self, cr, w):
        cr.set_source_rgb(*self.rgb)
        cr.set_line_width(max(1.4, self._line_width))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

    def _draw(self, _area, cr, w, h):
        self._setup_pen(cr, w)
        kind = self.kind

        if kind == "dashboard":
            s = min(w, h) * 0.23
            gap = s * 0.34
            start_x = (w - (2 * s + gap)) / 2
            start_y = (h - (2 * s + gap)) / 2
            for r in range(2):
                for c in range(2):
                    x = start_x + c * (s + gap)
                    y = start_y + r * (s + gap)
                    cr.rectangle(x, y, s, s)
                    cr.stroke()
            return

        if kind == "fan":
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.35
            cr.arc(cx, cy, r, 0, 2 * 3.14159)
            cr.stroke()
            cr.arc(cx, cy, r * 0.18, 0, 2 * 3.14159)
            cr.stroke()
            for a in (0.0, 1.57, 3.14, 4.71):
                x1 = cx + (r * 0.22) * math.cos(a)
                y1 = cy + (r * 0.22) * math.sin(a)
                x2 = cx + (r * 0.82) * math.cos(a + 0.44)
                y2 = cy + (r * 0.82) * math.sin(a + 0.44)
                cr.move_to(x1, y1)
                cr.line_to(x2, y2)
                cr.stroke()
            return

        if kind == "lighting":
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.22
            cr.arc(cx, cy - r * 0.25, r, 0, 2 * 3.14159)
            cr.stroke()
            cr.move_to(cx - r * 0.55, cy + r * 0.9)
            cr.line_to(cx + r * 0.55, cy + r * 0.9)
            cr.stroke()
            cr.move_to(cx - r * 0.34, cy + r * 0.52)
            cr.line_to(cx + r * 0.34, cy + r * 0.52)
            cr.stroke()
            cr.move_to(cx - r * 0.34, cy + r * 0.52)
            cr.line_to(cx - r * 0.34, cy + r * 0.9)
            cr.stroke()
            cr.move_to(cx + r * 0.34, cy + r * 0.52)
            cr.line_to(cx + r * 0.34, cy + r * 0.9)
            cr.stroke()
            return

        if kind == "keyboard":
            x = w * 0.16
            y = h * 0.30
            ww = w * 0.68
            hh = h * 0.38
            cr.rectangle(x, y, ww, hh)
            cr.stroke()
            key_w = ww / 7.5
            key_h = hh / 3.3
            for r in range(2):
                for c in range(6):
                    kx = x + key_w * 0.5 + c * key_w
                    ky = y + key_h * 0.5 + r * key_h
                    cr.rectangle(kx, ky, key_w * 0.64, key_h * 0.55)
                    cr.stroke()
            cr.rectangle(x + ww * 0.22, y + hh * 0.72, ww * 0.56, key_h * 0.35)
            cr.stroke()
            return

        if kind == "mux":
            x = w * 0.2
            y = h * 0.26
            ww = w * 0.6
            hh = h * 0.48
            cr.rectangle(x, y, ww, hh)
            cr.stroke()
            for i in range(4):
                px = x - ww * 0.08
                py = y + hh * 0.15 + i * hh * 0.22
                cr.move_to(px, py)
                cr.line_to(x, py)
                cr.stroke()
            for i in range(4):
                px = x + ww
                py = y + hh * 0.15 + i * hh * 0.22
                cr.move_to(px, py)
                cr.line_to(px + ww * 0.08, py)
                cr.stroke()
            cr.rectangle(x + ww * 0.22, y + hh * 0.22, ww * 0.56, hh * 0.56)
            cr.stroke()
            return

        if kind == "power":
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.25
            cr.arc(cx, cy, r, 0, 2 * 3.14159)
            cr.stroke()
            cr.move_to(cx - r*0.3, cy - r*0.6)
            cr.line_to(cx + r*0.4, cy + r*0.1)
            cr.line_to(cx - r*0.1, cy + r*0.1)
            cr.line_to(cx + r*0.3, cy + r*0.6)
            cr.stroke()
            return

        if kind == "app_profiles":
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.26
            cr.arc(cx, cy, r, 0, 2 * 3.14159)
            cr.stroke()
            cr.rectangle(cx - r*0.4, cy - r*0.4, r*0.8, r*0.8)
            cr.stroke()
            cr.move_to(cx - r*1.2, cy)
            cr.line_to(cx - r*0.7, cy)
            cr.stroke()
            cr.move_to(cx + r*0.7, cy)
            cr.line_to(cx + r*1.2, cy)
            cr.stroke()
            return

        if kind == "settings":
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.24
            cr.arc(cx, cy, r, 0, 2 * 3.14159)
            cr.stroke()
            cr.arc(cx, cy, r * 0.42, 0, 2 * 3.14159)
            cr.stroke()
            for i in range(8):
                a = i * (3.14159 / 4)
                x1 = cx + (r * 1.1) * math.cos(a)
                y1 = cy + (r * 1.1) * math.sin(a)
                x2 = cx + (r * 1.38) * math.cos(a)
                y2 = cy + (r * 1.38) * math.sin(a)
                cr.move_to(x1, y1)
                cr.line_to(x2, y2)
                cr.stroke()
            return

        if kind == "back":
            x = w * 0.74
            y = h * 0.5
            cr.move_to(x, y)
            cr.line_to(w * 0.3, y)
            cr.stroke()
            cr.move_to(w * 0.48, h * 0.28)
            cr.line_to(w * 0.3, y)
            cr.line_to(w * 0.48, h * 0.72)
            cr.stroke()
            return


class HPManagerWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("OmenCtl")
        self.set_default_size(1100, 750)
        self.set_decorated(True)
        self.set_resizable(True)

        # Register local icon directory with the theme
        display = Gdk.Display.get_default()
        icon_theme = Gtk.IconTheme.get_for_display(display)
        if IMAGES_DIR not in icon_theme.get_search_path():
            icon_theme.add_search_path(IMAGES_DIR)

        self.set_icon_name("omenctl")

        self.app_theme = "dark"
        self.temp_unit = "C"
        self.services   = {}
        self.ready      = False
        self._rebuilding = False
        self._launcher_cards = {}
        self._launcher_timer_id = None
        self._launcher_busy = False
        self._launcher_cpu_prev = None
        self._launcher_cpu_smooth = 0.0
        self._nvidia_smi = shutil.which("nvidia-smi") or ""
        self._nvidia_runtime_status_path = None
        self._nvidia_runtime_status_scanned = False
        self.performance_mode = "balanced"
        self._ui_scale_bucket = "normal"
        self._ui_scale_tick_id = 0
        self._ui_last_width = 0
        self._ui_last_height = 0
        self._content_overlay = None
        self._back_button_floating = False
        self._scroll_adjustment = None
        self._scroll_adjustment_handler = 0
        self._sidebar_tick_id = 0
        self._sidebar_current_width = 68
        self._load_config()
        self.page_titles = {
            "dashboard": T("dashboard"),
            "fan": T("fan"),
            "lighting": T("lighting"),
            "power": T("power_tuning"),
            "keyboard": T("keyboard"),
            "app_profiles": T("app_profiles"),
            "mux": "MUX",
            "settings": T("settings"),
        }

        self._apply_theme_preference()

        self._apply_css()
        self._build_ui()
        # Defer daemon connection so the window is presented first.
        # This prevents the GUI from appearing frozen/not-starting when D-Bus
        # services are unavailable or slow to respond after the new multi-service
        # architecture was introduced in v1.3.5.
        GLib.idle_add(self._connect_daemon)
        self._start_launcher_metrics()

        if HAS_ADW:
            try:
                sm = Adw.StyleManager.get_default()
                sm.connect("notify::dark", lambda *_: self._on_system_theme_notify())
            except Exception:
                pass

    @staticmethod
    def _home_title():
        lang = str(get_lang() or "").lower()
        return "Kontrol Merkezi" if lang.startswith("tr") else "Control Center"

    @staticmethod
    def _home_subtitle():
        return T("home_subtitle")

    @staticmethod
    def _build_model_brand_image(model_name, size=20):
        model_low = str(model_name or "").lower()
        image_file = None
        if "omen" in model_low:
            image_file = "omen.png"
        elif "victus" in model_low:
            image_file = "victus.png"

        if image_file:
            image_path = os.path.join(IMAGES_DIR, image_file)
            if os.path.exists(image_path):
                try:
                    texture = Gdk.Texture.new_from_filename(image_path)
                    image = Gtk.Image.new_from_paintable(texture)
                    image.set_pixel_size(size)
                    return image
                except Exception:
                    pass

        fallback = Gtk.Image.new_from_icon_name("computer-symbolic")
        fallback.set_pixel_size(size)
        return fallback

    @staticmethod
    def _human_storage(value_bytes):
        try:
            val = float(value_bytes)
        except Exception:
            return "N/A"
        if val <= 0:
            return "N/A"
        gib = val / (1024 ** 3)
        if gib >= 1024:
            return f"{gib / 1024:.1f} TB"
        return f"{gib:.0f} GB"

    @staticmethod
    def _trim_hw_text(text, max_len=26):
        txt = " ".join(str(text or "").split())
        if len(txt) <= max_len:
            return txt
        return txt[:max_len - 1].rstrip() + "..."

    def _get_home_hardware_info(self):
        info = {
            "cpu": "N/A",
            "disk": "N/A",
            "gpu": "N/A",
            "ram": "N/A",
        }

        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        info["cpu"] = self._trim_hw_text(line.split(":", 1)[1].strip(), 30)
                        break
        except Exception:
            pass

        try:
            total, _used, _free = shutil.disk_usage("/")
            info["disk"] = self._human_storage(total)
        except Exception:
            pass

        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        gib = kb / (1024 * 1024)
                        info["ram"] = f"{gib:.1f} GB"
                        break
        except Exception:
            pass

        # Prefer nvidia-smi when available, fallback to lspci.
        try:
            if self._nvidia_smi:
                out = subprocess.check_output(
                    [self._nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                ).decode().strip().splitlines()
                if out and out[0].strip():
                    info["gpu"] = self._trim_hw_text(out[0].strip(), 28)
            if info["gpu"] == "N/A":
                out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, timeout=1.5).decode("utf-8", "ignore")
                for line in out.splitlines():
                    low = line.lower()
                    if "vga compatible controller" in low or "3d controller" in low:
                        info["gpu"] = self._trim_hw_text(line.split(":", 2)[-1].strip(), 28)
                        break
        except Exception:
            pass

        return info

    # ── Config ───────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE) and tomllib is not None:
                with open(CONFIG_FILE, "rb") as f:
                    data = tomllib.load(f)
                self.app_theme = data.get("theme", "dark")
                self.temp_unit = data.get("temp_unit", "C")
                set_lang(data.get("lang"))
            elif os.path.exists(CONFIG_FILE_JSON):
                with open(CONFIG_FILE_JSON) as f:
                    data = json.load(f)
                self.app_theme = data.get("theme", "dark")
                self.temp_unit = data.get("temp_unit", "C")
                set_lang(data.get("lang"))
                self._save_config()
            # If only a TOML file exists but tomllib is unavailable, skip silently.
        except Exception:
            pass

    @staticmethod
    def _toml_escape(val):
        """Sanitize a string value for safe TOML embedding."""
        return str(val).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    def _save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            theme     = self._toml_escape(self.app_theme)
            lang      = self._toml_escape(get_lang())
            temp_unit = self._toml_escape(self.temp_unit)
            with open(CONFIG_FILE, "w") as f:
                f.write(f'theme = "{theme}"\n')
                f.write(f'lang = "{lang}"\n')
                f.write(f'temp_unit = "{temp_unit}"\n')
            # JSON fallback for systems without tomllib
            with open(CONFIG_FILE_JSON, "w") as f:
                json.dump({"theme": self.app_theme, "lang": get_lang(),
                           "temp_unit": self.temp_unit}, f)
        except Exception:
            pass

    # ── Theming helpers ───────────────────────────────────────────────────────

    def _apply_theme_preference(self):
        if HAS_ADW:
            sm = Adw.StyleManager.get_default()
            if self.app_theme == "dark":
                sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            elif self.app_theme == "light":
                sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            else:
                sm.set_color_scheme(Adw.ColorScheme.DEFAULT)
            return

        settings = Gtk.Settings.get_default()
        if settings is not None:
            if self.app_theme == "dark":
                settings.set_property("gtk-application-prefer-dark-theme", True)
            elif self.app_theme == "light":
                settings.set_property("gtk-application-prefer-dark-theme", False)

    def _get_system_accent(self):
        """Return the system/GTK accent colour as a hex string."""
        if not HAS_ADW:
            return "#3584e4"
        try:
            sm   = Adw.StyleManager.get_default()
            ac   = sm.get_accent_color()
            rgba = ac.to_rgba()
            r, g, b = int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
            if r or g or b:
                return f"#{r:02X}{g:02X}{b:02X}"
        except Exception:
            pass
        return "#3584e4"

    @staticmethod
    def _hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _lighten(hex_color, amount=30):
        r, g, b = HPManagerWindow._hex_to_rgb(hex_color)
        return f"#{min(255,r+amount):02X}{min(255,g+amount):02X}{min(255,b+amount):02X}"

    @staticmethod
    def _darken(hex_color, amount=30):
        r, g, b = HPManagerWindow._hex_to_rgb(hex_color)
        return f"#{max(0,r-amount):02X}{max(0,g-amount):02X}{max(0,b-amount):02X}"

    def _apply_css(self):
        accent       = self._get_system_accent()
        accent_hover = self._lighten(accent, 20)
        ar, ag, ab   = self._hex_to_rgb(accent)
        accent_dim            = f"rgba({ar}, {ag}, {ab}, 0.15)"
        accent_shadow         = "rgba(255,255,255,0.12)"
        accent_shadow_strong  = "rgba(255,255,255,0.18)"
        accent_glow           = "rgba(255,255,255,0.08)"
        accent_border_hover   = f"rgba({ar}, {ag}, {ab}, 0.3)"
        accent_dark           = self._darken(accent, 60)

        actual_theme = "dark"
        if self.app_theme == "dark":
            actual_theme = "dark"
        elif self.app_theme == "light":
            actual_theme = "light"
        elif HAS_ADW:
            sm = Adw.StyleManager.get_default()
            actual_theme = "dark" if sm.get_dark() else "light"
        else:
            settings = Gtk.Settings.get_default()
            prefers_dark = False
            if settings is not None:
                try:
                    prefers_dark = bool(settings.get_property("gtk-application-prefer-dark-theme"))
                except Exception:
                    prefers_dark = False
            actual_theme = "dark" if prefers_dark else "light"

        if actual_theme == "dark":
            mode_accent_map = {
                "eco": "#00f5a0",       # Vibrant Cyber Neon Mint
                "balanced": "#a855f7",  # Vibrant Electric Amethyst
                "performance": "#ff007f", # Vibrant Hot Neon Pink/Magenta
            }
            accent              = mode_accent_map.get(self.performance_mode, "#a855f7")
            accent_hover        = self._lighten(accent, 12)
            ar, ag, ab          = self._hex_to_rgb(accent)
            accent_dim          = f"rgba({ar}, {ag}, {ab}, 0.12)" # Sleek subtle accent alpha
            accent_shadow       = f"rgba({ar}, {ag}, {ab}, 0.28)" # Dynamic glowing colored shadow
            accent_shadow_strong = f"rgba({ar}, {ag}, {ab}, 0.42)"
            accent_glow         = f"rgba({ar}, {ag}, {ab}, 0.16)" # Interactive glow
            accent_border_hover = f"rgba({ar}, {ag}, {ab}, 0.48)"
            accent_dark         = self._darken(accent, 60)
            bg             = "#07080c"                         # Deep Obsidian Black
            sidebar_bg     = "#0a0b12"                         # Deep sidebar base
            sidebar_bg2    = "#10111a"                         # Sidebar gradient end
            card_bg        = "rgba(20, 18, 28, 0.72)"         # Translucent Amethyst Glass
            card_border    = "rgba(255, 255, 255, 0.07)"       # Frosted border
            sep_color      = "rgba(168, 85, 247, 0.12)"        # Purple-tinted separator
            fg             = "#ffffff"
            fg_dim         = "#cbd5e1"
            fg_very_dim    = "#94a3b8"
            input_bg       = "rgba(255, 255, 255, 0.08)"
            clean_ram_color = "inherit"
            launcher_title_color = "#ffffff"
            launcher_subtitle_color = "#94a3b8"
            launcher_metric_main_color = "#f8fafc"
            launcher_metric_sub_color = "#cbd5e1"
            launcher_temp_warm_color = "#e2e8f0"
            launcher_mode_badge_color = "rgba(168, 85, 247, 0.15)"
            launcher_mode_badge_muted_color = "rgba(255, 255, 255, 0.06)"
            launcher_dimmed_opacity = 0.55
            topbar_bg      = "rgba(10, 11, 15, 0.85)"
            topbar_border  = "rgba(255, 255, 255, 0.08)"
            topbar_shadow  = "rgba(0,0,0,0.65)"
        else:
            bg             = "#f3f4f6"                         # Minimalist Porcelain
            sidebar_bg     = "#f8f9fb"                         # Light sidebar base
            sidebar_bg2    = "#f0f1f5"                         # Light sidebar gradient end
            card_bg        = "rgba(255, 255, 255, 0.85)"
            card_border    = "rgba(0, 0, 0, 0.06)"
            sep_color      = "rgba(0, 0, 0, 0.08)"
            fg             = "#0f172a"
            fg_dim         = "#475569"
            fg_very_dim    = "#64748b"
            input_bg       = "rgba(0, 0, 0, 0.05)"
            clean_ram_color = "#0f172a"
            launcher_title_color = "#0f172a"
            launcher_subtitle_color = "#475569"
            launcher_metric_main_color = "#0f172a"
            launcher_metric_sub_color = "#475569"
            launcher_temp_warm_color = "#334155"
            launcher_mode_badge_color = "rgba(0, 0, 0, 0.05)"
            launcher_mode_badge_muted_color = "rgba(0, 0, 0, 0.02)"
            launcher_dimmed_opacity = 0.75
            topbar_bg      = "rgba(255, 255, 255, 0.90)"
            topbar_border  = "rgba(0, 0, 0, 0.06)"
            topbar_shadow  = "rgba(0, 0, 0, 0.08)"
            
            # Recalculate accent for light mode to maintain contrast
            mode_accent_map_light = {
                "eco": "#0d9488",       # Deep Mint Teal
                "balanced": "#4f46e5",  # Deep Royal Indigo
                "performance": "#db2777" # Deep Crimson/Rose
            }
            accent              = mode_accent_map_light.get(self.performance_mode, "#4f46e5")
            accent_hover        = self._darken(accent, 10)
            ar, ag, ab          = self._hex_to_rgb(accent)
            accent_dim          = f"rgba({ar}, {ag}, {ab}, 0.12)"
            accent_shadow       = f"rgba({ar}, {ag}, {ab}, 0.18)"
            accent_shadow_strong = f"rgba({ar}, {ag}, {ab}, 0.32)"
            accent_glow         = f"rgba({ar}, {ag}, {ab}, 0.10)"
            accent_border_hover = f"rgba({ar}, {ag}, {ab}, 0.32)"
            accent_dark         = self._darken(accent, 40)

        presets_css = ""
        surface_radius = 16
        preset_colors = ["#FF0000","#00FF00","#0000FF","#FFFFFF","#FFFF00",
                         "#00FFFF","#FF00FF","#FF6600","#7B00FF"]
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
        window {{
            background-color: transparent;
            color: {fg};
            font-family: "Geist", "Inter", "Noto Sans", sans-serif;
        }}
        .app-shell {{
            background-color: {bg};
            border-radius: 0px;
            border: none;
        }}
        .app-scale-compact .card {{
            padding: 16px;
        }}
        .app-scale-compact .inner-panel {{
            padding: 10px;
        }}
        .app-scale-compact .inline-page-header {{
            min-height: 30px;
            margin: 4px 6px 2px 6px;
        }}
        .app-scale-compact .launcher-card {{
            min-width: 200px;
            min-height: 146px;
        }}
        .app-scale-compact .launcher-icon-wrap {{
            min-height: 64px;
            padding: 6px 8px;
        }}
        .app-scale-spacious .card {{
            padding: 24px;
        }}
        .app-scale-spacious .inner-panel {{
            padding: 16px;
        }}
        .app-scale-spacious .launcher-card {{
            min-width: 250px;
            min-height: 186px;
        }}
        .app-scale-spacious .launcher-icon-wrap {{
            min-height: 92px;
            padding: 10px 12px;
        }}

        .floating-topbar {{
            background: {topbar_bg};
            border: 1px solid {topbar_border};
            border-radius: {surface_radius}px;
            padding: 2px 8px;
            box-shadow: 0 12px 28px {topbar_shadow};
            transition: background-color 260ms ease, border-color 260ms ease, box-shadow 260ms ease;
        }}
        .floating-sidebar {{
            background: linear-gradient(180deg, {sidebar_bg} 0%, {sidebar_bg2} 100%);
            border: none;
            border-right: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 0px;
            box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.03);
            padding: 8px 16px;
            transition: background-color 260ms ease, border-color 260ms ease, box-shadow 260ms ease, opacity 260ms ease;
        }}
        .sidebar-header-area {{
            padding: 16px 12px 12px 12px;
            margin-bottom: 0px;
        }}
        .sidebar-header-sep {{
            background: linear-gradient(90deg, transparent 5%, rgba({ar}, {ag}, {ab}, 0.18) 50%, transparent 95%);
            min-height: 1px;
            margin: 0px 14px 4px 14px;
        }}
        .sidebar-device-btn {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            padding: 10px;
            margin: 0px;
            transition: all 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
        }}
        .sidebar-device-btn:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba({ar}, {ag}, {ab}, 0.25);
            box-shadow: 0 4px 16px rgba({ar}, {ag}, {ab}, 0.12), 0 2px 8px rgba(0, 0, 0, 0.25);
            transform: scale(1.04);
        }}
        .sidebar-device-btn:active {{
            transform: scale(0.96);
            background: rgba(255, 255, 255, 0.04);
        }}
        .sidebar-device-model {{
            font-size: 11px;
            font-weight: 700;
            color: {fg_dim};
            margin-top: 24px;
            margin-top: 6px;
            padding: 0 4px;
            transition: opacity 180ms ease;
        }}
        .floating-page-title {{
            font-size: 12px;
            font-weight: 700;
            color: {fg};
            padding: 2px 8px;
            border-radius: 999px;
            border: 1px solid {card_border};
            background: alpha({fg}, 0.04);
            transition: background-color 220ms ease, color 220ms ease, border-color 220ms ease;
        }}
        .content-shell {{
            background: transparent;
            border: none;
            border-radius: 0px;
            box-shadow: none;
        }}
        .window-control-btn {{
            min-width: 28px;
            min-height: 28px;
            border-radius: 999px;
            padding: 0;
            border: 1px solid {card_border};
            background: transparent;
            color: {fg_dim};
            transition: all 120ms ease;
        }}
        .window-control-btn:hover {{
            background: {accent_dim};
            color: {fg};
            border-color: {accent_border_hover};
        }}
        .window-control-btn.close-btn:hover {{
            background: rgba(227, 51, 51, 0.22);
            border-color: rgba(227, 51, 51, 0.35);
            color: #ffffff;
        }}
        .menu-back-btn {{
            border-radius: 999px;
            border: 1px solid {card_border};
            background: alpha({fg}, 0.04);
            padding: 0;
            min-width: 32px;
            min-height: 32px;
            box-shadow: none;
        }}
        .menu-back-btn:hover {{
            background: alpha({fg}, 0.08);
            border-color: alpha(#ffffff, 0.32);
            box-shadow: 0 0 10px alpha(#ffffff, 0.14);
        }}
        .menu-back-btn image {{
            color: {fg};
        }}
        .menu-back-btn:disabled {{
            opacity: 0.35;
        }}
        .inline-page-header {{
            min-height: 36px;
            margin: 8px 10px 6px 10px;
        }}
        .inline-page-title {{
            font-size: 14px;
            font-weight: 760;
            color: {fg};
            letter-spacing: 0.2px;
        }}
        .floating-back-btn-active {{
            margin-top: 16px;
            margin-left: 16px;
            background: linear-gradient(180deg, alpha(#ffffff, 0.18), alpha(#ffffff, 0.10));
            border-color: alpha(#ffffff, 0.42);
            box-shadow: 0 10px 24px rgba(0,0,0,0.32);
        }}
        .floating-back-btn-active image {{
            color: #ffffff;
        }}

        .launcher-page-title {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: 0.3px;
            color: {launcher_title_color};
            transition: color 220ms ease;
        }}
        .launcher-page-subtitle {{
            font-size: 11px;
            color: {launcher_subtitle_color};
            font-weight: 500;
            margin-bottom: 2px;
            transition: color 220ms ease;
        }}
        .launcher-card {{
            background: alpha({fg}, 0.025);
            border: 1px solid alpha({fg}, 0.06);
            border-radius: 14px;
            padding: 0;
            min-width: 230px;
            min-height: 166px;
            transition: all 180ms ease;
            box-shadow: 0 8px 18px rgba(0,0,0,0.22);
        }}
        .launcher-card:hover {{
            background: alpha({fg}, 0.045);
            border-color: {accent};
            box-shadow: 0 12px 24px rgba(0,0,0,0.28), 0 0 14px {accent_shadow};
            transform: translateY(-2px);
        }}
        .launcher-card:active {{
            transform: scale(0.98);
        }}
        .launcher-icon-wrap {{
            background: rgba(152, 156, 166, 0.04);
            border-bottom: 1px solid alpha({fg}, 0.05);
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
            min-height: 76px;
            padding: 8px 10px;
            transition: background-color 220ms ease, border-color 220ms ease;
        }}
        .launcher-icon-wrap image {{
            color: alpha({fg}, 0.9);
            transition: color 220ms ease;
        }}
        .launcher-card-title {{
            font-size: 15px;
            font-weight: 760;
            letter-spacing: 0.2px;
            color: {launcher_title_color};
            transition: color 220ms ease;
        }}
        .launcher-card-sub {{
            font-size: 10px;
            font-weight: 520;
            color: {launcher_subtitle_color};
            transition: color 220ms ease;
        }}
        .launcher-metric-main {{
            font-size: 12px;
            font-weight: 700;
            color: {launcher_metric_main_color};
            font-family: "JetBrains Mono", "Geist", "Inter", monospace;
            transition: color 220ms ease;
        }}
        .launcher-metric-sub {{
            font-size: 10px;
            color: {launcher_metric_sub_color};
            font-weight: 520;
            font-family: "JetBrains Mono", "Geist", "Inter", monospace;
            transition: color 220ms ease;
        }}
        .launcher-temp-cool {{ color: #57c494; }}
        .launcher-temp-warm {{ color: {launcher_temp_warm_color}; }}
        .launcher-temp-hot {{ color: #ff8a61; }}
        .launcher-mode-badge {{
            border-radius: 999px;
            padding: 3px 9px;
            background: alpha({accent}, 0.18);
            border: 1px solid alpha({accent}, 0.42);
            color: {launcher_mode_badge_color};
            font-size: 10px;
            font-weight: 700;
            transition: background-color 220ms ease, border-color 220ms ease, color 220ms ease;
        }}
        .launcher-mode-badge-muted {{
            background: rgba(122, 128, 140, 0.24);
            border: 1px solid rgba(162, 170, 184, 0.45);
            color: {launcher_mode_badge_muted_color};
        }}
        .launcher-status-badge {{
            border-radius: 999px;
            min-width: 18px;
            min-height: 18px;
            padding: 0;
            background: rgba(224, 58, 58, 0.95);
            border: 1px solid rgba(255, 215, 215, 0.42);
            color: white;
            font-size: 11px;
            font-weight: 900;
        }}
        .launcher-status-badge-critical {{
            min-width: 26px;
            min-height: 26px;
            font-size: 14px;
            background: rgba(224, 58, 58, 1.0);
            border: 1px solid rgba(255, 225, 225, 0.65);
            box-shadow: 0 0 12px rgba(224, 58, 58, 0.35);
        }}
        .launcher-mini-bar {{
            min-height: 5px;
            border-radius: 999px;
            margin-top: 2px;
        }}
        levelbar.launcher-util-bar trough {{
            background: alpha({fg}, 0.14);
            border-radius: 999px;
            min-height: 4px;
        }}
        levelbar.launcher-cpu-bar block {{
            background: #4f97ff;
            border-radius: 999px;
        }}
        levelbar.launcher-gpu-bar block {{
            background: #ff8a61;
            border-radius: 999px;
        }}
        .launcher-card-dimmed {{
            opacity: {launcher_dimmed_opacity};
            border-color: alpha({fg}, 0.03);
            box-shadow: none;
        }}

        /* ── Global text color — override Adw defaults ── */
        label {{
            color: {fg};
            transition: color 220ms ease;
        }}
        .heading {{
            color: {fg};
            font-size: 15px;
            font-weight: 800;
            letter-spacing: 0.2px;
            transition: color 220ms ease;
        }}
        .title-1, .title-2, .title-3, .title-4 {{
            color: {fg};
            font-family: "JetBrains Mono", "Inter", "Roboto Mono", monospace;
            transition: color 220ms ease;
        }}
        .title-1 {{
            font-size: 30px;
            font-weight: 800;
        }}
        .title-2 {{
            font-size: 24px;
            font-weight: 760;
        }}
        .title-3 {{
            font-size: 20px;
            font-weight: 730;
        }}
        .title-4 {{
            font-size: 15px;
            font-weight: 700;
        }}
        .dim-label {{
            color: {fg_dim};
            font-size: 12px;
            font-weight: 520;
            transition: color 220ms ease;
        }}
        entry {{
            color: {fg};
            transition: color 220ms ease;
        }}
        image {{
            color: {fg_dim};
            transition: color 220ms ease;
        }}
        button label {{
            color: inherit;
        }}
        .suggested-action {{
            background: {accent};
            color: white;
            box-shadow: 0px 4px 12px alpha(#ffffff, 0.20);
            border: 1px solid alpha({accent}, 0.5);
            transition: all 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
        }}
        .suggested-action:hover {{
            box-shadow: 0px 6px 16px alpha(#ffffff, 0.30);
            transform: translateY(-2px);
        }}
        .suggested-action label {{
            color: white;
        }}
        .destructive-action {{
            background: #e33;
            color: white;
            box-shadow: 0px 4px 12px rgba(238, 51, 51, 0.3);
            border: 1px solid rgba(238, 51, 51, 0.5);
            transition: all 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
        }}
        .destructive-action:hover {{
            box-shadow: 0px 6px 16px rgba(238, 51, 51, 0.6);
            transform: translateY(-2px);
        }}
        .destructive-action label {{
            color: white;
        }}
        .max-fan-action {{
            background: linear-gradient(160deg, rgba(255,255,255,0.16), rgba(255,255,255,0.10));
            border: 1px solid rgba(255,255,255,0.28);
            box-shadow: 0px 4px 14px rgba(255,255,255,0.16);
        }}
        .max-fan-action:hover {{
            border-color: rgba(255,255,255,0.46);
            box-shadow: 0px 8px 20px rgba(255,255,255,0.22);
            transform: translateY(-1px);
        }}
        .clean-ram-action {{
            background: {card_bg};
            border: 1px solid {sep_color};
            box-shadow: 0px 4px 10px rgba(0,0,0,0.08);
            transition: all 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
        }}
        .clean-ram-action:hover {{
            box-shadow: 0px 6px 16px rgba(0,0,0,0.15);
            border-color: {accent_dim};
            transform: translateY(-2px);
        }}
        .clean-ram-action label {{
            color: {clean_ram_color};
            font-weight: 700;
        }}
        .action-btn-content {{
            margin: 0;
        }}
        .action-btn-content image {{
            color: {fg_dim};
        }}
        .action-btn-label {{
            font-size: 13px;
            font-weight: 760;
            letter-spacing: 0.2px;
        }}
        .dashboard-link-btn {{
            border-radius: 999px;
            padding: 5px 12px;
            min-height: 0;
            background: alpha({accent}, 0.14);
            border: 1px solid alpha({accent}, 0.38);
            color: {fg};
            box-shadow: 0 0 10px alpha(#ffffff, 0.08);
            transition: background-color 220ms ease, border-color 220ms ease, color 220ms ease, box-shadow 220ms ease;
        }}
        .dashboard-link-btn:hover {{
            background: alpha({accent}, 0.22);
            border-color: alpha({accent}, 0.56);
            box-shadow: 0 0 14px alpha(#ffffff, 0.14);
        }}

        /* ── Sidebar ── */
        .sidebar {{
            background-color: transparent;
            border-right: none;
        }}

        separator {{
            background: {sep_color};
            min-width: 1px; min-height: 1px;
        }}
        .sidebar-logo {{
            padding: 15px 0 10px 0;
        }}
        .sidebar-logo image {{
            opacity: 0.9;
        }}
        .logo-img-light {{
            -gtk-icon-filter: brightness(0);
        }}
        .logo-img {{
            margin-bottom: 4px;
        }}

        /* ── Nav Items ── */
        .nav-item {{
            padding: 10px 10px;
            margin: 3px 8px;
            border-radius: 10px;
            border: 1px solid transparent;
            transition: all 180ms cubic-bezier(0.2, 0.8, 0.2, 1);
            background: transparent;
            min-height: 0;
        }}
        .nav-item:hover {{
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.06);
        }}
        .nav-item.active {{
            background: linear-gradient(135deg, rgba({ar}, {ag}, {ab}, 0.14), rgba({ar}, {ag}, {ab}, 0.06));
            border-color: rgba({ar}, {ag}, {ab}, 0.22);
            box-shadow: 0 0 12px rgba({ar}, {ag}, {ab}, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }}
        .nav-item.active image,
        .nav-item.active label {{
            color: {accent};
        }}
        .theme-toggle-btn {{
            background: alpha({accent}, 0.12);
            border-color: alpha({accent}, 0.28);
            box-shadow: 0 2px 10px alpha({accent}, 0.08);
        }}
        .theme-toggle-btn:hover {{
            background: alpha({accent}, 0.20);
            border-color: alpha({accent}, 0.40);
            box-shadow: 0 4px 14px alpha({accent}, 0.14);
        }}
        .nav-label {{
            font-size: 12px;
            font-weight: 620;
            color: {fg_dim};
            margin: 0px;
            transition: color 180ms ease;
        }}
        .nav-item:hover .nav-label {{
            color: {fg};
        }}
        .nav-item.active .nav-label {{
            color: {accent};
            font-weight: 680;
        }}
        .nav-icon {{
            color: {fg_very_dim};
            transition: color 180ms ease;
        }}
        .theme-toggle-btn .nav-icon {{
            color: {accent};
        }}
        .nav-item:hover .nav-icon {{
            color: {fg};
        }}
        .theme-toggle-btn:hover .nav-icon {{
            color: {accent};
        }}
        .nav-item.active .nav-icon {{
            color: {accent};
        }}
        .nav-indicator {{
            background: {accent};
            border-radius: 999px;
            min-width: 3px;
            min-height: 18px;
            margin-right: 2px;
            box-shadow: 0 0 8px rgba({ar}, {ag}, {ab}, 0.5);
            transition: opacity 180ms ease;
        }}
        .nav-indicator-hidden {{
            opacity: 0;
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
        .stat-rpm {{
            font-size: 16px;
            color: {fg};
            font-weight: 700;
        }}
        .fan-title {{
            font-size: 14px;
            color: {fg};
            font-weight: 600;
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
            border-radius: 14px;
            transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
            min-width: 124px;
            min-height: 82px;
        }}
        .profile-btn:hover {{
            border-color: {accent_border_hover};
            box-shadow: 0 6px 16px alpha(#ffffff, 0.18);
            transform: translateY(-2px);
        }}
        .profile-btn:checked {{
            background: {accent_dim};
            border-color: {accent};
        }}
        .profile-emoji {{
            font-size: 24px;
        }}
        .profile-label {{
            font-size: 12px;
            font-weight: 600;
            color: {fg};
        }}

        .mux-btn {{
            background: {input_bg};
            border: 2px solid {card_border};
            border-radius: 18px;
            min-width: 140px;
            min-height: 140px;
            transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1);
            color: {fg};
        }}
        .mux-btn:hover {{
            border-color: {accent_border_hover};
            box-shadow: 0 6px 16px alpha(#ffffff, 0.18);
            transform: translateY(-2px);
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
            border-radius: 16px;
            border: 1px solid {card_border};
            padding: 0;
        }}
        .fan-mode-btn {{
            background: transparent;
            color: {fg};
            border: none;
            border-radius: 13px;
            padding: 7px 0;
            font-weight: 600;
            font-size: 12px;
            transition: all 0.2s ease;
            min-height: 0;
            min-width: 124px;
        }}
        .fan-mode-btn:hover {{
            background: alpha({fg}, 0.08);
        }}
        .fan-mode-btn:checked {{
            background: {accent};
            color: white;
            box-shadow: 0 4px 12px {accent_shadow_strong};
        }}

        /* ── Rebuilt compact fan controls ── */
        .fan-cyber-panel {{
            padding: 4px 0 2px 0;
        }}
        .fan-control-label {{
            font-size: 11px;
            color: {fg_dim};
            font-weight: 650;
            letter-spacing: 0.8px;
            text-transform: uppercase;
        }}
        .power-profile-grid {{
            margin-top: 2px;
        }}
        .power-profile-card {{
            background: alpha({fg}, 0.04);
            border: 1px solid alpha({fg}, 0.12);
            border-radius: 10px;
            box-shadow: inset 0 1px 0 alpha({fg}, 0.03);
            transition: all 0.18s ease;
        }}
        .power-profile-card:hover {{
            border-color: alpha({fg}, 0.22);
            background: alpha({fg}, 0.055);
        }}
        .power-profile-card:checked {{
            border-color: alpha({accent}, 0.72);
            background: alpha({accent}, 0.22);
            box-shadow: 0 0 16px alpha(#ffffff, 0.18), inset 0 1px 0 alpha(#ffffff, 0.24);
        }}
        .power-profile-title {{
            font-size: 12px;
            color: {fg};
            font-weight: 760;
            margin-bottom: 1px;
        }}
        .power-profile-desc {{
            font-size: 10px;
            color: {fg_dim};
            font-weight: 510;
            line-height: 1.2;
        }}

        .fan-mode-compact-strip {{
            background: alpha({fg}, 0.035);
            border: 1px solid alpha({fg}, 0.16);
            border-radius: 10px;
            padding: 1px;
        }}
        .fan-mode-compact-btn {{
            background: transparent;
            border: none;
            border-radius: 7px;
            min-height: 0;
            color: {fg_dim};
            font-size: 11px;
            font-weight: 640;
            padding: 5px 10px;
            transition: all 0.16s ease;
        }}
        .fan-mode-compact-btn:hover {{
            background: alpha({fg}, 0.08);
            color: {fg};
        }}
        .fan-mode-compact-btn:checked {{
            background: linear-gradient(180deg, alpha({accent}, 0.92), alpha({accent_dark}, 0.90));
            color: #f6f7f9;
            box-shadow: 0 0 10px alpha(#ffffff, 0.26);
        }}
        .fan-control-status {{
            font-size: 11px;
            color: {fg_dim};
            font-weight: 520;
            margin-top: 2px;
        }}

        /* ── Fan page dynamic theme accents ── */
        .fan-theme-eco .temp-circle {{
            border-color: #56d17a;
            box-shadow: 0 0 16px rgba(86, 209, 122, 0.18);
        }}
        .fan-theme-eco .sensor-bar {{ background: #56d17a; }}
        .fan-theme-eco .sensor-pod,
        .fan-theme-eco .fan-mode-compact-strip {{ border-color: rgba(86, 209, 122, 0.26); }}
        .fan-theme-eco .power-profile-card:checked,
        .fan-theme-eco .fan-mode-compact-btn:checked {{
            background: rgba(86, 209, 122, 0.24);
            border-color: rgba(122, 234, 156, 0.54);
            box-shadow: 0 0 8px rgba(86, 209, 122, 0.16);
        }}

        .fan-theme-balanced .temp-circle {{
            border-color: #3ca8ff;
            box-shadow: 0 0 16px rgba(60, 168, 255, 0.18);
        }}
        .fan-theme-balanced .sensor-bar {{ background: #3ca8ff; }}
        .fan-theme-balanced .sensor-pod,
        .fan-theme-balanced .fan-mode-compact-strip {{ border-color: rgba(60, 168, 255, 0.24); }}
        .fan-theme-balanced .power-profile-card:checked,
        .fan-theme-balanced .fan-mode-compact-btn:checked {{
            background: rgba(60, 168, 255, 0.24);
            border-color: rgba(128, 196, 255, 0.52);
            box-shadow: 0 0 8px rgba(60, 168, 255, 0.16);
        }}

        .fan-theme-performance .temp-circle {{
            border-color: #ef5b4a;
            box-shadow: 0 0 16px rgba(239, 91, 74, 0.20);
        }}
        .fan-theme-performance .sensor-bar {{ background: #ef5b4a; }}
        .fan-theme-performance .sensor-pod,
        .fan-theme-performance .fan-mode-compact-strip {{ border-color: rgba(239, 91, 74, 0.26); }}
        .fan-theme-performance .power-profile-card:checked,
        .fan-theme-performance .fan-mode-compact-btn:checked {{
            background: rgba(239, 91, 74, 0.24);
            border-color: rgba(255, 156, 145, 0.56);
            box-shadow: 0 0 8px rgba(239, 91, 74, 0.18);
        }}

        /* ── Global app colorization by performance mode ── */
        .app-perf-eco label,
        .app-perf-eco .heading,
        .app-perf-eco .section-title,
        .app-perf-eco .stat-lbl,
        .app-perf-eco .floating-page-title,
        .app-perf-balanced label,
        .app-perf-balanced .heading,
        .app-perf-balanced .section-title,
        .app-perf-balanced .stat-lbl,
        .app-perf-balanced .floating-page-title,
        .app-perf-performance label,
        .app-perf-performance .heading,
        .app-perf-performance .section-title,
        .app-perf-performance .stat-lbl,
        .app-perf-performance .floating-page-title {{
            color: {fg};
        }}
        .app-perf-eco button:checked,
        .app-perf-eco togglebutton:checked,
        .app-perf-eco .profile-btn:checked,
        .app-perf-eco .fan-mode-btn:checked,
        .app-perf-eco .zone-btn:checked {{
            background: rgba(86, 209, 122, 0.24);
            border-color: rgba(122, 234, 156, 0.50);
            color: {fg};
        }}
        .app-perf-eco scale highlight,
        .app-perf-eco progressbar progress,
        .app-perf-eco levelbar block.filled,
        .app-perf-eco .sensor-bar {{
            background: #56d17a;
        }}
        .app-perf-balanced button:checked,
        .app-perf-balanced togglebutton:checked,
        .app-perf-balanced .profile-btn:checked,
        .app-perf-balanced .fan-mode-btn:checked,
        .app-perf-balanced .zone-btn:checked {{
            background: rgba(60, 168, 255, 0.24);
            border-color: rgba(128, 196, 255, 0.50);
            color: {fg};
        }}
        .app-perf-balanced scale highlight,
        .app-perf-balanced progressbar progress,
        .app-perf-balanced levelbar block.filled,
        .app-perf-balanced .sensor-bar {{
            background: #3ca8ff;
        }}
        .app-perf-performance button:checked,
        .app-perf-performance togglebutton:checked,
        .app-perf-performance .profile-btn:checked,
        .app-perf-performance .fan-mode-btn:checked,
        .app-perf-performance .zone-btn:checked {{
            background: rgba(239, 91, 74, 0.24);
            border-color: rgba(255, 156, 145, 0.52);
            color: {fg};
        }}
        .app-perf-performance scale highlight,
        .app-perf-performance progressbar progress,
        .app-perf-performance levelbar block.filled,
        .app-perf-performance .sensor-bar {{
            background: #ef5b4a;
        }}

        /* ── Dashboard perf mode colors ── */
        .perf-eco:checked {{
            background: #6f7f99;
            box-shadow: 0 4px 12px rgba(111, 127, 153, 0.35);
        }}
        .perf-balanced:checked {{
            background: {accent};
            box-shadow: 0 4px 12px {accent_shadow_strong};
        }}
        .perf-performance:checked {{
            background: #e66100;
            box-shadow: 0 4px 12px rgba(255, 255, 255, 0.22);
        }}

        /* ── Tool cards ── */
        .tool-card {{
            background: {card_bg};
            border-radius: {surface_radius}px;
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
        .temp-circle {{
            background: radial-gradient(circle, {accent_glow} 0%, {card_bg} 100%);
            border: 2px solid {accent};
            border-radius: 50%;
            padding: 18px;
            box-shadow: 0 0 24px {accent_glow};
            min-width: 118px;
            min-height: 118px;
            transition: all 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
        }}
        .temp-circle:hover {{
            box-shadow: 0 0 50px {accent_shadow};
            transform: scale(1.05);
            border-color: {accent_hover};
        }}
        .sensor-bar {{
            background: {accent};
            border-radius: 3px;
            opacity: 0.42;
        }}
        .sensor-pod {{
            background: alpha({fg}, 0.03);
            border: 1px solid alpha({fg}, 0.08);
            border-radius: 12px;
            padding: 10px 12px;
        }}
        .sensor-card-item {{
            padding: 6px 8px;
            border-radius: 8px;
            background: alpha({fg}, 0.025);
            transition: all 0.2s ease;
        }}
        .sensor-card-item:hover {{
            background: alpha({fg}, 0.05);
        }}
        .sensor-temp-val {{
            font-size: 14px;
            font-weight: 680;
            color: {fg};
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
            border-radius: {surface_radius}px;
            border: 1px solid {card_border};
            padding: 12px;
            transition: all 0.2s ease;
        }}
        .game-card:hover {{
            border-color: {accent_border_hover};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .card {{
            background-color: {card_bg};
            border: 1px solid {card_border};
            border-radius: {surface_radius}px;
            padding: 28px;
            box-shadow: 0 12px 22px rgba(0,0,0,0.14);
        }}
        .inner-panel {{
            background: rgba(152, 156, 166, 0.07);
            border: 1px solid alpha({accent}, 0.14);
            border-radius: 14px;
            padding: 14px;
            box-shadow: inset 0 1px 0 alpha({fg}, 0.04), 0 0 0 1px alpha(#ffffff, 0.04), 0 8px 18px alpha(#ffffff, 0.08);
        }}
        .status-strip {{
            background: rgba(152, 156, 166, 0.06);
            border: 1px solid alpha({accent}, 0.12);
            border-radius: 12px;
            padding: 10px 12px;
            box-shadow: 0 6px 14px alpha(#ffffff, 0.07);
        }}
        .home-model-strip {{
            padding: 5px 8px;
            border-radius: 10px;
            border: 1px solid alpha({fg}, 0.22);
            box-shadow: 0 0 16px alpha({fg}, 0.10);
        }}
        .home-model-details {{
            min-width: 0;
        }}
        .home-model-top {{
            min-height: 0;
        }}
        .home-spec-row {{
            margin-top: 2px;
            border-top: 1px solid alpha({fg}, 0.08);
            padding-top: 6px;
        }}
        .home-spec-item {{
            border-radius: 8px;
            background: alpha({fg}, 0.03);
            border: 1px solid alpha({fg}, 0.08);
            padding: 5px 8px;
        }}
        .home-spec-item image {{
            color: {fg_very_dim};
            margin-right: 6px;
        }}
        .home-spec-title {{
            font-size: 10px;
            color: {fg_dim};
            letter-spacing: 0.4px;
            font-weight: 620;
        }}
        .home-spec-value {{
            font-size: 11px;
            font-weight: 720;
            color: {fg};
        }}
        .battery-sparkline-frame {{
            background: rgba(152, 156, 166, 0.06);
            border: 1px solid alpha({accent}, 0.12);
            border-radius: 12px;
            box-shadow: 0 0 14px alpha(#ffffff, 0.06);
            min-height: 62px;
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
            border-radius: {surface_radius}px;
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
            border-radius: {surface_radius}px;
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
            background: alpha({fg}, 0.04);
            border: 1px solid {card_border};
            outline: none;
            box-shadow: none;
            border-radius: 10px;
            color: {fg};
            min-height: 0;
            padding: 6px 10px;
        }}
        dropdown > button:hover {{
            background: alpha({fg}, 0.08);
        }}
        dropdown > button:focus {{
            outline: none;
            box-shadow: 0 0 0 2px alpha({accent}, 0.16);
            border: 1px solid alpha({accent}, 0.45);
        }}
        popover, popover.background {{
            background: transparent;
            border: none;
            box-shadow: none;
            color: {fg};
        }}
        popover > contents, popover.background > contents {{
            background: {card_bg};
            border: 1px solid alpha({fg}, 0.12);
            border-radius: 14px;
            box-shadow: 0 12px 28px rgba(0,0,0,0.24);
            padding: 6px;
        }}
        popover scrolledwindow,
        popover.background scrolledwindow,
        popover viewport,
        popover.background viewport,
        popover listview,
        popover.background listview {{
            background: {card_bg};
            color: {fg};
        }}
        popover modelbutton, popover label {{
            color: {fg};
        }}
        popover row label,
        popover modelbutton label {{
            color: {fg};
        }}
        popover modelbutton {{
            border-radius: 10px;
            padding: 8px 12px;
            margin: 1px 0;
            font-weight: 600;
            background: transparent;
        }}
        popover modelbutton:hover {{
            background: alpha({fg}, 0.08);
        }}
        popover row {{
            background: transparent;
            color: {fg};
            border-radius: 10px;
            min-height: 32px;
        }}
        popover row:hover {{
            background: alpha({fg}, 0.08);
        }}
        popover row:selected {{
            background: alpha({accent}, 0.16);
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

        /* ── Dashboard pill rows ── */
        .pill-row {{
            background: {accent_dim};
            border-radius: {surface_radius}px;
            padding: 8px 12px;
        }}
        .pill-frame {{
            background: rgba(152, 156, 166, 0.06);
            border-radius: {surface_radius}px;
            border: 1px solid alpha({accent}, 0.13);
            box-shadow: 0px 4px 10px rgba(0,0,0,0.08), 0 0 12px alpha(#ffffff, 0.05);
            transition: all 300ms cubic-bezier(0.2, 1, 0.2, 1);
        }}
        .profile-strip {{
            border-radius: 12px;
        }}
        .profile-tile {{
            min-height: 116px;
        }}
        .profile-caption {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}
        .profile-value {{
            font-size: 14px;
            font-weight: 760;
        }}
        .pill-frame:hover {{
            background: {accent_glow};
            border-color: {accent};
            box-shadow: 0px 8px 20px {accent_shadow};
            transform: translateY(-1px);
        }}
        .pill-muted {{
            opacity: 0.55;
            border-style: dashed;
        }}

        .temp-value {{
            font-family: "JetBrains Mono", "Roboto Mono", monospace;
            font-size: 30px;
            font-weight: 820;
            letter-spacing: 0.6px;
            color: {fg};
        }}
        .temp-unit {{
            font-family: "JetBrains Mono", "Roboto Mono", monospace;
            font-size: 16px;
            font-weight: 700;
            color: {fg_very_dim};
            margin-bottom: 8px;
        }}
        .sensor-name {{
            letter-spacing: 0.8px;
        }}
        .cpu-sparkline-frame {{
            background: rgba(152, 156, 166, 0.06);
            border: 1px solid alpha({accent}, 0.12);
            border-radius: 12px;
            box-shadow: 0 0 14px alpha(#ffffff, 0.06);
            margin-bottom: 6px;
            min-height: 62px;
        }}

        .info-inline {{
            font-family: "JetBrains Mono", "Inter", monospace;
            font-size: 12px;
            letter-spacing: 0.2px;
        }}
        .info-kernel-icon {{
            color: {fg_very_dim};
            margin-right: 4px;
        }}

        .debug-console {{
            background-color: #0c0c0c;
            color: #00ff41;
            font-family: 'Monospace', 'Courier New', monospace;
            font-size: 13px;
        }}
        .debug-console text {{
            background-color: #0c0c0c;
        }}

        {presets_css}
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ── UI construction ───────────────────────────────────────────────────────

    def _make_window_control_button(self, icon_name, callback, extra_css_class=None):
        btn = Gtk.Button()
        btn.add_css_class("window-control-btn")
        if extra_css_class:
            btn.add_css_class(extra_css_class)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        btn.set_child(icon)
        btn.connect("clicked", callback)
        return btn

    def _build_floating_bar(self):
        handle = Gtk.WindowHandle()

        bar = Gtk.Box(spacing=6)
        bar.add_css_class("floating-topbar")

        left = Gtk.Box(spacing=6, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)

        self.menu_back_btn = Gtk.Button()
        self.menu_back_btn.add_css_class("menu-back-btn")
        self.menu_back_btn.set_child(self._build_menu_back_content())
        self.menu_back_btn.set_tooltip_text("Ana Menü" if get_lang() == "tr" else "Main Menu")
        self.menu_back_btn.connect("clicked", lambda *_: self._navigate("home"))
        self.menu_back_btn.set_sensitive(False)
        self.menu_back_btn.set_opacity(0.35)
        self.menu_back_btn.set_size_request(32, 32)
        left.append(self.menu_back_btn)

        brand_icon = Gtk.Image()
        logo_path = os.path.join(IMAGES_DIR, "omenctl.png")
        if os.path.exists(logo_path):
            texture = Gdk.Texture.new_from_filename(logo_path)
            brand_icon.set_from_paintable(texture)
            brand_icon.set_pixel_size(20)
        else:
            brand_icon.set_from_icon_name("omenctl")
            brand_icon.set_pixel_size(20)
        self.brand_icon = brand_icon
        left.append(brand_icon)

        self.floating_page_title = Gtk.Label(label=self._home_title())
        self.floating_page_title.add_css_class("floating-page-title")
        left.append(self.floating_page_title)

        controls = Gtk.Box(spacing=6)
        controls.append(self._make_window_control_button(
            "window-minimize-symbolic", self._on_window_minimize
        ))
        self.fullscreen_btn = self._make_window_control_button(
            "view-fullscreen-symbolic", self._on_window_toggle_fullscreen
        )
        controls.append(self.fullscreen_btn)
        controls.append(self._make_window_control_button(
            "window-close-symbolic", self._on_window_close, "close-btn"
        ))

        bar.append(left)
        bar.append(controls)

        handle.set_child(bar)
        return handle

    def _build_floating_sidebar(self):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.add_css_class("sidebar")
        sidebar.add_css_class("floating-sidebar")
        sidebar.set_size_request(68, -1)
        sidebar.set_vexpand(True)
        sidebar.set_valign(Gtk.Align.FILL)
        sidebar.set_hexpand(False)

        # ── Header area with device logo ──
        header_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                              halign=Gtk.Align.CENTER)
        header_area.add_css_class("sidebar-header-area")

        brand = get_model_branding().lower()
        img_name = "victus.png" if "victus" in brand else "omen.png"
        img_path = os.path.join(IMAGES_DIR, img_name)

        device_btn = Gtk.Button()
        device_btn.add_css_class("sidebar-device-btn")

        device_img = Gtk.Image()
        if os.path.exists(img_path):
            texture = Gdk.Texture.new_from_filename(img_path)
            device_img.set_from_paintable(texture)
        else:
            device_img.set_from_icon_name("computer-symbolic")
        device_img.set_pixel_size(48)
        self.logo_icon = device_img
        device_btn.set_child(device_img)
        device_btn.set_tooltip_text("Menüyü Aç/Kapat" if get_lang() == "tr" else "Toggle Menu")
        device_btn.connect("clicked", self._toggle_sidebar)

        header_area.append(device_btn)

        # Device model name visible under logo when expanded
        device_model = get_device_model_name()
        self.device_model_lbl = Gtk.Label(label=device_model)
        self.device_model_lbl.add_css_class("sidebar-device-model")
        self.device_model_lbl.set_visible(False)
        self.device_model_lbl.set_valign(Gtk.Align.CENTER)
        self.device_model_lbl.set_halign(Gtk.Align.CENTER)
        header_area.append(self.device_model_lbl)

        sidebar.append(header_area)

        # ── Gradient accent separator ──
        header_sep = Gtk.DrawingArea()
        header_sep.add_css_class("sidebar-header-sep")
        header_sep.set_content_height(1)
        sidebar.append(header_sep)

        # ── Top spacer for vertical centering ──
        top_spacer = Gtk.Label(vexpand=True)
        sidebar.append(top_spacer)

        # ── Navigation items (excluding Settings) ──
        nav_items = [
            ("fan",       self.page_titles["fan"],       ["system-run-symbolic", "media-playback-start-symbolic", "applications-system-symbolic"]),
            ("lighting",  self.page_titles["lighting"],  ["preferences-color-symbolic", "applications-graphics-symbolic", "color-management-symbolic"]),
            ("power",     self.page_titles["power"],     ["battery-symbolic", "ac-adapter-symbolic", "power-profile-balanced-symbolic"]),
            ("keyboard",  self.page_titles["keyboard"],  ["preferences-desktop-keyboard-symbolic", "input-keyboard-symbolic"]),
            ("app_profiles", self.page_titles["app_profiles"], ["applications-system-symbolic", "preferences-system-symbolic"]),
            ("mux",       "MUX",                        ["display-symbolic", "video-display-symbolic", "computer-symbolic"]),
        ]

        self.nav_indicators = {}
        nav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for page_id, label, icon_name in nav_items:
            nav_box.append(self._make_nav_button(page_id, label, icon_name))
        sidebar.append(nav_box)

        # ── Bottom spacer for vertical centering ──
        bottom_spacer = Gtk.Label(vexpand=True)
        sidebar.append(bottom_spacer)

        # ── Bottom items (Theme Toggle & Settings) ──
        bottom_nav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        # Theme toggle button
        self.theme_toggle_btn = self._make_theme_toggle_button()
        bottom_nav_box.append(self.theme_toggle_btn)

        # Settings button
        self.settings_btn = self._make_nav_button("settings", self.page_titles["settings"], ["emblem-system-symbolic", "preferences-system-symbolic", "applications-system-symbolic"])
        bottom_nav_box.append(self.settings_btn)

        sidebar.append(bottom_nav_box)

        return sidebar

    def _toggle_sidebar(self, _btn):
        # Allow interrupting an active animation smoothly
        if getattr(self, "_sidebar_tick_id", 0):
            try:
                self.sidebar.remove_tick_callback(self._sidebar_tick_id)
            except Exception:
                pass
            self._sidebar_tick_id = 0

        self._sidebar_animating = True
        self.sidebar_expanded = not getattr(self, "sidebar_expanded", False)
        
        target_width = 200 if self.sidebar_expanded else 68
        
        # Always use the current animated width as start width to prevent instant jumps
        self._sidebar_start_width = getattr(self, "_sidebar_current_width", 68)
        self._sidebar_target_width = target_width
        self._sidebar_start_time = None
        self._sidebar_duration = 0.28 # Increased to 280ms for buttery-smooth sliding animation
        
        if self.sidebar_expanded:
            # Expand: Show labels and device model with 0 opacity immediately so they fade in
            for lbl in self.nav_labels.values():
                lbl.set_visible(True)
                lbl.set_opacity(0.0)
            if hasattr(self, "device_model_lbl") and self.device_model_lbl is not None:
                self.device_model_lbl.set_visible(True)
                self.device_model_lbl.set_opacity(0.0)
            for btn in self.nav_buttons.values():
                box = btn.get_child()
                if box:
                    box.set_spacing(10)
                    box.set_halign(Gtk.Align.START)
                    box.set_margin_start(8)
        else:
            # Collapse: Hide labels and device model immediately to avoid awkward wrapping during transition
            for lbl in self.nav_labels.values():
                lbl.set_visible(False)
            if hasattr(self, "device_model_lbl") and self.device_model_lbl is not None:
                self.device_model_lbl.set_visible(False)
            for btn in self.nav_buttons.values():
                box = btn.get_child()
                if box:
                    box.set_spacing(0)
                    box.set_halign(Gtk.Align.CENTER)
                    box.set_margin_start(0)

        # Start GdkFrameClock aligned animation tick
        self._sidebar_tick_id = self.sidebar.add_tick_callback(self._animate_sidebar_tick)

    def _animate_sidebar_tick(self, widget, frame_clock):
        if not getattr(self, "_sidebar_animating", False):
            self._sidebar_tick_id = 0
            return False

        frame_time = frame_clock.get_frame_time() / 1e6 # convert to seconds
        if self._sidebar_start_time is None:
            self._sidebar_start_time = frame_time

        elapsed = frame_time - self._sidebar_start_time
        t = min(1.0, elapsed / self._sidebar_duration)
        
        # Smooth easeOutCubic curve: f(t) = 1 - (1-t)^3
        ease = 1 - (1 - t) ** 3
        w = int(self._sidebar_start_width + (self._sidebar_target_width - self._sidebar_start_width) * ease)
        
        # Update animated width cache
        self._sidebar_current_width = w
        self.sidebar.set_size_request(w, -1)
        
        # Fade in the labels and device model label dynamically during expansion
        if self.sidebar_expanded:
            for lbl in self.nav_labels.values():
                lbl.set_opacity(ease)
            if hasattr(self, "device_model_lbl") and self.device_model_lbl is not None:
                self.device_model_lbl.set_opacity(ease)
        
        if t >= 1.0:
            self.sidebar.set_size_request(self._sidebar_target_width, -1)
            self._sidebar_current_width = self._sidebar_target_width
            self._sidebar_animating = False
            self._sidebar_tick_id = 0
            
            if self.sidebar_expanded:
                for lbl in self.nav_labels.values():
                    lbl.set_opacity(1.0)
                if hasattr(self, "device_model_lbl") and self.device_model_lbl is not None:
                    self.device_model_lbl.set_opacity(1.0)
                self.sidebar.add_css_class("expanded")
            else:
                self.sidebar.remove_css_class("expanded")
                
            return False
            
        return True

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("app-shell")
        root.set_overflow(Gtk.Overflow.HIDDEN)
        self._root_shell = root
        self.set_child(root)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.nav_labels  = {}
        self.nav_buttons = {}

        self._content_overlay = Gtk.Overlay(hexpand=True, vexpand=True)
        root.append(self._content_overlay)

        # Main horizontal layout: docked sidebar on the left, stack on the right
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0,
                       hexpand=True, vexpand=True)
        self._content_overlay.set_child(body)

        # Build docked sidebar
        self.sidebar = self._build_floating_sidebar()
        body.append(self.sidebar)

        self.menu_back_btn = Gtk.Button()
        self.menu_back_btn.add_css_class("menu-back-btn")
        self.menu_back_btn.set_child(self._build_menu_back_content())
        self.menu_back_btn.set_tooltip_text("Ana Menü" if get_lang() == "tr" else "Main Menu")
        self.menu_back_btn.connect("clicked", lambda *_: self._navigate("home"))
        self.menu_back_btn.set_sensitive(False)
        self.menu_back_btn.set_opacity(0.35)
        self.menu_back_btn.set_size_request(32, 32)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        content.add_css_class("content-shell")
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        content.set_margin_start(18)
        content.set_margin_end(18)
        self.inline_page_header = Gtk.Box(spacing=8)
        self.inline_page_header.add_css_class("inline-page-header")

        self.inline_page_title = Gtk.Label(label="", xalign=0)
        self.inline_page_title.add_css_class("inline-page-title")
        self.inline_page_title.set_hexpand(True)
        self.inline_page_header.append(self.inline_page_title)

        content.append(self.inline_page_header)
        content.append(self.stack)
        body.append(content)

        self.home_page = self._build_home_page()

        # Pages
        self.fan_page        = FanPage(service=None, on_profile_change=self._on_profile_mode_changed)
        self.lighting_page   = LightingPage(service=None)
        self.power_page      = PowerPage(service=None)
        self.keyboard_page   = KeyboardPage(service=None)
        self.app_profiles_page = AppProfilesPage(service=None)
        self.mux_page        = MUXPage(service=None)
        self.settings_page   = SettingsPage(
            on_theme_change=self._on_theme_change,
            on_lang_change=self._on_lang_change,
            on_temp_unit_change=self._on_temp_unit_change,
            service=None,
        )

        self.stack.add_named(self.home_page, "home")
        self.stack.add_named(self.fan_page,        "fan")
        self.stack.add_named(self.lighting_page,   "lighting")
        self.stack.add_named(self.power_page,      "power")
        self.stack.add_named(self.keyboard_page,   "keyboard")
        self.stack.add_named(self.app_profiles_page, "app_profiles")
        self.stack.add_named(self.mux_page,        "mux")
        self.stack.add_named(self.settings_page,   "settings")

        self.fan_page.set_dark(self.app_theme == "dark")
        self.fan_page.set_temp_unit(self.temp_unit)

        self._rebuilding = True
        self.settings_page.set_theme_index(
            0 if self.app_theme == "dark" else 1 if self.app_theme == "light" else 2)
        self.settings_page.set_lang_index(0 if get_lang() == "tr" else 1)
        self.settings_page.set_temp_unit_index(0 if self.temp_unit == "C" else 1)
        self._rebuilding = False

        self._navigate("fan")
        self._set_performance_mode("balanced")
        self._update_fullscreen_button_icon()
        self.connect("notify::fullscreened", self._on_fullscreen_state_changed)
        self._install_responsive_scaling()

    def _build_home_page(self):
        sc = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._launcher_cards = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(10)
        root.set_margin_start(14)
        root.set_margin_end(14)
        root.set_margin_bottom(12)
        sc.set_child(root)
        self._home_root_box = root
        self._home_scroll = sc

        model_strip = Gtk.Box(spacing=12)
        model_strip.add_css_class("status-strip")
        model_strip.add_css_class("home-model-strip")
        model_name = get_device_model_name()

        model_icon = self._build_model_brand_image(model_name, size=84)
        model_strip.append(model_icon)
        self._home_model_icon = model_icon

        details_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        details_col.set_hexpand(True)
        details_col.add_css_class("home-model-details")

        top_row = Gtk.Box(spacing=10)
        top_row.add_css_class("home-model-top")
        model_label = Gtk.Label(label=model_name, xalign=0)
        model_label.add_css_class("heading")
        model_label.set_hexpand(True)
        top_row.append(model_label)
        details_col.append(top_row)

        hw = self._get_home_hardware_info()
        labels = {
            "cpu": "CPU",
            "disk": "Disk" if get_lang() == "en" else "Disk",
            "gpu": "GPU",
            "ram": "RAM",
        }
        icons = {
            "cpu": ["processor-symbolic", "cpu-symbolic"],
            "disk": ["drive-harddisk-symbolic"],
            "gpu": ["display-symbolic", "video-display-symbolic", "computer-symbolic"],
            "ram": ["media-memory-symbolic", "media-flash-symbolic"],
        }

        spec_row = Gtk.Box(spacing=8, homogeneous=True)
        spec_row.add_css_class("home-spec-row")
        self._home_spec_row = spec_row
        for key in ("cpu", "disk", "gpu", "ram"):
            item = Gtk.Box(spacing=6)
            item.add_css_class("home-spec-item")

            gicon = Gio.ThemedIcon.new_from_names(icons[key])
            ico = Gtk.Image.new_from_gicon(gicon)
            ico.set_pixel_size(14)
            item.append(ico)

            txt_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            ttl = Gtk.Label(label=labels[key], xalign=0)
            ttl.add_css_class("home-spec-title")
            txt_col.append(ttl)
            val = Gtk.Label(label=hw.get(key, "N/A"), xalign=0)
            val.add_css_class("home-spec-value")
            txt_col.append(val)
            item.append(txt_col)

            spec_row.append(item)

        details_col.append(spec_row)
        model_strip.append(details_col)
        root.append(model_strip)

        subtitle = Gtk.Label(label=self._home_subtitle(), xalign=0)
        subtitle.add_css_class("launcher-page-subtitle")
        root.append(subtitle)

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(3)
        flow.set_min_children_per_line(1)
        flow.set_row_spacing(12)
        flow.set_column_spacing(12)
        flow.set_homogeneous(True)
        flow.set_valign(Gtk.Align.START)
        flow.set_hexpand(True)
        root.append(flow)
        self._home_flow = flow

        labels_tr = {
            "dashboard": "Sistem özeti ve canlı sensörler",
            "fan": "Fan, güç ve termal profiller",
            "lighting": "Aydınlatma efektleri ve parlaklık",
            "power": "Gelişmiş voltaj ve termal limit ayarları",
            "keyboard": "Özel tuşlar ve kısayollar",
            "app_profiles": "Oyun ve uygulamalara özel güç modları",
            "mux": "GPU geçiş modu ve sürücü",
            "settings": "Tema, dil ve uygulama ayarları",
        }
        labels_en = {
            "dashboard": "System overview and live sensors",
            "fan": "Fan, power and thermal profiles",
            "lighting": "Lighting effects and brightness",
            "power": "Advanced undervolt and thermal limit settings",
            "keyboard": "Special keys and shortcuts",
            "app_profiles": "Per-app power and fan profiles",
            "mux": "GPU switching mode and driver",
            "settings": "Theme, language and app settings",
        }
        desc = labels_tr if str(get_lang() or "").lower().startswith("tr") else labels_en

        cards = [
            ("dashboard", self.page_titles["dashboard"], "dashboard"),
            ("fan", self.page_titles["fan"], "fan"),
            ("lighting", self.page_titles["lighting"], "lighting"),
            ("power", self.page_titles["power"], "power"),
            ("keyboard", self.page_titles["keyboard"], "keyboard"),
            ("app_profiles", self.page_titles["app_profiles"], "app_profiles"),
            ("mux", "MUX", "mux"),
            ("settings", self.page_titles["settings"], "settings"),
        ]

        for page_id, title_text, icon_name in cards:
            flow.insert(self._make_launcher_card(page_id, title_text, desc.get(page_id, ""), icon_name), -1)

        self._apply_home_scale(self._ui_scale_bucket)

        return sc

    def _pick_ui_scale_bucket(self, width, height):
        if width < 1120 or height < 720:
            return "compact"
        if width > 1600 and height > 920:
            return "spacious"
        return "normal"

    def _install_responsive_scaling(self):
        if hasattr(self, "_root_shell") and self._root_shell is not None and not self._ui_scale_tick_id:
            self._ui_scale_tick_id = self._root_shell.add_tick_callback(self._on_scale_tick)
        GLib.idle_add(self._apply_ui_scale_from_current_size)

    def _on_scale_tick(self, _widget, _frame_clock):
        width, height = self._get_current_ui_size()
        if width != self._ui_last_width or height != self._ui_last_height:
            self._ui_last_width = width
            self._ui_last_height = height
            self._apply_ui_scale(width, height)
        return GLib.SOURCE_CONTINUE

    def _get_current_ui_size(self):
        width = 0
        height = 0
        if hasattr(self, "_root_shell") and self._root_shell is not None:
            try:
                width = max(width, int(self._root_shell.get_width() or 0))
                height = max(height, int(self._root_shell.get_height() or 0))
            except Exception:
                pass

        try:
            width = max(width, int(self.get_width() or 0))
            height = max(height, int(self.get_height() or 0))
        except Exception:
            pass
        return width, height

    def _apply_ui_scale_from_current_size(self):
        width, height = self._get_current_ui_size()
        self._ui_last_width = width
        self._ui_last_height = height
        self._apply_ui_scale(width, height)
        return False

    def _apply_ui_scale(self, width, height):
        bucket = self._pick_ui_scale_bucket(int(width or 0), int(height or 0))
        if bucket == self._ui_scale_bucket and getattr(self, "_ui_scale_applied_once", False):
            return

        self._ui_scale_bucket = bucket
        self._ui_scale_applied_once = True

        classes = ("app-scale-compact", "app-scale-normal", "app-scale-spacious")
        target_cls = f"app-scale-{bucket}"
        targets = [self]
        if hasattr(self, "_root_shell") and self._root_shell:
            targets.append(self._root_shell)

        for target in targets:
            for cls in classes:
                target.remove_css_class(cls)
            target.add_css_class(target_cls)

        self._apply_home_scale(bucket)
        for page_attr in ("fan_page", "lighting_page", "power_page", "keyboard_page", "app_profiles_page", "mux_page", "settings_page"):
            page = getattr(self, page_attr, None)
            if page and hasattr(page, "set_ui_scale"):
                try:
                    page.set_ui_scale(bucket, int(width or 0), int(height or 0))
                except Exception:
                    pass

    def _apply_home_scale(self, bucket):
        root = getattr(self, "_home_root_box", None)
        flow = getattr(self, "_home_flow", None)
        icon = getattr(self, "_home_model_icon", None)
        spec_row = getattr(self, "_home_spec_row", None)
        if not root or not flow:
            return

        if bucket == "compact":
            root.set_spacing(8)
            root.set_margin_top(8)
            root.set_margin_start(10)
            root.set_margin_end(10)
            root.set_margin_bottom(10)
            flow.set_row_spacing(10)
            flow.set_column_spacing(10)
            if icon is not None:
                icon.set_pixel_size(66)
            if spec_row is not None:
                spec_row.set_spacing(6)
        elif bucket == "spacious":
            root.set_spacing(12)
            root.set_margin_top(14)
            root.set_margin_start(18)
            root.set_margin_end(18)
            root.set_margin_bottom(16)
            flow.set_row_spacing(14)
            flow.set_column_spacing(14)
            if icon is not None:
                icon.set_pixel_size(92)
            if spec_row is not None:
                spec_row.set_spacing(10)
        else:
            root.set_spacing(10)
            root.set_margin_top(10)
            root.set_margin_start(14)
            root.set_margin_end(14)
            root.set_margin_bottom(12)
            flow.set_row_spacing(12)
            flow.set_column_spacing(12)
            if icon is not None:
                icon.set_pixel_size(84)
            if spec_row is not None:
                spec_row.set_spacing(8)

    def _make_launcher_card(self, page_id, title_text, subtitle_text, icon_key):
        btn = Gtk.Button()
        btn.add_css_class("launcher-card")
        btn.connect("clicked", lambda *_: self._navigate(page_id))

        overlay = Gtk.Overlay()
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        icon_wrap = Gtk.Box(halign=Gtk.Align.FILL, valign=Gtk.Align.START, vexpand=False)
        icon_wrap.add_css_class("launcher-icon-wrap")
        icon = self._make_fixed_menu_icon(icon_key, 42)
        icon.set_halign(Gtk.Align.START)
        icon.set_valign(Gtk.Align.START)
        icon.set_margin_start(6)
        icon.set_margin_top(2)
        icon_wrap.append(icon)
        column.append(icon_wrap)

        column.append(Gtk.Box(vexpand=True))

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        text_box.set_margin_top(8)
        text_box.set_margin_bottom(8)
        text_box.set_margin_start(12)
        text_box.set_margin_end(12)

        title = Gtk.Label(label=title_text, xalign=0)
        title.add_css_class("launcher-card-title")
        text_box.append(title)

        subtitle = Gtk.Label(label=subtitle_text, xalign=0)
        subtitle.add_css_class("launcher-card-sub")
        subtitle.set_wrap(True)
        subtitle.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        text_box.append(subtitle)

        column.append(text_box)

        metric_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        metric_box.set_halign(Gtk.Align.END)
        metric_box.set_valign(Gtk.Align.END)
        metric_box.set_margin_end(8)
        metric_box.set_margin_bottom(8)

        metric_main = Gtk.Label(label="--", xalign=1)
        metric_main.add_css_class("launcher-metric-main")
        metric_box.append(metric_main)

        metric_sub = Gtk.Label(label="", xalign=1)
        metric_sub.add_css_class("launcher-metric-sub")
        metric_box.append(metric_sub)

        mini_bar = None
        cpu_bar = None
        gpu_bar = None
        if page_id == "dashboard":
            cpu_bar = Gtk.LevelBar()
            cpu_bar.set_min_value(0.0)
            cpu_bar.set_max_value(100.0)
            cpu_bar.set_value(0.0)
            cpu_bar.set_size_request(88, 4)
            cpu_bar.add_css_class("launcher-mini-bar")
            cpu_bar.add_css_class("launcher-util-bar")
            cpu_bar.add_css_class("launcher-cpu-bar")
            metric_box.append(cpu_bar)

            gpu_bar = Gtk.LevelBar()
            gpu_bar.set_min_value(0.0)
            gpu_bar.set_max_value(100.0)
            gpu_bar.set_value(0.0)
            gpu_bar.set_size_request(88, 4)
            gpu_bar.add_css_class("launcher-mini-bar")
            gpu_bar.add_css_class("launcher-util-bar")
            gpu_bar.add_css_class("launcher-gpu-bar")
            metric_box.append(gpu_bar)

        if page_id == "lighting":
            mini_bar = Gtk.LevelBar()
            mini_bar.set_min_value(0.0)
            mini_bar.set_max_value(100.0)
            mini_bar.set_value(0.0)
            mini_bar.set_size_request(76, 5)
            mini_bar.add_css_class("launcher-mini-bar")
            mini_bar.add_css_class("launcher-util-bar")
            metric_box.append(mini_bar)

        mode_badge = None
        if page_id == "mux":
            mode_badge = Gtk.Label(label="Hybrid")
            mode_badge.add_css_class("launcher-mode-badge")
            mode_badge.set_halign(Gtk.Align.END)
            mode_badge.set_valign(Gtk.Align.START)
            mode_badge.set_margin_top(8)
            mode_badge.set_margin_end(8)

        status_badge = Gtk.Label(label="!")
        status_badge.add_css_class("launcher-status-badge")
        status_badge.set_halign(Gtk.Align.START)
        status_badge.set_valign(Gtk.Align.START)
        status_badge.set_margin_top(8)
        status_badge.set_margin_start(8)
        status_badge.set_visible(False)

        overlay.set_child(column)
        overlay.add_overlay(metric_box)
        overlay.add_overlay(status_badge)
        if mode_badge is not None:
            overlay.add_overlay(mode_badge)

        self._launcher_cards[page_id] = {
            "button": btn,
            "icon": icon,
            "metric_main": metric_main,
            "metric_sub": metric_sub,
            "mini_bar": mini_bar,
            "cpu_bar": cpu_bar,
            "gpu_bar": gpu_bar,
            "mode_badge": mode_badge,
            "status_badge": status_badge,
        }

        btn.set_child(overlay)
        return btn

    def _make_fixed_menu_icon(self, icon_key, size):
        dark = self._is_effective_dark()
        rgb = (0.92, 0.94, 0.97) if dark else (0.16, 0.18, 0.22)
        return FixedMenuIcon(icon_key, size=size, rgb=rgb)

    def _build_menu_back_content(self):
        row = Gtk.Box()
        row.set_halign(Gtk.Align.CENTER)
        row.set_valign(Gtk.Align.CENTER)
        dark = self._is_effective_dark()
        rgb = (1.0, 1.0, 1.0) if dark else (0.16, 0.18, 0.22)
        row.append(FixedMenuIcon("back", size=18, rgb=rgb, line_width=2.8))
        return row

    def _is_effective_dark(self):
        if self.app_theme == "dark":
            return True
        if self.app_theme == "light":
            return False
        if HAS_ADW:
            try:
                return bool(Adw.StyleManager.get_default().get_dark())
            except Exception:
                return True
        settings = Gtk.Settings.get_default()
        if settings is not None:
            try:
                return bool(settings.get_property("gtk-application-prefer-dark-theme"))
            except Exception:
                pass
        return True

    def _refresh_launcher_icon_colors(self):
        dark = self._is_effective_dark()
        rgb = (0.92, 0.94, 0.97) if dark else (0.16, 0.18, 0.22)
        for refs in self._launcher_cards.values():
            icon = refs.get("icon")
            if icon is None:
                continue
            try:
                icon.rgb = rgb
                icon.queue_draw()
            except Exception:
                pass

    def _on_window_minimize(self, *_):
        try:
            self.minimize()
        except Exception:
            pass

    def _on_window_close(self, *_):
        self.close()

    def _on_window_toggle_fullscreen(self, *_):
        try:
            is_fullscreened = bool(self.get_property("fullscreened"))
            if is_fullscreened:
                self.unfullscreen()
            else:
                self.fullscreen()
        except Exception:
            pass

    def _on_fullscreen_state_changed(self, *_):
        self._update_fullscreen_button_icon()

    def _update_fullscreen_button_icon(self):
        if not hasattr(self, "fullscreen_btn"):
            return
        try:
            is_fullscreened = bool(self.get_property("fullscreened"))
        except Exception:
            is_fullscreened = False
        icon_name = "view-restore-symbolic" if is_fullscreened else "view-fullscreen-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        self.fullscreen_btn.set_child(icon)

    def _make_nav_button(self, page_id, label, icon_names):
        btn = Gtk.Button()
        btn.add_css_class("nav-item")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)

        # Vertical accent indicator bar
        indicator = Gtk.DrawingArea()
        indicator.add_css_class("nav-indicator")
        indicator.add_css_class("nav-indicator-hidden")
        indicator.set_content_width(3)
        indicator.set_content_height(18)
        indicator.set_valign(Gtk.Align.CENTER)
        box.append(indicator)
        self.nav_indicators[page_id] = indicator

        if isinstance(icon_names, (list, tuple)):
            gicon = Gio.ThemedIcon.new_from_names(list(icon_names))
            icon = Gtk.Image.new_from_gicon(gicon)
        else:
            icon = Gtk.Image.new_from_icon_name(icon_names)
        icon.set_pixel_size(24)
        icon.add_css_class("nav-icon")
        icon.set_valign(Gtk.Align.CENTER)
        box.append(icon)

        lbl = Gtk.Label(label=label)
        lbl.add_css_class("nav-label")
        lbl.set_visible(False) # HIDE BY DEFAULT ON STARTUP
        lbl.set_valign(Gtk.Align.CENTER)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_wrap(False)
        self.nav_labels[page_id] = lbl
        box.append(lbl)

        btn.set_child(box)
        btn.connect("clicked", lambda w, pid=page_id: self._navigate(pid))
        self.nav_buttons[page_id] = btn
        return btn

    def _make_theme_toggle_button(self):
        btn = Gtk.Button()
        btn.add_css_class("nav-item")
        btn.add_css_class("theme-toggle-btn")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)

        # Align with other buttons via spacer
        indicator = Gtk.Box()
        indicator.set_size_request(3, 18)
        indicator.set_valign(Gtk.Align.CENTER)
        box.append(indicator)

        self.theme_toggle_icon = Gtk.Image()
        self.theme_toggle_icon.set_pixel_size(24)
        self.theme_toggle_icon.add_css_class("nav-icon")
        self.theme_toggle_icon.set_valign(Gtk.Align.CENTER)
        box.append(self.theme_toggle_icon)

        lbl_text = T("light") if self.app_theme == "dark" else T("dark")
        self.theme_toggle_lbl = Gtk.Label(label=lbl_text)
        self.theme_toggle_lbl.add_css_class("nav-label")
        self.theme_toggle_lbl.set_visible(False)
        self.theme_toggle_lbl.set_valign(Gtk.Align.CENTER)
        self.theme_toggle_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.theme_toggle_lbl.set_wrap(False)
        self.nav_labels["theme_toggle"] = self.theme_toggle_lbl
        box.append(self.theme_toggle_lbl)

        btn.set_child(box)
        btn.connect("clicked", self._toggle_app_theme)
        self.nav_buttons["theme_toggle"] = btn

        self._update_theme_toggle_icon_state()
        return btn

    def _toggle_app_theme(self, _btn):
        next_theme = "light" if self.app_theme == "dark" else "dark"
        self._on_theme_change(next_theme)
        if hasattr(self, "settings_page") and self.settings_page is not None:
            self.settings_page.set_theme_index(0 if next_theme == "dark" else 1)

    def _is_dark_mode(self):
        if self.app_theme == "dark":
            return True
        elif self.app_theme == "light":
            return False
        
        # System theme detection
        if HAS_ADW:
            try:
                sm = Adw.StyleManager.get_default()
                return sm.get_dark()
            except Exception:
                pass
        settings = Gtk.Settings.get_default()
        if settings is not None:
            try:
                return bool(settings.get_property("gtk-application-prefer-dark-theme"))
            except Exception:
                pass
        return False

    def _update_theme_toggle_icon_state(self):
        if not hasattr(self, "theme_toggle_icon") or self.theme_toggle_icon is None:
            return
        is_dark = self._is_dark_mode()
        icon_name = "weather-clear-symbolic" if is_dark else "weather-clear-night-symbolic"
        self.theme_toggle_icon.set_from_icon_name(icon_name)
        lbl_text = T("light") if is_dark else T("dark")
        if hasattr(self, "theme_toggle_lbl") and self.theme_toggle_lbl is not None:
            self.theme_toggle_lbl.set_label(lbl_text)

    def _on_system_theme_notify(self):
        self._update_theme_toggle_icon_state()
        self._apply_css()
        self._refresh_launcher_icon_colors()
        self._update_logo()
        if hasattr(self, "menu_back_btn"):
            self.menu_back_btn.set_child(self._build_menu_back_content())

    def _find_first_scrolled_window(self, widget):
        if widget is None:
            return None
        if isinstance(widget, Gtk.ScrolledWindow):
            return widget

        child = widget.get_first_child()
        while child is not None:
            found = self._find_first_scrolled_window(child)
            if found is not None:
                return found
            child = child.get_next_sibling()
        return None

    def _set_back_button_floating(self, floating):
        if not hasattr(self, "menu_back_btn"):
            return
        floating = bool(floating)
        if self._back_button_floating == floating:
            return

        btn = self.menu_back_btn
        parent = btn.get_parent()
        if parent is not None:
            parent.remove(btn)

        if floating and self._content_overlay is not None:
            btn.add_css_class("floating-back-btn-active")
            btn.set_halign(Gtk.Align.START)
            btn.set_valign(Gtk.Align.START)
            self._content_overlay.add_overlay(btn)
        else:
            btn.remove_css_class("floating-back-btn-active")
            btn.set_halign(Gtk.Align.FILL)
            btn.set_valign(Gtk.Align.FILL)
            if hasattr(self, "inline_page_header"):
                self.inline_page_header.prepend(btn)

        self._back_button_floating = floating

    def _clear_scroll_tracking(self):
        if self._scroll_adjustment is not None and self._scroll_adjustment_handler:
            try:
                self._scroll_adjustment.disconnect(self._scroll_adjustment_handler)
            except Exception:
                pass
        self._scroll_adjustment = None
        self._scroll_adjustment_handler = 0

    def _on_scroll_value_changed(self, adjustment):
        try:
            value = float(adjustment.get_value())
        except Exception:
            value = 0.0
        should_float = value > 36 and hasattr(self, "menu_back_btn") and self.menu_back_btn.get_sensitive()
        self._set_back_button_floating(should_float)

    def _bind_back_button_scroll_behavior(self, page_id):
        self._clear_scroll_tracking()
        self._set_back_button_floating(False)

    def _navigate(self, page_id):
        self.stack.set_visible_child_name(page_id)
        if hasattr(self, "inline_page_header"):
            self.inline_page_header.set_visible(page_id != "home")
        if hasattr(self, "inline_page_title"):
            if page_id == "home":
                self.inline_page_title.set_label("")
            else:
                self.inline_page_title.set_label(self.page_titles.get(page_id, page_id.title()))
        if hasattr(self, "menu_back_btn"):
            is_home = page_id == "home"
            self.menu_back_btn.set_sensitive(not is_home)
            self.menu_back_btn.set_visible(not is_home)
            self.menu_back_btn.set_opacity(1.0)
            self._set_back_button_floating(False)
        self._bind_back_button_scroll_behavior(page_id)
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.add_css_class("active")
            elif "active" in btn.get_css_classes():
                btn.remove_css_class("active")
        # Update indicator bars
        for pid, ind in getattr(self, "nav_indicators", {}).items():
            if pid == page_id:
                ind.remove_css_class("nav-indicator-hidden")
            elif "nav-indicator-hidden" not in ind.get_css_classes():
                ind.add_css_class("nav-indicator-hidden")
        page = self.stack.get_child_by_name(page_id)
        if hasattr(page, "refresh"):
            page.refresh()
        if page_id == "home":
            self._refresh_launcher_metrics()

    def _update_logo(self):
        """Load the app logo from disk into self.logo_icon."""
        logo_path = os.path.join(IMAGES_DIR, "omenctl.png")
        if hasattr(self, 'logo_icon') and self.logo_icon is not None:
            brand = get_model_branding().lower()
            img_name = "victus.png" if "victus" in brand else "omen.png"
            img_path = os.path.join(IMAGES_DIR, img_name)
            if os.path.exists(img_path):
                texture = Gdk.Texture.new_from_filename(img_path)
                self.logo_icon.set_from_paintable(texture)
            else:
                self.logo_icon.set_from_icon_name("computer-symbolic")
        if hasattr(self, 'brand_icon') and self.brand_icon is not None:
            if os.path.exists(logo_path):
                texture = Gdk.Texture.new_from_filename(logo_path)
                self.brand_icon.set_from_paintable(texture)
            else:
                self.brand_icon.set_from_icon_name("omenctl")

    # ── Daemon connection ─────────────────────────────────────────────────────

    def _connect_daemon(self):
        """Connect to all D-Bus daemon services.

        On first invocation (typically at startup or right after install) some
        services may not yet be ready — each systemd unit has a 2-second
        ExecStartPre sleep.  We therefore keep track of which services are still
        missing and schedule a retry every 5 seconds for up to 60 seconds (12
        attempts) so the GUI becomes fully functional without requiring a reboot.
        """
        if not hasattr(self, "_daemon_retry_count"):
            self._daemon_retry_count = 0
        if not hasattr(self, "_daemon_retry_timer"):
            self._daemon_retry_timer = None

        try:
            from pydbus import SystemBus
            bus = SystemBus()
        except Exception as e:
            print(f"⚠ Cannot connect to D-Bus: {e}")
            self._schedule_daemon_retry()
            return

        if not hasattr(self, "services") or self.services is None:
            self.services = {}

        # Only (re-)connect services that are not yet available
        missing_after = []
        for name in ("fan", "rgb", "power", "mux", "platform"):
            if self.services.get(name) is not None:
                continue  # already connected
            try:
                self.services[name] = bus.get(f"com.yyl.hpmanager.{name}")
                print(f"✓ {name} service connected")
            except Exception as e:
                print(f"⚠ {name} service unavailable: {e}")
                self.services[name] = None
                missing_after.append(name)

        # Push available services to pages regardless of whether all are up
        self._apply_services_to_pages()

        if missing_after:
            self._schedule_daemon_retry()
        else:
            # All services up — cancel any pending retry timer
            self._cancel_daemon_retry()
            print("All daemon services connected.")
            self._refresh_launcher_metrics()

    def _apply_services_to_pages(self):
        """Push currently-available services to their respective pages."""
        svcs = getattr(self, "services", {}) or {}
        self.ready = any(v is not None for v in svcs.values())

        if hasattr(self, "fan_page") and self.fan_page is not None:
            self.fan_page.set_service(svcs.get("fan"))
            self.fan_page.set_platform_service(svcs.get("platform"))
            self.fan_page.set_power_service(svcs.get("power"))
            self.fan_page.set_rgb_service(svcs.get("rgb"))
        if hasattr(self, "lighting_page") and self.lighting_page is not None:
            self.lighting_page.set_service(svcs.get("rgb"))
        if hasattr(self, "power_page") and self.power_page is not None:
            self.power_page.set_service(svcs.get("power"))
        if hasattr(self, "keyboard_page") and self.keyboard_page is not None:
            self.keyboard_page.set_service(svcs.get("platform"))
        if hasattr(self, "app_profiles_page") and self.app_profiles_page is not None:
            self.app_profiles_page.set_power_service(svcs.get("power"))
        if hasattr(self, "mux_page") and self.mux_page is not None:
            self.mux_page.set_service(svcs.get("mux"))
        if hasattr(self, "settings_page") and self.settings_page is not None:
            self.settings_page.set_service(svcs.get("mux"))
        self._refresh_launcher_metrics()

    def _schedule_daemon_retry(self):
        """Schedule a single retry attempt in 5 seconds (max 12 attempts)."""
        MAX_RETRIES = 12
        RETRY_INTERVAL_MS = 5000

        self._daemon_retry_count = getattr(self, "_daemon_retry_count", 0) + 1
        if self._daemon_retry_count > MAX_RETRIES:
            print("⚠ Daemon retry limit reached. Some services may be unavailable.")
            print("  If this is a fresh install, a reboot may still be required for kernel modules.")
            return

        print(f"  Retry {self._daemon_retry_count}/{MAX_RETRIES} in {RETRY_INTERVAL_MS // 1000}s…")
        self._daemon_retry_timer = GLib.timeout_add(RETRY_INTERVAL_MS, self._daemon_retry_tick)

    def _cancel_daemon_retry(self):
        """Cancel any pending retry timer."""
        tid = getattr(self, "_daemon_retry_timer", None)
        if tid is not None:
            try:
                GLib.source_remove(tid)
            except Exception:
                pass
            self._daemon_retry_timer = None

    def _daemon_retry_tick(self):
        """Called by the GLib timer; trigger a retry and return False to cancel timer."""
        self._daemon_retry_timer = None  # timer fired, clear handle
        self._connect_daemon()
        return GLib.SOURCE_REMOVE

    def _set_performance_mode(self, profile):
        mode_map = {
            "power-saver": "eco",
            "balanced": "balanced",
            "performance": "performance",
            "eco": "eco",
        }
        mode = mode_map.get(str(profile), "balanced")
        prev_mode = self.performance_mode
        self.performance_mode = mode

        classes = ("app-perf-eco", "app-perf-balanced", "app-perf-performance")
        target_class = f"app-perf-{mode}"
        targets = [self]
        if hasattr(self, "_root_shell") and self._root_shell:
            targets.append(self._root_shell)

        for target in targets:
            for cls in classes:
                target.remove_css_class(cls)
            target.add_css_class(target_class)

        # In dark mode, accent color follows active performance mode.
        if prev_mode != mode and self._is_effective_dark():
            self._apply_css()

    def _on_profile_mode_changed(self, profile):
        self._set_performance_mode(profile)

    # ── Settings callbacks ────────────────────────────────────────────────────

    def _on_theme_change(self, theme):
        if self._rebuilding:
            return
        self.app_theme = theme
        self._save_config()
        self._apply_theme_preference()
        self._apply_css()
        self._refresh_launcher_icon_colors()
        if hasattr(self, "menu_back_btn"):
            self.menu_back_btn.set_child(self._build_menu_back_content())
        if hasattr(self, 'fan_page'):
            self.fan_page.set_dark(theme == "dark")
        self._update_logo()
        self._refresh_launcher_metrics()
        self._update_theme_toggle_icon_state()

    def _on_lang_change(self, lang):
        if self._rebuilding:
            return
        if get_lang() == lang:
            return
        set_lang(lang)
        self._save_config()
        self.page_titles = {
            "dashboard": T("dashboard"),
            "fan": T("fan"),
            "lighting": T("lighting"),
            "power": T("power_tuning"),
            "keyboard": T("keyboard"),
            "app_profiles": T("app_profiles"),
            "mux": "MUX",
            "settings": T("settings"),
        }
        for pid, lbl in self.nav_labels.items():
            if pid in self.page_titles:
                lbl.set_label(self.page_titles[pid])
        if hasattr(self, "inline_page_title"):
            current = self.stack.get_visible_child_name() if hasattr(self, "stack") else "home"
            if current == "home":
                self.inline_page_title.set_label("")
            else:
                self.inline_page_title.set_label(self.page_titles.get(current, current.title()))
        if hasattr(self, "menu_back_btn"):
            self.menu_back_btn.set_child(self._build_menu_back_content())
            self.menu_back_btn.set_tooltip_text("Ana Menü" if get_lang() == "tr" else "Main Menu")
        # Defer page rebuild — cannot destroy widgets inside a signal handler
        GLib.idle_add(self._rebuild_pages)

    def _start_launcher_metrics(self):
        if self._launcher_timer_id is not None:
            return
        self._refresh_launcher_metrics()
        self._launcher_timer_id = GLib.timeout_add(_LAUNCHER_REFRESH_MS, self._tick_launcher_metrics)

    def _tick_launcher_metrics(self):
        if hasattr(self, "stack"):
            try:
                if self.stack.get_visible_child_name() != "home":
                    return GLib.SOURCE_CONTINUE
            except Exception:
                pass
        self._refresh_launcher_metrics()
        return GLib.SOURCE_CONTINUE

    def _refresh_launcher_metrics(self):
        if hasattr(self, "stack"):
            try:
                if self.stack.get_visible_child_name() != "home":
                    return
            except Exception:
                pass
        if self._launcher_busy:
            return
        self._launcher_busy = True
        threading.Thread(target=self._fetch_launcher_metrics, daemon=True).start()

    def _get_nvidia_runtime_status_path(self):
        if self._nvidia_runtime_status_scanned:
            return self._nvidia_runtime_status_path

        self._nvidia_runtime_status_scanned = True
        try:
            for dev in os.listdir("/sys/bus/pci/devices"):
                vendor_file = f"/sys/bus/pci/devices/{dev}/vendor"
                if not os.path.exists(vendor_file):
                    continue
                try:
                    with open(vendor_file) as f:
                        if f.read().strip() == "0x10de":
                            path = f"/sys/bus/pci/devices/{dev}/power/runtime_status"
                            self._nvidia_runtime_status_path = path if os.path.exists(path) else None
                            break
                except Exception:
                    continue
        except Exception:
            pass
        return self._nvidia_runtime_status_path

    def _is_nvidia_awake(self):
        path = self._get_nvidia_runtime_status_path()
        if path is None or not os.path.exists(path):
            return True
        try:
            with open(path) as f:
                return f.read().strip() != "suspended"
        except Exception:
            return True

    def _fetch_launcher_metrics(self):
        services = getattr(self, "services", None)
        data = {
            "ok": bool(services and any(services.values())),
            "sys": {},
            "fan": {},
            "pp": {},
            "light": {},
            "gpu": {},
            "cpu_pct": None,
            "gpu_pct": None,
        }
        try:
            if services:
                try:
                    if services.get("platform"):
                        raw = _dbus_call(services["platform"].GetSystemInfo)
                        if raw is not None:
                            data["sys"] = json.loads(raw)
                except Exception:
                    pass
                try:
                    if services.get("fan"):
                        raw = _dbus_call(services["fan"].GetFanInfo)
                        if raw is not None:
                            data["fan"] = json.loads(raw)
                except Exception:
                    pass
                try:
                    if services.get("power"):
                        raw = _dbus_call(services["power"].GetPowerProfile)
                        if raw is not None:
                            data["pp"] = json.loads(raw)
                except Exception:
                    pass
                try:
                    if services.get("rgb"):
                        raw = _dbus_call(services["rgb"].GetState)
                        if raw is not None:
                            data["light"] = json.loads(raw)
                except Exception:
                    pass
                try:
                    if services.get("mux"):
                        raw = _dbus_call(services["mux"].GetGpuInfo)
                        if raw is not None:
                            data["gpu"] = json.loads(raw)
                except Exception:
                    pass

            try:
                with open("/proc/stat") as f:
                    cpu = f.readline().strip().split()
                vals = [int(x) for x in cpu[1:9]]
                idle_all = vals[3] + vals[4]
                total = sum(vals)
                pct = self._launcher_cpu_smooth
                if self._launcher_cpu_prev is not None:
                    prev_total, prev_idle = self._launcher_cpu_prev
                    total_delta = total - prev_total
                    idle_delta = idle_all - prev_idle
                    if total_delta > 0:
                        pct = (1.0 - (idle_delta / total_delta)) * 100.0
                self._launcher_cpu_prev = (total, idle_all)
                if self._launcher_cpu_smooth <= 0.0:
                    self._launcher_cpu_smooth = max(0.0, min(100.0, pct))
                else:
                    self._launcher_cpu_smooth = (self._launcher_cpu_smooth * 0.62) + (max(0.0, min(100.0, pct)) * 0.38)
                data["cpu_pct"] = self._launcher_cpu_smooth
            except Exception:
                pass

            if self._nvidia_smi:
                if self._is_nvidia_awake():
                    try:
                        out = subprocess.check_output(
                            [self._nvidia_smi, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                            stderr=subprocess.DEVNULL,
                            timeout=1.5,
                        ).decode().strip()
                        data["gpu_pct"] = float(out)
                    except Exception:
                        pass
                else:
                    data["gpu_pct"] = 0.0
        finally:
            GLib.idle_add(self._apply_launcher_metrics, data)

    def _set_launcher_badge(self, page_id, visible):
        refs = self._launcher_cards.get(page_id)
        if not refs:
            return
        badge = refs.get("status_badge")
        if badge is not None:
            badge.set_visible(bool(visible))

    def _set_launcher_dimmed(self, page_id, dimmed):
        refs = self._launcher_cards.get(page_id)
        if not refs:
            return
        btn = refs.get("button")
        if btn is None:
            return
        if dimmed:
            btn.add_css_class("launcher-card-dimmed")
        else:
            btn.remove_css_class("launcher-card-dimmed")

    @staticmethod
    def _set_temp_tone(label, temp):
        for cls in ("launcher-temp-cool", "launcher-temp-warm", "launcher-temp-hot"):
            label.remove_css_class(cls)
        try:
            t = float(temp)
        except Exception:
            t = 0.0
        if t > 0 and t < 50:
            label.add_css_class("launcher-temp-cool")
        elif t >= 80:
            label.add_css_class("launcher-temp-hot")
        else:
            label.add_css_class("launcher-temp-warm")

    def _apply_launcher_metrics(self, data):
        self._launcher_busy = False
        if not self._launcher_cards:
            return False

        ok = bool(data.get("ok"))
        sysi = data.get("sys", {}) or {}
        fani = data.get("fan", {}) or {}
        ppi = data.get("pp", {}) or {}
        ligi = data.get("light", {}) or {}
        gpui = data.get("gpu", {}) or {}
        cpu_pct = data.get("cpu_pct")
        gpu_pct = data.get("gpu_pct")

        if not ok:
            for pid, refs in self._launcher_cards.items():
                if pid == "settings":
                    self._set_launcher_dimmed(pid, False)
                    badge = refs.get("status_badge")
                    if badge is not None:
                        badge.add_css_class("launcher-status-badge-critical")
                    self._set_launcher_badge(pid, True)
                    refs["metric_main"].set_label("Daemon Kapalı" if get_lang() == "tr" else "Daemon Offline")
                    refs["metric_sub"].set_label("Ayarlar" if get_lang() == "tr" else "Settings")
                else:
                    self._set_launcher_dimmed(pid, True)
                    self._set_launcher_badge(pid, False)
                    refs["metric_main"].set_label("Beklemede" if get_lang() == "tr" else "Standby")
                    refs["metric_sub"].set_label("-")
            return False

        for pid, refs in self._launcher_cards.items():
            self._set_launcher_dimmed(pid, False)
            badge = refs.get("status_badge")
            if badge is not None:
                badge.remove_css_class("launcher-status-badge-critical")

        dash = self._launcher_cards.get("dashboard")
        if dash:
            ct = int(sysi.get("cpu_temp", 0) or 0)
            gt = int(sysi.get("gpu_temp", 0) or 0)
            cp = int(cpu_pct) if cpu_pct is not None else 0
            gp = int(gpu_pct) if gpu_pct is not None else 0
            dash["metric_main"].set_label(f"CPU {ct}°C • {cp}%")
            dash["metric_sub"].set_label(f"GPU {gt}°C • {gp}%")
            self._set_temp_tone(dash["metric_main"], ct)
            self._set_temp_tone(dash["metric_sub"], gt)
            if dash.get("cpu_bar") is not None:
                dash["cpu_bar"].set_value(max(0, min(100, cp)))
            if dash.get("gpu_bar") is not None:
                dash["gpu_bar"].set_value(max(0, min(100, gp)))
            self._set_launcher_badge("dashboard", (not ok) or (ct <= 0 and gt <= 0))

        perf = self._launcher_cards.get("fan")
        if perf:
            active = str(ppi.get("active", "balanced"))
            self._set_performance_mode(active)
            profile_map = {
                "power-saver": "Sessiz" if get_lang() == "tr" else "Quiet",
                "balanced": "Dengeli" if get_lang() == "tr" else "Balanced",
                "performance": "Performans" if get_lang() == "tr" else "Performance",
            }
            profile = profile_map.get(active, active.capitalize())
            fans = fani.get("fans", {}) if isinstance(fani, dict) else {}
            rpms = []
            for fid in sorted(fans.keys()):
                try:
                    cur = int(fans[fid].get("current", 0))
                except Exception:
                    cur = 0
                if cur > 0:
                    rpms.append(str(cur))
            rpm_str = "/".join(rpms) if rpms else "0"
            perf["metric_main"].set_label(profile)
            perf["metric_sub"].set_label(f"{rpm_str} RPM")
            self._set_launcher_badge("fan", (not ok) or (not bool(fani)))

        light = self._launcher_cards.get("lighting")
        if light:
            mode = str(ligi.get("mode", "unknown"))
            mode_map = {
                "static": T("static_eff"),
                "breathing": T("breathing"),
                "wave": T("wave"),
                "cycle": T("cycle"),
            }
            bright = int(ligi.get("brightness", 0) or 0)
            light["metric_main"].set_label(mode_map.get(mode, mode.capitalize()))
            light["metric_sub"].set_label(f"{bright}%")
            if light.get("mini_bar") is not None:
                light["mini_bar"].set_value(max(0, min(100, bright)))
            lighting_module_ok = os.path.exists("/sys/module/hp_rgb_lighting")
            self._set_launcher_badge("lighting", (not ok) or (not lighting_module_ok) or (not bool(ligi)))

        mux = self._launcher_cards.get("mux")
        if mux:
            mode = str(gpui.get("mode", "unknown"))
            mode_map = {
                "integrated": "iGPU",
                "intel": "iGPU",
                "discrete": "dGPU",
                "nvidia": "dGPU",
                "dedicated": "dGPU",
                "hybrid": "Hybrid",
                "on-demand": "Hybrid",
            }
            mode_text = mode_map.get(mode, "N/A")
            mux["metric_main"].set_label(mode_text)
            mux["metric_sub"].set_label("")
            if mux.get("mode_badge") is not None:
                mux["mode_badge"].set_label(mode_text)
                if mode_text == "N/A" or mode.lower() == "unknown":
                    mux["mode_badge"].add_css_class("launcher-mode-badge-muted")
                else:
                    mux["mode_badge"].remove_css_class("launcher-mode-badge-muted")
            self._set_launcher_badge("mux", (not ok) or (mode_text == "N/A"))

        keyboard = self._launcher_cards.get("keyboard")
        if keyboard:
            keyboard["metric_main"].set_label("0 Aktif" if get_lang() == "tr" else "0 Active")
            keyboard["metric_sub"].set_label("Varsayılan" if get_lang() == "tr" else "Default")
            self._set_launcher_badge("keyboard", False)

        power = self._launcher_cards.get("power")
        if power:
            caps = ppi.get("capabilities", {}) if isinstance(ppi, dict) else {}
            supported = caps.get("supports_undervolt", True) or caps.get("supports_tcc_offset", True) or caps.get("supports_power_limits", True)
            is_tr = get_lang() == "tr"
            if not supported:
                power["metric_main"].set_label("Desteklenmiyor" if is_tr else "Unsupported")
                power["metric_sub"].set_label("")
                self._set_launcher_dimmed("power", True)
                if "power" in self.nav_buttons:
                    self.nav_buttons["power"].set_visible(False)
            else:
                uv = ppi.get("undervolt_mv", 0)
                tcc = ppi.get("tcc_offset", 0)
                power["metric_main"].set_label(f"{uv}mV" if uv < 0 else ("Varsayılan" if is_tr else "Default"))
                power["metric_sub"].set_label(f"TCC: {tcc}" if tcc > 0 else ("Limit Yok" if is_tr else "No Limit"))
                self._set_launcher_dimmed("power", False)
                if "power" in self.nav_buttons:
                    self.nav_buttons["power"].set_visible(True)
            self._set_launcher_badge("power", False)

        app_profiles = self._launcher_cards.get("app_profiles")
        if app_profiles:
            is_tr = get_lang() == "tr"
            enabled = ppi.get("app_profiles_enabled", False)
            app_profiles["metric_main"].set_label(("Aktif" if enabled else "Kapalı") if is_tr else ("Active" if enabled else "Inactive"))
            app_profiles["metric_sub"].set_label("Otomatik" if is_tr else "Auto")
            self._set_launcher_badge("app_profiles", False)

        settings = self._launcher_cards.get("settings")
        if settings:
            settings["metric_main"].set_label("OK" if ok else "Offline")
            settings["metric_sub"].set_label("Daemon")
            self._set_launcher_badge("settings", not ok)

        return False

    def _on_temp_unit_change(self, unit):
        if self._rebuilding:
            return
        self.temp_unit = unit
        self._save_config()
        if hasattr(self, 'fan_page'):
            self.fan_page.set_temp_unit(unit)

    # ── Page rebuild (language change) ────────────────────────────────────────

    def _rebuild_pages(self):
        """Destroy and recreate all pages so T() picks up the new language."""
        self._rebuilding = True
        try:
            current_page = self.stack.get_visible_child_name()
            if current_page == "dashboard":
                current_page = "fan"

            for attr in ('fan_page', 'lighting_page', 'power_page'):
                page = getattr(self, attr, None)
                if page and hasattr(page, 'cleanup'):
                    page.cleanup()

            for name in ("home", "fan", "lighting", "power", "keyboard", "app_profiles", "mux", "settings"):
                child = self.stack.get_child_by_name(name)
                if child:
                    self.stack.remove(child)

            self.home_page = self._build_home_page()
            self.fan_page        = FanPage(service=None, on_profile_change=self._on_profile_mode_changed)
            self.lighting_page   = LightingPage(service=None)
            self.power_page      = PowerPage(service=None)
            self.keyboard_page   = KeyboardPage(service=None)
            self.app_profiles_page = AppProfilesPage(service=None)
            self.mux_page        = MUXPage(service=None)
            self.settings_page   = SettingsPage(
                on_theme_change=self._on_theme_change,
                on_lang_change=self._on_lang_change,
                on_temp_unit_change=self._on_temp_unit_change,
                service=None,
            )

            self.stack.add_named(self.home_page, "home")
            self.stack.add_named(self.fan_page,        "fan")
            self.stack.add_named(self.lighting_page,   "lighting")
            self.stack.add_named(self.power_page,      "power")
            self.stack.add_named(self.keyboard_page,   "keyboard")
            self.stack.add_named(self.app_profiles_page, "app_profiles")
            self.stack.add_named(self.mux_page,        "mux")
            self.stack.add_named(self.settings_page,   "settings")

            # Reconnect daemon services to the freshly-created pages
            services = getattr(self, "services", None)
            if services:
                self.fan_page.set_service(services.get("fan"))
                self.fan_page.set_platform_service(services.get("platform"))
                self.fan_page.set_power_service(services.get("power"))
                self.lighting_page.set_service(services.get("rgb"))
                self.power_page.set_service(services.get("power"))
                self.keyboard_page.set_service(services.get("platform"))
                self.app_profiles_page.set_power_service(services.get("power"))
                self.mux_page.set_service(services.get("mux"))
                self.settings_page.set_service(services.get("mux"))

            self.fan_page.set_dark(self.app_theme == "dark")
            self.fan_page.set_temp_unit(self.temp_unit)
            if self.performance_mode == "eco":
                self._set_performance_mode("power-saver")
            elif self.performance_mode == "performance":
                self._set_performance_mode("performance")
            else:
                self._set_performance_mode("balanced")

            self.settings_page.set_theme_index(
                0 if self.app_theme == "dark" else 1 if self.app_theme == "light" else 2)
            self.settings_page.set_lang_index(0 if get_lang() == "tr" else 1)
            self.settings_page.set_temp_unit_index(0 if self.temp_unit == "C" else 1)

            self._navigate(current_page or "home")
            self._apply_ui_scale_from_current_size()
            self._refresh_launcher_metrics()
        finally:
            self._rebuilding = False
        return False  # Do not repeat GLib.idle_add

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def do_close_request(self):
        app = self.get_application()
        if not getattr(self, "force_quit", False):
            self.set_visible(False)
            return True

        # Cancel daemon retry timer if active
        self._cancel_daemon_retry()

        self._clear_scroll_tracking()
        if self._ui_scale_tick_id:
            try:
                if hasattr(self, "_root_shell") and self._root_shell is not None:
                    self._root_shell.remove_tick_callback(self._ui_scale_tick_id)
            except Exception:
                pass
            self._ui_scale_tick_id = 0
        if self._launcher_timer_id:
            try:
                GLib.source_remove(self._launcher_timer_id)
            except Exception:
                pass
            self._launcher_timer_id = None
        for attr in ('lighting_page', 'fan_page', 'power_page'):
            page = getattr(self, attr, None)
            if page and hasattr(page, 'cleanup'):
                try:
                    page.cleanup()
                except Exception as e:
                    print(f"Cleanup error for {attr}: {e}")
        # Terminate tray icon process when the application fully quits
        if app is not None and getattr(app, "tray_proc", None) is not None:
            try:
                app.tray_proc.terminate()
                app.tray_proc = None
            except Exception:
                pass
        try:
            app.quit()
        except Exception as e:
            print(f"Application quit error: {e}")
        return False


# ── Application ───────────────────────────────────────────────────────────────

class HPManagerApp(Adw.Application if HAS_ADW else Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('command-line', self._on_command_line)
        self.tray_proc = None
        self._tray_watchdog_id = None

    def _on_command_line(self, app, cmdline):
        args = cmdline.get_arguments()
        is_hidden = "--hidden" in args
        is_quit = "--quit" in args

        if is_quit:
            # Stop watchdog first so it won't restart the tray we're about to kill
            self._stop_tray_watchdog()
            if hasattr(self, 'win'):
                self.win.force_quit = True
                self.win.close()
            # Terminate tray process
            if self.tray_proc:
                try:
                    self.tray_proc.terminate()
                    self.tray_proc = None
                except Exception:
                    pass
            # Kill any stray omen-tray processes not tracked by us
            try:
                subprocess.run(["pkill", "-f", "omen-tray.py"], check=False)
            except Exception:
                pass
            self.quit()
            return 0

        if not hasattr(self, 'win'):
            print("Initializing window...", flush=True)
            self.hold()  # Keep app alive in background when hidden
            self.win = HPManagerWindow(application=app)
            self._start_tray()
            self._start_tray_watchdog()

        if not is_hidden:
            self.win.present()

        return 0

    # ── Tray lifecycle ────────────────────────────────────────────────────────

    def _start_tray(self):
        """Launch the tray icon process, killing any stale instance first."""
        if not shutil.which("omen-tray"):
            return
        # Kill any pre-existing stray tray process
        try:
            subprocess.run(["pkill", "-f", "omen-tray.py"], check=False)
        except Exception:
            pass
        # Clear lock file so the new instance can acquire it
        lock_file = os.path.expanduser("~/.cache/omen-tray.lock")
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception:
            pass
        try:
            self.tray_proc = subprocess.Popen(["omen-tray"])
            print("Tray icon started.", flush=True)
        except Exception as e:
            print(f"Failed to start tray process: {e}")

    def _start_tray_watchdog(self):
        """Start a 10-second periodic check to keep the tray icon alive."""
        if self._tray_watchdog_id is not None:
            return  # already running
        self._tray_watchdog_id = GLib.timeout_add(10_000, self._tray_watchdog_tick)

    def _stop_tray_watchdog(self):
        """Cancel the watchdog timer."""
        if self._tray_watchdog_id is not None:
            try:
                GLib.source_remove(self._tray_watchdog_id)
            except Exception:
                pass
            self._tray_watchdog_id = None

    def _tray_watchdog_tick(self):
        """Called every 10 s — restart tray if it has died."""
        # Stop if app is shutting down
        if getattr(getattr(self, "win", None), "force_quit", False):
            self._tray_watchdog_id = None
            return GLib.SOURCE_REMOVE

        proc = getattr(self, "tray_proc", None)
        if proc is None or proc.poll() is not None:
            print("Tray process died — restarting...", flush=True)
            self._start_tray()

        return GLib.SOURCE_CONTINUE


def main():
    print("Initializing Application...", flush=True)
    if not HAS_ADW:
        print("Warning: libadwaita (Adw) not found. Running with GTK fallback theme support.", flush=True)
    app = HPManagerApp(
        application_id="com.yyl.hpmanager",
        flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
    )
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
