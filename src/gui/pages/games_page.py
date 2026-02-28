#!/usr/bin/env python3
"""Games Library Page - Yüklü oyunları tespit edip gösterir."""
import os, json, subprocess, shutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

try:
    from i18n import T
except ImportError:
    # Fallback if running standalone for testing (and sys.path not set)
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from i18n import T


class GamesPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.set_margin_top(30)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.set_margin_bottom(30)

        self.games = []
        self._build_ui()
        GLib.idle_add(self._scan_games)

    def _build_ui(self):
        # Header
        header = Gtk.Box(spacing=15)
        self.title = Gtk.Label(label=T("game_library"), xalign=0)
        self.title.add_css_class("page-title")
        header.append(self.title)
        header.append(Gtk.Label(hexpand=True))

        self.count_label = Gtk.Label(label="")
        self.count_label.add_css_class("stat-lbl")
        header.append(self.count_label)
        self.append(header)

        # Search
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(T("search_games"))
        self.search.add_css_class("search-entry")
        self.search.connect("search-changed", self._on_search)
        self.append(self.search)

        # Scrolled game grid
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flow = Gtk.FlowBox()
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_max_children_per_line(5)
        self.flow.set_min_children_per_line(2)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_homogeneous(True)
        self.flow.set_column_spacing(15)
        self.flow.set_row_spacing(15)
        scroll.set_child(self.flow)
        self.append(scroll)

        # Empty state
        self.empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, vexpand=True)
        self.empty_box.add_css_class("empty-state")
        ic = Gtk.Image.new_from_icon_name("applications-games-symbolic")
        ic.set_pixel_size(64)
        ic.set_opacity(0.3)
        self.empty_box.append(ic)
        self.empty_lbl = Gtk.Label(label=T("no_games_found"))
        self.empty_lbl.add_css_class("stat-lbl")
        self.empty_box.append(self.empty_lbl)
        self.empty_sub = Gtk.Label(label=T("install_hint"))
        self.empty_sub.add_css_class("stat-lbl")
        self.empty_sub.set_opacity(0.5)
        self.empty_box.append(self.empty_sub)
        self.append(self.empty_box)

    def _scan_games(self):
        self.games = []
        self.games.extend(self._scan_steam())
        self.games.extend(self._scan_lutris())
        self.games.extend(self._scan_heroic())
        self._populate()
        return False

    def _scan_steam(self):
        games = []
        steam_paths = [
            os.path.expanduser("~/.steam/steam/steamapps"),
            os.path.expanduser("~/.local/share/Steam/steamapps"),
        ]
        for spath in steam_paths:
            if not os.path.exists(spath):
                continue
            for f in os.listdir(spath):
                if f.startswith("appmanifest_") and f.endswith(".acf"):
                    try:
                        with open(os.path.join(spath, f)) as fh:
                            data = fh.read()
                        name = self._parse_vdf_value(data, "name")
                        appid = self._parse_vdf_value(data, "appid")
                        if name and name.lower() not in ("steamworks common redistributables", "proton"):
                            games.append({
                                "name": name,
                                "source": "Steam",
                                "appid": appid,
                                "launch": f"steam://rungameid/{appid}"
                            })
                    except Exception:
                        pass
            break  # Only first valid path
        return games

    def _parse_vdf_value(self, data, key):
        for line in data.splitlines():
            line = line.strip()
            parts = line.replace('"', '').split('\t')
            parts = [p for p in parts if p]
            if len(parts) >= 2 and parts[0].lower() == key.lower():
                return parts[1]
        return None

    def _scan_lutris(self):
        games = []
        if not shutil.which("lutris"):
            return games
        try:
            out = subprocess.check_output(
                ["lutris", "-lo", "--json"],
                stderr=subprocess.DEVNULL, timeout=10
            ).decode()
            for g in json.loads(out):
                games.append({
                    "name": g.get("name", "Unknown"),
                    "source": "Lutris",
                    "slug": g.get("slug", ""),
                    "launch": f"lutris:rungameid/{g.get('id', '')}"
                })
        except Exception:
            pass
        return games

    def _scan_heroic(self):
        games = []
        heroic_path = os.path.expanduser("~/.config/heroic/GamesConfig")
        lib_path = os.path.expanduser("~/.config/heroic/store_cache/gog_library.json")
        epic_path = os.path.expanduser("~/.config/heroic/store_cache/legendary_library.json")

        for path in [lib_path, epic_path]:
            if os.path.exists(path):
                try:
                    with open(path) as fh:
                        data = json.load(fh)
                    lib = data.get("library", data) if isinstance(data, dict) else data
                    if isinstance(lib, list):
                        for g in lib:
                            title = g.get("title", g.get("app_name", "Unknown"))
                            games.append({
                                "name": title,
                                "source": "Heroic",
                                "launch": None
                            })
                except Exception:
                    pass
        return games

    def _populate(self):
        # Remove all children
        child = self.flow.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.flow.remove(child)
            child = next_child

        if not self.games:
            self.empty_box.set_visible(True)
            self.count_label.set_label("")
            return

        self.empty_box.set_visible(False)
        self.count_label.set_label(T("games_count").format(count=len(self.games)))

        for game in sorted(self.games, key=lambda g: g["name"].lower()):
            card = self._make_game_card(game)
            self.flow.append(card)

    def _make_game_card(self, game):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("game-card")
        card.set_size_request(180, 200)

        # Icon area
        icon_box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        icon_box.set_size_request(180, 120)
        icon_box.add_css_class("game-icon-box")

        source_icons = {
            "Steam": "applications-games-symbolic",
            "Lutris": "input-gaming-symbolic",
            "Heroic": "applications-games-symbolic",
        }
        icon = Gtk.Image.new_from_icon_name(source_icons.get(game["source"], "applications-games-symbolic"))
        icon.set_pixel_size(48)
        icon.set_opacity(0.6)
        icon_box.append(icon)
        card.append(icon_box)

        # Name
        name_lbl = Gtk.Label(label=game["name"], xalign=0)
        name_lbl.set_ellipsize(3)  # END
        name_lbl.set_max_width_chars(20)
        name_lbl.add_css_class("game-name")
        card.append(name_lbl)

        # Source badge
        src_box = Gtk.Box(spacing=6)
        src_lbl = Gtk.Label(label=game["source"])
        src_lbl.add_css_class("game-source")
        src_box.append(src_lbl)
        card.append(src_box)

        # Launch button
        if game.get("launch"):
            btn = Gtk.Button(label=f"▶ {T('start_game')}")
            btn.add_css_class("game-launch-btn")
            btn.connect("clicked", lambda w, cmd=game["launch"]: self._launch(cmd))
            card.append(btn)

        return card

    def _launch(self, cmd):
        try:
            subprocess.Popen(["xdg-open", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _on_search(self, entry):
        query = entry.get_text().lower()
        child = self.flow.get_first_child()
        while child:
            fb_child = child  # FlowBoxChild wrapper
            box = fb_child.get_child()
            if box:
                visible = True
                if query:
                    # Get name label text
                    name_widget = None
                    c = box.get_first_child()
                    idx = 0
                    while c:
                        if idx == 1 and isinstance(c, Gtk.Label):
                            name_widget = c
                            break
                        c = c.get_next_sibling()
                        idx += 1
                    if name_widget:
                        visible = query in name_widget.get_label().lower()
                fb_child.set_visible(visible)
            child = child.get_next_sibling()

    def refresh(self):
        GLib.idle_add(self._scan_games)
