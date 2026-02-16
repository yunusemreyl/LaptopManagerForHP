#!/usr/bin/env python3
"""Tools Page - Gaming araçlarını yönetir ve yükler.
Multi-distro support: Arch/Fedora/Debian-Ubuntu/openSUSE + Flatpak."""
import os, subprocess, shutil, threading
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def T(k):
    from i18n import T as _T
    return _T(k)


def _detect_distro():
    """Detect distro family from /etc/os-release."""
    distro_id = ""
    id_like = ""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    distro_id = line.split("=", 1)[1].strip().strip('"').lower()
                elif line.startswith("ID_LIKE="):
                    id_like = line.split("=", 1)[1].strip().strip('"').lower()
    except:
        pass

    # Determine family
    if distro_id in ("arch", "manjaro", "endeavouros", "garuda", "cachyos", "arcolinux"):
        return "arch"
    if "arch" in id_like:
        return "arch"
    if distro_id in ("fedora", "nobara", "ultramarine"):
        return "fedora"
    if "fedora" in id_like:
        return "fedora"
    if distro_id in ("debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "neon", "tuxedo"):
        return "debian"
    if "debian" in id_like or "ubuntu" in id_like:
        return "debian"
    if distro_id in ("opensuse-tumbleweed", "opensuse-leap", "suse"):
        return "suse"
    if "suse" in id_like:
        return "suse"

    # Fallback: detect by package manager
    if shutil.which("pacman"):
        return "arch"
    if shutil.which("dnf"):
        return "fedora"
    if shutil.which("apt"):
        return "debian"
    if shutil.which("zypper"):
        return "suse"

    return "unknown"


DISTRO = _detect_distro()


def _has_aur_helper():
    """Check for AUR helper availability."""
    for helper in ("paru", "yay", "trizen", "pikaur"):
        if shutil.which(helper):
            return helper
    return None


# Tool definitions with per-distro package names
TOOLS = [
    {
        "id": "steam",
        "name": "Steam",
        "desc": "steam_desc",
        "icon": "applications-games-symbolic",
        "check_cmd": ["steam", "--version"],
        "check_flatpak": "com.valvesoftware.Steam",
        "pkg": {
            "arch": "steam",  # Requires multilib
            "fedora": None,   # Needs RPM Fusion — prefer flatpak
            "debian": "steam-installer",
            "suse": None,     # Prefer flatpak
        },
        "flatpak_id": "com.valvesoftware.Steam",
        "note_fedora": "Flatpak ile kurulacak (RPM Fusion gerekmez)",
        "note_suse": "Flatpak ile kurulacak",
    },
    {
        "id": "lutris",
        "name": "Lutris",
        "desc": "lutris_desc",
        "icon": "input-gaming-symbolic",
        "check_cmd": ["lutris", "--version"],
        "check_flatpak": "net.lutris.Lutris",
        "pkg": {
            "arch": "lutris",
            "fedora": "lutris",
            "debian": "lutris",
            "suse": "lutris",
        },
        "flatpak_id": "net.lutris.Lutris",
    },
    {
        "id": "protonup-qt",
        "name": "ProtonUp-Qt",
        "desc": "protonup_desc",
        "icon": "system-software-install-symbolic",
        "check_cmd": None,
        "check_flatpak": "net.davidotek.pupgui2",
        "pkg": {
            "arch": "protonup-qt",       # AUR
            "fedora": None,
            "debian": None,
            "suse": None,
        },
        "flatpak_id": "net.davidotek.pupgui2",
        "aur": True,
    },
    {
        "id": "heroic",
        "name": "Heroic Games Launcher",
        "desc": "heroic_desc",
        "icon": "applications-games-symbolic",
        "check_cmd": None,
        "check_flatpak": "com.heroicgameslauncher.hgl",
        "pkg": {
            "arch": "heroic-games-launcher-bin",  # AUR
            "fedora": None,
            "debian": None,
            "suse": None,
        },
        "flatpak_id": "com.heroicgameslauncher.hgl",
        "aur": True,
    },
    {
        "id": "mangohud",
        "name": "MangoHud",
        "desc": "mangohud_desc",
        "icon": "utilities-system-monitor-symbolic",
        "check_cmd": ["mangohud", "--version"],
        "check_flatpak": None,
        "pkg": {
            "arch": "mangohud",
            "fedora": "mangohud",
            "debian": "mangohud",
            "suse": "mangohud",
        },
        "flatpak_id": None,
    },
    {
        "id": "gamemode",
        "name": "GameMode",
        "desc": "gamemode_desc",
        "icon": "emblem-system-symbolic",
        "check_cmd": ["gamemoded", "--status"],
        "check_flatpak": None,
        "pkg": {
            "arch": "gamemode",
            "fedora": "gamemode",
            "debian": "gamemode",
            "suse": "gamemode",
        },
        "flatpak_id": None,
    },
]


class ToolsPage(Gtk.Box):
    def __init__(self, service=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.service = service
        self.set_margin_top(30)
        self.set_margin_start(40)
        self.set_margin_end(40)
        self.set_margin_bottom(30)

        self._build_ui()
        GLib.idle_add(self._check_all)

    def _build_ui(self):
        # Header
        self.title = Gtk.Label(label=T("tools_title"), xalign=0)
        self.title.add_css_class("page-title")
        self.append(self.title)

        desc = Gtk.Label(label=T("tools_desc"), xalign=0)
        desc.add_css_class("stat-lbl")
        desc.set_margin_bottom(10)
        self.append(desc)

        # Scrolled list
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.list_box)
        self.append(scroll)

        self.tool_widgets = {}
        for tool in TOOLS:
            card = self._make_tool_card(tool)
            self.list_box.append(card)

    def _make_tool_card(self, tool):
        card = Gtk.Box(spacing=20)
        card.add_css_class("tool-card")

        # Icon
        icon = Gtk.Image.new_from_icon_name(tool["icon"])
        icon.set_pixel_size(40)
        icon.set_valign(Gtk.Align.CENTER)
        card.append(icon)

        # Info
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, valign=Gtk.Align.CENTER)
        name_lbl = Gtk.Label(label=tool["name"], xalign=0)
        name_lbl.add_css_class("tool-name")
        info.append(name_lbl)
        desc_lbl = Gtk.Label(label=T(tool["desc"]), xalign=0)
        desc_lbl.add_css_class("tool-desc")
        info.append(desc_lbl)
        card.append(info)

        # Status
        status_box = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)

        status_lbl = Gtk.Label(label=T("checking"))
        status_lbl.add_css_class("tool-status")
        status_box.append(status_lbl)

        btn = Gtk.Button(label=T("install"))
        btn.add_css_class("tool-install-btn")
        btn.set_visible(False)
        btn.connect("clicked", lambda w, t=tool: self._install_tool(t))
        status_box.append(btn)

        spinner = Gtk.Spinner()
        spinner.set_visible(False)
        status_box.append(spinner)

        card.append(status_box)

        self.tool_widgets[tool["id"]] = {
            "status": status_lbl,
            "btn": btn,
            "spinner": spinner,
            "card": card,
        }

        return card

    def _check_tool(self, tool):
        installed = False

        # Check native
        if tool.get("check_cmd"):
            if shutil.which(tool["check_cmd"][0]):
                installed = True

        # Check flatpak
        if not installed and tool.get("check_flatpak"):
            try:
                result = subprocess.run(
                    ["flatpak", "info", tool["check_flatpak"]],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    installed = True
            except:
                pass

        # Update UI on main thread
        GLib.idle_add(self._update_status, tool["id"], installed)

    def _update_status(self, tool_id, installed):
        w = self.tool_widgets.get(tool_id)
        if not w:
            return
        if installed:
            w["status"].set_label(T("installed"))
            w["status"].add_css_class("tool-installed")
            w["btn"].set_visible(False)
        else:
            w["status"].set_label(T("not_installed"))
            w["status"].add_css_class("tool-not-installed")
            w["btn"].set_visible(True)

    def _check_all(self):
        for tool in TOOLS:
            t = threading.Thread(target=self._check_tool, args=(tool,), daemon=True)
            t.start()
        return False

    def _install_tool(self, tool):
        w = self.tool_widgets.get(tool["id"])
        if not w:
            return

        w["btn"].set_visible(False)
        w["spinner"].set_visible(True)
        w["spinner"].start()
        w["status"].set_label(T("installing"))

        def do_install():
            success = False
            method = ""

            # Get package name for current distro
            pkg = tool.get("pkg", {}).get(DISTRO)
            flatpak_id = tool.get("flatpak_id")
            is_aur = tool.get("aur", False) and DISTRO == "arch"

            # Strategy 1: Native package manager (preferred)
            if pkg and not is_aur:
                success, method = self._try_native_install(pkg)

            # Strategy 2: AUR (Arch only)
            if not success and is_aur and pkg:
                aur_helper = _has_aur_helper()
                if aur_helper:
                    try:
                        subprocess.run(
                            [aur_helper, "-S", "--noconfirm", pkg],
                            check=True, capture_output=True, timeout=600
                        )
                        success = True
                        method = f"AUR ({aur_helper})"
                    except:
                        pass

            # Strategy 3: Flatpak (fallback / preferred for some distros)
            if not success and flatpak_id and shutil.which("flatpak"):
                try:
                    # Ensure flathub is added
                    subprocess.run(
                        ["flatpak", "remote-add", "--if-not-exists", "flathub",
                         "https://dl.flathub.org/repo/flathub.flatpakrepo"],
                        capture_output=True, timeout=30
                    )
                    subprocess.run(
                        ["flatpak", "install", "-y", "--noninteractive", "flathub", flatpak_id],
                        check=True, capture_output=True, timeout=600
                    )
                    success = True
                    method = "Flatpak"
                except:
                    pass

            # Strategy 4: Try native as last resort (for distros where pkg was None)
            if not success and not pkg and flatpak_id is None:
                # Really last resort — try generic package name
                generic_pkg = tool.get("pkg", {}).get("debian") or tool["id"]
                success, method = self._try_native_install(generic_pkg)

            GLib.idle_add(self._install_done, tool["id"], success, method)

        t = threading.Thread(target=do_install, daemon=True)
        t.start()

    def _try_native_install(self, pkg_name):
        """Try to install via the system's native package manager."""
        pm_commands = {
            "arch": ["pkexec", "pacman", "-S", "--noconfirm", pkg_name],
            "fedora": ["pkexec", "dnf", "install", "-y", pkg_name],
            "debian": ["pkexec", "apt", "install", "-y", pkg_name],
            "suse": ["pkexec", "zypper", "install", "-y", pkg_name],
        }

        cmd = pm_commands.get(DISTRO)
        if cmd:
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=300)
                return True, DISTRO
            except:
                pass

        # Fallback: try all known managers
        fallback_managers = [
            ("pacman", ["pkexec", "pacman", "-S", "--noconfirm", pkg_name]),
            ("apt", ["pkexec", "apt", "install", "-y", pkg_name]),
            ("dnf", ["pkexec", "dnf", "install", "-y", pkg_name]),
            ("zypper", ["pkexec", "zypper", "install", "-y", pkg_name]),
        ]
        for pm, cmd in fallback_managers:
            if shutil.which(pm):
                try:
                    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
                    return True, pm
                except:
                    pass
                break

        return False, ""

    def _install_done(self, tool_id, success, method=""):
        w = self.tool_widgets.get(tool_id)
        if not w:
            return
        w["spinner"].stop()
        w["spinner"].set_visible(False)

        if success:
            label = T("installed")
            if method:
                label += f" ({method})"
            w["status"].set_label(label)
            w["status"].add_css_class("tool-installed")
            w["btn"].set_visible(False)
        else:
            w["status"].set_label(T("install_failed"))
            w["status"].add_css_class("tool-not-installed")
            w["btn"].set_label(T("retry"))
            w["btn"].set_visible(True)
