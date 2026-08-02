#!/usr/bin/env python3
"""Settings Page with GitHub update checker — i18n via T()."""
import os, platform, threading, json, subprocess, shutil, tempfile, glob
from utils.updater import OmenUpdater
from utils.diagnostics import generate_diagnostic_report, generate_github_issue_body
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk
from widgets.smooth_scroll import SmoothScrolledWindow
from widgets.mapping_wizard import MappingWizard

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def T(k):
    from i18n import T as _T
    try:
        from gi.repository import Adw
    except ImportError: pass
    return _T(k)


APP_VERSION = "1.6.6"
GITHUB_REPO = "yunusemreyl/OmenCtl"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

# Resolve images directory
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_SRC = os.path.abspath(os.path.join(_BASE_DIR, "..", "..", ".."))
_PROJ_INSTALLED = os.path.abspath(os.path.join(_BASE_DIR, "..", ".."))
if os.path.exists(os.path.join(_PROJ_SRC, "images", "omenctl.png")):
    _IMAGES_DIR = os.path.join(_PROJ_SRC, "images")
elif os.path.exists(os.path.join(_PROJ_INSTALLED, "images", "omenctl.png")):
    _IMAGES_DIR = os.path.join(_PROJ_INSTALLED, "images")
else:
    _IMAGES_DIR = "/usr/share/hp-manager/images"


