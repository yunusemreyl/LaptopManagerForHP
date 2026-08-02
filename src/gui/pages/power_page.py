#!/usr/bin/env python3
"""Power Tuning & Undervolt Page — advanced CPU/GPU power management."""
import os, json
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

def T(k):
    from i18n import T as _T
    return _T(k)

class PowerPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self.service = service
        
        self.logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "images", "omenlogo.png")
        if not os.path.exists(self.logo_path):
            self.logo_path = "/usr/share/hp-manager/images/omenlogo.png"
            
        self._build_ui()

    def set_service(self, service):
        self.service = service
        self._sync_state()

    def _build_ui(self):
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        root.set_margin_top(24)
        root.set_margin_start(32)
        root.set_margin_end(32)
        root.set_margin_bottom(24)
        scroll.set_child(root)
        self.append(scroll)
        self._root_box = root

        # Header with Logo
        header = Gtk.Box(spacing=15, valign=Gtk.Align.CENTER)
        self._header_box = header
        if os.path.exists(self.logo_path):
            from gi.repository import Gdk
            texture = Gdk.Texture.new_from_filename(self.logo_path)
            img = Gtk.Image.new_from_paintable(texture)
            img.set_pixel_size(48)
            header.append(img)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        title_row = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
        title_row.append(Gtk.Label(label=T("power_tuning"), xalign=0, css_classes=["title-1"]))
        
        badge = Gtk.Box(valign=Gtk.Align.CENTER)
        badge.add_css_class("osd")
        lbl = Gtk.Label(label="EXPERIMENTAL", css_classes=["caption", "accent"])
        lbl.set_margin_start(8)
        lbl.set_margin_end(8)
        lbl.set_margin_top(2)
        lbl.set_margin_bottom(2)
        badge.append(lbl)
        title_row.append(badge)
        
        title_box.append(title_row)
        
        desc = Gtk.Label(label=T("power_tuning_desc"), xalign=0, css_classes=["dim-label"])
        title_box.append(desc)
        header.append(title_box)
        root.append(header)

        root.append(Gtk.Separator())

        # Determine CPU Vendor and Model for compatibility
        is_amd = False
        cpu_model = "Unknown CPU"
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "AuthenticAMD" in line:
                        is_amd = True
                    if line.startswith("model name") and cpu_model == "Unknown CPU":
                        cpu_model = line.split(":", 1)[1].strip()
        except Exception:
            pass

        # Undervolt support logic
        uv_supported = False
        if is_amd:
            # The standard ryzenadj tool does not support Curve Optimizer (--curve-opt).
            # We disable it in the UI to avoid confusion until a proper tool (e.g., amdctl or a ryzenadj fork) is supported.
            uv_supported = False
        else:
            # Intel: Any CPU from Haswell (4th Gen) up to 11th Gen usually supports it.
            # 12th Gen and newer only support it on unlocked HX/HK series.
            import re
            m = re.search(r'i[3579]-(\d+)', cpu_model)
            if m:
                gen_str = m.group(1)
                gen = int(gen_str[0]) if len(gen_str) == 4 else int(gen_str[0:2]) if len(gen_str) == 5 else 0
                
                if 4 <= gen <= 11:
                    uv_supported = True
                elif gen >= 12:
                    if "HX" in cpu_model or "HK" in cpu_model:
                        uv_supported = True
            else:
                # Fallback for older Xeons, Core M, or unrecognized names
                if "HX" in cpu_model or "HK" in cpu_model or "v5" in cpu_model or "v6" in cpu_model:
                    uv_supported = True

        # ── UNDERVOLT CARD ──
        uv_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        uv_card.add_css_class("card")
        self._uv_card = uv_card
        
        uv_header = Gtk.Box(spacing=10)
        uv_header.append(Gtk.Image.new_from_icon_name("system-run-symbolic"))
        uv_title = "Curve Optimizer (AMD)" if is_amd else T("undervolt_label")
        uv_header.append(Gtk.Label(label=uv_title, xalign=0, css_classes=["heading"]))
        uv_card.append(uv_header)

        uv_box = Gtk.Box(spacing=15)
        uv_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        uv_info.append(Gtk.Label(label=uv_title, xalign=0, css_classes=["title-4"]))
        uv_info.append(Gtk.Label(label=T("undervolt_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        
        if not uv_supported:
            warn_lbl = Gtk.Label(label=f"Not supported by {cpu_model}", xalign=0, css_classes=["caption", "error"])
            uv_info.append(warn_lbl)
            
        uv_box.append(uv_info)
        
        # AMD Curve Optimizer goes negative (-30 is common), Intel is also negative (mV)
        self.uv_spin = Gtk.SpinButton.new_with_range(-200, 0, 5)
        self.uv_spin.set_valign(Gtk.Align.CENTER)
        uv_box.append(self.uv_spin)
        uv_suffix = "Steps" if is_amd else "mV"
        uv_box.append(Gtk.Label(label=uv_suffix, valign=Gtk.Align.CENTER))
        uv_card.append(uv_box)
        
        if not uv_supported:
            self.uv_spin.set_sensitive(False)
            uv_card.set_sensitive(False)
        
        root.append(uv_card)

        # ── TCC OFFSET CARD ──
        tcc_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        tcc_card.add_css_class("card")
        self._tcc_card = tcc_card
        
        tcc_header = Gtk.Box(spacing=10)
        tcc_header.append(Gtk.Image.new_from_icon_name("weather-clear-symbolic"))
        tcc_title = "Thermal Limit Offset (AMD)" if is_amd else T("tcc_label")
        tcc_header.append(Gtk.Label(label=tcc_title, xalign=0, css_classes=["heading"]))
        tcc_card.append(tcc_header)

        tcc_box = Gtk.Box(spacing=15)
        tcc_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        tcc_info.append(Gtk.Label(label=tcc_title, xalign=0, css_classes=["title-4"]))
        tcc_info.append(Gtk.Label(label=T("tcc_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        tcc_box.append(tcc_info)
        
        self.tcc_spin = Gtk.SpinButton.new_with_range(0, 60, 1)
        self.tcc_spin.set_valign(Gtk.Align.CENTER)
        tcc_box.append(self.tcc_spin)
        tcc_card.append(tcc_box)
        
        root.append(tcc_card)

        # ── POWER LIMITS CARD ──
        pl_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        pl_card.add_css_class("card")
        self._pl_card = pl_card
        
        pl_header = Gtk.Box(spacing=10)
        pl_header.append(Gtk.Image.new_from_icon_name("battery-good-symbolic"))
        pl_header.append(Gtk.Label(label=T("power_limits_label"), xalign=0, css_classes=["heading"]))
        pl_card.append(pl_header)

        pl_sw_box = Gtk.Box(spacing=15)
        pl_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        pl_info.append(Gtk.Label(label=T("power_limits_label"), xalign=0, css_classes=["title-4"]))
        pl_info.append(Gtk.Label(label=T("power_limits_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        pl_sw_box.append(pl_info)
        self.pl_sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        pl_sw_box.append(self.pl_sw)
        pl_card.append(pl_sw_box)

        pl_card.append(Gtk.Separator())

        pl1_box = Gtk.Box(spacing=15)
        pl1_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        pl1_info.append(Gtk.Label(label=T("pl1_w"), xalign=0, css_classes=["title-4"]))
        pl1_box.append(pl1_info)
        self.pl1_spin = Gtk.SpinButton.new_with_range(15, 150, 5)
        self.pl1_spin.set_valign(Gtk.Align.CENTER)
        pl1_box.append(self.pl1_spin)
        pl1_box.append(Gtk.Label(label="W", valign=Gtk.Align.CENTER))
        pl_card.append(pl1_box)

        pl2_box = Gtk.Box(spacing=15)
        pl2_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        pl2_info.append(Gtk.Label(label=T("pl2_w"), xalign=0, css_classes=["title-4"]))
        pl2_box.append(pl2_info)
        self.pl2_spin = Gtk.SpinButton.new_with_range(15, 200, 5)
        self.pl2_spin.set_valign(Gtk.Align.CENTER)
        pl2_box.append(self.pl2_spin)
        pl2_box.append(Gtk.Label(label="W", valign=Gtk.Align.CENTER))
        pl_card.append(pl2_box)

        root.append(pl_card)

        # Footer Action
        footer = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        self._footer_box = footer
        self.apply_btn = Gtk.Button(label=T("apply_power"))
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", self._on_apply)
        footer.append(self.apply_btn)
        root.append(footer)
        
        # Attribution
        attr_box = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.END)
        attr_box.set_margin_top(8)
        attr_text = "powered by flygoat/RyzenAdj" if is_amd else "powered by georgewhewell/undervolt"
        attr_label = Gtk.Label(label=attr_text, css_classes=["dim-label"])
        attr_label.set_opacity(0.4)
        attr_box.append(attr_label)
        root.append(attr_box)

        self._sync_state()
        self.set_ui_scale("normal")

    def set_ui_scale(self, bucket, _width=0, _height=0):
        root = getattr(self, "_root_box", None)
        if root is not None:
            if bucket == "compact":
                root.set_spacing(16)
                root.set_margin_top(12)
                root.set_margin_start(14)
                root.set_margin_end(14)
                root.set_margin_bottom(12)
            elif bucket == "spacious":
                root.set_spacing(28)
                root.set_margin_top(30)
                root.set_margin_start(40)
                root.set_margin_end(40)
                root.set_margin_bottom(28)
            else:
                root.set_spacing(24)
                root.set_margin_top(24)
                root.set_margin_start(32)
                root.set_margin_end(32)
                root.set_margin_bottom(24)

        if hasattr(self, "_header_box") and self._header_box is not None:
            self._header_box.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_uv_card") and self._uv_card is not None:
            self._uv_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_tcc_card") and self._tcc_card is not None:
            self._tcc_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_pl_card") and self._pl_card is not None:
            self._pl_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "apply_btn") and self.apply_btn is not None:
            self.apply_btn.set_size_request(150 if bucket == "compact" else 210 if bucket == "spacious" else 180, 38 if bucket == "compact" else 46 if bucket == "spacious" else 42)

    def _sync_state(self):
        if not self.service: return
        try:
            raw = self.service.GetPowerProfile()
            st = json.loads(raw)
            self.uv_spin.set_value(st.get("undervolt_mv", 0))
            self.tcc_spin.set_value(st.get("tcc_offset", 0))
            self.pl_sw.set_active(st.get("pl_enabled", False))
            self.pl1_spin.set_value(st.get("pl1_w", 45))
            self.pl2_spin.set_value(st.get("pl2_w", 80))
        except Exception: pass

    def _on_apply(self, btn):
        if not self.service: return
        uv = int(self.uv_spin.get_value())
        tcc = int(self.tcc_spin.get_value())
        pl_en = self.pl_sw.get_active()
        pl1 = int(self.pl1_spin.get_value())
        pl2 = int(self.pl2_spin.get_value())
        
        try:
            self.service.SetUndervolt(uv)
            self.service.SetTccOffset(tcc)
            self.service.SetPowerLimits(pl_en, pl1, pl2)
            
            toast = Gtk.MessageDialog(
                transient_for=self.get_root(),
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=T("power_applied")
            )
            toast.connect("response", lambda r, id: r.destroy())
            toast.present()
        except Exception as e:
            print(f"Apply power tuning failed: {e}")
