import os
import sys
import subprocess
import shutil
import threading
import json
import locale
import time
import random

# --- 1. BOOTSTRAP ---
def bootstrap_system():
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
    except:
        print("⚙️  Kütüphaneler eksik, kuruluyor...")
        prefix = [] if os.geteuid() == 0 else ["sudo"]
        if shutil.which("apt"):
            subprocess.run(prefix + ["apt", "update"], check=False)
            subprocess.run(prefix + ["apt", "install", "-y", "python3-gi", "libadwaita-1-0", "python3-psutil"], check=False)

bootstrap_system()

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango

# --- AYARLAR ---
INSTALL_DIR = "/opt/omen-control"
CONFIG_DIR = "/etc/omen-control"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SERVICE_FILE = "/etc/systemd/system/omen-control.service"
DESKTOP_FILE = "/usr/share/applications/omen-control.desktop"
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

FUN_MESSAGES = [
    "🐧 Penguenler besleniyor...",
    "🔥 RGB sıvıları dolduruluyor...",
    "🔧 Kernel modülleri ikna ediliyor...",
    "📦 Paketler kamyondan indiriliyor...",
    "☕ Kahve molası veriliyor...",
    "🚀 HP Omen kalkışa hazırlanıyor...",
    "🎮 FPS değerleri hesaplanıyor...",
    "💿 Windows anıları siliniyor..."
]

LANGS = {
    "tr": {
        "title": "Omen Kontrol Kurulumu",
        "lbl_select": "Kurulum Seçenekleri",
        "lbl_select_sub": "Sisteme kurulacak bileşenleri seçiniz:",
        "lbl_auth": "Yetki Doğrulama",
        "lbl_auth_sub": "Sistem dosyalarını değiştirmek için parolanızı girin.",
        "pass_placeholder": "Kullanıcı Parolası",
        "pass_err": "Hatalı parola! Lütfen tekrar deneyin.",
        "lbl_update": "Sistemi Güncelle",
        "sub_update": "Tüm paketleri günceller.",
        "lbl_nvidia": "Nvidia Sürücüleri",
        "sub_nvidia": "Resmi sürücüler (Otomatik).",
        "sub_nvidia_warn": "UYARI: Bu sistemde manuel kurulum önerilir.",
        "lbl_steam": "Steam",
        "sub_steam": "Valve resmi istemcisi.",
        "lbl_heroic": "Heroic Launcher",
        "sub_heroic": "Epic/GOG oyunları için.",
        "lbl_tools": "Oyun Araçları",
        "sub_tools": "MangoHud, Goverlay, GameMode, Lutris.",
        "btn_next": "İleri >",
        "btn_install": "Kurulumu Başlat",
        "btn_retry": "Tekrar Dene",
        "btn_skip": "Atla",
        "desc_welcome": "Bu araç HP cihazınızı Linux için yapılandırır.\nDevam etmek için yönetici yetkisi gerekecektir.",
        "finish_desc": "Kurulum tamamlandı. Lütfen bilgisayarı YENİDEN BAŞLATIN.",
        "err_100": ">>> HATA: Paket yöneticisi meşgul.",
        "log_sudo_ok": ">>> Yetki doğrulandı. İşlemler başlıyor...",
        "log_nvidia_manual": ">>> BİLGİ: Nvidia sürücüsü manuel kurulmalı (sudo ubuntu-drivers install)."
    }
}

SERVICE_CONTENT = f"""[Unit]
Description=Omen Control RGB Service
After=multi-user.target

[Service]
ExecStart=/usr/bin/python3 {INSTALL_DIR}/backend.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
"""

DESKTOP_CONTENT = f"""[Desktop Entry]
Name=Omen Control
Comment=HP Victus RGB Controller
Exec={INSTALL_DIR}/gui.py
Icon=omen-control
Terminal=false
Type=Application
Categories=Utility;Settings;
StartupWMClass=gui.py
"""

