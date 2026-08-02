import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import urllib.parse
import subprocess
import json

def T(k):
    from i18n import T as _T
    try:
        return _T(k)
    except ImportError:
        return k.replace("_", " ").title()

class MappingWizard(Gtk.Box):
    def __init__(self, dump_data_json=""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add_css_class("settings-card")
        self.set_margin_bottom(16)
        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_padding(16)
        
        self.dump_data_json = dump_data_json
        self.current_key_idx = 0
        self.mapping = {}
        
        self._build_ui()
        self._check_device()

    def set_padding(self, padding):
        self.set_margin_top(padding)
        self.set_margin_bottom(padding)
        self.set_margin_start(padding)
        self.set_margin_end(padding)

    def _build_ui(self):
        # Header
        header = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        icon = Gtk.Label(label="⌨️")
        self.title_lbl = Gtk.Label(label=T("per_key_wizard"), xalign=0)
        self.title_lbl.add_css_class("section-title")
        header.append(icon)
        header.append(self.title_lbl)
        self.append(header)
        
        # Info Box (shown initially or if no device)
        self.info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        desc = Gtk.Label(
            label=T("wizard_start_desc"),
            wrap=True, xalign=0
        )
        desc.add_css_class("settings-row-sublabel")
        self.info_box.append(desc)
        
        self.start_btn = Gtk.Button(label=T("wizard_btn"))
        self.start_btn.add_css_class("suggested-action")
        self.start_btn.connect("clicked", self._on_start_clicked)
        self.info_box.append(self.start_btn)
        
        self.status_lbl = Gtk.Label(label="", xalign=0)
        self.status_lbl.add_css_class("settings-row-sublabel")
        self.info_box.append(self.status_lbl)
        
        self.append(self.info_box)
        
        # Wizard Box (shown during mapping)
        self.wizard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.wizard_box.set_visible(False)
        
        self.progress_lbl = Gtk.Label(label=T("wizard_progress"), xalign=0)
        self.progress_lbl.add_css_class("settings-row-label")
        self.wizard_box.append(self.progress_lbl)
        
        instr = Gtk.Label(
            label=T("wizard_instruction"),
            wrap=True, xalign=0
        )
        instr.add_css_class("settings-row-sublabel")
        self.wizard_box.append(instr)
        
        self.key_entry = Gtk.Entry(placeholder_text="Enter key name...")
        self.key_entry.connect("activate", self._on_next_clicked)
        self.wizard_box.append(self.key_entry)
        
        btn_box = Gtk.Box(spacing=12)
        
        self.skip_btn = Gtk.Button(label=T("wizard_skip"))
        self.skip_btn.connect("clicked", self._on_skip_clicked)
        btn_box.append(self.skip_btn)
        
        self.finish_btn = Gtk.Button(label=T("wizard_cancel"))
        self.finish_btn.connect("clicked", self._on_cancel_clicked)
        btn_box.append(self.finish_btn)
        
        self.wizard_box.append(btn_box)
        self.append(self.wizard_box)
        
        self.connect("destroy", self._on_destroy)

    def _check_device(self):
        # Allow starting the wizard anyway for now, it's harmless if it fails.
        pass

    def _on_start_clicked(self, btn):
        self.info_box.set_visible(False)
        self.wizard_box.set_visible(True)
        self.current_key_idx = 0
        self.mapping = {}
        self._light_current_key()
        self.key_entry.grab_focus()

    def _light_current_key(self):
        self.progress_lbl.set_label(f"Key {self.current_key_idx + 1} of 104")
        self.key_entry.set_text("")
        try:
            from pydbus import SystemBus
            bus = SystemBus()
            svc = bus.get("com.yyl.hpmanager.rgb")
            svc.TestSingleKey(self.current_key_idx, 255, 0, 0)
        except Exception as e:
            print(f"Error testing key: {e}")

    def _on_next_clicked(self, *args):
        val = self.key_entry.get_text().strip()
        if val:
            self.mapping[str(self.current_key_idx)] = val
        self._advance()

    def _on_skip_clicked(self, btn):
        self._advance()

    def _advance(self):
        self.current_key_idx += 1
        if self.current_key_idx >= 104:
            self._on_finish_clicked(None)
        else:
            self._light_current_key()
            self.key_entry.grab_focus()

    def _on_cancel_clicked(self, btn):
        self.wizard_box.set_visible(False)
        self.info_box.set_visible(True)
        self._restore_rgb_state()

    def _on_finish_clicked(self):
        self.wizard_box.set_visible(False)
        self.info_box.set_visible(True)
        self.status_lbl.set_label("Saving mapping...")
        self._restore_rgb_state()
        
        try:
            from pydbus import SystemBus
            bus = SystemBus()
            svc = bus.get("com.yyl.hpmanager.rgb")
            map_json = json.dumps(self.mapping)
            svc.SavePerKeyMap(map_json)
            self.status_lbl.set_label("✅ " + T("wizard_complete"))
        except Exception as e:
            self.status_lbl.set_label(f"Error saving map: {e}")

    def _restore_rgb_state(self):
        try:
            # rgb_service will eventually need a RestoreState but it re-applies automatically right now via DBus Ping or similar.
            pass
        except Exception as e:
            print(f"Error restoring RGB state: {e}")

    def _on_destroy(self, *args):
        if self.wizard_box.get_visible():
            self._restore_rgb_state()
