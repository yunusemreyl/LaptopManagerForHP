import sys, os, subprocess, shutil, threading, json, locale
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gdk

# --- KURULUM SABİTLERİ ---
INSTALL_DIR = "/opt/omen-control"
CONFIG_DIR = "/etc/omen-control"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SERVICE_FILE = "/etc/systemd/system/omen-control.service"
DESKTOP_FILE = "/usr/share/applications/omen-control.desktop"

# --- DİL SÖZLÜĞÜ ---
LANGS = {
    "tr": {
        "title": "Omen Kontrol Kurulumu",
        "welcome_title": "HP Cihaz Yapılandırma Aracı",
        "welcome_desc": "Bu araç, HP Victus/Omen cihazınızı Linux üzerinde tam performansla kullanmanız için gereken sürücüleri, RGB kontrol merkezini ve oyun kütüphanelerini kurarak sisteminizi kullanıma hazır hale getirir.",
        "step_select": "Kurulum Seçenekleri",
        "step_select_desc": "Sisteminize eklemek istediğiniz bileşenleri seçin:",
        "lbl_nvidia": "NVIDIA Sürücüleri",
        "sub_nvidia": "Tescilli sürücüler, CUDA ve donanım hızlandırma paketleri.",
        "lbl_update": "Sistem Güncellemesi",
        "sub_update": "Kuruluma başlamadan önce tüm sistem paketlerini günceller.",
        "lbl_steam": "Steam",
        "sub_steam": "Dünyanın en popüler dijital oyun mağazası ve platformu.",
        "lbl_heroic": "Heroic Games Launcher",
        "sub_heroic": "Epic Games, GOG ve Amazon Prime oyunlarını çalıştırmak için açık kaynaklı başlatıcı.",
        "lbl_libs": "Oyun Kütüphaneleri",
        "sub_libs": "Oyun performansı için Gamemode, Lutris ve Wine bağımlılıkları.",
        "p_deps": "Adım 1/4: Temel Paketler",
        "d_deps": "Gerekli Python ve sistem araçları yükleniyor...",
        "p_driver": "Adım 2/4: Sürücü",
        "d_driver": "hp-wmi çekirdek modülü derleniyor ve sisteme işleniyor...",
        "p_app": "Adım 3/4: Omen Control",
        "d_app": "Uygulama dosyaları kopyalanıyor ve servisler başlatılıyor...",
        "p_extra": "Adım 4/4: Ekstra Paketler",
        "d_extra": "Seçtiğiniz oyun ve donanım araçları kuruluyor...",
        "finish_title": "Kurulum Tamamlandı!",
        "finish_desc": "Cihazınız kullanıma hazır.\nDeğişikliklerin tam olarak uygulanması için bilgisayarı yeniden başlatmanız önerilir.",
        "btn_next": "İleri >",
        "btn_start": "Kurulumu Başlat",
        "btn_close": "Kapat",
        "btn_retry": "Hata (Tekrar Dene)",
        "msg_no_select": "Ekstra bir seçim yapılmadı, bu adım atlanıyor...",
        "msg_error": "HATA",
        "log_start": ">>> İşlem başlatılıyor...",
        "log_flatpak_add": ">>> Flatpak deposu ekleniyor...",
        "log_flatpak_err": "Flatpak bulunamadı, Heroic kurulamadı."
    },
    "en": {
        "title": "Omen Control Setup",
        "welcome_title": "HP Device Configuration Tool",
        "welcome_desc": "This tool creates a ready-to-use environment for your HP Victus/Omen device on Linux. It installs necessary drivers, the RGB control center, and gaming utilities to ensure maximum performance.",
        "step_select": "Installation Options",
        "step_select_desc": "Select the components you want to add to your system:",
        "lbl_nvidia": "NVIDIA Drivers",
        "sub_nvidia": "Proprietary drivers, CUDA, and hardware acceleration packages.",
        "lbl_update": "System Update",
        "sub_update": "Updates all system packages before starting installation.",
        "lbl_steam": "Steam",
        "sub_steam": "The world's most popular digital game store and platform.",
        "lbl_heroic": "Heroic Games Launcher",
        "sub_heroic": "Open source launcher for Epic Games, GOG, and Amazon Prime games.",
        "lbl_libs": "Gaming Libraries",
        "sub_libs": "Gamemode, Lutris, and Wine dependencies for gaming performance.",
        "p_deps": "Step 1/4: Basic Packages",
        "d_deps": "Installing necessary Python and system tools...",
        "p_driver": "Step 2/4: Driver",
        "d_driver": "Compiling and registering the hp-wmi kernel module...",
        "p_app": "Step 3/4: Omen Control",
        "d_app": "Copying application files and starting services...",
        "p_extra": "Step 4/4: Extra Packages",
        "d_extra": "Installing selected gaming and hardware tools...",
        "finish_title": "Installation Complete!",
        "finish_desc": "Your device is ready to use.\nIt is recommended to restart your computer to apply all changes.",
        "btn_next": "Next >",
        "btn_start": "Start Installation",
        "btn_close": "Close",
        "btn_retry": "Error (Retry)",
        "msg_no_select": "No extra selection made, skipping this step...",
        "msg_error": "ERROR",
        "log_start": ">>> Process started...",
        "log_flatpak_add": ">>> Adding Flatpak repository...",
        "log_flatpak_err": "Flatpak not found, skipping Heroic."
    }
}

