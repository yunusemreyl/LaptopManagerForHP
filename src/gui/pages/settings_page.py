#!/usr/bin/env python3
"""Settings Page with GitHub update checker — i18n via T()."""
import os, platform, threading, json, subprocess, shutil, tempfile
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from widgets.smooth_scroll import SmoothScrolledWindow

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def T(k):
    from i18n import T as _T
    return _T(k)


APP_VERSION = "1.1.1"
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

        scroll = SmoothScrolledWindow(vexpand=True)
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

        self.install_btn = Gtk.Button(label=T("install_update"))
        self.install_btn.add_css_class("suggested-action")
        self.install_btn.set_visible(False)
        self.install_btn.connect("clicked", self._install_update)
        update_row.append(self.install_btn)

        update_card.append(update_row)

        # Progress bar for download/install
        self.update_progress = Gtk.ProgressBar()
        self.update_progress.set_visible(False)
        self.update_progress.set_show_text(True)
        update_card.append(self.update_progress)

        # Restart button (shown after successful update)
        self.restart_btn = Gtk.Button(label=T("restart_app"))
        self.restart_btn.add_css_class("suggested-action")
        self.restart_btn.set_visible(False)
        self.restart_btn.connect("clicked", self._restart_app)
        update_card.append(self.restart_btn)

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

        hp_rgb_lighting_loaded = self._is_module_loaded("hp_rgb_lighting")
        hp_wmi_loaded = self._is_module_loaded("hp_wmi")

        drivers = [("hp-rgb-lighting", hp_rgb_lighting_loaded), ("hp-wmi (Fan/Thermal/Key)", hp_wmi_loaded)]
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
        # ── Debug Log ──
        debug_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        debug_card.add_css_class("card")
        
        debug_hdr = Gtk.Box(spacing=15)
        debug_info_lbl = Gtk.Label(label=T("debug_info_desc") or "If you encounter errors, please copy the debug logs and share them with the developer.", wrap=True, hexpand=True, xalign=0)
        debug_hdr.append(debug_info_lbl)
        
        copy_debug_btn = Gtk.Button(label=T("copy_debug_log") or "Copy Debug Info")
        copy_debug_btn.add_css_class("profile-btn")
        copy_debug_btn.connect("clicked", self._copy_debug_log)
        
        debug_card.append(Gtk.Label(label="Debug Information", xalign=0, css_classes=["section-title"]))
        debug_card.append(debug_hdr)
        debug_card.append(copy_debug_btn)
        content.append(debug_card)

        scroll.set_child(content)
        self.append(scroll)

    # ── Update Checker ──
    def _check_update(self, btn):
        self.update_btn.set_sensitive(False)
        self.update_spinner.set_visible(True)
        self.update_spinner.start()
        self.update_status.set_label(T("update_checking"))
        self.download_btn.set_visible(False)
        self.install_btn.set_visible(False)
        self.restart_btn.set_visible(False)
        self._latest_tarball_url = None
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _do_check_update(self):
        try:
            import urllib.request
            req = urllib.request.Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                latest = data.get("tag_name", "").lstrip("v").strip()
                tarball_url = data.get("tarball_url", "")
                if latest and self._version_compare(latest, APP_VERSION) > 0:
                    self._latest_tarball_url = tarball_url
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
            self.install_btn.set_visible(True)
        else:
            self.update_status.set_label(f"✓ {T('up_to_date')} (v{latest_ver})")

    def _update_error(self, err):
        self.update_spinner.stop()
        self.update_spinner.set_visible(False)
        self.update_btn.set_sensitive(True)
        self.update_status.set_label(T("conn_failed"))

    def _open_releases(self, btn):
        subprocess.Popen(["xdg-open", GITHUB_RELEASES_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ── Auto Update Installer ──
    def _install_update(self, btn):
        """Download tarball from GitHub, extract, and run install.sh via pkexec."""
        if not getattr(self, '_latest_tarball_url', None):
            self.update_status.set_label(f"{T('update_failed')}: No URL")
            return
        self.install_btn.set_sensitive(False)
        self.download_btn.set_visible(False)
        self.update_btn.set_sensitive(False)
        self.update_progress.set_visible(True)
        self.update_progress.set_fraction(0.0)
        self.update_progress.set_text(T("downloading_update"))
        self.update_status.set_label(T("downloading_update"))
        threading.Thread(target=self._do_install_update, daemon=True).start()

    def _do_install_update(self):
        """Background: download → extract → pkexec install.sh."""
        import urllib.request, tarfile
        tmp_dir = None
        try:
            # Step 1: Download tarball
            GLib.idle_add(self._install_progress, 0.1, T("downloading_update"))
            tmp_dir = tempfile.mkdtemp(prefix="hp-manager-update-")
            tarball_path = os.path.join(tmp_dir, "update.tar.gz")

            req = urllib.request.Request(self._latest_tarball_url,
                                         headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                with open(tarball_path, 'wb') as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = min(downloaded / total, 0.5)  # download = 0-50%
                            GLib.idle_add(self._install_progress, pct, T("downloading_update"))

            GLib.idle_add(self._install_progress, 0.5, T("installing_update"))

            # Step 2: Extract tarball
            with tarfile.open(tarball_path, 'r:gz') as tar:
                try:
                    tar.extractall(path=tmp_dir, filter='data')
                except TypeError:
                    # Python < 3.12 doesn't support filter argument
                    tar.extractall(path=tmp_dir)

            # Find the extracted directory (GitHub tarballs have a single top-level dir)
            extracted_dirs = [d for d in os.listdir(tmp_dir)
                             if os.path.isdir(os.path.join(tmp_dir, d))]
            if not extracted_dirs:
                raise RuntimeError("No directory found in tarball")
            src_dir = os.path.join(tmp_dir, extracted_dirs[0])

            # Step 3: Run update.sh via pkexec (or install.sh fallback)
            install_script = os.path.join(src_dir, "update.sh")
            if not os.path.exists(install_script):
                install_script = os.path.join(src_dir, "install.sh")
                if not os.path.exists(install_script):
                    raise RuntimeError(f"update.sh or install.sh not found in {src_dir}")

            os.chmod(install_script, 0o755)
            GLib.idle_add(self._install_progress, 0.6, T("installing_update"))

            result = subprocess.run(
                ["pkexec", "bash", install_script],
                cwd=src_dir,
                capture_output=True, text=True, timeout=300
            )

            GLib.idle_add(self._install_progress, 0.95, T("installing_update"))

            if result.returncode == 0:
                GLib.idle_add(self._install_done, True, "")
            else:
                err = result.stderr.strip() or result.stdout.strip() or f"Exit code: {result.returncode}"
                GLib.idle_add(self._install_done, False, err)

        except Exception as e:
            GLib.idle_add(self._install_done, False, str(e))
        finally:
            # Cleanup temp files
            if tmp_dir and os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir)
                except Exception:
                    pass

    def _install_progress(self, fraction, text):
        """Update progress bar from main thread."""
        self.update_progress.set_fraction(fraction)
        self.update_progress.set_text(text)
        return False

    def _install_done(self, success, error_msg):
        """Handle install completion from main thread."""
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
        """Restart the application after a successful update."""
        import sys
        python = sys.executable
        script = os.path.abspath(sys.argv[0]) if sys.argv else ""
        if script and os.path.exists(script):
            subprocess.Popen([python, script])
        app = self.get_root()
        if app and hasattr(app, 'get_application'):
            application = app.get_application()
            if application:
                application.quit()
                return
        # Fallback: just exit
        sys.exit(0)

    @staticmethod
    def _version_compare(v1, v2):
        """Compare two version strings (basic semantic).
        Returns >0 if v1>v2, <0 if v1<v2, 0 if equal.
        """
        import re
        def parse(v):
            v = str(v).strip()
            # extract dots and digits
            m = re.match(r'^([\d.]+)', v)
            if not m:
                return [0]
            return [int(x) for x in m.group(1).split('.') if x]
        
        n1 = parse(v1)
        n2 = parse(v2)
        
        # pad to same length
        maxlen = max(len(n1), len(n2))
        n1.extend([0] * (maxlen - len(n1)))
        n2.extend([0] * (maxlen - len(n2)))
        
        for a, b in zip(n1, n2):
            if a > b:
                return 1
            if a < b:
                return -1
        return 0

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
        err_text = self._gather_debug_info()
        self.get_clipboard().set(err_text)
        btn.set_label(T("copied_to_clipboard") or "Copied to Clipboard!")
        GLib.timeout_add(2000, lambda: btn.set_label(T("copy_debug_log") or "Copy Debug Info") or False)
        
    def _gather_debug_info(self):
        import platform, subprocess
        out = [f"HP Laptop Manager Version: {APP_VERSION}"]
        out.append(f"OS Default: {self._get_distro()}")
        out.append(f"Kernel: {platform.release()}")
        out.append(f"python_version: {platform.python_version()}")
        out.append("Loaded Modules:")
        try:
            lsmod_out = subprocess.check_output(["lsmod"], stderr=subprocess.DEVNULL, timeout=2).decode(errors='ignore')
            for mod in ('hp_wmi', 'hp_rgb_lighting', 'hp_omen_core'):
                if mod in lsmod_out:
                    out.append(f"  - {mod}: Yes")
                else:
                    out.append(f"  - {mod}: No")
        except Exception:
            pass
        out.append("Service Status:")
        try:
            status = subprocess.check_output(["systemctl", "status", "hp-manager.service"], stderr=subprocess.STDOUT, timeout=2).decode(errors='ignore')
            lines = status.splitlines()
            for i in range(min(5, len(lines))):
                out.append(f"  {lines[i].strip()}")
        except Exception as e:
            out.append(f"  Error: {e}")
        return "\n".join(out)
