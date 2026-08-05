"""Bundled, theme-aware OmenCtl SVG icons.

The icon set lives in a private hicolor search path so it works consistently
across desktop environments without replacing the user's global icon theme.
"""

import os

from gi.repository import Gdk, Gio, Gtk


_GUI_DIR = os.path.dirname(os.path.abspath(__file__))
_ICON_ROOT_CANDIDATES = (
    os.environ.get("OMENCTL_ICON_DIR", ""),
    os.path.abspath(os.path.join(_GUI_DIR, "..", "..", "data", "icons")),
    os.path.abspath(os.path.join(_GUI_DIR, "..", "icons")),
    "/usr/share/hp-manager/icons",
)

ICON_KEYS = frozenset({
    "appearance", "applications", "autostart", "back", "chevron", "clean",
    "computer", "cpu", "dashboard", "delete", "diagnostics", "disk", "edit",
    "fan", "game", "github", "gpu", "keyboard", "language", "legal", "lighting",
    "lock", "memory", "os", "power", "settings", "success", "temperature",
    "terminal", "theme", "update", "warning",
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


def icon_root():
    """Return the first available bundled icon theme root."""
    return next((path for path in _ICON_ROOT_CANDIDATES if path and os.path.isdir(path)), None)


def icon_name(key):
    """Return the themed icon name for a semantic key."""
    normalized = str(key or "").strip().lower().replace("-", "_")
    normalized = ICON_ALIASES.get(normalized, normalized).replace("_", "-")
    return f"omenctl-{normalized}-symbolic"


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


def make_icon(key, size=20, css_class=None, fallback="image-missing-symbolic"):
    """Create a consistently sized symbolic ``Gtk.Image``."""
    ensure_icon_theme()
    names = [icon_name(key)]
    if fallback:
        names.append(fallback)
    image = Gtk.Image.new_from_gicon(Gio.ThemedIcon.new_from_names(names))
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
