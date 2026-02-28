#!/usr/bin/env python3
"""Settings Page with GitHub update checker — i18n via T()."""
import os, platform, threading, json
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def T(k):
    from i18n import T as _T
    return _T(k)


APP_VERSION = "4.6"
GITHUB_REPO = "yunusemreyl/LaptopManagerForHP"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


class SettingsPage(Gtk.Box):
    def __init__(self, on_theme_change=None, on_lang_change=None, on_temp_unit_change=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.on_theme_change = on_theme_change
        self.on_lang_change = on_lang_change
        self.on_temp_unit_change = on_temp_unit_change
        self.set_margin_top(30)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.set_margin_bottom(30)

        self._build_ui()

    def _build_ui(self):
        title = Gtk.Label(label=T("settings"), xalign=0)
        title.add_css_class("page-title")
        self.append(title)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        # ── Appearance ──
        appear_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        appear_card.add_css_class("card")
        appear_card.append(Gtk.Label(label=T("appearance"), xalign=0, css_classes=["section-title"]))

        # Theme
        theme_row = Gtk.Box(spacing=20)
        theme_row.append(Gtk.Label(label=T("theme"), hexpand=True, xalign=0))
        self.theme_dd = Gtk.DropDown(model=Gtk.StringList.new([T("dark"), T("light"), T("system")]))
        self.theme_dd.connect("notify::selected", self._on_theme)
        theme_row.append(self.theme_dd)
        appear_card.append(theme_row)

        appear_card.append(Gtk.Separator())

        # Language
        lang_row = Gtk.Box(spacing=20)
        lang_row.append(Gtk.Label(label=T("lang_label"), hexpand=True, xalign=0))
        self.lang_dd = Gtk.DropDown(model=Gtk.StringList.new(["Türkçe", "English"]))
        self.lang_dd.connect("notify::selected", self._on_lang)
        lang_row.append(self.lang_dd)
        appear_card.append(lang_row)

        appear_card.append(Gtk.Separator())

        # Temperature Unit
        temp_row = Gtk.Box(spacing=20)
        temp_row.append(Gtk.Label(label=T("temp_unit"), hexpand=True, xalign=0))
        self.temp_dd = Gtk.DropDown(model=Gtk.StringList.new([T("celsius"), T("fahrenheit")]))
        self.temp_dd.connect("notify::selected", self._on_temp_unit)
        temp_row.append(self.temp_dd)
        appear_card.append(temp_row)

        content.append(appear_card)

        # ── Updates ──
        update_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        update_card.add_css_class("card")
        update_card.append(Gtk.Label(label=T("updates"), xalign=0, css_classes=["section-title"]))

        update_row = Gtk.Box(spacing=15, valign=Gtk.Align.CENTER)

        ver_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        ver_box.append(Gtk.Label(label=f"{T('current_ver')}: v{APP_VERSION}", xalign=0))
        self.update_status = Gtk.Label(label="", xalign=0, css_classes=["stat-lbl"])
        ver_box.append(self.update_status)
        update_row.append(ver_box)

        self.update_spinner = Gtk.Spinner()
        self.update_spinner.set_visible(False)
        update_row.append(self.update_spinner)

        self.update_btn = Gtk.Button(label=T("check_update"))
        self.update_btn.add_css_class("update-btn")
        self.update_btn.connect("clicked", self._check_update)
        update_row.append(self.update_btn)

        self.download_btn = Gtk.Button(label=T("download"))
        self.download_btn.add_css_class("update-btn")
        self.download_btn.set_visible(False)
        self.download_btn.connect("clicked", self._open_releases)
        update_row.append(self.download_btn)

        update_card.append(update_row)
        content.append(update_card)

        # ── System Info ──
        info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        info_card.add_css_class("card")
        info_card.append(Gtk.Label(label=T("sys_info"), xalign=0, css_classes=["section-title"]))

        sys_info = [
            (T("computer"), platform.node()),
            (T("kernel"), platform.release()),
            (T("os_name"), self._get_distro()),
            (T("arch"), platform.machine()),
        ]
        for label, value in sys_info:
            row = Gtk.Box(spacing=20)
            row.append(Gtk.Label(label=label, hexpand=True, xalign=0, css_classes=["stat-lbl"]))
            row.append(Gtk.Label(label=value, xalign=1, css_classes=["stat-lbl"]))
            info_card.append(row)
        content.append(info_card)

        # ── Driver Status ──
        driver_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        driver_card.add_css_class("card")
        driver_card.append(Gtk.Label(label=T("driver_status"), xalign=0, css_classes=["section-title"]))

        hp_omen_core_loaded = os.path.exists("/sys/devices/platform/hp-omen-core")
        hp_wmi_loaded = os.path.exists("/sys/devices/platform/hp-wmi")

        drivers = [("hp-omen-core", hp_omen_core_loaded), ("hp-wmi (Fan/Thermal/Key)", hp_wmi_loaded)]
        for name, loaded in drivers:
            row = Gtk.Box(spacing=20)
            row.append(Gtk.Label(label=name, hexpand=True, xalign=0))
            status = Gtk.Label(label=T("loaded") if loaded else T("not_loaded"))
            status.add_css_class("tool-installed" if loaded else "tool-not-installed")
            row.append(status)
            driver_card.append(row)
        content.append(driver_card)

        # ── About ──
        about_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        about_card.add_css_class("card")

        about_header = Gtk.Box(spacing=15)
        app_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        app_icon.set_pixel_size(48)
        about_header.append(app_icon)

        about_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        about_text.append(Gtk.Label(label=f"HP Laptop Manager v{APP_VERSION}", xalign=0, css_classes=["stat-big"]))
        about_text.append(Gtk.Label(
            label=f"{T('developer')}: <a href='https://github.com/yunusemreyl'>yunusemreyl</a>",
            use_markup=True, xalign=0, css_classes=["stat-lbl"]
        ))
        about_text.append(Gtk.Label(
            label=T("disclaimer"),
            use_markup=True, xalign=0, css_classes=["stat-lbl"], wrap=True
        ))
        about_header.append(about_text)
        about_card.append(about_header)
        content.append(about_card)

        scroll.set_child(content)
        self.append(scroll)

    # ── Update Checker ──
    def _check_update(self, btn):
        self.update_btn.set_sensitive(False)
        self.update_spinner.set_visible(True)
        self.update_spinner.start()
        self.update_status.set_label(T("update_checking"))
        self.download_btn.set_visible(False)
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _do_check_update(self):
        try:
            import urllib.request
            req = urllib.request.Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                latest = data.get("tag_name", "").lstrip("v").strip()
                if latest and self._version_compare(latest, APP_VERSION) > 0:
                    GLib.idle_add(self._update_result, True, latest)
                else:
                    GLib.idle_add(self._update_result, False, latest or APP_VERSION)
        except Exception as e:
            GLib.idle_add(self._update_error, str(e))

    def _update_result(self, has_update, latest_ver):
        self.update_spinner.stop()
        self.update_spinner.set_visible(False)
        self.update_btn.set_sensitive(True)
        if has_update:
            self.update_status.set_label(f"{T('new_ver_available')}: v{latest_ver}")
            self.update_status.add_css_class("update-available")
            self.download_btn.set_visible(True)
        else:
            self.update_status.set_label(f"✓ {T('up_to_date')} (v{latest_ver})")

    def _update_error(self, err):
        self.update_spinner.stop()
        self.update_spinner.set_visible(False)
        self.update_btn.set_sensitive(True)
        self.update_status.set_label(T("conn_failed"))

    def _open_releases(self, btn):
        import subprocess
        subprocess.Popen(["xdg-open", GITHUB_RELEASES_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _version_compare(v1, v2):
        def parts(v):
            return [int(x) for x in v.split(".") if x.isdigit()]
        p1, p2 = parts(v1), parts(v2)
        for a, b in zip(p1, p2):
            if a != b: return a - b
        return len(p1) - len(p2)

    # ── Theme / Lang ──
    def _on_theme(self, dd, _):
        idx = dd.get_selected()
        theme = "dark" if idx == 0 else "light" if idx == 1 else "system"
        if self.on_theme_change:
            self.on_theme_change(theme)

    def _on_lang(self, dd, _):
        lang = "tr" if dd.get_selected() == 0 else "en"
        if self.on_lang_change:
            self.on_lang_change(lang)

    def set_theme_index(self, idx):
        self.theme_dd.set_selected(idx)

    def set_lang_index(self, idx):
        self.lang_dd.set_selected(idx)

    def set_temp_unit_index(self, idx):
        self.temp_dd.set_selected(idx)

    def _on_temp_unit(self, dd, _):
        unit = "C" if dd.get_selected() == 0 else "F"
        if self.on_temp_unit_change:
            self.on_temp_unit_change(unit)

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
