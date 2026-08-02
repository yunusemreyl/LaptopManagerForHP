#!/usr/bin/env python3
"""Keyboard & Shortcuts Page — tailored for OMEN/Victus hotkeys."""
import os, platform, subprocess, json
# pyrefly: ignore [missing-import]
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

def T(k):
    from i18n import T as _T
    return _T(k)

def _detect_model_type():
    for dmi_file in ("/sys/devices/virtual/dmi/id/product_name",
                     "/sys/devices/virtual/dmi/id/product_family"):
        try:
            if os.path.exists(dmi_file):
                with open(dmi_file) as f:
                    name = f.read().strip().lower()
                    if "victus" in name: return "victus"
                    if "omen" in name: return "omen"
        except Exception: pass
    return "omen"

class KeyboardPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self.service = service
        
    def set_service(self, service):
        self.service = service
        self._sync_state()
        
        self.model_type = _detect_model_type()
        self.branding = "OMEN" if self.model_type == "omen" else "Victus"
        
        # Resolve logo path
        self.logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "images", "omenlogo.png")
        if not os.path.exists(self.logo_path):
            self.logo_path = "/usr/share/hp-manager/images/omenlogo.png"
            
        self._build_ui()

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
        title = Gtk.Label(label=T("keyboard_shortcuts"), xalign=0, css_classes=["title-1"])
        title_box.append(title)
        desc = Gtk.Label(label=T("shortcuts_desc"), xalign=0, css_classes=["dim-label"])
        title_box.append(desc)
        header.append(title_box)
        root.append(header)

        root.append(Gtk.Separator())

        # ── KEYBOARD FIXES (The main meat) ──
        fix_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        fix_card.add_css_class("card")
        self._fix_card = fix_card
        
        fix_header = Gtk.Box(spacing=10)
        fix_header.append(Gtk.Image.new_from_icon_name("system-run-symbolic"))
        fix_header.append(Gtk.Label(label=T("driver_status"), xalign=0, css_classes=["heading"]))
        fix_card.append(fix_header)

        # PrtSc Fix
        prtsc_box = Gtk.Box(spacing=15)
        prtsc_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        prtsc_info.append(Gtk.Label(label=T("prt_sc_fix"), xalign=0, css_classes=["title-4"]))
        prtsc_info.append(Gtk.Label(label=T("prt_sc_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        prtsc_box.append(prtsc_info)
        self.prtsc_sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        prtsc_box.append(self.prtsc_sw)
        fix_card.append(prtsc_box)

        fix_card.append(Gtk.Separator())

        # F1 Fix
        f1_box = Gtk.Box(spacing=15)
        f1_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        f1_info.append(Gtk.Label(label=T("f1_fix"), xalign=0, css_classes=["title-4"]))
        f1_info.append(Gtk.Label(label=T("f1_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        f1_box.append(f1_info)
        self.f1_sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        f1_box.append(self.f1_sw)
        fix_card.append(f1_box)

        root.append(fix_card)
        
        # ── MACROS (Commands) ──
        macro_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        macro_card.add_css_class("card")
        self._macro_card = macro_card
        
        macro_header = Gtk.Box(spacing=10)
        macro_header.append(Gtk.Image.new_from_icon_name("preferences-desktop-keyboard-shortcuts-symbolic"))
        macro_header.append(Gtk.Label(label="Macros & Commands", xalign=0, css_classes=["heading"]))
        macro_card.append(macro_header)
        
        macro_desc = Gtk.Label(label="Assign terminal commands or click the icon to choose an application.", xalign=0, css_classes=["dim-label"])
        macro_card.append(macro_desc)
        
        self.macro_entries = {}
        for m_id, m_name in [("omen_key", "Omen Key"), ("calculator", "Calculator Key")]:
            m_box = Gtk.Box(spacing=15)
            lbl = Gtk.Label(label=m_name, xalign=0, css_classes=["title-4"])
            lbl.set_size_request(130, -1)
            m_box.append(lbl)
            entry = Gtk.Entry(placeholder_text="Terminal command...", hexpand=True)
            self.macro_entries[m_id] = entry
            m_box.append(entry)
            
            btn = Gtk.Button(icon_name="application-x-executable-symbolic")
            btn.set_tooltip_text("Choose installed application")
            btn.connect("clicked", lambda b, e=entry: self._show_app_chooser(e))
            m_box.append(btn)
            
            macro_card.append(m_box)
            
        root.append(macro_card)

        # Footer Action
        footer = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        self._footer_box = footer
        self.apply_btn = Gtk.Button(label=T("apply_shortcuts"))
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", self._on_apply)
        footer.append(self.apply_btn)
        root.append(footer)

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

        if hasattr(self, "_keys_card") and self._keys_card is not None:
            self._keys_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_fix_card") and self._fix_card is not None:
            self._fix_card.set_spacing(14 if bucket == "compact" else 24 if bucket == "spacious" else 20)

        if hasattr(self, "apply_btn") and self.apply_btn is not None:
            self.apply_btn.set_size_request(150 if bucket == "compact" else 210 if bucket == "spacious" else 180, 38 if bucket == "compact" else 46 if bucket == "spacious" else 42)

    def _make_shortcut_row(self, title, desc, icon_name):
        row = Gtk.Box(spacing=15)
        if icon_name.startswith("/") or icon_name.endswith(".png"):
            if os.path.exists(icon_name):
                from gi.repository import Gdk
                texture = Gdk.Texture.new_from_filename(icon_name)
                icon = Gtk.Image.new_from_paintable(texture)
            else:
                icon = Gtk.Image.new_from_icon_name("image-missing")
        else:
            icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        row.append(icon)
        
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.append(Gtk.Label(label=title, xalign=0))
        info.append(Gtk.Label(label=desc, xalign=0, css_classes=["stat-lbl"]))
        row.append(info)
        return row

    def _sync_state(self):
        if not self.service: return
        try:
            st = json.loads(self.service.GetState())
            self.prtsc_sw.set_active(st.get("prtsc_fix", False))
            self.f1_sw.set_active(st.get("f1_fix", False))
        except Exception: pass
        
        try:
            config_path = os.path.expanduser("~/.config/hp-manager/macros.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    macros = json.load(f)
                for k, v in macros.items():
                    if k in getattr(self, "macro_entries", {}):
                        self.macro_entries[k].set_text(v)
        except Exception: pass

    def _on_apply(self, btn):
        if not self.service: return
        p = self.prtsc_sw.get_active()
        f = self.f1_sw.get_active()
        
        try:
            macros = {}
            for k, entry in getattr(self, "macro_entries", {}).items():
                t = entry.get_text().strip()
                if t:
                    macros[k] = t
            config_dir = os.path.expanduser("~/.config/hp-manager")
            os.makedirs(config_dir, exist_ok=True)
            with open(os.path.join(config_dir, "macros.json"), "w") as f_obj:
                json.dump(macros, f_obj)
        except Exception as e:
            print(f"Failed to save macros: {e}")
            
        try:
            self.service.SetKeyboardFixes(p, f)
            
            # Show success toast or info
            toast = Gtk.MessageDialog(
                transient_for=self.get_root(),
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=T("hwdb_applied")
            )
            toast.connect("response", lambda r, id: r.destroy())
            toast.present()
        except Exception as e:
            print(f"Apply shortcuts failed: {e}")

    def _show_app_chooser(self, entry_widget):
        class AppChooserDialog(Gtk.Dialog):
            def __init__(self, parent, entry):
                super().__init__(title="Select Application", transient_for=parent, use_header_bar=1)
                self.set_default_size(400, 500)
                self.entry = entry
                
                box = self.get_content_area()
                box.set_spacing(10)
                box.set_margin_start(10)
                box.set_margin_end(10)
                box.set_margin_top(10)
                box.set_margin_bottom(10)
                
                from gi.repository import Gio
                apps = Gio.AppInfo.get_all()
                apps = sorted([a for a in apps if a.should_show()], key=lambda x: (x.get_name() or "").lower())
                
                scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
                scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                listbox = Gtk.ListBox()
                listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
                listbox.connect("row-activated", self.on_row_activated)
                
                for app in apps:
                    row = Gtk.ListBoxRow()
                    hbox = Gtk.Box(spacing=15)
                    hbox.set_margin_start(10)
                    hbox.set_margin_end(10)
                    hbox.set_margin_top(8)
                    hbox.set_margin_bottom(8)
                    
                    icon = app.get_icon()
                    if icon:
                        img = Gtk.Image.new_from_gicon(icon)
                    else:
                        img = Gtk.Image.new_from_icon_name("application-x-executable")
                    img.set_pixel_size(32)
                    hbox.append(img)
                    
                    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    vbox.append(Gtk.Label(label=app.get_name(), xalign=0))
                    vbox.append(Gtk.Label(label=app.get_description() or "", xalign=0, css_classes=["dim-label", "caption"]))
                    hbox.append(vbox)
                    
                    row.set_child(hbox)
                    row.app_info = app
                    listbox.append(row)
                    
                scroll.set_child(listbox)
                box.append(scroll)
                
            def on_row_activated(self, listbox, row):
                app = row.app_info
                cmd = app.get_executable()
                desktop_id = app.get_id()
                if desktop_id:
                    cmd = f"gtk-launch {desktop_id}"
                self.entry.set_text(cmd)
                self.destroy()

        dialog = AppChooserDialog(self.get_root(), entry_widget)
        dialog.present()