# --- SERVİS VE KISAYOL İÇERİKLERİ ---
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
Icon={INSTALL_DIR}/images/omen_logo.png
Terminal=false
Type=Application
Categories=Utility;Settings;
"""

class InstallWizard(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Dil Algılama
        sys_lang = locale.getdefaultlocale()[0]
        self.lang_code = "tr" if sys_lang and "TR" in sys_lang.upper() else "en"
        self.txt = LANGS[self.lang_code]

        self.set_title(self.txt["title"])
        self.set_default_size(650, 600)
        self.set_resizable(False)

        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        self.distro = self.detect_distro()

        # Checkboxlar
        self.chk_nvidia = Gtk.CheckButton()
        self.chk_steam = Gtk.CheckButton()
        self.chk_heroic = Gtk.CheckButton()
        self.chk_libs = Gtk.CheckButton()
        self.chk_update = Gtk.CheckButton()

        self.pages = []
        self.current_page_idx = 0

        self.setup_ui()

    def detect_distro(self):
        try:
            with open("/etc/os-release") as f:
                data = f.read().lower()
                if "fedora" in data: return "fedora"
                if "ubuntu" in data or "debian" in data: return "debian"
                if "arch" in data: return "arch"
        except: pass
        return "linux"

    def setup_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header Bar & Logo
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)

        # Logoyu HeaderBar'a ekle (Eğer varsa)
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "omen_logo.png")
        if os.path.exists(logo_path):
            img = Gtk.Image.new_from_file(logo_path)
            img.set_pixel_size(24)
            img.set_margin_end(10)
            header.pack_start(img)

        main_box.append(header)

        # Sayfa Yığını
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack.set_transition_duration(400)
        self.stack.set_hexpand(True); self.stack.set_vexpand(True)
        main_box.append(self.stack)

        # --- SAYFALAR ---
        self.add_page(self.create_welcome_page(), "welcome")
        self.ui_select = self.create_selection_page()
        self.add_page(self.ui_select["box"], "select")

        self.ui_deps = self.create_progress_page(self.txt["p_deps"], self.txt["d_deps"])
        self.add_page(self.ui_deps["box"], "deps")

        self.ui_driver = self.create_progress_page(self.txt["p_driver"], self.txt["d_driver"])
        self.add_page(self.ui_driver["box"], "driver")

        self.ui_app = self.create_progress_page(self.txt["p_app"], self.txt["d_app"])
        self.add_page(self.ui_app["box"], "app")

        self.ui_extras = self.create_progress_page(self.txt["p_extra"], self.txt["d_extra"])
        self.add_page(self.ui_extras["box"], "extras")

        self.add_page(self.create_finish_page(), "finish")

        # Alt Bar
        action_bar = Gtk.ActionBar()
        main_box.append(action_bar)

        self.btn_next = Gtk.Button(label=self.txt["btn_next"], css_classes=["suggested-action"])
        self.btn_next.set_size_request(160, -1)
        self.btn_next.connect("clicked", self.on_next)

        end_pack = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        end_pack.set_hexpand(True); end_pack.set_halign(Gtk.Align.END)
        end_pack.append(self.btn_next)
        action_bar.pack_end(end_pack)

    def add_page(self, widget, name):
        self.stack.add_named(widget, name)
        self.pages.append(name)

    def create_welcome_page(self):
        page = Adw.StatusPage()
        page.set_icon_name("system-software-install-symbolic")
        page.set_title(self.txt["welcome_title"])
        page.set_description(self.txt["welcome_desc"])
        return page

    def create_selection_page(self):
        scrolled = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=20, margin_bottom=20, margin_start=40, margin_end=40)
        scrolled.set_child(box)

        box.append(Gtk.Label(label=self.txt["step_select"], css_classes=["title-2"], xalign=0))
        box.append(Gtk.Label(label=self.txt["step_select_desc"], css_classes=["body"], xalign=0))

        grp = Adw.PreferencesGroup()
        r1 = Adw.ActionRow(title=self.txt["lbl_nvidia"], subtitle=self.txt["sub_nvidia"])
        r1.add_prefix(self.chk_nvidia); grp.add(r1)
        r2 = Adw.ActionRow(title=self.txt["lbl_update"], subtitle=self.txt["sub_update"])
        r2.add_prefix(self.chk_update); grp.add(r2)
        box.append(grp)

        grp2 = Adw.PreferencesGroup(title="Gaming")
        r3 = Adw.ActionRow(title=self.txt["lbl_steam"], subtitle=self.txt["sub_steam"])
        r3.add_prefix(self.chk_steam); grp2.add(r3)
        r4 = Adw.ActionRow(title=self.txt["lbl_heroic"], subtitle=self.txt["sub_heroic"])
        r4.add_prefix(self.chk_heroic); grp2.add(r4)
        r5 = Adw.ActionRow(title=self.txt["lbl_libs"], subtitle=self.txt["sub_libs"])
        r5.add_prefix(self.chk_libs); grp2.add(r5)
        box.append(grp2)
        return {"box": scrolled}

    def create_progress_page(self, title, desc):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=30, margin_bottom=30, margin_start=30, margin_end=30)
        box.append(Gtk.Label(label=title, css_classes=["title-2"], xalign=0))
        box.append(Gtk.Label(label=desc, css_classes=["body"], xalign=0, opacity=0.7))
        scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scrolled.add_css_class("frame")
        log = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD, bottom_margin=10, left_margin=10, top_margin=10)
        p = Gtk.CssProvider(); p.load_from_data(b"textview text { background-color: #101010; color: #33ff33; font-size: 11px; }")
        log.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        scrolled.set_child(log); box.append(scrolled)
        prog = Gtk.ProgressBar(); box.append(prog)
        return {"box": box, "log": log, "prog": prog, "buffer": log.get_buffer()}

    def create_finish_page(self):
        page = Adw.StatusPage()
        page.set_icon_name("object-select-symbolic")
        page.set_title(self.txt["finish_title"])
        page.set_description(self.txt["finish_desc"])
        return page

    def log(self, ui, text):
        buf = ui["buffer"]; end = buf.get_end_iter()
        buf.insert(end, text + "\n")
        ui["log"].scroll_to_mark(buf.create_mark(None, end, False), 0.0, True, 0.0, 1.0)

    def run_thread(self, task, ui):
        self.btn_next.set_sensitive(False)
        ui["prog"].set_fraction(0.1)
        def worker():
            try:
                task(ui)
                GLib.idle_add(ui["prog"].set_fraction, 1.0)
                GLib.idle_add(self.next_step)
            except Exception as e:
                GLib.idle_add(self.log, ui, f"\n{self.txt['msg_error']}: {e}")
                GLib.idle_add(ui["prog"].set_fraction, 0.0)
                GLib.idle_add(self.btn_next.set_sensitive, True)
                GLib.idle_add(self.btn_next.set_label, self.txt["btn_retry"])
        threading.Thread(target=worker, daemon=True).start()

    def run_cmd(self, cmd, ui):
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            if line: GLib.idle_add(self.log, ui, line.strip())
        if proc.returncode != 0: raise Exception(f"Exit Code: {proc.returncode}")

    def next_step(self):
        if self.current_page_idx < len(self.pages) - 1:
            self.current_page_idx += 1
            page_name = self.pages[self.current_page_idx]
            self.stack.set_visible_child_name(page_name)
            self.btn_next.set_sensitive(True)
            if page_name == "select": self.btn_next.set_label(self.txt["btn_start"])
            elif page_name == "deps": self.run_thread(self.task_deps, self.ui_deps)
            elif page_name == "driver": self.run_thread(self.task_driver, self.ui_driver)
            elif page_name == "app": self.run_thread(self.task_app, self.ui_app)
            elif page_name == "extras":
                if not any([self.chk_nvidia.get_active(), self.chk_steam.get_active(), self.chk_heroic.get_active(), self.chk_libs.get_active(), self.chk_update.get_active()]):
                    self.log(self.ui_extras, self.txt["msg_no_select"])
                    self.next_step()
                else: self.run_thread(self.task_extras, self.ui_extras)
            elif page_name == "finish": self.btn_next.set_label(self.txt["btn_close"])

    def on_next(self, btn):
        if self.current_page_idx == len(self.pages) - 1: self.close()
        else: self.next_step()

    def task_deps(self, ui):
        GLib.idle_add(self.log, ui, self.txt["log_start"])
        cmd = ""
        if self.distro == "fedora": cmd = "dnf install python3-psutil python3-gobject gtk4 libadwaita kernel-devel gcc make -y"
        elif self.distro == "debian": cmd = "apt update && apt install python3-psutil python3-gi libgtk-4-dev libadwaita-1-dev build-essential linux-headers-$(uname -r) -y"
        elif self.distro == "arch": cmd = "pacman -S python-psutil python-gobject gtk4 libadwaita base-devel linux-headers --noconfirm"
        if cmd: self.run_cmd(cmd, ui)

    def task_driver(self, ui):
        GLib.idle_add(self.log, ui, self.txt["log_start"])
        cwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "driver")
        self.run_cmd(f"cd {cwd} && make clean", ui)
        self.run_cmd(f"cd {cwd} && make", ui)
        try: self.run_cmd("rmmod hp-wmi", ui)
        except: pass
        self.run_cmd(f"cd {cwd} && insmod hp-wmi.ko", ui)
        dest = f"/lib/modules/{os.uname().release}/kernel/drivers/platform/x86/"
        self.run_cmd(f"cp {cwd}/hp-wmi.ko {dest}", ui)
        self.run_cmd("depmod -a", ui)

    def task_app(self, ui):
        GLib.idle_add(self.log, ui, self.txt["log_start"])
        if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)
        if not os.path.exists(INSTALL_DIR + "/images"): os.makedirs(INSTALL_DIR + "/images")

        src = os.path.dirname(os.path.abspath(__file__))
        shutil.copy(f"{src}/backend.py", f"{INSTALL_DIR}/backend.py")
        shutil.copy(f"{src}/gui.py", f"{INSTALL_DIR}/gui.py")
        if os.path.exists(f"{src}/images/keyboard.png"): shutil.copy(f"{src}/images/keyboard.png", f"{INSTALL_DIR}/images/keyboard.png")
        if os.path.exists(f"{src}/images/omen_logo.png"): shutil.copy(f"{src}/images/omen_logo.png", f"{INSTALL_DIR}/images/omen_logo.png")

        os.chmod(f"{INSTALL_DIR}/backend.py", 0o755); os.chmod(f"{INSTALL_DIR}/gui.py", 0o755)

        # Config ve İzinler (666)
        if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
        os.chmod(CONFIG_DIR, 0o777)
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                json.dump({"enabled": True, "mode": 0, "zone_colors": ["#FF0000"]*4, "bri": 1.0, "spd": 50, "power": "balanced"}, f)
        os.chmod(CONFIG_FILE, 0o666) # GUI yazabilsin diye

        with open(SERVICE_FILE, "w") as f: f.write(SERVICE_CONTENT)
        with open(DESKTOP_FILE, "w") as f: f.write(DESKTOP_CONTENT)

        self.run_cmd("systemctl daemon-reload", ui)
        self.run_cmd("systemctl enable --now omen-control.service", ui)

    def task_extras(self, ui):
        GLib.idle_add(self.log, ui, self.txt["log_start"])
        if self.chk_update.get_active():
            if self.distro == "fedora": self.run_cmd("dnf update -y", ui)
            elif self.distro == "debian": self.run_cmd("apt update && apt upgrade -y", ui)
            elif self.distro == "arch": self.run_cmd("pacman -Syu --noconfirm", ui)

        if self.chk_nvidia.get_active():
            if self.distro == "fedora": self.run_cmd("dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda -y", ui)
            elif self.distro == "debian": self.run_cmd("apt install nvidia-driver firmware-misc-nonfree -y", ui)
            elif self.distro == "arch": self.run_cmd("pacman -S nvidia nvidia-utils --noconfirm", ui)

        if self.chk_steam.get_active():
            if self.distro == "fedora": self.run_cmd("dnf install steam -y", ui)
            elif self.distro == "debian": self.run_cmd("apt install steam -y", ui)
            elif self.distro == "arch": self.run_cmd("pacman -S steam --noconfirm", ui)

        if self.chk_heroic.get_active():
            GLib.idle_add(self.log, ui, self.txt["log_flatpak_add"])
            if shutil.which("flatpak"):
                self.run_cmd("flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo", ui)
                self.run_cmd("flatpak install flathub com.heroicgameslauncher.hgl -y", ui)
            else:
                GLib.idle_add(self.log, ui, self.txt["log_flatpak_err"])

        if self.chk_libs.get_active():
            if self.distro == "fedora": self.run_cmd("dnf install gamemode lutris wine -y", ui)
            elif self.distro == "debian": self.run_cmd("apt install gamemode lutris wine -y", ui)
            elif self.distro == "arch": self.run_cmd("pacman -S gamemode lutris wine --noconfirm", ui)

if __name__ == "__main__":
    app = Adw.Application(application_id="com.victus.setup")
    app.connect("activate", lambda a: InstallWizard(application=a).present())
    app.run(sys.argv)
