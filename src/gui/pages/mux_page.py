#!/usr/bin/env python3
"""MUX Page - GPU info + mode switching — i18n via T()."""
import os, json, subprocess, shutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def T(k):
    from i18n import T as _T
    return _T(k)


def _get_nvidia_info():
    info = {"name": "", "driver": ""}
    if not shutil.which("nvidia-smi"):
        return info
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        parts = out.split(",")
        if len(parts) >= 2:
            info["name"] = parts[0].strip()
            info["driver"] = parts[1].strip()
        elif len(parts) == 1:
            info["name"] = parts[0].strip()
    except: pass
    return info


class MUXPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.service = service
        self.set_margin_top(30)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.set_margin_bottom(30)

        self.current_mode = "unknown"
        self.backend = "none"
        self._mode_loaded = False
        self._build_ui()
        GLib.idle_add(self._refresh)

    def set_service(self, service):
        self.service = service
        GLib.idle_add(self._refresh)

    def _build_ui(self):
        title = Gtk.Label(label=T("mux_switch"), xalign=0)
        title.add_css_class("page-title")
        self.append(title)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        # ═══ GPU INFO CARD ═══
        gpu_info = _get_nvidia_info()
        if gpu_info["name"]:
            gpu_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            gpu_card.add_css_class("card")

            gpu_header = Gtk.Box(spacing=10)
            gpu_header.append(Gtk.Image.new_from_icon_name("video-display-symbolic"))
            gpu_header.append(Gtk.Label(label=T("gpu_info"), css_classes=["section-title"]))
            gpu_card.append(gpu_header)

            name_row = Gtk.Box(spacing=20)
            name_row.append(Gtk.Label(label=T("gpu_card"), hexpand=True, xalign=0, css_classes=["stat-lbl"]))
            name_row.append(Gtk.Label(label=gpu_info["name"], xalign=1, css_classes=["stat-big"]))
            gpu_card.append(name_row)

            if gpu_info["driver"]:
                drv_row = Gtk.Box(spacing=20)
                drv_row.append(Gtk.Label(label=T("driver_ver"), hexpand=True, xalign=0, css_classes=["stat-lbl"]))
                drv_row.append(Gtk.Label(label=gpu_info["driver"], xalign=1, css_classes=["stat-big"]))
                gpu_card.append(drv_row)

            scroll_content.append(gpu_card)

        # ═══ GPU MODE CARD ═══
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=25)
        card.add_css_class("card")

        header = Gtk.Box(spacing=10)
        header.append(Gtk.Image.new_from_icon_name("video-display-symbolic"))
        header.append(Gtk.Label(label=T("gpu_mode"), css_classes=["section-title"]))
        card.append(header)

        self.mux_box = Gtk.Box(spacing=20, homogeneous=True, halign=Gtk.Align.CENTER)
        self.mux_group = None

        modes = [
            ("hybrid", T("hybrid"), T("hybrid_desc"), "battery-level-80-symbolic"),
            ("discrete", T("discrete"), T("discrete_desc"), "speedometer-symbolic"),
            ("integrated", T("integrated"), T("integrated_desc"), "battery-level-100-symbolic"),
        ]

        self.mode_buttons = {}
        for mode_id, label, desc, icon in modes:
            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            btn = Gtk.ToggleButton()
            btn.set_size_request(160, 130)
            btn.add_css_class("mux-btn")
            btn_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            ic = Gtk.Image.new_from_icon_name(icon)
            ic.set_pixel_size(48)
            btn_content.append(ic)
            btn.set_child(btn_content)
            if self.mux_group:
                btn.set_group(self.mux_group)
            else:
                self.mux_group = btn
            btn.connect("toggled", lambda w, m=mode_id: self._on_mode_select(m) if w.get_active() else None)
            wrapper.append(btn)
            wrapper.append(Gtk.Label(label=label, css_classes=["stat-big"]))
            wrapper.append(Gtk.Label(label=desc, css_classes=["stat-lbl"], wrap=True, justify=Gtk.Justification.CENTER))
            self.mux_box.append(wrapper)
            self.mode_buttons[mode_id] = btn

        card.append(self.mux_box)

        self.status_label = Gtk.Label(label=T("gpu_checking"), css_classes=["stat-lbl"], wrap=True, xalign=0.5)
        card.append(self.status_label)

        self.backend_label = Gtk.Label(label="", css_classes=["stat-lbl"], xalign=0.5)
        self.backend_label.set_opacity(0.5)
        card.append(self.backend_label)
        scroll_content.append(card)

        # Warning
        self.warn_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER)
        self.warn_card.add_css_class("warning-box")
        self.warn_card.set_margin_top(10)
        self.warn_card.set_visible(False)
        warn_row = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        warn_row.append(Gtk.Image.new_from_icon_name("dialog-warning-symbolic"))
        warn_row.append(Gtk.Label(label=T("restart_warn"), css_classes=["warning-sub"]))
        self.warn_card.append(warn_row)
        scroll_content.append(self.warn_card)

        # Not available
        self.not_available = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, halign=Gtk.Align.CENTER)
        self.not_available.add_css_class("warning-box")
        self.not_available.set_visible(False)
        ic = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        ic.set_pixel_size(48)
        self.not_available.append(ic)
        self.not_available.append(Gtk.Label(label=T("mux_not_found"), css_classes=["warning-text"]))
        self.not_available.append(Gtk.Label(label=T("mux_install_hint"), css_classes=["warning-sub"], wrap=True))
        scroll_content.append(self.not_available)

        scroll.set_child(scroll_content)
        self.append(scroll)

    def _on_mode_select(self, mode):
        if mode == self.current_mode or not self.service or not self._mode_loaded:
            return
        self.warn_card.set_visible(True)
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(), modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=T("restart"),
            secondary_text=T("restart_confirm").format(mode=mode)
        )
        dialog.connect("response", lambda d, resp: self._apply_mode(mode, resp, d))
        dialog.present()

    def _apply_mode(self, mode, response, dialog):
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            try:
                result = self.service.SetGpuMode(mode)
                if result == "OK":
                    self.status_label.set_label(T("mode_set").format(mode=mode))
                    os.system("systemctl reboot")
                else:
                    self.status_label.set_label(f"{T('error')}: {result}")
            except Exception as e:
                self.status_label.set_label(f"{T('error')}: {e}")
        else:
            self.warn_card.set_visible(False)
            if self.current_mode in self.mode_buttons:
                self.mode_buttons[self.current_mode].set_active(True)

    def _refresh(self):
        if not self.service:
            return
        try:
            info = json.loads(self.service.GetGpuInfo())
            self.backend = info.get("backend", "none")
            self.current_mode = info.get("mode", "unknown")
            available = info.get("available", False)
            if available:
                self.not_available.set_visible(False)
                self.mux_box.set_visible(True)
                self.backend_label.set_label(f"Backend: {self.backend}")
                self.status_label.set_label(f"{T('mode')}: {self.current_mode}")
                mode_map = {
                    "hybrid": "hybrid", "on-demand": "hybrid",
                    "discrete": "discrete", "dedicated": "discrete", "nvidia": "discrete",
                    "integrated": "integrated", "intel": "integrated",
                }
                mapped = mode_map.get(self.current_mode, self.current_mode)
                if mapped in self.mode_buttons:
                    self.mode_buttons[mapped].set_active(True)
                self._mode_loaded = True
            else:
                self.not_available.set_visible(True)
                self.mux_box.set_visible(False)
                self.status_label.set_label(T("mux_not_found"))
        except: pass
