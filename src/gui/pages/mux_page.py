#!/usr/bin/env python3
"""MUX Page - GPU info + mode switching — i18n via T()."""
import os
import json
import subprocess
import shutil
import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio


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
            ["nvidia-smi", "--query-gpu=name,driver_version",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        parts = out.split(",")
        if len(parts) >= 2:
            info["name"]   = parts[0].strip()
            info["driver"] = parts[1].strip()
        elif len(parts) == 1:
            info["name"] = parts[0].strip()
    except Exception:
        pass
    return info


# Human-readable backend labels
_BACKEND_LABELS = {
    "envycontrol":  "envycontrol",
    "supergfxctl":  "supergfxctl",
    "prime-select": "prime-select",
    "wmi-native":   "Native WMI Orchestrator",
    "none":         "—",
}


class MUXPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.service = service
        self.set_margin_top(30)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.set_margin_bottom(30)

        self.current_mode = "unknown"
        self.backend      = "none"
        self._mode_loaded = False
        self._build_ui()
        GLib.idle_add(self._refresh)

    def set_service(self, service):
        self.service = service
        GLib.idle_add(self._refresh)

    def refresh(self):
        GLib.idle_add(self._refresh)

    # ── GPU detection ─────────────────────────────────────────────────────────
    def _detect_gpus(self):
        import re
        igpu = T("integrated_desc")
        dgpu = T("discrete_desc")
        try:
            out = subprocess.check_output(["lspci"], text=True, timeout=5)
            for line in out.splitlines():
                if "VGA" in line or "3D" in line:
                    if "Intel" in line:
                        igpu = ("Intel Iris Xe Graphics"
                                if "Iris" in line else "Intel UHD Graphics")
                    elif "AMD" in line or "Radeon" in line:
                        igpu = "AMD Radeon Graphics"
                    if "NVIDIA" in line:
                        m = re.search(r'(RTX \d+[A-Za-z\s]*|GTX \d+[A-Za-z\s]*)', line)
                        dgpu = f"NVIDIA GeForce {m.group(1).strip()}" if m else "NVIDIA GeForce"
        except Exception:
            pass
        return igpu, dgpu

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        _dyn_igpu, dyn_dgpu = self._detect_gpus()

        title = Gtk.Label(label=T("mux_switch"), xalign=0)
        title.add_css_class("page-title")
        self.append(title)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self._scroll_content = scroll_content

        # GPU info card
        gpu_info = _get_nvidia_info()
        
        self.gpu_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.gpu_card.add_css_class("card")

        gpu_header = Gtk.Box(spacing=10)
        disp_icon = Gio.ThemedIcon.new_from_names(["display-symbolic", "video-display-symbolic", "computer-symbolic"])
        gpu_header.append(Gtk.Image.new_from_gicon(disp_icon))
        gpu_header.append(Gtk.Label(label=T("gpu_info"),
                                    css_classes=["section-title"]))
        self.gpu_card.append(gpu_header)

        if gpu_info["name"]:
            name_row = Gtk.Box(spacing=20)
            name_row.append(Gtk.Label(label=T("gpu_card"), hexpand=True,
                                      xalign=0, css_classes=["stat-lbl"]))
            name_row.append(Gtk.Label(label=gpu_info["name"],
                                      xalign=1, css_classes=["stat-big"]))
            self.gpu_card.append(name_row)

            if gpu_info["driver"]:
                drv_row = Gtk.Box(spacing=20)
                drv_row.append(Gtk.Label(label=T("driver_ver"), hexpand=True,
                                         xalign=0, css_classes=["stat-lbl"]))
                drv_row.append(Gtk.Label(label=gpu_info["driver"],
                                         xalign=1, css_classes=["stat-big"]))
                self.gpu_card.append(drv_row)

        # Mode row
        mode_row = Gtk.Box(spacing=20)
        mode_row.append(Gtk.Label(label=T("mode"), hexpand=True, xalign=0, css_classes=["stat-lbl"]))
        self.mode_val = Gtk.Label(label="-", xalign=1, css_classes=["stat-big"])
        mode_row.append(self.mode_val)
        self.gpu_card.append(mode_row)
        
        # Backend row
        backend_row = Gtk.Box(spacing=20)
        backend_row.append(Gtk.Label(label="Backend", hexpand=True, xalign=0, css_classes=["stat-lbl"]))
        self.backend_val = Gtk.Label(label="-", xalign=1, css_classes=["stat-big"])
        backend_row.append(self.backend_val)
        self.gpu_card.append(backend_row)

        # Displays row
        disp_row = Gtk.Box(spacing=20)
        disp_row.append(Gtk.Label(label="Bağlı Ekran Çıkışları", hexpand=True, xalign=0, css_classes=["stat-lbl"]))
        self.displays_val = Gtk.Label(label="-", xalign=1, justify=Gtk.Justification.RIGHT, css_classes=["stat-big"])
        disp_row.append(self.displays_val)
        self.gpu_card.append(disp_row)

        scroll_content.append(self.gpu_card)

        # Mode selection card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=25)
        card.add_css_class("card")

        header = Gtk.Box(spacing=10)
        header.append(Gtk.Image.new_from_gicon(disp_icon))
        header.append(Gtk.Label(label=T("gpu_mode"), css_classes=["section-title"]))
        card.append(header)

        self.mux_box = Gtk.Box(spacing=20, homogeneous=True,
                               halign=Gtk.Align.CENTER)
        self.mode_buttons: dict = {}

        # ── Hybrid (group anchor) ──────────────────────────────────────────────
        self.hybrid_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                    spacing=10, halign=Gtk.Align.CENTER)
        hybrid_icon = Gtk.Image.new_from_icon_name("preferences-system-symbolic")
        hybrid_icon.set_pixel_size(80)
        self._hybrid_icon = hybrid_icon
        self.btn_hybrid = Gtk.ToggleButton(child=hybrid_icon)
        self.btn_hybrid.add_css_class("mux-btn")
        self.btn_hybrid.connect("toggled",
            lambda w: self._on_mode_select("hybrid") if w.get_active() else None)
        self.hybrid_outer.append(self.btn_hybrid)
        self.hybrid_outer.append(Gtk.Label(label=T("hybrid"),
                                           css_classes=["stat-big"]))
        desc_hybrid = Gtk.Label(label=T("hybrid_desc"))
        desc_hybrid.set_justify(Gtk.Justification.CENTER)
        desc_hybrid.add_css_class("stat-lbl")
        self.hybrid_outer.append(desc_hybrid)
        self.mux_box.append(self.hybrid_outer)
        self.mode_buttons["hybrid"]    = self.btn_hybrid
        self.mode_buttons["on-demand"] = self.btn_hybrid

        # ── Discrete ──────────────────────────────────────────────────────────
        self.dgpu_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                  spacing=10, halign=Gtk.Align.CENTER)
        dgpu_icon = Gtk.Image.new_from_gicon(disp_icon)
        dgpu_icon.set_pixel_size(80)
        dgpu_icon.set_halign(Gtk.Align.CENTER)
        self._dgpu_icon = dgpu_icon
        self.btn_dgpu = Gtk.ToggleButton(child=dgpu_icon)
        self.btn_dgpu.add_css_class("mux-btn")
        self.btn_dgpu.set_group(self.btn_hybrid)  # Hybrid is group anchor
        self.btn_dgpu.connect("toggled",
            lambda w: self._on_mode_select("discrete") if w.get_active() else None)
        self.dgpu_outer.append(self.btn_dgpu)
        self.dgpu_outer.append(Gtk.Label(label=T("discrete"),
                                         css_classes=["stat-big"]))
        desc_dgpu = Gtk.Label(label=dyn_dgpu)
        desc_dgpu.set_justify(Gtk.Justification.CENTER)
        desc_dgpu.add_css_class("stat-lbl")
        self.dgpu_outer.append(desc_dgpu)
        self.mux_box.append(self.dgpu_outer)
        self.mode_buttons["discrete"]  = self.btn_dgpu
        self.mode_buttons["dedicated"] = self.btn_dgpu
        self.mode_buttons["nvidia"]    = self.btn_dgpu

        card.append(self.mux_box)

        self.status_label = Gtk.Label(
            label="", css_classes=["stat-lbl"],
            wrap=True, xalign=0.5)
        card.append(self.status_label)

        scroll_content.append(card)

        # Reboot warning (shown only when reboot is actually required)
        self.warn_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                 spacing=12, halign=Gtk.Align.CENTER)
        self.warn_card.add_css_class("warning-box")
        self.warn_card.set_margin_top(10)
        self.warn_card.set_visible(False)
        warn_row = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        warn_row.append(Gtk.Image.new_from_icon_name("dialog-warning-symbolic"))
        warn_row.append(Gtk.Label(label=T("restart_warn"),
                                  css_classes=["warning-sub"]))
        self.warn_card.append(warn_row)
        scroll_content.append(self.warn_card)

        # Not available state
        self.not_available = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                     spacing=15, halign=Gtk.Align.CENTER)
        self.not_available.add_css_class("warning-box")
        self.not_available.set_visible(False)
        ic = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        ic.set_pixel_size(48)
        self.not_available.append(ic)
        self.not_available.append(
            Gtk.Label(label="WMI MUX arayüzü bulunamadı", css_classes=["warning-text"]))
        self.not_available.append(
            Gtk.Label(label="hp-rgb-lighting çekirdek modülü yüklenmemiş veya WMI MUX desteklenmiyor.",
                      css_classes=["warning-sub"], wrap=True))

        scroll_content.append(self.not_available)

        scroll.set_child(scroll_content)
        self.append(scroll)

        # Subtle developer signature
        sig = Gtk.Label(label="developed by yunusemreyl")
        sig.set_opacity(0.18)
        sig.set_halign(Gtk.Align.END)
        sig.set_margin_end(8)
        sig.set_margin_bottom(4)
        sig.add_css_class("stat-lbl")
        self.append(sig)
        self._signature_label = sig
        self.set_ui_scale("normal")

    def set_ui_scale(self, bucket, _width=0, _height=0):
        if bucket == "compact":
            self.set_spacing(14)
            self.set_margin_top(14)
            self.set_margin_start(16)
            self.set_margin_end(16)
            self.set_margin_bottom(14)
        elif bucket == "spacious":
            self.set_spacing(24)
            self.set_margin_top(36)
            self.set_margin_start(48)
            self.set_margin_end(48)
            self.set_margin_bottom(34)
        else:
            self.set_spacing(20)
            self.set_margin_top(30)
            self.set_margin_start(40)
            self.set_margin_end(40)
            self.set_margin_bottom(30)

        content = getattr(self, "_scroll_content", None)
        if content is not None:
            content.set_spacing(14 if bucket == "compact" else 24 if bucket == "spacious" else 20)

        self.mux_box.set_spacing(12 if bucket == "compact" else 26 if bucket == "spacious" else 20)

        icon_size = 64 if bucket == "compact" else 92 if bucket == "spacious" else 80
        for icon in (getattr(self, "_dgpu_icon", None), getattr(self, "_hybrid_icon", None)):
            if icon is not None:
                icon.set_pixel_size(icon_size)

        btn_size = 72 if bucket == "compact" else 96 if bucket == "spacious" else 84
        for mode in ("discrete", "hybrid"):
            btn = self.mode_buttons.get(mode)
            if btn is not None:
                btn.set_size_request(btn_size, btn_size)

        if hasattr(self, "warn_card") and self.warn_card is not None:
            self.warn_card.set_margin_top(6 if bucket == "compact" else 14 if bucket == "spacious" else 10)

        sig = getattr(self, "_signature_label", None)
        if sig is not None:
            sig.set_margin_end(6 if bucket == "compact" else 10 if bucket == "spacious" else 8)

    # ── Mode selection logic ──────────────────────────────────────────────────
    def _on_mode_select(self, mode):
        if mode == self.current_mode or not self.service or not self._mode_loaded:
            return

        # For the BIOS backend, first probe whether Advanced Optimus is present
        # by checking if a dry-run read matches immediately after write.
        # We delegate this to the daemon (SetGpuMode returns OK vs OK_REBOOT_REQUIRED).
        # Ask confirmation only when a reboot will be required.
        self._try_set_mode(mode)

    def _try_set_mode(self, mode):
        """Apply the mode; ask for reboot confirmation only if needed."""
        if not self.service:
            return

        try:
            result = self.service.SetGpuMode(mode)
        except Exception as e:
            self.status_label.set_label(f"{T('error')}: {e}")
            # Restore button to current mode
            self._restore_button()
            return

        if result == "OK":
            # Advanced Optimus or a tool that handled the switch live — no reboot needed
            self.current_mode = mode
            self.status_label.set_label(T("mode_set").format(mode=mode))
            self.warn_card.set_visible(False)

        elif result == "OK_REBOOT_REQUIRED":
            # Classic MUX — change staged, takes effect after reboot
            self.current_mode = mode
            self.warn_card.set_visible(True)
            self.status_label.set_label(T("mode_set").format(mode=mode))

            # Offer reboot now
            dialog = Gtk.MessageDialog(
                transient_for=self.get_root(), modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=T("restart"),
                secondary_text=T("restart_confirm").format(mode=mode),
            )
            dialog.connect("response", self._on_reboot_response)
            dialog.present()

        else:
            # Error
            self.status_label.set_label(f"{T('error')}: {result}")
            self._restore_button()

    def _restore_button(self):
        """Snap buttons back to the previously active mode."""
        mode_map = {
            "hybrid":     "hybrid",    "on-demand":  "hybrid",
            "discrete":   "discrete",  "dedicated":  "discrete",
            "nvidia":     "discrete",
        }
        mapped = mode_map.get(self.current_mode, self.current_mode)
        if mapped in self.mode_buttons:
            self.mode_buttons[mapped].set_active(True)

    def _on_reboot_response(self, dialog, response):
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            try:
                subprocess.run(["systemctl", "reboot"], check=True, timeout=10)
            except Exception as e:
                self.status_label.set_label(
                    f"{T('mode_set').format(mode=self.current_mode)} "
                    f"({T('error')}: reboot: {e})")

    # ── Data refresh ──────────────────────────────────────────────────────────
    def _refresh(self):
        if not self.service:
            return
        try:
            info = json.loads(self.service.GetGpuInfo())
            self.backend      = info.get("backend", "none")
            self.current_mode = info.get("mode",    "unknown")
            available         = info.get("available", False)

            if available:
                self.not_available.set_visible(False)
                self.mux_box.set_visible(True)
                self.mode_val.set_label(self.current_mode.capitalize())
                self.backend_val.set_label(_BACKEND_LABELS.get(self.backend, self.backend))

                mode_map = {
                    "hybrid":     "hybrid",    "on-demand":  "hybrid",
                    "discrete":   "discrete",  "dedicated":  "discrete",
                    "nvidia":     "discrete",
                }
                mapped = mode_map.get(self.current_mode, self.current_mode)
                if mapped in self.mode_buttons:
                    self._mode_loaded = False
                    self.mode_buttons[mapped].set_active(True)
                    self._mode_loaded = True

                displays = info.get("displays", [])
                if displays:
                    disp_texts = [f"{d['display']} → {d['gpu']}" for d in displays]
                    self.displays_val.set_label("\n".join(disp_texts))
                else:
                    self.displays_val.set_label("Yok")
            else:
                self.not_available.set_visible(True)
                self.mux_box.set_visible(False)
                self.status_label.set_label(T("mux_not_found"))
                if hasattr(self, 'displays_val'):
                    self.displays_val.set_label("")
        except Exception:
            pass