class InstallWizard(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        try:
            sys_lang = locale.getlocale()[0]
        except:
            sys_lang = "en"
            
        self.lang_code = "tr" if sys_lang and "TR" in sys_lang.upper() else "en"
        self.txt = LANGS["tr"] 

        self.set_title(self.txt["title"])
        self.set_default_size(800, 700)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        self.resume_event = threading.Event()
        self.user_decision = None 
        self.fun_timer_id = None
        self.mgr = self.detect_mgr()
        self.sudo_pass = None

        self.setup_ui()

    def setup_ui(self):
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main)

        header = Adw.HeaderBar()
        main.append(header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack.set_hexpand(True); self.stack.set_vexpand(True)
        main.append(self.stack)

        self.stack.add_named(Adw.StatusPage(icon_name="system-run-symbolic", title="Hoş Geldiniz", description=self.txt["desc_welcome"]), "welcome")
        
        self.ui_select = self.create_selection_page()
        self.stack.add_named(self.ui_select["box"], "select")

        self.ui_auth = self.create_auth_page()
        self.stack.add_named(self.ui_auth["box"], "auth")

        self.ui_proc = self.create_proc_page()
        self.stack.add_named(self.ui_proc["box"], "proc")

        self.stack.add_named(Adw.StatusPage(icon_name="emblem-ok-symbolic", title="Tamamlandı", description=self.txt["finish_desc"]), "finish")

        act = Gtk.ActionBar()
        main.append(act)
        
        self.btn_skip = Gtk.Button(label=self.txt["btn_skip"], css_classes=["destructive-action"])
        self.btn_skip.set_visible(False)
        self.btn_skip.connect("clicked", lambda x: self.on_user_response("skip"))

        self.btn_next = Gtk.Button(label=self.txt["btn_next"], css_classes=["suggested-action"])
        self.btn_next.set_size_request(140, -1)
        self.btn_next.connect("clicked", self.on_next)

        box_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box_btns.append(self.btn_skip)
        box_btns.append(self.btn_next)
        act.pack_end(box_btns)

        self.curr_step_name = "welcome"

    def create_selection_page(self):
        scr = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=20, margin_start=40, margin_end=40)
        scr.set_child(box)

        box.append(Gtk.Label(label=self.txt["lbl_select"], css_classes=["title-2"], xalign=0))
        box.append(Gtk.Label(label=self.txt["lbl_select_sub"], opacity=0.7, xalign=0))

        self.chk_update = Gtk.CheckButton(active=True)
        self.chk_nvidia = Gtk.CheckButton()
        self.chk_steam = Gtk.CheckButton()
        self.chk_heroic = Gtk.CheckButton()
        self.chk_tools = Gtk.CheckButton()

        g1 = Adw.PreferencesGroup(title="Sistem")
        g1.add(self.create_row(self.txt["lbl_update"], self.txt["sub_update"], self.chk_update))
        nv_sub = self.txt["sub_nvidia"]
        if self.mgr == "apt": nv_sub = self.txt["sub_nvidia_warn"]
        g1.add(self.create_row(self.txt["lbl_nvidia"], nv_sub, self.chk_nvidia))
        box.append(g1)

        g2 = Adw.PreferencesGroup(title="Oyun ve Performans")
        g2.add(self.create_row(self.txt["lbl_steam"], self.txt["sub_steam"], self.chk_steam))
        g2.add(self.create_row(self.txt["lbl_heroic"], self.txt["sub_heroic"], self.chk_heroic))
        g2.add(self.create_row(self.txt["lbl_tools"], self.txt["sub_tools"], self.chk_tools))
        box.append(g2)
        return {"box": scr}

    def create_auth_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic")
        icon.set_pixel_size(96)
        box.append(icon)
        
        lbl = Gtk.Label(label=self.txt["lbl_auth"], css_classes=["title-1"])
        box.append(lbl)
        lbl_sub = Gtk.Label(label=self.txt["lbl_auth_sub"])
        box.append(lbl_sub)

        entry = Gtk.PasswordEntry()
        entry.set_property("placeholder-text", self.txt["pass_placeholder"])
        entry.set_width_chars(30)
        entry.connect("activate", lambda w: self.on_next(None))
        box.append(entry)

        err_lbl = Gtk.Label(label="", css_classes=["error"])
        err_lbl.set_visible(False)
        box.append(err_lbl)

        return {"box": box, "entry": entry, "err": err_lbl}

    def create_proc_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=20, margin_start=20, margin_end=20)
        scr = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scr.add_css_class("frame")
        log = Gtk.TextView(editable=False, monospace=True, bottom_margin=10, left_margin=10)
        
        p = Gtk.CssProvider()
        p.load_from_data(b"textview text { background-color: #0d0d0d; color: #33ff33; font-family: 'Monospace'; font-size: 12px; }")
        log.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        
        scr.set_child(log)
        box.append(scr)
        
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        spinner = Gtk.Spinner()
        status_label = Gtk.Label(label="Hazır...", xalign=0)
        status_box.append(spinner); status_box.append(status_label); box.append(status_box)
        prog = Gtk.ProgressBar(); box.append(prog)
        
        return {"box": box, "log": log, "prog": prog, "buf": log.get_buffer(), "spinner": spinner, "status_lbl": status_label}

    def create_row(self, t, s, c):
        r = Adw.ActionRow(title=t, subtitle=s)
        r.add_prefix(c)
        return r

    def log(self, ui, text, error=False):
        buf = ui["buf"]; end = buf.get_end_iter()
        if error:
            if not buf.get_tag_table().lookup("err"):
                 buf.create_tag("err", foreground="#ff5555", weight=700)
            buf.insert_with_tags_by_name(end, f"{text}\n", "err")
        else:
            buf.insert(end, f"{text}\n")
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        ui["log"].scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def update_fun_message(self, ui):
        if ui["spinner"].get_spinning():
            ui["status_lbl"].set_label(random.choice(FUN_MESSAGES))
        return True

    def on_user_response(self, action):
        self.user_decision = action
        self.resume_event.set()

    def on_next(self, btn):
        if self.curr_step_name == "welcome":
            self.curr_step_name = "select"
            self.stack.set_visible_child_name("select")
            
        elif self.curr_step_name == "select":
            self.curr_step_name = "auth"
            self.stack.set_visible_child_name("auth")
            self.btn_next.set_label(self.txt["btn_install"])
            self.ui_auth["entry"].grab_focus()
            
        elif self.curr_step_name == "auth":
            pwd = self.ui_auth["entry"].get_text()
            if not pwd: return
            self.validate_sudo(pwd)
            
        elif self.curr_step_name == "finish":
            self.close()

    def validate_sudo(self, password):
        self.btn_next.set_sensitive(False)
        self.ui_auth["err"].set_visible(False)

        def check():
            try:
                cmd = ["sudo", "-S", "-v"]
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = p.communicate(input=f"{password}\n".encode())
                
                if p.returncode == 0:
                    GLib.idle_add(self.start_installation, password)
                else:
                    GLib.idle_add(self.on_auth_fail)
            except:
                GLib.idle_add(self.on_auth_fail)
        
        threading.Thread(target=check, daemon=True).start()

    def on_auth_fail(self):
        self.ui_auth["err"].set_label(self.txt["pass_err"])
        self.ui_auth["err"].set_visible(True)
        self.ui_auth["entry"].set_text("")
        self.btn_next.set_sensitive(True)

    def start_installation(self, password):
        self.sudo_pass = password
        self.curr_step_name = "proc"
        self.stack.set_visible_child_name("proc")
        self.btn_next.set_visible(False)
        self.start_thread(self.run_all_tasks, self.ui_proc)

    def run_all_tasks(self, ui):
        self.log(ui, self.txt["log_sudo_ok"])
        self.task_deps(ui)
        self.task_apps(ui)
        self.task_driver(ui)
        self.task_final(ui)

    def start_thread(self, func, ui):
        ui["prog"].set_fraction(0.1)
        ui["spinner"].start()
        self.fun_timer_id = GLib.timeout_add(3000, self.update_fun_message, ui)
        
        def runner():
            try:
                func(ui)
                GLib.idle_add(ui["prog"].set_fraction, 1.0)
                GLib.idle_add(ui["spinner"].stop)
                GLib.idle_add(ui["status_lbl"].set_label, "Tamamlandı.")
                GLib.idle_add(self.on_finish)
            except Exception as e:
                GLib.idle_add(self.log, ui, f"KRİTİK HATA: {e}", True)
                GLib.idle_add(ui["spinner"].stop)
                
        threading.Thread(target=runner, daemon=True).start()

    def on_finish(self):
        if self.fun_timer_id: GLib.source_remove(self.fun_timer_id)
        self.curr_step_name = "finish"
        self.stack.set_visible_child_name("finish")
        self.btn_next.set_visible(True)
        self.btn_next.set_label("Kapat")

    def run_cmd(self, cmd, ui):
        safe_cmd = f"bash -c '{cmd}'"
        full_cmd = f"echo '{self.sudo_pass}' | sudo -S -p '' {safe_cmd}"
        
        while True:
            self.resume_event.clear()
            p = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            while True:
                line = p.stdout.readline()
                if not line and p.poll() is not None: break
                if line: GLib.idle_add(self.log, ui, line.strip())
            
            if p.returncode == 0: return True
            
            GLib.idle_add(self.log, ui, self.txt["err_100"] if p.returncode == 100 else f">>> HATA KODU: {p.returncode}", True)
            GLib.idle_add(self.set_error_ui, True)
            self.resume_event.wait()
            GLib.idle_add(self.set_error_ui, False)
            if self.user_decision == "skip": return False

    def set_error_ui(self, active):
        self.btn_next.set_visible(True)
        self.btn_next.set_sensitive(True)
        self.btn_skip.set_visible(active)
        self.btn_next.set_label(self.txt["btn_retry"] if active else "...")
        if active: self.btn_next.add_css_class("destructive-action")
        else: self.btn_next.remove_css_class("destructive-action"); self.btn_next.set_visible(False)

    def detect_mgr(self):
        for mgr in ["dnf", "apt", "pacman", "zypper"]:
            if shutil.which(mgr): return mgr
        return None

    def task_deps(self, ui):
        GLib.idle_add(ui["status_lbl"].set_label, "Bağımlılıklar...")
        try: k_ver = subprocess.check_output(['uname', '-r']).decode().strip()
        except: k_ver = "unknown"
        cmds = []
        if self.mgr == "dnf":
            cmds.append("dnf update -y" if self.chk_update.get_active() else "true")
            cmds.append(f"dnf install -y gcc make kernel-devel-{k_ver} kernel-headers || dnf install -y gcc make kernel-devel kernel-headers")
        elif self.mgr == "apt":
            cmds.append("apt update" + (" && apt upgrade -y" if self.chk_update.get_active() else ""))
            cmds.append("apt install -y build-essential linux-headers-$(uname -r)")
        elif self.mgr == "pacman":
            cmds.append("pacman -Syu --noconfirm" if self.chk_update.get_active() else "true")
            cmds.append("pacman -S --noconfirm base-devel linux-headers")
        for c in cmds: self.run_cmd(c, ui)

    def task_apps(self, ui):
        GLib.idle_add(ui["status_lbl"].set_label, "Uygulamalar...")
        if self.chk_nvidia.get_active():
            if self.mgr == "dnf": self.run_cmd("dnf install -y akmod-nvidia", ui)
            elif self.mgr == "pacman": self.run_cmd("pacman -S --noconfirm nvidia nvidia-utils", ui)
            elif self.mgr == "apt": GLib.idle_add(self.log, ui, self.txt["log_nvidia_manual"])

        if self.chk_steam.get_active(): self.run_cmd(f"{self.mgr} install -y steam", ui)
        if self.chk_tools.get_active():
            pkgs = "gamemode mangohud goverlay lutris wine"
            self.run_cmd(f"{self.mgr} install -y {pkgs}", ui)
        if self.chk_heroic.get_active() and shutil.which("flatpak"): 
            self.run_cmd("flatpak install flathub com.heroicgameslauncher.hgl -y", ui)

    def task_driver(self, ui):
        GLib.idle_add(ui["status_lbl"].set_label, "Sürücüler...")
        cwd = os.path.join(SRC_DIR, "driver")
        if not os.path.exists(cwd): return
        
        self.run_cmd(f"cd {cwd} && make clean && make", ui)
        self.run_cmd("rmmod hp-wmi || true", ui)
        self.run_cmd(f"cd {cwd} && insmod hp-wmi.ko", ui)
        
        dest = f"/lib/modules/{os.uname().release}/kernel/drivers/platform/x86/"
        self.run_cmd(f"mkdir -p {dest}", ui)
        self.run_cmd(f"cp {cwd}/hp-wmi.ko {dest} && depmod -a", ui)
        self.run_cmd(f"echo 'hp-wmi' | tee /etc/modules-load.d/hp-wmi.conf > /dev/null", ui)

    def task_final(self, ui):
        GLib.idle_add(ui["status_lbl"].set_label, "Son Ayarlar...")
        
        # 1. Dosyaları önce temp'e yaz (Shell kaçış hatalarını önlemek için)
        tmp_svc = "/tmp/omen.service"
        tmp_desk = "/tmp/omen.desktop"
        
        try:
            with open(tmp_svc, "w") as f: f.write(SERVICE_CONTENT)
            with open(tmp_desk, "w") as f: f.write(DESKTOP_CONTENT)
        except Exception as e:
            GLib.idle_add(self.log, ui, f"Temp yazma hatası: {e}", True)

        self.run_cmd(f"mkdir -p {INSTALL_DIR}/images", ui)
        self.run_cmd(f"mkdir -p {CONFIG_DIR}", ui)
        self.run_cmd(f"cp {SRC_DIR}/backend.py {INSTALL_DIR}/backend.py", ui)
        self.run_cmd(f"cp {SRC_DIR}/gui.py {INSTALL_DIR}/gui.py", ui)
        
        img_src = os.path.join(SRC_DIR, "images")
        if os.path.exists(img_src):
            self.run_cmd(f"cp -r {img_src}/* {INSTALL_DIR}/images/", ui)
            src_logo = os.path.join(img_src, "omen_logo.png")
            if os.path.exists(src_logo):
                self.run_cmd(f"cp {src_logo} /usr/share/pixmaps/omen-control.png", ui)
                hicolor_dir = "/usr/share/icons/hicolor/256x256/apps"
                self.run_cmd(f"mkdir -p {hicolor_dir}", ui)
                self.run_cmd(f"cp {src_logo} {hicolor_dir}/omen-control.png", ui)

        self.run_cmd(f"chmod 755 {INSTALL_DIR}/backend.py", ui)
        self.run_cmd(f"chmod 755 {INSTALL_DIR}/gui.py", ui)
        self.run_cmd(f"chmod 777 {CONFIG_DIR}", ui)

        if not os.path.exists(CONFIG_FILE):
            default_conf = '{"enabled": true, "mode": 0, "zone_colors": ["#FF0000", "#FF0000", "#FF0000", "#FF0000"]}'
            self.run_cmd(f"echo '{default_conf}' | tee {CONFIG_FILE} > /dev/null", ui)
        self.run_cmd(f"chmod 666 {CONFIG_FILE}", ui)

        # 2. Temp dosyalarını taşı
        self.run_cmd(f"mv {tmp_svc} {SERVICE_FILE}", ui)
        self.run_cmd(f"mv {tmp_desk} {DESKTOP_FILE}", ui)

        self.run_cmd("systemctl daemon-reload && systemctl enable --now omen-control.service", ui)
        self.run_cmd("gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true", ui)
        
        GLib.idle_add(self.log, ui, ">>> BAŞARIYLA TAMAMLANDI.")

if __name__ == "__main__":
    app = Adw.Application(application_id="com.victus.setup")
    app.connect("activate", lambda a: InstallWizard(application=a).present())
    app.run(sys.argv)