class SettingsPage(Gtk.Box):

    def __init__(self, on_theme_change=None, on_lang_change=None, on_temp_unit_change=None, service=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_theme_change = on_theme_change
        self.on_lang_change = on_lang_change
        self.on_temp_unit_change = on_temp_unit_change
        self.service = service
        self._mux_backends = []
        self._updating_mux_dd = False

        self._css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
        self._update_theme_css()

        try:
            from gi.repository import Adw
            sm = Adw.StyleManager.get_default()
            sm.connect("notify::dark", lambda *_: self._update_theme_css())
        except Exception:
            pass

        self._build_ui()

    # ── Custom CSS ────────────────────────────────────────────────────────────

    def _is_dark(self, theme_name=None):
        if theme_name is None:
            if hasattr(self, "theme_dd") and self.theme_dd is not None:
                idx = self.theme_dd.get_selected()
                theme_name = "dark" if idx == 0 else "light" if idx == 1 else "system"
            else:
                theme_name = "system"

        if theme_name == "dark":
            return True
        elif theme_name == "light":
            return False

        try:
            from gi.repository import Adw
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

    def _update_theme_css(self, theme_name=None):
        is_dark = self._is_dark(theme_name)

        if is_dark:
            card_bg = "rgba(20, 18, 28, 0.72)"
            card_border = "rgba(255, 255, 255, 0.07)"
            sep_color = "rgba(168, 85, 247, 0.12)"
            fg = "#ffffff"
            row_hover_bg = "rgba(255, 255, 255, 0.04)"
            row_hover_bg_button = "rgba(255, 255, 255, 0.05)"
            row_active_bg_button = "rgba(255, 255, 255, 0.08)"
            fg_sublabel = "rgba(255, 255, 255, 0.6)"
            chevron_color = "rgba(255, 255, 255, 0.25)"
            ver_badge_bg = "rgba(255, 255, 255, 0.06)"
            ver_badge_border = "rgba(255, 255, 255, 0.1)"
            ver_badge_fg = "rgba(255, 255, 255, 0.8)"
            dev_link_fg = "rgba(255, 255, 255, 0.6)"
            disclaimer_bg = "rgba(255, 255, 255, 0.04)"
            disclaimer_fg = "rgba(255, 255, 255, 0.55)"
            progress_trough_bg = "rgba(255, 255, 255, 0.05)"
            sys_info_val_fg = "rgba(255, 255, 255, 0.6)"
            drop_bg = "rgba(255, 255, 255, 0.08)"
            drop_border = "rgba(255, 255, 255, 0.07)"
            drop_hover_bg = "rgba(255, 255, 255, 0.12)"
            drop_hover_border = "rgba(255, 255, 255, 0.18)"
        else:
            card_bg = "rgba(255, 255, 255, 0.85)"
            card_border = "rgba(0, 0, 0, 0.06)"
            sep_color = "rgba(0, 0, 0, 0.08)"
            fg = "#0f172a"
            row_hover_bg = "rgba(0, 0, 0, 0.04)"
            row_hover_bg_button = "rgba(0, 0, 0, 0.05)"
            row_active_bg_button = "rgba(0, 0, 0, 0.08)"
            fg_sublabel = "rgba(0, 0, 0, 0.6)"
            chevron_color = "rgba(0, 0, 0, 0.25)"
            ver_badge_bg = "rgba(0, 0, 0, 0.06)"
            ver_badge_border = "rgba(0, 0, 0, 0.1)"
            ver_badge_fg = "rgba(0, 0, 0, 0.8)"
            dev_link_fg = "rgba(0, 0, 0, 0.6)"
            disclaimer_bg = "rgba(0, 0, 0, 0.04)"
            disclaimer_fg = "rgba(0, 0, 0, 0.55)"
            progress_trough_bg = "rgba(0, 0, 0, 0.05)"
            sys_info_val_fg = "rgba(0, 0, 0, 0.6)"
            drop_bg = "rgba(0, 0, 0, 0.05)"
            drop_border = "rgba(0, 0, 0, 0.06)"
            drop_hover_bg = "rgba(0, 0, 0, 0.1)"
            drop_hover_border = "rgba(0, 0, 0, 0.15)"

        css = f"""
        .settings-scroll-content {{
            margin: 12px 24px 24px 24px;
        }}
        
        .settings-card {{
            border-radius: 12px;
            background: {card_bg};
            border: 1px solid {card_border};
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
            padding: 4px;
            margin-bottom: 4px;
        }}
        
        .settings-sep {{
            opacity: 1;
            background-color: {sep_color};
            margin-left: 4px;
            margin-right: 4px;
            min-height: 1px;
        }}

        .section-title {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            color: #8e8e93;
            margin-left: 4px;
            margin-bottom: 6px;
        }}

        .settings-row {{
            padding: 8px 4px;
            border-radius: 8px;
            background: transparent;
            transition: background 0.15s ease;
        }}
        .settings-row:hover {{
            background: {row_hover_bg};
        }}
        
        button.settings-row {{
            background: transparent;
            border: none;
            box-shadow: none;
            padding: 8px 4px;
            text-shadow: none;
            -gtk-icon-shadow: none;
            color: {fg};
        }}
        button.settings-row:hover {{
            background: {row_hover_bg_button};
        }}
        button.settings-row:active {{
            background: {row_active_bg_button};
        }}
        
        .settings-row-label {{
            font-size: 13px;
            font-weight: 500;
            color: {fg};
        }}
        .settings-row-sublabel {{
            font-size: 11px;
            opacity: 0.75;
            color: {fg_sublabel};
        }}
        
        .driver-status-badge {{
            border-radius: 99px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        .driver-status-badge.badge-loaded {{
            background: rgba(48, 209, 88, 0.15);
            color: #30d158;
        }}
        .driver-status-badge.badge-not-loaded {{
            background: rgba(255, 69, 58, 0.15);
            color: #ff453a;
        }}
        .badge-label {{
            font-size: 11px;
            font-weight: 700;
        }}
        .driver-name {{
            font-size: 12px;
            font-weight: 500;
            color: {fg};
            font-family: "JetBrains Mono", "Geist", monospace;
        }}

        .chevron-arrow {{
            color: {chevron_color};
            margin-left: 8px;
        }}

        .about-brand-box {{
            padding: 12px 0px 4px 0px;
        }}
        .about-logo-inline {{
            transition: transform 0.2s ease;
        }}
        .settings-card.card-about:hover .about-logo-inline {{
            transform: scale(1.15);
        }}
        .about-app-name {{
            font-size: 16px;
            font-weight: 700;
            color: {fg};
        }}
        .about-ver-badge {{
            background: {ver_badge_bg};
            border: 1px solid {ver_badge_border};
            color: {ver_badge_fg};
            border-radius: 99px;
            padding: 1px 8px;
            font-size: 10px;
            font-weight: 600;
        }}
        .about-dev-link {{
            font-size: 11px;
            color: {dev_link_fg};
        }}
        .about-dev-link a {{
            color: #0a84ff;
            font-weight: 600;
            text-decoration: none;
        }}
        .about-dev-link a:hover {{
            text-decoration: underline;
        }}
        .about-disclaimer-box {{
            background: {disclaimer_bg};
            border-radius: 8px;
            padding: 10px;
            margin-top: 4px;
        }}
        .about-disclaimer {{
            font-size: 10px;
            line-height: 1.4;
            color: {disclaimer_fg};
        }}

        .update-ver-label {{
            font-size: 13px;
            font-weight: 600;
            color: {fg};
        }}
        .update-progress-bar {{
            margin-top: 6px;
        }}
        .update-progress-bar trough {{
            min-height: 6px;
            border-radius: 999px;
            background: {progress_trough_bg};
        }}
        .update-progress-bar progress {{
            border-radius: 999px;
            background: #0a84ff;
        }}

        .sys-info-key {{
            font-size: 12px;
            font-weight: 500;
            color: {fg};
        }}
        .sys-info-val {{
            font-size: 12px;
            font-weight: 500;
            color: {sys_info_val_fg};
            font-family: "JetBrains Mono", "Geist", monospace;
        }}

        dropdown, dropdown button, dropdown > button.toggle {{
            background: {drop_bg};
            border: 1px solid {drop_border};
            border-radius: 8px;
            color: {fg};
            font-weight: 500;
            font-size: 12px;
            transition: all 0.15s ease;
        }}
        dropdown:hover, dropdown button:hover {{
            background: {drop_hover_bg};
            border-color: {drop_hover_border};
        }}
        """
        self._css_provider.load_from_data(css.encode())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_section_header(self, emoji, title_text):
        """Create a section header with title and prefixed emoji."""
        hbox = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        
        full_title = f"{emoji}  {title_text}" if emoji else title_text
        lbl = Gtk.Label(label=full_title, xalign=0, halign=Gtk.Align.START)
        lbl.add_css_class("section-title")
        hbox.append(lbl)
        return hbox

    def _make_settings_row(self, emoji, label_text, control_widget, sublabel=None, bg_class=None):
        """Create a standard settings row with prefixed emoji: label | control."""
        row = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)
        row.add_css_class("settings-row")

        full_label = f"{emoji}  {label_text}" if emoji else label_text

        # Text column vertically centered and left-aligned
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
        main_lbl = Gtk.Label(label=full_label, xalign=0, halign=Gtk.Align.START)
        main_lbl.add_css_class("settings-row-label")
        text_col.append(main_lbl)
        if sublabel:
            sub_lbl = Gtk.Label(label=sublabel, xalign=0, halign=Gtk.Align.START)
            sub_lbl.add_css_class("settings-row-sublabel")
            text_col.append(sub_lbl)
        row.append(text_col)

        control_widget.set_valign(Gtk.Align.CENTER)
        control_widget.set_halign(Gtk.Align.END)
        row.append(control_widget)
        return row

    def _make_sep(self):
        sep = Gtk.Separator()
        sep.add_css_class("settings-sep")
        return sep

    def _make_driver_row(self, emoji, driver_name, is_loaded):
        """Create a driver status row with prefixed emoji."""
        row = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)
        row.add_css_class("settings-row")

        full_name = f"{emoji}  {driver_name}" if emoji else driver_name

        # Text vertically centered and left-aligned
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
        name_lbl = Gtk.Label(label=full_name, xalign=0, halign=Gtk.Align.START)
        name_lbl.add_css_class("driver-name")
        text_col.append(name_lbl)
        row.append(text_col)

        # Capsule status badge
        badge = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER, halign=Gtk.Align.END)
        badge.add_css_class("driver-status-badge")
        badge.add_css_class("badge-loaded" if is_loaded else "badge-not-loaded")

        status_lbl = Gtk.Label(label=T("loaded") if is_loaded else T("not_loaded"), halign=Gtk.Align.CENTER)
        status_lbl.add_css_class("badge-label")
        badge.append(status_lbl)

        row.append(badge)
        return row

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        scroll = SmoothScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.add_css_class("settings-scroll-content")
        self._content_box = content

        # ══════════════════════════════════════════════════════════════════════
        # 1. PREFERENCES CARD
        # ══════════════════════════════════════════════════════════════════════
        appear_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        appear_card.add_css_class("settings-card")
        appear_card.add_css_class("card-pref")
        self._appear_card = appear_card

        content.append(self._make_section_header("🎨", T("appearance")))

        # Theme row
        self.theme_dd = Gtk.DropDown(model=Gtk.StringList.new(
            [T("dark"), T("light"), T("system")]))
        self.theme_dd.connect("notify::selected", self._on_theme)
        appear_card.append(self._make_settings_row(
            "🌓", T("theme"), self.theme_dd, bg_class="icon-bg-theme"))

        appear_card.append(self._make_sep())

        # Language row
        self.lang_dd = Gtk.DropDown(model=Gtk.StringList.new(["Türkçe", "English"]))
        self.lang_dd.connect("notify::selected", self._on_lang)
        appear_card.append(self._make_settings_row(
            "🌐", T("lang_label"), self.lang_dd, bg_class="icon-bg-lang"))

        appear_card.append(self._make_sep())

        # Temperature row
        self.temp_dd = Gtk.DropDown(model=Gtk.StringList.new(
            [T("celsius"), T("fahrenheit")]))
        self.temp_dd.connect("notify::selected", self._on_temp_unit)
        appear_card.append(self._make_settings_row(
            "🌡️", T("temp_unit"), self.temp_dd, bg_class="icon-bg-temp"))

        appear_card.append(self._make_sep())

        # Autostart row
        self.autostart_switch = Gtk.Switch()
        self.autostart_switch.set_valign(Gtk.Align.CENTER)
        self.autostart_switch.connect("state-set", self._on_autostart_toggle)
        desktop_file = os.path.expanduser("~/.config/autostart/omenctl-bg.desktop")
        self.autostart_switch.set_active(os.path.exists(desktop_file))
        autostart_lbl = T("autostart") if "autostart" in globals() else "Autostart on login"
        appear_card.append(self._make_settings_row(
            "🚀", autostart_lbl, self.autostart_switch, bg_class="icon-bg-sys"))

        content.append(appear_card)

        # ══════════════════════════════════════════════════════════════════════
        # 2. UPDATES CARD
        # ══════════════════════════════════════════════════════════════════════
        update_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        update_card.add_css_class("settings-card")
        update_card.add_css_class("card-update")
        self._update_card = update_card

        content.append(self._make_section_header("🔄", T("updates")))

        update_row = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)
        update_row.add_css_class("settings-row")
        self._update_row = update_row

        # Version info left side (Vertically centered)
        ver_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
        ver_lbl = Gtk.Label(
            label=f"🚀  OmenCtl v{APP_VERSION}", xalign=0, halign=Gtk.Align.START)
        ver_lbl.add_css_class("update-ver-label")
        ver_box.append(ver_lbl)

        self.update_status = Gtk.Label(label="", xalign=0, halign=Gtk.Align.START)
        self.update_status.add_css_class("settings-row-sublabel")
        ver_box.append(self.update_status)
        update_row.append(ver_box)

        # Spinner
        self.update_spinner = Gtk.Spinner()
        self.update_spinner.set_visible(False)
        update_row.append(self.update_spinner)

        # Buttons
        self.update_btn = Gtk.Button(label=T("check_update"))
        self.update_btn.add_css_class("update-btn")
        self.update_btn.connect("clicked", self._check_update)
        update_row.append(self.update_btn)

        self.download_btn = Gtk.Button(label=T("download"))
        self.download_btn.add_css_class("update-btn")
        self.download_btn.set_visible(False)
        self.download_btn.connect("clicked", self._open_releases)
        update_row.append(self.download_btn)

        self.install_btn = Gtk.Button(label=T("install_update"))
        self.install_btn.add_css_class("suggested-action")
        self.install_btn.set_visible(False)
        self.install_btn.connect("clicked", self._install_update)
        update_row.append(self.install_btn)

        update_card.append(update_row)

        # Progress bar
        self.update_progress = Gtk.ProgressBar()
        self.update_progress.set_visible(False)
        self.update_progress.set_show_text(True)
        self.update_progress.add_css_class("update-progress-bar")
        update_card.append(self.update_progress)

        # Restart button
        self.restart_btn = Gtk.Button(label=T("restart_app"))
        self.restart_btn.add_css_class("suggested-action")
        self.restart_btn.set_visible(False)
        self.restart_btn.connect("clicked", self._restart_app)
        update_card.append(self.restart_btn)

        content.append(update_card)

        # ══════════════════════════════════════════════════════════════════════
        # 3. SYSTEM & DRIVERS CARD
        # ══════════════════════════════════════════════════════════════════════
        info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        info_card.add_css_class("settings-card")
        info_card.add_css_class("card-sys")
        self._info_card = info_card

        content.append(self._make_section_header("💻", T("sys_info")))

        # System info rows with emojis
        sys_info = [
            ("🖥️",           T("computer"),  platform.node(),       "icon-bg-theme"),
            ("⚙️",           T("kernel"),    platform.release(),    "icon-bg-mux"),
            ("🐧",           T("os_name"),   self._get_distro(),    "icon-bg-lang"),
            ("🔌",           T("arch"),      platform.machine(),    "icon-bg-sys"),
        ]
        
        for idx, (emoji, label, value, bg_class) in enumerate(sys_info):
            row = self._make_settings_row(emoji, label, Gtk.Box(), sublabel=value, bg_class=bg_class)
            info_card.append(row)
            if idx < len(sys_info) - 1:
                info_card.append(self._make_sep())

        info_card.append(self._make_sep())

        # Driver status rows
        hp_rgb_loaded = self._is_module_loaded("hp_rgb_lighting")
        hp_wmi_loaded = self._is_module_loaded("hp_wmi")

        # Store as _driver_card for set_ui_scale compatibility
        self._driver_card = info_card

        info_card.append(self._make_driver_row("💡", "hp-rgb-lighting", hp_rgb_loaded))
        info_card.append(self._make_sep())
        info_card.append(self._make_driver_row("🌪️", "hp-wmi (Fan/Thermal/Key)", hp_wmi_loaded))

        content.append(info_card)

        # ══════════════════════════════════════════════════════════════════════
        # 4. GPU / MUX BACKEND CARD
        # ══════════════════════════════════════════════════════════════════════
        mux_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        mux_card.add_css_class("settings-card")
        mux_card.add_css_class("card-mux")
        self._mux_card = mux_card

        content.append(self._make_section_header("🎮", T("gpu_mux_label")))

        self.mux_dd = Gtk.DropDown(model=Gtk.StringList.new([T("mux_auto")]))
        self.mux_dd.connect("notify::selected", self._on_mux_backend)
        mux_card.append(self._make_settings_row(
            "🏎️", T("mux_backend_label"), self.mux_dd, bg_class="icon-bg-mux"))

        self.mux_status = Gtk.Label(label="", xalign=0, halign=Gtk.Align.START)
        self.mux_status.add_css_class("settings-row-sublabel")
        self.mux_status.set_margin_start(4)
        self.mux_status.set_margin_bottom(8)
        mux_card.append(self.mux_status)

        content.append(mux_card)

        # ══════════════════════════════════════════════════════════════════════
        # 5. DIAGNOSTICS CARD
        # ══════════════════════════════════════════════════════════════════════
        debug_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        debug_card.add_css_class("settings-card")
        debug_card.add_css_class("card-diag")
        self._debug_card = debug_card

        content.append(self._make_section_header("🩺", T("debug_info_title")))

        dump_btn = Gtk.Button()
        dump_btn.add_css_class("settings-row")
        dump_btn.connect("clicked", lambda *_: self.main_stack.set_visible_child_name("dump"))
        
        dump_inner = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)
        
        dump_lbl = Gtk.Label(label=f"📟  {T('troubleshooting_dump')}", xalign=0, hexpand=True, valign=Gtk.Align.CENTER)
        dump_lbl.add_css_class("settings-row-label")
        dump_inner.append(dump_lbl)

        chevron1 = Gtk.Image.new_from_icon_name("go-next-symbolic")
        chevron1.add_css_class("chevron-arrow")
        dump_inner.append(chevron1)
        dump_btn.set_child(dump_inner)
        debug_card.append(dump_btn)

        content.append(debug_card)

        # ══════════════════════════════════════════════════════════════════════
        # 6. PER-KEY RGB MAPPING
        # ══════════════════════════════════════════════════════════════════════
        self.mapping_wizard = MappingWizard()
        content.append(self.mapping_wizard)

        # ══════════════════════════════════════════════════════════════════════
        # 7. ABOUT CARD
        # ══════════════════════════════════════════════════════════════════════
        about_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        about_card.add_css_class("settings-card")
        about_card.add_css_class("card-about")
        self._about_card = about_card

        # App logo image placed inline
        app_logo = Gtk.Image()
        app_logo.add_css_class("about-logo-inline")
        logo_path = os.path.join(_IMAGES_DIR, "omenctl.png")
        if os.path.exists(logo_path):
            try:
                texture = Gdk.Texture.new_from_filename(logo_path)
                app_logo.set_from_paintable(texture)
            except Exception:
                app_logo.set_from_icon_name("computer-symbolic")
        else:
            app_logo.set_from_icon_name("computer-symbolic")
        app_logo.set_pixel_size(24)
        app_logo.set_valign(Gtk.Align.CENTER)
        
        self._about_icon = None

        # Text column (Vertically centered & left-aligned)
        about_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        
        name_row = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        name_row.append(app_logo)
        
        name_lbl = Gtk.Label(label="OmenCtl", xalign=0, halign=Gtk.Align.START)
        name_lbl.add_css_class("about-app-name")
        name_row.append(name_lbl)

        ver_badge = Gtk.Label(label=f"v{APP_VERSION}", halign=Gtk.Align.START)
        ver_badge.add_css_class("about-ver-badge")
        name_row.append(ver_badge)
        about_text.append(name_row)

        dev_lbl = Gtk.Label(
            label=f"{T('developer')}: <a href='https://github.com/yunusemreyl'>yunusemreyl</a>",
            use_markup=True, xalign=0, halign=Gtk.Align.START)
        dev_lbl.add_css_class("about-dev-link")
        about_text.append(dev_lbl)

        # Horizontal Box grouping Texts (Left-aligned, flush left)
        profile_row = Gtk.Box(spacing=16, valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        profile_row.add_css_class("about-brand-box")
        profile_row.set_margin_start(4)
        profile_row.set_margin_top(8)
        profile_row.set_margin_bottom(8)
        profile_row.append(about_text)
        about_card.append(profile_row)

        about_card.append(self._make_sep())

        # Disclaimer (Left-aligned, flush left)
        disclaimer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.START)
        disclaimer_box.add_css_class("about-disclaimer-box")
        disclaimer_box.set_margin_start(4)
        disclaimer_lbl = Gtk.Label(
            label=f"⚖️  {T('disclaimer')}", use_markup=True, xalign=0.0, wrap=True, halign=Gtk.Align.START)
        disclaimer_lbl.add_css_class("about-disclaimer")
        disclaimer_box.append(disclaimer_lbl)
        about_card.append(disclaimer_box)

        content.append(about_card)

        # ── Assemble ──
        scroll.set_child(content)
        
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(250)
        
        self.main_stack.add_named(scroll, "main")
        self.main_stack.add_named(self._build_dump_page(), "dump")
        
        self.append(self.main_stack)
        
        GLib.idle_add(self._refresh_mux_backend)
        self.set_ui_scale("normal")

    # ── Dump Page UI ──────────────────────────────────────────────────────────

    def _build_dump_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Header Box
        header = Gtk.Box(spacing=12, orientation=Gtk.Orientation.HORIZONTAL)
        header.set_margin_top(12)
        header.set_margin_bottom(12)
        header.set_margin_start(16)
        header.set_margin_end(16)
        
        back_btn = Gtk.Button(label=f"⬅️ {T('back')}")
        back_btn.add_css_class("suggested-action")
        back_btn.connect("clicked", lambda *_: self.main_stack.set_visible_child_name("main"))
        header.append(back_btn)
        
        title_lbl = Gtk.Label(label=T("thanks_for_using"), hexpand=True, halign=Gtk.Align.CENTER)
        title_lbl.add_css_class("settings-row-label")
        header.append(title_lbl)
        
        self.github_issue_btn = Gtk.Button(label=f"🚀 {T('send_to_github')}")
        self.github_issue_btn.add_css_class("suggested-action")
        self.github_issue_btn.connect("clicked", self._create_github_issue)
        header.append(self.github_issue_btn)
        
        page.append(header)
        page.append(self._make_sep())
        
        # Scrolled window for content
        scroll = SmoothScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.dump_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.dump_content.set_margin_top(16)
        self.dump_content.set_margin_bottom(16)
        self.dump_content.set_margin_start(24)
        self.dump_content.set_margin_end(24)
        scroll.set_child(self.dump_content)
        page.append(scroll)
        
        self.main_stack.connect("notify::visible-child-name", self._on_stack_changed)
        
        return page

    def _on_stack_changed(self, stack, param):
        if stack.get_visible_child_name() == "dump":
            self._load_dump_data()

    def _load_dump_data(self):
        # clear content
        while child := self.dump_content.get_first_child():
            self.dump_content.remove(child)
            
        spinner = Gtk.Spinner()
        spinner.start()
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_size_request(32, 32)
        self.dump_content.append(spinner)
        
        def _worker():
            try:
                from pydbus import SystemBus
                import json
                bus = SystemBus()
                svc = bus.get("com.yyl.hpmanager.platform")
                j_str = svc.GetHardwareDumpJson()
                GLib.idle_add(self._render_dump_data, j_str)
            except Exception as e:
                GLib.idle_add(self._render_dump_error, str(e))
                
        threading.Thread(target=_worker, daemon=True).start()

    def _render_dump_error(self, error_str):
        while child := self.dump_content.get_first_child():
            self.dump_content.remove(child)
        err_lbl = Gtk.Label(label=f"Failed to fetch data: {error_str}")
        self.dump_content.append(err_lbl)

    def _render_dump_data(self, json_str):
        import json
        while child := self.dump_content.get_first_child():
            self.dump_content.remove(child)
            
        try:
            data = json.loads(json_str)
        except Exception as e:
            self._render_dump_error(f"JSON Parse Error: {e}")
            return
        
        # System Table
        sys_data = data.get("system", {})
        self.dump_content.append(self._make_section_header("💻", T("sys_info")))
        
        sys_grid = Gtk.Grid(row_spacing=8, column_spacing=16)
        sys_grid.set_halign(Gtk.Align.CENTER)
        row = 0
        
        lbl_p = Gtk.Label(label="Property", halign=Gtk.Align.START)
        lbl_p.add_css_class("section-title")
        sys_grid.attach(lbl_p, 0, row, 1, 1)
        
        lbl_v = Gtk.Label(label="Value", halign=Gtk.Align.START)
        lbl_v.add_css_class("section-title")
        sys_grid.attach(lbl_v, 1, row, 1, 1)
        
        row += 1
        for k, v in sys_data.items():
            sys_grid.attach(Gtk.Label(label=str(k), halign=Gtk.Align.START), 0, row, 1, 1)
            sys_grid.attach(Gtk.Label(label=str(v), halign=Gtk.Align.START), 1, row, 1, 1)
            row += 1
        self.dump_content.append(sys_grid)
        self.dump_content.append(self._make_sep())
            
        # Capabilities Table
        cap_data = data.get("capabilities", {})
        if cap_data:
            self.dump_content.append(self._make_section_header("⚙️", "Donanım Yetenekleri"))
            cap_grid = Gtk.Grid(row_spacing=8, column_spacing=16)
            cap_grid.set_halign(Gtk.Align.CENTER)
            row = 0
            lbl_p = Gtk.Label(label="Özellik", halign=Gtk.Align.START)
            lbl_p.add_css_class("section-title")
            cap_grid.attach(lbl_p, 0, row, 1, 1)
            lbl_v = Gtk.Label(label="Durum", halign=Gtk.Align.START)
            lbl_v.add_css_class("section-title")
            cap_grid.attach(lbl_v, 1, row, 1, 1)
            row += 1
            for k, v in cap_data.items():
                cap_grid.attach(Gtk.Label(label=str(k), halign=Gtk.Align.START), 0, row, 1, 1)
                cap_grid.attach(Gtk.Label(label=str(v), halign=Gtk.Align.START), 1, row, 1, 1)
                row += 1
            self.dump_content.append(cap_grid)
            self.dump_content.append(self._make_sep())
            
        # ACPI Table
        acpi = data.get("acpi", {})
        methods = acpi.get("methods_found", {})
        
        self.dump_content.append(self._make_section_header("🔍", "ACPI / DSDT Mappings"))
        grid = Gtk.Grid(row_spacing=8, column_spacing=16)
        grid.set_halign(Gtk.Align.CENTER)
        
        row = 0
        lbl1 = Gtk.Label(label="Offset / Metod", halign=Gtk.Align.START)
        lbl1.add_css_class("section-title")
        lbl2 = Gtk.Label(label="Değer / Karşılık", halign=Gtk.Align.START)
        lbl2.add_css_class("section-title")
        grid.attach(lbl1, 0, row, 1, 1)
        grid.attach(lbl2, 1, row, 1, 1)
        row += 1
        
        if not methods:
            grid.attach(Gtk.Label(label="No methods found", halign=Gtk.Align.START), 0, row, 2, 1)
        else:
            for k, v in methods.items():
                l1 = Gtk.Label(label=str(k), halign=Gtk.Align.START)
                l2 = Gtk.Label(label=str(v), halign=Gtk.Align.START)
                grid.attach(l1, 0, row, 1, 1)
                grid.attach(l2, 1, row, 1, 1)
                row += 1
                
        self.dump_content.append(grid)
        self.dump_content.append(self._make_sep())
        
        # Errors in bash
        errors = acpi.get("errors", [])
        if errors:
            self.dump_content.append(self._make_section_header("⚠️", "Hatalar / Çıktılar"))
            
            tv = Gtk.TextView()
            tv.set_editable(False)
            tv.set_monospace(True)
            # Apply some terminal like styling
            tv.get_style_context().add_class("card-diag")
            tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            tv.set_margin_start(8)
            tv.set_margin_end(8)
            tv.set_margin_top(8)
            tv.set_margin_bottom(8)
            
            buf = tv.get_buffer()
            buf.set_text("\n".join(errors))
            
            scroll_err = Gtk.ScrolledWindow(vexpand=True)
            scroll_err.set_child(tv)
            scroll_err.set_size_request(-1, 200)
            self.dump_content.append(scroll_err)

    # ── UI Scaling ────────────────────────────────────────────────────────────

    def set_ui_scale(self, bucket, _width=0, _height=0):
        content = getattr(self, "_content_box", None)
        if content is None:
            return

        if bucket == "compact":
            margins = (6, 12, 12, 12)
            content_spacing = 12
            card_spacing = 5
            drop_w = 120
            btn_h = 32
            icon_sz = 24
            about_sz = 42
        elif bucket == "spacious":
            margins = (12, 32, 32, 12)
            content_spacing = 20
            card_spacing = 8
            drop_w = 170
            btn_h = 42
            icon_sz = 32
            about_sz = 58
        else:
            margins = (8, 24, 24, 8)
            content_spacing = 16
            card_spacing = 6
            drop_w = 146
            btn_h = 38
            icon_sz = 28
            about_sz = 52

        content.set_margin_top(margins[0])
        content.set_margin_start(margins[1])
        content.set_margin_end(margins[2])
        content.set_margin_bottom(margins[3])
        content.set_spacing(content_spacing)

        for attr in ("_appear_card", "_update_card", "_info_card",
                      "_mux_card", "_about_card", "_debug_card"):
            card = getattr(self, attr, None)
            if card is not None:
                card.set_spacing(card_spacing)

        for dd in (getattr(self, "theme_dd", None),
                   getattr(self, "lang_dd", None),
                   getattr(self, "temp_dd", None),
                   getattr(self, "mux_dd", None)):
            if dd is not None:
                dd.set_size_request(drop_w, -1)

        for btn in (getattr(self, "update_btn", None),
                    getattr(self, "download_btn", None),
                    getattr(self, "install_btn", None),
                    getattr(self, "restart_btn", None)):
            if btn is not None:
                btn.set_size_request(-1, btn_h)

        for icon in (getattr(self, "_debug_term_icon", None),
                     getattr(self, "_debug_copy_icon", None),
                     getattr(self, "_debug_github_icon", None)):
            if icon is not None and hasattr(icon, 'set_pixel_size'):
                icon.set_pixel_size(icon_sz)

        about_icon = getattr(self, "_about_icon", None)
        if about_icon is not None:
            if hasattr(about_icon, 'set_pixel_size'):
                about_icon.set_pixel_size(about_sz)
            else:
                about_icon.set_size_request(about_sz, about_sz)

    # ── Service ───────────────────────────────────────────────────────────────

    def set_service(self, service):
        self.service = service
        GLib.idle_add(self._refresh_mux_backend)

    def _refresh_mux_backend(self):
        if not self.service:
            self.mux_status.set_label(T("mux_not_found"))
            return False
        try:
            info = json.loads(self.service.GetGpuInfo())
            available = info.get("available_backends", [])
            forced = info.get("forced_backend", "auto")
            labels = [T("mux_auto")] + available

            self._updating_mux_dd = True
            self._mux_backends = available[:]
            self.mux_dd.set_model(Gtk.StringList.new(labels))
            if forced == "auto":
                self.mux_dd.set_selected(0)
            elif forced in available:
                self.mux_dd.set_selected(available.index(forced) + 1)
            else:
                self.mux_dd.set_selected(0)
            self._updating_mux_dd = False

            active_backend = info.get("backend", "none")
            self.mux_status.set_label(f"Active backend: {active_backend}")
        except Exception as e:
            self._updating_mux_dd = False
            self.mux_status.set_label(f"{T('error')}: {e}")
        return False

    def _on_autostart_toggle(self, switch, state):
        desktop_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(desktop_dir, "omenctl-bg.desktop")
        if state:
            try:
                os.makedirs(desktop_dir, exist_ok=True)
                with open(desktop_file, "w") as f:
                    f.write("[Desktop Entry]\nType=Application\nName=OmenCtl Background\nExec=omenctl --hidden\nIcon=omenctl\nTerminal=false\nNoDisplay=true\n")
            except Exception as e:
                print(f"Failed to enable autostart: {e}")
                return True
        else:
            if os.path.exists(desktop_file):
                try:
                    os.remove(desktop_file)
                except Exception as e:
                    print(f"Failed to disable autostart: {e}")
                    return True
        return False

    def _on_mux_backend(self, dd, _):
        if self._updating_mux_dd or not self.service:
            return
        idx = dd.get_selected()
        backend = "auto" if idx == 0 else self._mux_backends[idx - 1]
        try:
            res = self.service.SetMuxBackend(backend)
            if res != "OK":
                self.mux_status.set_label(f"{T('error')}: {res}")
                return
            GLib.timeout_add(300, self._refresh_mux_backend)
        except Exception as e:
            self.mux_status.set_label(f"{T('error')}: {e}")

    # ── Update Checker ────────────────────────────────────────────────────────

    def _check_update(self, btn):
        self.update_btn.set_sensitive(False)
        self.update_spinner.set_visible(True)
        self.update_spinner.start()
        self.update_status.set_label(T("update_checking"))
        self.download_btn.set_visible(False)
        self.install_btn.set_visible(False)
        self.restart_btn.set_visible(False)
        if not hasattr(self, 'updater'):
            self.updater = OmenUpdater(APP_VERSION, T)
        self.updater.check_update_async(self._update_result, self._update_error)

    def _update_result(self, has_update, latest_ver):
        self.update_spinner.stop()
        self.update_spinner.set_visible(False)
        self.update_btn.set_sensitive(True)
        if has_update:
            self.update_status.set_label(f"{T('new_ver_available')}: v{latest_ver}")
            self.update_status.add_css_class("update-available")
            self.download_btn.set_visible(True)
            self.install_btn.set_visible(True)
        else:
            self.update_status.set_label(f"✓ {T('up_to_date')} (v{latest_ver})")

    def _update_error(self, err):
        self.update_spinner.stop()
        self.update_spinner.set_visible(False)
        self.update_btn.set_sensitive(True)
        self.update_status.set_label(T("conn_failed"))

    def _open_releases(self, btn):
        if not hasattr(self, 'updater'):
            self.updater = OmenUpdater(APP_VERSION, T)
        self.updater.open_releases_page()

    def _install_update(self, btn):
        self.install_btn.set_sensitive(False)
        self.download_btn.set_visible(False)
        self.update_btn.set_sensitive(False)
        self.update_progress.set_visible(True)
        self.update_progress.set_fraction(0.0)
        self.update_progress.set_text(T("downloading_update"))
        self.update_status.set_label(T("downloading_update"))
        if not hasattr(self, 'updater'):
            self.updater = OmenUpdater(APP_VERSION, T)
        self.updater.install_update_async(self._install_progress, self._install_done)

    def _install_progress(self, fraction, text):
        self.update_progress.set_fraction(fraction)
        self.update_progress.set_text(text)
        return False

    def _install_done(self, success, error_msg):
        self.update_progress.set_fraction(1.0 if success else 0.0)
        self.update_progress.set_visible(False)
        self.install_btn.set_visible(False)
        self.update_btn.set_sensitive(True)
        if success:
            self.update_status.set_label(f"✓ {T('update_success')}")
            self.update_status.remove_css_class("update-available")
            self.restart_btn.set_visible(True)
        else:
            self.update_status.set_label(f"{T('update_failed')}: {error_msg}")
            self.install_btn.set_sensitive(True)
            self.install_btn.set_visible(True)
        return False

    def _restart_app(self, btn):
        app = self.get_root()
        if app and hasattr(app, 'get_application'):
            application = app.get_application()
            if application:
                application.quit()
        if not hasattr(self, 'updater'):
            self.updater = OmenUpdater(APP_VERSION, T)
        self.updater.restart_app()
    # ── Theme / Lang ──────────────────────────────────────────────────────────
    def _on_theme(self, dd, _):
        idx = dd.get_selected()
        theme = "dark" if idx == 0 else "light" if idx == 1 else "system"
        self._update_theme_css(theme)
        if self.on_theme_change:
            self.on_theme_change(theme)

    def _on_lang(self, dd, _):
        lang = "tr" if dd.get_selected() == 0 else "en"
        if self.on_lang_change:
            self.on_lang_change(lang)

    def set_theme_index(self, idx):
        self.theme_dd.set_selected(idx)
        theme = "dark" if idx == 0 else "light" if idx == 1 else "system"
        self._update_theme_css(theme)

    def set_lang_index(self, idx):
        self.lang_dd.set_selected(idx)

    def set_temp_unit_index(self, idx):
        self.temp_dd.set_selected(idx)

    def _on_temp_unit(self, dd, _):
        unit = "C" if dd.get_selected() == 0 else "F"
        if self.on_temp_unit_change:
            self.on_temp_unit_change(unit)

    def _is_module_loaded(self, module_name):
        """Check if a kernel module is loaded via sysfs or lsmod.
        Handles both custom DKMS modules and stock kernel modules."""
        # Check common sysfs platform device paths
        sysfs_name = module_name.replace("_", "-")
        for path in (f"/sys/devices/platform/{sysfs_name}",
                     f"/sys/devices/platform/{module_name}"):
            if os.path.exists(path):
                return True
        # Fallback: check lsmod
        try:
            import subprocess
            result = subprocess.run(
                ["lsmod"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if line.split()[0] == module_name:
                    return True
        except Exception:
            pass
        return False

    def _get_distro(self):
        try:
            import subprocess
            return subprocess.check_output(["lsb_release", "-ds"], stderr=subprocess.DEVNULL).decode().strip().replace('"', '')
        except Exception:
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            return line.split("=", 1)[1].strip().strip('"')
            except Exception: pass
        return "Linux"


    def _copy_debug_log(self, btn):
        btn.set_sensitive(False)
        def worker():
            txt = generate_diagnostic_report(APP_VERSION, self._get_distro())
            GLib.idle_add(self._copy_done, txt, btn)
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _copy_done(self, text, btn):
        from gi.repository import Gdk
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_content(Gdk.ContentProvider.new_for_value(text))
        btn.set_sensitive(True)

    def _show_debug_terminal(self, _):
        dialog = Gtk.Window(title="Diagnose & Check", transient_for=self.get_root(), modal=True)
        dialog.set_default_size(800, 600)
        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        term = Gtk.TextView(editable=False, cursor_visible=False)
        term.add_css_class("terminal-text")
        term.set_margin_start(12)
        term.set_margin_end(12)
        term.set_margin_top(12)
        term.set_margin_bottom(12)
        buf = term.get_buffer()
        scroll.set_child(term)
        dialog.set_child(scroll)
        dialog.present()
        def run_diag():
            txt = generate_diagnostic_report(APP_VERSION, self._get_distro())
            GLib.idle_add(lambda: buf.set_text(txt))
        import threading
        threading.Thread(target=run_diag, daemon=True).start()

    def _create_github_issue(self, btn):
        btn.set_sensitive(False)
        old_label = btn.get_child().get_label() if btn.get_child() else "Create Issue"
        if btn.get_child(): btn.get_child().set_label("Gathering info...")
        def _worker():
            try:
                diag = generate_github_issue_body(APP_VERSION, self._get_distro())
                GLib.idle_add(self._open_github_issue, diag, old_label, btn)
            except Exception as e:
                GLib.idle_add(self._github_issue_error, str(e), old_label, btn)
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _open_github_issue(self, diag, old_label, btn):
        import urllib.parse
        import subprocess
        title = urllib.parse.quote(diag["title"])
        body = urllib.parse.quote(diag["body"])
        url = f"https://github.com/yunusemreyl/OmenCtl/issues/new?title={title}&body={body}"
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if btn.get_child(): btn.get_child().set_label(old_label)
        btn.set_sensitive(True)

    def _github_issue_error(self, error_msg, old_label, btn):
        if btn.get_child(): btn.get_child().set_label(old_label)
        btn.set_sensitive(True)
        print(f"Error creating GitHub issue: {error_msg}")
