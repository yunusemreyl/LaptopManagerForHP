"""Bundled, theme-aware OmenCtl SVG icons.

The icon set lives in a private hicolor search path so it works consistently
across desktop environments without replacing the user's global icon theme.
"""

import os

from gi.repository import Gdk, GLib, Gtk


_GUI_DIR = os.path.dirname(os.path.abspath(__file__))
_ICON_ROOT_CANDIDATES = (
    os.environ.get("OMENCTL_ICON_DIR", ""),
    os.path.abspath(os.path.join(_GUI_DIR, "..", "..", "data", "icons")),
    os.path.abspath(os.path.join(_GUI_DIR, "..", "icons")),
    "/usr/share/hp-manager/icons",
)

ICON_KEYS = frozenset({
    "appearance", "applications", "autostart", "back", "battery", "chevron", "clean",
    "computer", "cpu", "dashboard", "delete", "diagnostics", "disk", "edit",
    "fan", "game", "github", "gpu", "keyboard", "language", "legal", "lighting",
    "lock", "memory", "os", "power", "settings", "success", "temperature",
    "terminal", "theme", "update", "warning", "moon", "performance", "sun",
})

ICON_ALIASES = {
    "app_profiles": "applications",
    "application": "applications",
    "architecture": "cpu",
    "driver": "settings",
    "kernel": "settings",
    "mux": "gpu",
    "system_info": "computer",
}

_registered_displays = set()
_svg_cache = {}


def icon_root():
    """Return the first available bundled icon theme root."""
    return next((path for path in _ICON_ROOT_CANDIDATES if path and os.path.isdir(path)), None)


def icon_name(key):
    """Return the themed icon name for a semantic key."""
    normalized = str(key or "").strip().lower().replace("-", "_")
    normalized = ICON_ALIASES.get(normalized, normalized).replace("_", "-")
    return f"omenctl-{normalized}-symbolic"


def icon_file(key):
    """Return the bundled SVG path for a semantic key, when available."""
    root = icon_root()
    if root is None:
        return None
    path = os.path.join(root, "hicolor", "scalable", "actions", f"{icon_name(key)}.svg")
    return path if os.path.isfile(path) else None


def ensure_icon_theme():
    """Register the private hicolor root for the active GTK display."""
    display = Gdk.Display.get_default()
    root = icon_root()
    if display is None or root is None:
        return False

    display_id = id(display)
    if display_id in _registered_displays:
        return True

    theme = Gtk.IconTheme.get_for_display(display)
    if root not in theme.get_search_path():
        theme.add_search_path(root)
    _registered_displays.add(display_id)
    return True


def _svg_paintable(path):
    """Load a GTK-native, recolorable SVG paintable."""
    if path in _svg_cache:
        return _svg_cache[path]
    if not hasattr(Gtk, "Svg"):
        return None
    with open(path, "rb") as source:
        paintable = Gtk.Svg.new_from_bytes(GLib.Bytes.new(source.read()))
    _svg_cache[path] = paintable
    return paintable


def set_icon(image, key, fallback="image-missing-symbolic"):
    """Set an existing ``Gtk.Image`` to a bundled, recolorable SVG."""
    path = icon_file(key)
    if path:
        paintable = _svg_paintable(path)
        if paintable is not None:
            image.set_from_paintable(paintable)
        else:
            image.set_from_file(path)
    else:
        image.set_from_icon_name(fallback)
    return image


def make_icon(key, size=20, css_class=None, fallback="image-missing-symbolic"):
    """Create a consistently sized, theme-aware SVG ``Gtk.Image``."""
    image = Gtk.Image()
    set_icon(image, key, fallback)
    image.set_pixel_size(int(size))
    image.set_size_request(int(size), int(size))
    image.set_valign(Gtk.Align.CENTER)
    if css_class:
        image.add_css_class(css_class)
    return image


def make_icon_label(key, text, size=18, spacing=8):
    """Create a horizontal icon and text pair for button content."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    box.set_valign(Gtk.Align.CENTER)
    box.append(make_icon(key, size))
    box.append(Gtk.Label(label=text))
    return box
