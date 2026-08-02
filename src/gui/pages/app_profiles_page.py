#!/usr/bin/env python3
"""
OMEN Command Center for Linux — Dedicated Application Profiles Page.
Contributed by CodesRahul96
"""
import os, json
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "daemon"))
sys.path.insert(0, "/usr/libexec/hp-manager")

from common.app_launchers import parse_exec_command

def T(k):
    from i18n import T as _T
    return _T(k)

class AppProfilesPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self.power_service = service
        
        # Resolve logo path
        self.logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "images", "omenlogo.png")
        if not os.path.exists(self.logo_path):
            self.logo_path = "/usr/share/hp-manager/images/omenlogo.png"

        self._build_ui()
        
        # Periodic refresh timeout (every 2 seconds)
        self._refresh_timer_id = GLib.timeout_add_seconds(2, self._on_periodic_refresh)

    def _on_periodic_refresh(self):
        if self.get_mapped() and self.power_service:
            self._refresh_app_profiles()
        return True

    def cleanup(self):
        if hasattr(self, "_refresh_timer_id") and self._refresh_timer_id is not None:
            GLib.source_remove(self._refresh_timer_id)
            self._refresh_timer_id = None

    def set_power_service(self, power_service):
        self.power_service = power_service
        GLib.idle_add(self._refresh_app_profiles)

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

        # ── Header with Logo ──
        header = Gtk.Box(spacing=15, valign=Gtk.Align.CENTER)
        self._header_box = header
        if os.path.exists(self.logo_path):
            texture = Gdk.Texture.new_from_filename(self.logo_path)
            img = Gtk.Image.new_from_paintable(texture)
            img.set_pixel_size(48)
            header.append(img)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label=T("app_profiles"), xalign=0, css_classes=["title-1"])
        title_box.append(title)
        desc = Gtk.Label(label=T("app_profiles_desc"), xalign=0, css_classes=["dim-label"])
        title_box.append(desc)
        header.append(title_box)
        root.append(header)

        root.append(Gtk.Separator())

        # ── Toggle Switch Card ──
        toggle_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        toggle_card.add_css_class("card")
        self._toggle_card = toggle_card
        
        lbl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        lbl_box.append(Gtk.Label(label=T("app_profiles"), xalign=0, css_classes=["title-4"]))
        lbl_box.append(Gtk.Label(label=T("app_profiles_desc"), xalign=0, css_classes=["dim-label"], wrap=True))
        toggle_card.append(lbl_box)
        
        self.app_profiles_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.app_profiles_switch.connect("state-set", self._on_app_profiles_toggle)
        toggle_card.append(self.app_profiles_switch)
        root.append(toggle_card)

        # ── Add/Edit Mapping Form Card ──
        add_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        add_card.add_css_class("card")
        self._add_card = add_card
        
        self.form_heading_lbl = Gtk.Label(label=T("add"), xalign=0, css_classes=["heading"])
        add_card.append(self.form_heading_lbl)

        form_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        
        self.add_app_entry = Gtk.Entry()
        self.add_app_entry.set_placeholder_text(T("placeholder_app"))
        self.add_app_entry.set_hexpand(True)
        self.add_app_entry.set_valign(Gtk.Align.CENTER)
        form_box.append(self.add_app_entry)
        
        self.add_profile_dd = Gtk.DropDown(model=Gtk.StringList.new([T("saver"), T("balanced"), T("performance")]))
        self.add_profile_dd.set_valign(Gtk.Align.CENTER)
        form_box.append(self.add_profile_dd)
        
        self.add_category_dd = Gtk.DropDown(model=Gtk.StringList.new([T("game"), T("program"), T("other")]))
        self.add_category_dd.set_valign(Gtk.Align.CENTER)
        form_box.append(self.add_category_dd)
        
        self.add_fan_dd = Gtk.DropDown(model=Gtk.StringList.new([T("fan_default"), T("fan_auto"), T("fan_max")]))
        self.add_fan_dd.set_valign(Gtk.Align.CENTER)
        form_box.append(self.add_fan_dd)
        
        self.add_theme_dd = Gtk.DropDown(model=Gtk.StringList.new([T("theme_default"), T("theme_dark"), T("theme_light")]))
        self.add_theme_dd.set_valign(Gtk.Align.CENTER)
        self.add_theme_dd.set_tooltip_text(T("theme_label"))
        form_box.append(self.add_theme_dd)
        
        self.add_btn = Gtk.Button(label=T("add"))
        self.add_btn.add_css_class("suggested-action")
        self.add_btn.set_valign(Gtk.Align.CENTER)
        self.add_btn.connect("clicked", self._add_app_profile)
        form_box.append(self.add_btn)

        self.cancel_edit_btn = Gtk.Button(label="✕")
        self.cancel_edit_btn.add_css_class("update-btn")
        self.cancel_edit_btn.set_valign(Gtk.Align.CENTER)
        self.cancel_edit_btn.set_visible(False)
        self.cancel_edit_btn.set_tooltip_text(T("wizard_cancel"))
        self.cancel_edit_btn.connect("clicked", self._cancel_edit_mode)
        form_box.append(self.cancel_edit_btn)
        
        add_card.append(form_box)
        root.append(add_card)

        # ── Configuration Mappings List Card ──
        self.list_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.list_card.add_css_class("card")
        
        list_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, valign=Gtk.Align.CENTER)
        list_header_box.append(Gtk.Label(label=T("app_profiles"), xalign=0, hexpand=True, css_classes=["heading"]))
        
        # View switcher (Grid vs List)
        self.view_mode = "grid"  # default to professional grid card view
        switcher_box = Gtk.Box(spacing=4)
        switcher_box.add_css_class("inner-panel")
        switcher_box.set_valign(Gtk.Align.CENTER)
        
        self.btn_grid_view = Gtk.Button(label="░")
        self.btn_grid_view.set_tooltip_text("Grid View")
        self.btn_grid_view.add_css_class("update-btn")
        self.btn_grid_view.connect("clicked", lambda *_: self._set_view_mode("grid"))
        switcher_box.append(self.btn_grid_view)
        
        self.btn_list_view = Gtk.Button(label="≡")
        self.btn_list_view.set_tooltip_text("List View")
        self.btn_list_view.add_css_class("update-btn")
        self.btn_list_view.connect("clicked", lambda *_: self._set_view_mode("list"))
        switcher_box.append(self.btn_list_view)
        
        list_header_box.append(switcher_box)
        self.list_card.append(list_header_box)
        
        self.app_profiles_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.list_card.append(self.app_profiles_list_box)
        root.append(self.list_card)

        # Initialize Auto-Suggest completions
        self._editing_app_key = None
        self._init_autocomplete()

        self._refresh_app_profiles()
        self.set_ui_scale("normal")

    def _set_view_mode(self, mode):
        if self.view_mode != mode:
            self.view_mode = mode
            self._refresh_app_profiles()

    def _init_autocomplete(self):
        self._selected_exec_name = None
        self._selected_icon_name = None
        self.list_store = Gtk.ListStore(str, str, str)  # display_name, exec_name, icon_name
        self.completion = Gtk.EntryCompletion()
        self.completion.set_model(self.list_store)
        self.completion.set_text_column(0)
        self.completion.set_inline_completion(False)
        self.completion.set_popup_completion(True)
        self.completion.set_minimum_key_length(1)
        self.completion.set_match_func(self._completion_match_func)
        self.completion.connect("match-selected", self._on_completion_match_selected)
        
        self.add_app_entry.set_completion(self.completion)
        
        import threading
        threading.Thread(target=self._scan_installed_apps, daemon=True).start()

    def _completion_match_func(self, completion, key, tree_iter):
        model = completion.get_model()
        display_text = model.get_value(tree_iter, 0)
        if not key:
            return True
        key = key.lower()
        return key in display_text.lower()

    def _on_completion_match_selected(self, completion, model, tree_iter):
        display_name = model.get_value(tree_iter, 0)
        exec_name = model.get_value(tree_iter, 1)
        icon_name = model.get_value(tree_iter, 2)
        self.add_app_entry.set_text(display_name)
        self._selected_exec_name = exec_name
        self._selected_icon_name = icon_name
        self.add_app_entry.set_position(-1)
        return True

    def _scan_installed_apps(self):
        import glob
        apps = []
        seen = set()
        paths = ["/usr/share/applications/*.desktop", os.path.expanduser("~/.local/share/applications/*.desktop")]
        for path_glob in paths:
            for filepath in glob.glob(path_glob):
                try:
                    with open(filepath, "r", errors="ignore") as f:
                        name = None
                        exec_cmd = None
                        icon_name = None
                        in_desktop_entry = False
                        for line in f:
                            line_strip = line.strip()
                            if line_strip == "[Desktop Entry]":
                                in_desktop_entry = True
                                continue
                            elif line_strip.startswith("[") and line_strip.endswith("]"):
                                in_desktop_entry = False
                            
                            if not in_desktop_entry:
                                continue
                                
                            if line.startswith("Name="):
                                name = line.split("=", 1)[1].strip()
                            elif line.startswith("Exec="):
                                exec_raw = line.split("=", 1)[1].strip()
                                if exec_raw:
                                    exec_cmd = parse_exec_command(exec_raw)
                            elif line.startswith("Icon="):
                                icon_name = line.split("=", 1)[1].strip()
                                    
                            if name and exec_cmd:
                                key = (name, exec_cmd, icon_name or exec_cmd)
                                if (name, exec_cmd) not in seen:
                                    seen.add((name, exec_cmd))
                                    apps.append(key)
                                break
                except Exception:
                    pass
        
        common_tools = [
            ("Android Studio", "studio", "android-studio"),
            ("Android Studio", "java", "android-studio"),
            ("Steam", "steam", "steam"),
            ("Visual Studio Code", "code", "vscode"),
            ("Firefox", "firefox", "firefox"),
            ("Google Chrome", "chrome", "google-chrome"),
            ("Google Chrome", "google-chrome", "google-chrome"),
            ("Discord", "discord", "discord"),
            ("Spotify", "spotify", "spotify"),
            ("Minecraft", "minecraft", "minecraft"),
            ("Lutris", "lutris", "lutris"),
            ("Heroic Games Launcher", "heroic", "heroic"),
            ("OBS Studio", "obs", "obs"),
            ("VLC Media Player", "vlc", "vlc"),
            ("Wine", "wine", "wine"),
            ("IntelliJ IDEA", "idea", "intellij-idea-community"),
            ("PyCharm", "pycharm", "pycharm"),
            ("WebStorm", "webstorm", "webstorm"),
            ("Terminal", "bash", "utilities-terminal"),
            ("Qemu/KVM", "qemu-system-x86_64", "qemu"),
        ]
        for name, exec_cmd, icon in common_tools:
            if (name, exec_cmd) not in seen:
                seen.add((name, exec_cmd))
                apps.append((name, exec_cmd, icon))

        apps.sort(key=lambda x: x[0].lower())

        def update_store():
            for name, exec_cmd, icon in apps:
                display_name = f"{name} ({exec_cmd})"
                self.list_store.append([display_name, exec_cmd, icon])
            return False

        GLib.idle_add(update_store)

    def _refresh_app_profiles(self):
        if not self.power_service:
            self.app_profiles_switch.set_sensitive(False)
            self.list_card.set_visible(False)
            self._add_card.set_visible(False)
            return False
        
        self.app_profiles_switch.set_sensitive(True)
        self.list_card.set_visible(True)
        self._add_card.set_visible(True)

        try:
            raw = self.power_service.GetPowerProfile()
            data = json.loads(raw)
            
            # Sync switch without trigger recursion
            self._block_sync = True
            enabled = data.get("app_profiles_enabled", False)
            if self.app_profiles_switch.get_active() != enabled:
                self.app_profiles_switch.set_active(enabled)
            self._block_sync = False
            
            # Clear list box
            while True:
                child = self.app_profiles_list_box.get_first_child()
                if not child:
                    break
                self.app_profiles_list_box.remove(child)
                
            # Populate container
            app_profiles = data.get("app_profiles", {})
            if not app_profiles:
                empty_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
                empty_row.set_margin_top(8)
                empty_row.set_margin_bottom(8)
                empty_lbl = Gtk.Label(label=T("no_profiles"), xalign=0, css_classes=["dim-label"])
                empty_row.append(empty_lbl)
                self.app_profiles_list_box.append(empty_row)
            elif self.view_mode == "grid":
                # Render Professional Grid Layout
                grid_flow = Gtk.FlowBox()
                grid_flow.set_valign(Gtk.Align.START)
                grid_flow.set_max_children_per_line(4)
                grid_flow.set_min_children_per_line(1)
                grid_flow.set_selection_mode(Gtk.SelectionMode.NONE)
                grid_flow.set_column_spacing(16)
                grid_flow.set_row_spacing(16)

                theme_icon = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                active_app = data.get("active_app")

                for app_name, val in app_profiles.items():
                    if isinstance(val, dict):
                        profile = val.get("profile", "balanced")
                        category = val.get("category", "game")
                        display_name = val.get("name", app_name)
                        fan_mode = val.get("fan_mode", "default")
                        theme = val.get("theme", "default")
                        icon_name = val.get("icon", app_name)
                    else:
                        profile = val
                        category = "game"
                        display_name = app_name
                        fan_mode = "default"
                        theme = "default"
                        icon_name = app_name

                    is_active = active_app and (active_app.lower() == app_name.lower())

                    # Outer Card Box
                    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
                    card.add_css_class("inner-panel")
                    card.set_size_request(210, 165)

                    # Top Row: Icon + Title + Active Status Badge
                    top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, valign=Gtk.Align.CENTER)
                    
                    if theme_icon.has_icon(icon_name):
                        img = Gtk.Image.new_from_icon_name(icon_name)
                    else:
                        fallback_icon = "application-x-executable-symbolic" if category == "program" else "input-gaming-symbolic"
                        img = Gtk.Image.new_from_icon_name(fallback_icon)
                    img.set_pixel_size(32)
                    top_box.append(img)

                    title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
                    title_lbl = Gtk.Label(label=display_name, xalign=0, css_classes=["title-4"], ellipsize=3)
                    title_box.append(title_lbl)

                    if is_active:
                        act_lbl = Gtk.Label(css_classes=["caption"])
                        act_lbl.set_markup(f"<span foreground='#57c494' weight='bold'>[{T('active')}]</span>")
                        act_lbl.set_xalign(0)
                        title_box.append(act_lbl)

                    top_box.append(title_box)
                    card.append(top_box)

                    card.append(Gtk.Separator())

                    # Meta Settings Badges
                    p_text = T("saver") if profile == "power-saver" else T("balanced") if profile == "balanced" else T("performance")
                    meta_parts = [f"⚡ {p_text}"]
                    if fan_mode and fan_mode != "default":
                        fan_lbl_text = T("fan_auto") if fan_mode == "auto" else T("fan_max")
                        meta_parts.append(f"🌀 {fan_lbl_text}")
                    if theme == "dark":
                        meta_parts.append("🌙 Dark")
                    elif theme == "light":
                        meta_parts.append("☀️ Light")

                    meta_lbl = Gtk.Label(label="\n".join(meta_parts), xalign=0, css_classes=["dim-label"], wrap=True)
                    meta_lbl.set_vexpand(True)
                    card.append(meta_lbl)

                    # Action Buttons Row
                    actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)

                    launch_btn = Gtk.Button(label="▶")
                    launch_btn.add_css_class("suggested-action")
                    launch_btn.set_tooltip_text(T("launch"))
                    launch_btn.connect("clicked", lambda *_, a=app_name, v=val: self._launch_app_program(a, v))
                    actions_box.append(launch_btn)

                    edit_btn = Gtk.Button(label="✏️")
                    edit_btn.add_css_class("update-btn")
                    edit_btn.set_tooltip_text(T("edit"))
                    edit_btn.connect("clicked", lambda *_, a=app_name, v=val: self._start_edit_app_profile(a, v))
                    actions_box.append(edit_btn)

                    del_btn = Gtk.Button(label="🗑️")
                    del_btn.add_css_class("update-btn")
                    del_btn.set_tooltip_text(T("delete"))
                    del_btn.connect("clicked", lambda *_, a=app_name: self._delete_app_profile(a))
                    actions_box.append(del_btn)

                    card.append(actions_box)
                    grid_flow.append(card)

                self.app_profiles_list_box.append(grid_flow)
            else:
                # Render List Layout
                for idx, (app_name, val) in enumerate(app_profiles.items()):
                    if isinstance(val, dict):
                        profile = val.get("profile", "balanced")
                        category = val.get("category", "game")
                        display_name = val.get("name", app_name)
                    else:
                        profile = val
                        category = "game"
                        display_name = app_name
                        
                    if idx > 0:
                        self.app_profiles_list_box.append(Gtk.Separator(margin_top=8, margin_bottom=8))
                        
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
                    row.set_margin_top(4)
                    row.set_margin_bottom(4)
                    
                    icon_name = val.get("icon", app_name) if isinstance(val, dict) else app_name
                    icon_widget = None
                    theme_icon = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
                    if theme_icon.has_icon(icon_name):
                        icon_widget = Gtk.Image.new_from_icon_name(icon_name)
                        icon_widget.set_pixel_size(24)
                    else:
                        fallback_icon = "application-x-executable-symbolic" if category == "program" else "input-gaming-symbolic"
                        icon_widget = Gtk.Image.new_from_icon_name(fallback_icon)
                        icon_widget.set_pixel_size(24)
                    
                    row.append(icon_widget)
                        
                    active_app = data.get("active_app")
                    is_active = active_app and (active_app.lower() == app_name.lower())
                    
                    lbl_text = display_name
                    if is_active:
                        lbl_text += f" <span foreground='#57c494' size='small' weight='bold'>[{T('active')}]</span>"
                        
                    lbl = Gtk.Label(xalign=0, hexpand=True, halign=Gtk.Align.START, css_classes=["title-4"])
                    lbl.set_markup(lbl_text)
                    
                    # Extract fan mode and theme
                    fan_mode = val.get("fan_mode", "default") if isinstance(val, dict) else "default"
                    theme = val.get("theme", "default") if isinstance(val, dict) else "default"
                    
                    p_text = T("saver") if profile == "power-saver" else T("balanced") if profile == "balanced" else T("performance")
                    meta_parts = [p_text]
                    if fan_mode and fan_mode != "default":
                        fan_lbl_text = T("fan_auto") if fan_mode == "auto" else T("fan_max")
                        meta_parts.append(fan_lbl_text)
                    if theme == "dark":
                        meta_parts.append("\U0001f319")  # 🌙
                    elif theme == "light":
                        meta_parts.append("\u2600\ufe0f")   # ☀️
                    lbl_settings = " • ".join(meta_parts)
                        
                    profile_lbl = Gtk.Label(label=lbl_settings, xalign=0, halign=Gtk.Align.END, css_classes=["dim-label"])
                    
                    launch_btn = Gtk.Button(label="▶")
                    launch_btn.add_css_class("update-btn")
                    launch_btn.set_valign(Gtk.Align.CENTER)
                    launch_btn.set_tooltip_text(T("launch"))
                    launch_btn.connect("clicked", lambda *_, a=app_name, v=val: self._launch_app_program(a, v))

                    edit_btn = Gtk.Button(label="✏️")
                    edit_btn.add_css_class("update-btn")
                    edit_btn.set_valign(Gtk.Align.CENTER)
                    edit_btn.set_tooltip_text(T("edit"))
                    edit_btn.connect("clicked", lambda *_, a=app_name, v=val: self._start_edit_app_profile(a, v))

                    del_btn = Gtk.Button(label="🗑️")
                    del_btn.add_css_class("update-btn")
                    del_btn.set_valign(Gtk.Align.CENTER)
                    del_btn.set_tooltip_text(T("delete"))
                    del_btn.connect("clicked", lambda *_, a=app_name: self._delete_app_profile(a))
                    
                    row.append(lbl)
                    row.append(profile_lbl)
                    row.append(launch_btn)
                    row.append(edit_btn)
                    row.append(del_btn)
                    
                    self.app_profiles_list_box.append(row)
                
        except Exception as e:
            print(f"Failed to refresh app profiles: {e}")
            
        return False

    def _start_edit_app_profile(self, app_name, val):
        self._editing_app_key = app_name
        self.form_heading_lbl.set_label(T("edit"))
        self.add_btn.set_label(T("update"))
        self.cancel_edit_btn.set_visible(True)

        if isinstance(val, dict):
            profile = val.get("profile", "balanced")
            category = val.get("category", "game")
            display_name = val.get("name", app_name)
            fan_mode = val.get("fan_mode", "default")
            theme = val.get("theme", "default")
            icon_name = val.get("icon", app_name)
        else:
            profile = val
            category = "game"
            display_name = app_name
            fan_mode = "default"
            theme = "default"
            icon_name = app_name

        self.completion.set_popup_completion(False)
        self.add_app_entry.set_text(display_name)
        self._selected_exec_name = app_name
        self._selected_icon_name = icon_name
        self.completion.set_popup_completion(True)

        profile_map_inv = {"power-saver": 0, "balanced": 1, "performance": 2}
        self.add_profile_dd.set_selected(profile_map_inv.get(profile, 1))

        cat_map_inv = {"game": 0, "program": 1, "other": 2}
        self.add_category_dd.set_selected(cat_map_inv.get(category, 0))

        fan_map_inv = {"default": 0, "auto": 1, "max": 2}
        self.add_fan_dd.set_selected(fan_map_inv.get(fan_mode, 0))

        theme_map_inv = {"default": 0, "dark": 1, "light": 2}
        self.add_theme_dd.set_selected(theme_map_inv.get(theme, 0))

    def _cancel_edit_mode(self, btn=None):
        self._editing_app_key = None
        self.form_heading_lbl.set_label(T("add"))
        self.add_btn.set_label(T("add"))
        self.cancel_edit_btn.set_visible(False)
        self.add_app_entry.set_text("")
        self._selected_exec_name = None
        self._selected_icon_name = None

    def _on_app_profiles_toggle(self, switch, state):
        if getattr(self, "_block_sync", False):
            return False
        if not self.power_service:
            return True
        try:
            self.power_service.SetAppProfilesEnabled(bool(state))
        except Exception as e:
            print(f"Failed to toggle app profiles: {e}")
        return False

    def _add_app_profile(self, btn):
        if not self.power_service:
            return
        
        app_input = self.add_app_entry.get_text().strip()
        if not app_input:
            return
            
        selected_idx = self.add_profile_dd.get_selected()
        profiles_map = {0: "power-saver", 1: "balanced", 2: "performance"}
        profile = profiles_map.get(selected_idx, "balanced")
        
        cat_idx = self.add_category_dd.get_selected()
        cat_map = {0: "game", 1: "program", 2: "other"}
        category = cat_map.get(cat_idx, "game")
        
        fan_idx = self.add_fan_dd.get_selected()
        fan_map = {0: "default", 1: "auto", 2: "max"}
        fan_mode = fan_map.get(fan_idx, "default")
        
        theme_idx = self.add_theme_dd.get_selected()
        theme_map = {0: "default", 1: "dark", 2: "light"}
        theme = theme_map.get(theme_idx, "default")
        
        # Check if we have a mapped suggestion selected or if we are editing an existing item
        exec_name = getattr(self, "_selected_exec_name", None)
        if not exec_name:
            exec_name = self._editing_app_key if self._editing_app_key else app_input.lower()
            display_name = app_input
        else:
            display_name = app_input
            
        try:
            raw = self.power_service.GetPowerProfile()
            data = json.loads(raw)
            app_profiles = data.get("app_profiles", {})

            # If editing and key changed, remove old key
            if self._editing_app_key and self._editing_app_key in app_profiles and self._editing_app_key != exec_name:
                del app_profiles[self._editing_app_key]

            icon_name = getattr(self, "_selected_icon_name", None) or exec_name
            app_profiles[exec_name] = {
                "profile": profile,
                "category": category,
                "name": display_name,
                "fan_mode": fan_mode,
                "theme": theme,
                "icon": icon_name,
            }
            
            self.power_service.SetAppProfiles(json.dumps(app_profiles))
            self._cancel_edit_mode()
            self._refresh_app_profiles()
        except Exception as e:
            print(f"Failed to add/update app profile: {e}")

    def _launch_app_program(self, app_name, val):
        import subprocess
        
        # Check if application/process is already running
        target_token = app_name.split("_", 1)[1] if "_" in app_name else app_name
        is_running = False
        target_pid = None

        try:
            for pid_str in os.listdir("/proc"):
                if not pid_str.isdigit():
                    continue
                try:
                    cmdline_path = os.path.join("/proc", pid_str, "cmdline")
                    if os.stat(cmdline_path).st_uid < 1000:
                        continue
                    with open(cmdline_path, "r", errors="ignore") as f:
                        cmdline = f.read().replace("\x00", " ").strip().lower()
                    if target_token.lower() in cmdline:
                        is_running = True
                        target_pid = pid_str
                        break
                except Exception:
                    pass
        except Exception:
            pass

        # If already running, bring existing window to focus
        if is_running and target_pid:
            try:
                # Try wmctrl first
                if shutil.which("wmctrl"):
                    res = subprocess.run(["wmctrl", "-ia", str(target_pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        return
                    # Try matching by window title / app name
                    disp_name = val.get("name", target_token) if isinstance(val, dict) else target_token
                    res = subprocess.run(["wmctrl", "-a", disp_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        return
                
                # Fallback to xdotool
                if shutil.which("xdotool"):
                    res = subprocess.run(["xdotool", "search", "--pid", str(target_pid), "windowactivate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        return
            except Exception:
                pass
            # App is already running, prevent launching duplicate windows
            print(f"Program '{target_token}' is already running (PID: {target_pid}). Focused existing instance.")
            return

        # Not running -> launch fresh instance
        try:
            if app_name.startswith("steam_"):
                game_id = app_name.split("_", 1)[1]
                subprocess.Popen(["steam", f"steam://rungameid/{game_id}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif app_name.startswith("flatpak_"):
                flatpak_id = app_name.split("_", 1)[1]
                subprocess.Popen(["flatpak", "run", flatpak_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif app_name.startswith("snap_"):
                snap_id = app_name.split("_", 1)[1]
                subprocess.Popen(["snap", "run", snap_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif app_name.startswith("lutris_"):
                lutris_id = app_name.split("_", 1)[1]
                subprocess.Popen(["lutris", f"lutris:rungameid/{lutris_id}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif app_name.startswith("heroic_"):
                heroic_id = app_name.split("_", 1)[1]
                subprocess.Popen(["heroic", f"heroic://launch/{heroic_id}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen([app_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Failed to launch program {app_name}: {e}")

    def _delete_app_profile(self, app_name):
        if not self.power_service:
            return
        try:
            raw = self.power_service.GetPowerProfile()
            data = json.loads(raw)
            app_profiles = data.get("app_profiles", {})
            if app_name in app_profiles:
                del app_profiles[app_name]
                self.power_service.SetAppProfiles(json.dumps(app_profiles))
                self._refresh_app_profiles()
        except Exception as e:
            print(f"Failed to delete app profile: {e}")

    def refresh(self):
        self._refresh_app_profiles()

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

        if hasattr(self, "_toggle_card") and self._toggle_card is not None:
            self._toggle_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)

        if hasattr(self, "_add_card") and self._add_card is not None:
            self._add_card.set_spacing(10 if bucket == "compact" else 18 if bucket == "spacious" else 15)
