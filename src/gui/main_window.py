#!/usr/bin/env python3
import sys, os, json, cairo, gi, math, time, platform, subprocess, shutil, locale, colorsys, glob
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Pango, PangoCairo
from pydbus import SystemBus

APP_VERSION = "3.0-Final"
CONFIG_FILE = os.path.expanduser("~/.config/omen-control.json")

# --- ÇEVİRİ ALTYAPISI ---
# Varsayılan dil (Config'den yüklenecek)
active_lang = "en"

TRANSLATIONS = {
    "en": {
        "dash": "Dashboard", "rgb": "Lighting", "perf": "Thermals", "mux": "GPU Switcher", "set": "Settings",
        "cpu_temp": "CPU", "gpu_temp": "GPU", "ram": "RAM", "health": "Health",
        "disk": "DISK", "bat": "BATTERY", "uptime": "UPTIME",
        "l_pwr": "Keyboard Power", "eff": "Effect", "dir": "Direction", "spd": "Speed", "bri": "Brightness",
        "mux_tit": "GPU Mode", "mux_desc": "Reboot required to apply changes.",
        "hybrid": "Hybrid", "disc": "Discrete", "integ": "Integrated",
        "h_desc": "Balanced", "d_desc": "Gaming", "i_desc": "Eco",
        "z1": "Zone 1", "z2": "Zone 2", "z3": "Zone 3", "z4": "Zone 4", "all": "All Zones",
        "fan_msg": "Kernel 6.20+ Required", "fan_sub": "Fan control will be active with the 6.20 kernel update.",
        "theme": "App Theme", "dark": "Dark Mode", "light": "Light Mode",
        "driver": "Driver", "kernel": "Kernel",
        "reboot_tit": "Restart Required", "reboot_msg": "System needs to restart to apply GPU mode.",
        "dev_by": "Developed by",
        "disclaimer": "This tool is not affiliated with Hewlett Packard.",
        "lang": "Language"
    },
    "tr": {
        "dash": "Genel Bakış", "rgb": "Aydınlatma", "perf": "Termal Durum", "mux": "GPU Yönetimi", "set": "Ayarlar",
        "cpu_temp": "CPU", "gpu_temp": "GPU", "ram": "RAM", "health": "Ömür",
        "disk": "DİSK", "bat": "BATARYA", "uptime": "SÜRE",
        "l_pwr": "Klavye Işığı", "eff": "Efekt", "dir": "Yön", "spd": "Hız", "bri": "Parlaklık",
        "mux_tit": "GPU Modu", "mux_desc": "Değişiklik için yeniden başlatma gerekir.",
        "hybrid": "Hibrit", "disc": "Harici", "integ": "Dahili",
        "h_desc": "Dengeli", "d_desc": "Performans", "i_desc": "Tasarruf",
        "z1": "1. Bölge", "z2": "2. Bölge", "z3": "3. Bölge", "z4": "4. Bölge", "all": "Tümü",
        "fan_msg": "Kernel 6.20+ Gerekiyor", "fan_sub": "Fan kontrolü 6.20 kernel güncellemesiyle aktif olacaktır.",
        "theme": "Uygulama Teması", "dark": "Karanlık Mod", "light": "Açık Mod",
        "driver": "Sürücü", "kernel": "Çekirdek",
        "reboot_tit": "Yeniden Başlat", "reboot_msg": "GPU modunu değiştirmek için sistemin yeniden başlatılması gerekiyor.",
        "dev_by": "Geliştirici:",
        "disclaimer": "Bu aracın <b>Hewlett Packard</b> ile resmi bir bağlantısı bulunmamaktadır.",
        "lang": "Dil / Language"
    }
}

def T(k):
    # Global değişkeni kullanarak çeviri yap
    return TRANSLATIONS.get(active_lang, TRANSLATIONS["en"]).get(k, k)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_PATHS = [
    os.path.expanduser("~/hp-control-center/images"),
    os.path.abspath(os.path.join(BASE_DIR, "../../images")),
    "/usr/share/hp-control-center/images"
]
IMG_DIR = next((p for p in SEARCH_PATHS if os.path.exists(p)), "/tmp")
KEYBOARD_IMG = os.path.join(IMG_DIR, "keyboard.png")
LOGO_IMG = os.path.join(IMG_DIR, "omen_logo.png")
HP_LOGO_IMG = os.path.join(IMG_DIR, "hp_logo.png")
PRESETS = ["#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#FFFF00", "#00FFFF", "#FF00FF"]

class SysMonitor:
    def __init__(self):
        self.last_cpu = self._read_cpu()
        self.bat_path = next((f"/sys/class/power_supply/{b}" for b in ["BAT0", "BAT1", "BAT2"] if os.path.exists(f"/sys/class/power_supply/{b}")), None)
        self.hostname = platform.node(); self.kernel = platform.release()
        self.distro = self._get_distro(); self.nvidia_detail = self._get_nvidia_detail()
        self.cpu_model = self._get_cpu_model()

    def _read_cpu(self):
        try: l = open('/proc/stat').readline().split(); return (sum(float(x) for x in l[1:]), float(l[4]))
        except: return (0,0)
    def get_ram(self):
        try: m={l.split()[0].rstrip(':'):int(l.split()[1]) for l in open('/proc/meminfo')}; return (m['MemTotal']-m['MemAvailable'])/m['MemTotal']*100
        except: return 0
    def get_disk_perc(self): 
        try: t, u, f = shutil.disk_usage("/"); return (u / t) * 100
        except: return 0
    def get_battery_perc(self):
        try: return int(open(f"{self.bat_path}/capacity").read()) if self.bat_path else 0
        except: return 0
    def get_battery_health(self):
        try: return int((int(open(f"{self.bat_path}/charge_full").read()) / int(open(f"{self.bat_path}/charge_full_design").read())) * 100) if self.bat_path else 100
        except: return 100
    def get_cpu_temp(self):
        for p in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
            try: return int(open(p).read()) / 1000
            except: pass
        return 0
    def get_gpu_temp(self):
        try: return float(subprocess.check_output(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"]).decode().strip())
        except: return 0
    def _get_nvidia_detail(self):
        if shutil.which("nvidia-smi"):
            try:
                m = subprocess.check_output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]).decode("utf-8").strip().split('\n')[0]
                v = subprocess.check_output(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]).decode("utf-8").strip().split('\n')[0]
                return (m, v)
            except: return ("NVIDIA", "N/A")
        return ("GPU", "N/A")
    def _get_distro(self):
        try: return subprocess.check_output(["lsb_release", "-ds"]).decode().strip().replace('"', '')
        except: return "Linux"
    def _get_cpu_model(self):
        try: return open("/proc/cpuinfo").read().split("model name")[1].split(":")[1].split("\n")[0].strip().split("@")[0].strip()
        except: return "Unknown CPU"
    def get_uptime(self):
        try: s=float(open('/proc/uptime').readline().split()[0]); return f"{int(s//3600)}h {int((s%3600)//60)}m"
        except: return "-"

monitor = SysMonitor()

class CircularGauge(Gtk.DrawingArea):
    def __init__(self, label, color, theme="dark"):
        super().__init__(); self.set_size_request(180, 180); self.label=label; self.color=color; self.val=0; self.txt="0°"; self.theme = theme
        self.set_draw_func(self.draw)
    def update_theme(self, theme): self.theme = theme; self.queue_draw()
    def set_val(self, v, t): self.val=v; self.txt=t; self.queue_draw()
    def draw(self, _, cr, w, h):
        cx, cy = w/2, h/2; r = 60
        bg_col = (0.9, 0.9, 0.9, 1) if self.theme == "light" else (0.3, 0.3, 0.3, 1)
        fg_col = (0.2, 0.2, 0.2) if self.theme == "light" else (1, 1, 1) 
        cr.set_line_width(8); cr.set_source_rgba(*bg_col); cr.arc(cx,cy,r,0,2*math.pi); cr.stroke()
        cr.set_line_width(8); cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_source_rgb(*self.color)
        cr.arc(cx, cy, r, -math.pi/2, -math.pi/2 + (2*math.pi*(self.val/100))); cr.stroke()
        cr.set_source_rgb(*fg_col); l = PangoCairo.create_layout(cr); l.set_text(self.txt, -1); l.set_font_description(Pango.FontDescription("Sans Bold 28"))
        ink, log = l.get_extents(); cr.move_to(cx - (log.width/Pango.SCALE)/2, cy - (log.height/Pango.SCALE)/2 - 5); PangoCairo.show_layout(cr, l)
        cr.set_source_rgba(fg_col[0], fg_col[1], fg_col[2], 0.7); l2 = PangoCairo.create_layout(cr); l2.set_text(self.label, -1); l2.set_font_description(Pango.FontDescription("Sans Bold 11"))
        ink2, log2 = l2.get_extents(); cr.move_to(cx - (log2.width/Pango.SCALE)/2, cy + 35); PangoCairo.show_layout(cr, l2)

class OmenMainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.set_title("HP Omen Control"); self.set_default_size(1200, 850)
        
        # PENCERE İKONU
        if os.path.exists(LOGO_IMG):
            try: Gdk.Texture.new_from_filename(LOGO_IMG)
            except: pass

        self.service=None; self.ready=False; self.power=True; self.mode="static"
        self.speed=50; self.brightness=100; self.direction="ltr"
        self.zone_rgba=[Gdk.RGBA() for _ in range(4)]; [c.parse("red") for c in self.zone_rgba]; self.selected_zone=4
        
        self.app_theme = "dark"
        self.dash_timer = None # Timer'ları takip etmek için
        self.anim_id = None
        
        self.load_config() # Dili ve temayı yükle
        self.rebuild_ui() # Arayüzü oluştur

    def load_config(self):
        global active_lang
        try:
            if os.path.exists(CONFIG_FILE): 
                data = json.load(open(CONFIG_FILE))
                self.app_theme = data.get("theme", "dark")
                active_lang = data.get("lang", "en") # Kayıtlı dili çek
        except: pass

    def save_config(self):
        try: json.dump({"theme": self.app_theme, "lang": active_lang}, open(CONFIG_FILE, 'w'))
        except: pass

    # --- CANLI ARAYÜZ YENİLEME (HOT RELOAD) ---
    def rebuild_ui(self):
        # Eski timerları temizle
        if self.dash_timer: GLib.source_remove(self.dash_timer)
        if self.anim_id: GLib.source_remove(self.anim_id)
        
        # Mevcut arayüzü temizle
        self.set_child(None)
        
        # Yeni ayarlarla CSS ve UI yükle
        self.load_css()
        self.setup_ui()
        
        # Timerları tekrar başlat
        self.connect_daemon() # İlk bağlantı denemesi
        self.dash_timer = GLib.timeout_add(2000, self.update_dash)
        self.anim_id = GLib.timeout_add(33, self.draw_anim)

    def load_css(self):
        if self.app_theme == "light":
            bg = "#fafafa"; fg = "#333333"; sidebar_bg = "#ffffff"; sidebar_border = "rgba(0,0,0,0.05)"
            card_bg = "#ffffff"; card_border = "rgba(0,0,0,0.08)"; pill_bg = "#f0f0f0"; pill_fg = "#555"
            btn_bg = "#f5f5f5"; btn_border = "#e0e0e0"; btn_check_bg = "#ffebee"
            row_hover = "rgba(0,0,0,0.05)"; row_sel = "#d32f2f"; row_fg = "#666"
            stat_lbl_col = "#777"; mux_icon_col = "#333333"
            scale_trough = "#e0e0e0"; dropdown_bg = "#f0f0f0"; dropdown_fg = "#333"
            brand_title = "#222"; brand_sub = "#d32f2f"
            hp_logo_filter = "none"
        else: # Dark Mode
            bg = "#242424"; fg = "#ffffff"; sidebar_bg = "#242424"; sidebar_border = "rgba(255,255,255,0.08)"
            card_bg = "#303030"; card_border = "rgba(255,255,255,0.1)"; pill_bg = "rgba(255,255,255,0.1)"; pill_fg = "#ffffff"
            btn_bg = "rgba(255,255,255,0.08)"; btn_border = "rgba(255,255,255,0.1)"; btn_check_bg = "rgba(211, 47, 47, 0.4)"
            row_hover = "rgba(255,255,255,0.1)"; row_sel = "rgba(255,255,255,0.15)"; row_fg = "#ffffff"
            stat_lbl_col = "#e0e0e0"; mux_icon_col = "#ffffff"; scale_trough = "rgba(255,255,255,0.2)"; dropdown_bg = "rgba(255,255,255,0.08)"; dropdown_fg = "#fff"
            brand_title = "#ffffff"; brand_sub = "#ff5252"
            hp_logo_filter = "invert(1)"

        cols = "".join([f".col-{i} {{ background-color: {c}; border-radius: 50%; min-width: 26px; min-height: 26px; padding: 0px; margin: 6px; border: 2px solid {card_border}; box-shadow: none; transition: 0.2s; }}\n.col-{i}:hover {{ transform: scale(1.2); border-color: {fg}; }}" for i,c in enumerate(PRESETS)])
        
        css = f"""
        window {{ background-color: {bg}; color: {fg}; }}
        .sidebar {{ background-color: {sidebar_bg}; border-right: 1px solid {sidebar_border}; }}
        .sidebar row {{ padding: 12px 16px; margin: 4px 10px; border-radius: 8px; font-weight: 600; color: {row_fg}; transition: 0.2s; }}
        .sidebar row:selected {{ background: {row_sel}; color: {fg}; }}
        .card {{ background-color: {card_bg}; border-radius: 16px; border: 1px solid {card_border}; padding: 24px; }}
        
        .app-title {{ font-size: 28px; font-weight: 900; letter-spacing: 2px; color: {brand_title}; margin-bottom: 2px; }}
        .app-sub {{ font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: {brand_sub}; opacity: 0.9; }}

        dropdown {{ background: transparent; border: none; box-shadow: none; }}
        dropdown > button {{ background-color: {dropdown_bg}; color: {dropdown_fg}; border: none; border-radius: 8px; padding: 6px 12px; box-shadow: none; }}
        dropdown > popover {{ background-color: {card_bg}; border: 1px solid {card_border}; box-shadow: none; }}
        dropdown > popover > contents {{ background: transparent; border: none; padding: 0; margin: 0; box-shadow: none; }}
        listview {{ background-color: transparent; border: none; }}
        
        scale trough {{ background-color: {scale_trough}; border-radius: 4px; }}
        scale highlight {{ background-color: #3584e4; border-radius: 4px; }}
        
        .page-title {{ font-size: 26px; font-weight: 800; margin-bottom: 25px; opacity: 1.0; color: {fg}; }}
        .section-title {{ font-size: 11px; font-weight: 700; color: {stat_lbl_col}; text-transform: uppercase; letter-spacing: 1.5px; }}
        .stat-big {{ font-size: 22px; font-weight: 800; color: {fg}; }}
        .stat-lbl {{ font-size: 12px; color: {stat_lbl_col}; font-weight: 600; }}
        .zone-btn {{ background: {btn_bg}; color: {fg}; border: 1px solid {btn_border}; border-radius: 20px; padding: 8px 16px; margin: 0 4px; font-weight: 600; transition: 0.2s; }}
        .zone-btn:checked {{ background: #d32f2f; color: white; border-color: #d32f2f; }}
        .mux-btn {{ background-color: {btn_bg}; border: 2px solid {btn_border}; border-radius: 24px; transition: 0.2s; padding: 0px; color: {mux_icon_col}; }}
        .mux-btn:checked {{ background-image: linear-gradient(135deg, #d32f2f, #9a0000); border-color: #ff5252; box-shadow: 0 8px 25px rgba(211,47,47,0.25); color: white; }}
        .warning-box {{ background-color: rgba(255, 200, 0, 0.1); border: 1px solid rgba(255, 200, 0, 0.3); border-radius: 12px; padding: 30px; }}
        .warning-text {{ color: #ffcc00; font-weight: 800; font-size: 18px; }}
        .warning-sub {{ color: #e6b800; font-weight: 600; font-size: 13px; }}
        .pill {{ background: {pill_bg}; color: {pill_fg}; border-radius: 20px; padding: 8px 16px; font-size: 12px; font-weight: 600; margin: 5px; border: 1px solid {card_border}; }}
        .kb-frame {{ background: rgba(0,0,0,0.2); border: 1px solid {card_border}; border-radius: 20px; padding: 10px; }}
        levelbar block.low {{ background-color: #d32f2f; }} levelbar block.high {{ background-color: #2ecc71; }}
        
        .disclaimer-box {{ border: 1px solid {card_border}; border-radius: 12px; padding: 20px; background-color: {btn_bg}; }}
        .hp-logo {{ filter: {hp_logo_filter}; }}
        """ + cols
        
        self.provider = Gtk.CssProvider()
        self.provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def setup_ui(self):
        hbox=Gtk.Box(orientation=0); self.set_child(hbox)
        sb=Gtk.Box(orientation=1); sb.add_css_class("sidebar"); sb.set_size_request(260,-1); hbox.append(sb)
        
        lb=Gtk.Box(orientation=1, spacing=4, margin_top=45, margin_bottom=45, halign=3)
        if os.path.exists(LOGO_IMG): 
            img=Gtk.Image.new_from_file(LOGO_IMG); img.set_pixel_size(72); img.set_margin_bottom(10); lb.append(img)
        lb.append(Gtk.Label(label="OMEN", css_classes=["app-title"]))
        lb.append(Gtk.Label(label="CONTROL CENTER", css_classes=["app-sub"]))
        sb.append(lb)
        
        self.stack=Gtk.Stack(); self.top_ls=Gtk.ListBox(); self.top_ls.connect("row-selected", self.on_menu)
        for p,l,i in [("sys",T("dash"),"computer-symbolic"),("rgb",T("rgb"),"weather-clear-night-symbolic"),("perf",T("perf"),"weather-tornado-symbolic"),("mux",T("mux"),"video-display-symbolic")]:
            self.add_menu_item(self.top_ls, p, l, i)
        sb.append(self.top_ls); sb.append(Gtk.Label(vexpand=True))
        self.bot_ls=Gtk.ListBox(); self.bot_ls.connect("row-selected", self.on_menu); self.add_menu_item(self.bot_ls, "set", T("set"), "emblem-system-symbolic"); sb.append(self.bot_ls)
        cont=Gtk.Box(orientation=1, hexpand=True); cont.append(self.stack); hbox.append(cont)
        for pid in ["sys","rgb","perf","mux","set"]: self.stack.add_named(getattr(self, f"create_{pid}")(), pid)
        self.top_ls.select_row(self.top_ls.get_row_at_index(0))

    def add_menu_item(self, ls, pid, lbl, ico):
        r=Gtk.ListBoxRow(); r.pid=pid; b=Gtk.Box(spacing=15, margin_start=20, margin_top=10, margin_bottom=10)
        b.append(Gtk.Image.new_from_icon_name(ico)); b.append(Gtk.Label(label=lbl)); r.set_child(b); ls.append(r)

    def on_menu(self, ls, row):
        if row: (self.bot_ls if ls == self.top_ls else self.top_ls).select_row(None); self.stack.set_visible_child_name(row.pid)

    # --- GUI BÖLÜMLERİ ---
    def create_sys(self):
        v=Gtk.Box(orientation=1, spacing=30, margin_top=40, margin_start=50, margin_end=50)
        v.append(Gtk.Label(label=T("dash"), xalign=0, css_classes=["page-title"]))
        ib=Gtk.FlowBox(min_children_per_line=3, selection_mode=0)
        nv_model, nv_ver = monitor.nvidia_detail
        info=[("computer-symbolic", monitor.hostname), ("applications-system-symbolic", monitor.distro), ("video-display-symbolic", nv_model), ("applications-engineering-symbolic", f"{T('driver')}: {nv_ver}"), ("cpu-symbolic", monitor.cpu_model), ("network-server-symbolic", f"{T('kernel')}: {monitor.kernel}")]
        for i,t in info:
            b=Gtk.Box(spacing=10); b.add_css_class("pill"); b.append(Gtk.Image.new_from_icon_name(i)); b.append(Gtk.Label(label=t)); ib.append(b)
        v.append(ib)
        c1=Gtk.Box(orientation=1, spacing=20); c1.add_css_class("card")
        r1=Gtk.Grid(column_spacing=80, row_spacing=20, halign=3)
        self.g_cpu=CircularGauge(T("cpu_temp"), (0.9, 0.4, 0.1), self.app_theme); self.g_gpu=CircularGauge(T("gpu_temp"), (0.15, 0.8, 0.4), self.app_theme); self.g_ram=CircularGauge(T("ram"), (0.1, 0.5, 1.0), self.app_theme)
        r1.attach(self.g_cpu,0,0,1,1); r1.attach(self.g_gpu,1,0,1,1); r1.attach(self.g_ram,2,0,1,1); c1.append(r1); v.append(c1)
        c2=Gtk.Box(spacing=40, homogeneous=True); c2.add_css_class("card")
        self.lbl_disk_p = Gtk.Label(label="0%", css_classes=["stat-big"]); self.lbl_bat_p = Gtk.Label(label="0%", css_classes=["stat-big"]); self.lbl_bat_h = Gtk.Label(label="--", css_classes=["stat-lbl"])
        self.bar_d=Gtk.LevelBar(); self.bar_d.set_size_request(-1,6); self.bar_b=Gtk.LevelBar(); self.bar_b.set_size_request(-1,6)
        def detail_col(tit, val_lbl, widget, extra=None):
            b = Gtk.Box(orientation=1, spacing=8); h = Gtk.Box(spacing=5); h.append(Gtk.Label(label=tit, css_classes=["section-title"])); h.append(Gtk.Label(hexpand=True)); h.append(val_lbl)
            b.append(h); b.append(widget)
            if extra: b.append(extra)
            return b
        c2.append(detail_col(T("disk"), self.lbl_disk_p, self.bar_d))
        h_box = Gtk.Box(spacing=5); h_box.append(Gtk.Label(label=f"{T('health')}:", css_classes=["stat-lbl"])); h_box.append(self.lbl_bat_h)
        c2.append(detail_col(T("bat"), self.lbl_bat_p, self.bar_b, extra=h_box))
        up_box = Gtk.Box(orientation=1, spacing=8); self.lbl_up = Gtk.Label(label="--", css_classes=["stat-big"]); up_box.append(Gtk.Label(label=T("uptime"), css_classes=["section-title"])); up_box.append(self.lbl_up)
        c2.append(up_box); v.append(c2); return v

    def create_rgb(self):
        v=Gtk.Box(orientation=1, spacing=25)
        kb_box=Gtk.Box(orientation=1, margin_top=20, halign=3); kb_box.add_css_class("kb-frame")
        ov=Gtk.Overlay(); ov.set_size_request(680, 250); self.glow=Gtk.DrawingArea(); self.glow.set_draw_func(self.render); ov.set_child(self.glow)
        if os.path.exists(KEYBOARD_IMG): p=Gtk.Picture.new_for_filename(KEYBOARD_IMG); p.set_content_fit(2); ov.add_overlay(p)
        kb_box.append(ov); v.append(kb_box)
        tab=Gtk.Box(spacing=10, halign=3); self.zg=None
        zones = [T("z1"), T("z2"), T("z3"), T("z4"), T("all")]
        for i,t in enumerate(zones):
            b=Gtk.ToggleButton(label=t); b.add_css_class("zone-btn"); b.set_group(self.zg) if self.zg else setattr(self,'zg',b)
            if i==4: b.set_active(True)
            b.connect("toggled", lambda w,x=i: setattr(self,'selected_zone',x) if w.get_active() else None); tab.append(b)
        v.append(tab)
        c=Gtk.Box(orientation=1, spacing=25, margin_start=60, margin_end=60); c.add_css_class("card")
        r1=Gtk.Box(spacing=20); pb=Gtk.Box(spacing=10, valign=3); pb.append(Gtk.Label(label=T("l_pwr"), css_classes=["section-title"])); self.sw=Gtk.Switch(valign=3); self.sw.connect("state-set", self.act_pwr); pb.append(self.sw); r1.append(pb); r1.append(Gtk.Separator(orientation=1))
        cb=Gtk.Box(spacing=8, halign=3)
        for i in range(len(PRESETS)): b=Gtk.Button(); b.add_css_class(f"col-{i}"); b.set_size_request(26,26); b.connect("clicked", lambda w,co=PRESETS[i]: self.act_col(co)); cb.append(b)
        pick=Gtk.Button(label="+", halign=3); pick.add_css_class("col-0"); pick.set_size_request(26,26); pick.connect("clicked", self.open_picker); cb.append(pick); r1.append(cb); c.append(r1); c.append(Gtk.Separator(orientation=0))
        g=Gtk.Grid(column_spacing=40, row_spacing=25, halign=3)
        g.attach(Gtk.Label(label=T("eff"), xalign=1, css_classes=["section-title"]), 0, 0, 1, 1); self.dr=Gtk.DropDown(model=Gtk.StringList.new(["Static","Breathing","Wave","Cycle"])); self.dr.connect("notify::selected", self.act_mode); g.attach(self.dr, 1, 0, 1, 1)
        self.lbl_d=Gtk.Label(label=T("dir"), xalign=1, css_classes=["section-title"]); g.attach(self.lbl_d, 2, 0, 1, 1); self.dd=Gtk.DropDown(model=Gtk.StringList.new(["L->R","R->L"])); self.dd.connect("notify::selected", self.act_dir); g.attach(self.dd, 3, 0, 1, 1)
        g.attach(Gtk.Label(label=T("spd"), xalign=1, css_classes=["section-title"]), 0, 1, 1, 1); self.sc_s=Gtk.Scale.new_with_range(0,1,100,1); self.sc_s.set_size_request(180,-1); self.sc_s.connect("value-changed", self.act_spd); g.attach(self.sc_s, 1, 1, 1, 1)
        g.attach(Gtk.Label(label=T("bri"), xalign=1, css_classes=["section-title"]), 2, 1, 1, 1); self.sc_b=Gtk.Scale.new_with_range(0,0,100,1); self.sc_b.set_size_request(180,-1); self.sc_b.connect("value-changed", self.act_bri); g.attach(self.sc_b, 3, 1, 1, 1); c.append(g); v.append(c); return v

    def create_mux(self):
        v=Gtk.Box(orientation=1, spacing=30, margin_top=40, margin_start=50, margin_end=50)
        v.append(Gtk.Label(label=T("mux"), xalign=0, css_classes=["page-title"]))
        c=Gtk.Box(orientation=1, spacing=30); c.add_css_class("card"); c.append(Gtk.Label(label=T("mux_tit"), xalign=0, css_classes=["section-title"]))
        mux_box=Gtk.Box(spacing=20, homogeneous=True, halign=3); self.m_grp=None
        def mk_card(title, desc, icon, mode):
            wrapper = Gtk.Box(orientation=1, spacing=12)
            btn = Gtk.ToggleButton(); btn.set_group(self.m_grp) if self.m_grp else setattr(self,'m_grp',btn)
            btn.set_size_request(160, 130) 
            img = Gtk.Image.new_from_icon_name(icon); img.set_pixel_size(64); img.set_halign(3); img.set_valign(3)
            btn.set_child(img); btn.add_css_class("mux-btn")
            btn.connect("toggled", lambda w,md=mode: self.act_mux(md) if w.get_active() else None)
            lbl_t = Gtk.Label(label=title, css_classes=["stat-big"])
            lbl_d = Gtk.Label(label=desc, css_classes=["stat-lbl"], wrap=True, justify=3)
            wrapper.append(btn); wrapper.append(lbl_t); wrapper.append(lbl_d)
            return wrapper
        mux_box.append(mk_card(T("hybrid"), T("h_desc"), "battery-level-80-symbolic", "hybrid"))
        mux_box.append(mk_card(T("disc"), T("d_desc"), "speedometer-symbolic", "discrete"))
        mux_box.append(mk_card(T("integ"), T("i_desc"), "video-display-symbolic", "integrated"))
        c.append(mux_box); c.append(Gtk.Label(label=T("mux_desc"), wrap=True, xalign=0.5, css_classes=["stat-lbl"])); v.append(c); return v

    def create_perf(self):
        v=Gtk.Box(orientation=1, spacing=30, margin_top=40, margin_start=50, margin_end=50)
        v.append(Gtk.Label(label=T("perf"), xalign=0, css_classes=["page-title"]))
        c=Gtk.Box(orientation=1, spacing=20, valign=3); c.add_css_class("warning-box"); c.set_size_request(-1, 300)
        ic=Gtk.Image.new_from_icon_name("dialog-warning-symbolic"); ic.set_pixel_size(80); c.append(ic)
        t1=Gtk.Label(label=T("fan_msg"), css_classes=["warning-text"]); c.append(t1)
        t2=Gtk.Label(label=T("fan_sub"), css_classes=["warning-sub"], wrap=True, justify=3); c.append(t2)
        v.append(c); return v

    def create_set(self):
        v=Gtk.Box(orientation=1, spacing=30, margin_top=40, margin_start=50, margin_end=50)
        v.append(Gtk.Label(label=T("set"), xalign=0, css_classes=["page-title"]))
        c1=Gtk.Box(orientation=1, spacing=25); c1.add_css_class("card")
        
        # Tema
        r_th=Gtk.Box(spacing=20); r_th.append(Gtk.Label(label=T("theme"), css_classes=["section-title"])); d_th=Gtk.DropDown(model=Gtk.StringList.new([T("dark"), T("light")])); 
        d_th.set_selected(1 if self.app_theme=="light" else 0); d_th.connect("notify::selected", self.change_theme); r_th.append(d_th); c1.append(r_th)
        c1.append(Gtk.Separator())
        
        # Dil
        r_ln=Gtk.Box(spacing=20); r_ln.append(Gtk.Label(label=T("lang"), css_classes=["section-title"])); d_ln=Gtk.DropDown(model=Gtk.StringList.new(["English","Türkçe"])); 
        d_ln.set_selected(1 if active_lang=="tr" else 0); d_ln.connect("notify::selected", self.change_language); r_ln.append(d_ln); c1.append(r_ln)
        v.append(c1)
        
        # --- YASAL UYARI & KİMLİK ---
        disc_box = Gtk.Box(orientation=0, spacing=25); disc_box.add_css_class("disclaimer-box"); disc_box.set_margin_top(15)
        if os.path.exists(HP_LOGO_IMG):
            h_img = Gtk.Image.new_from_file(HP_LOGO_IMG); h_img.set_pixel_size(52); h_img.add_css_class("hp-logo"); disc_box.append(h_img)
        info_v = Gtk.Box(orientation=1, spacing=6)
        info_v.append(Gtk.Label(label=f"HP Omen Control v{APP_VERSION}", xalign=0, css_classes=["stat-big"]))
        dev_text = f"{T('dev_by')} <a href='https://github.com/yunusemreyl/Omen-Control-App'><b>yunusemreyl</b></a>\n{T('disclaimer')}"
        lbl_dev = Gtk.Label(label=dev_text, use_markup=True, xalign=0, css_classes=["stat-lbl"])
        info_v.append(lbl_dev); disc_box.append(info_v); v.append(disc_box)
        return v

    def change_theme(self, dd, _):
        self.app_theme = "light" if dd.get_selected() == 1 else "dark"
        self.save_config(); self.rebuild_ui()

    def change_language(self, dd, _):
        global active_lang
        active_lang = "tr" if dd.get_selected() == 1 else "en"
        self.save_config(); self.rebuild_ui()

    def update_dash(self):
        try:
            self.g_cpu.set_val(min(monitor.get_cpu_temp(), 100), f"{int(monitor.get_cpu_temp())}°C")
            self.g_gpu.set_val(min(monitor.get_gpu_temp(), 100), f"{int(monitor.get_gpu_temp())}°C")
            self.g_ram.set_val(monitor.get_ram(), f"{int(monitor.get_ram())}%")
            self.bar_d.set_value(monitor.get_disk_perc()/100); self.lbl_disk_p.set_label(f"{int(monitor.get_disk_perc())}%")
            self.bar_b.set_value(monitor.get_battery_perc()/100); self.lbl_bat_p.set_label(f"{int(monitor.get_battery_perc())}%")
            self.lbl_bat_h.set_label(f"{monitor.get_battery_health()}%"); self.lbl_up.set_label(monitor.get_uptime()); return True
        except: return True

    def connect_daemon(self):
        try:
            bus=SystemBus(); self.service=bus.get("com.yyl.hpcontrolcenter"); st=json.loads(self.service.GetState())
            self.power=st['power']; self.mode=st['mode']; self.speed=st['speed']; self.brightness=st['brightness']; self.direction=st['direction']
            self.sc_b.set_value(self.brightness); self.sc_s.set_value(self.speed); self.sw.set_active(self.power)
            try: idx=["static","breathing","wave","cycle"].index(self.mode); self.dr.set_selected(idx)
            except: pass
            self.dd.set_selected(0 if self.direction=="ltr" else 1); self.ready=True; print("Daemon Connected!"); return False
        except: return True

    def draw_anim(self): 
        if self.power: self.glow.queue_draw()
        return True
    def render(self, _, cr, w, h):
        if not self.power: return
        cr.set_operator(cairo.Operator.ADD); bri=self.sc_b.get_value()/100; t=time.time(); ct=[(w*0.2,h*0.5),(w*0.4,h*0.5),(w*0.6,h*0.5),(w*0.8,h*0.5)]
        for i, (cx,cy) in enumerate(ct):
            r,g,b=self.zone_rgba[i].red, self.zone_rgba[i].green, self.zone_rgba[i].blue
            f=(math.sin(t*3)+1)*0.5 if self.mode=="breathing" else 1
            if self.mode=="cycle": f=1; r,g,b=colorsys.hsv_to_rgb((t*0.5)%1,1,1)
            elif self.mode=="wave": 
                f=1
                offset = (i * 0.15) if self.direction == "ltr" else ((3-i) * 0.15)
                h_val = (t*0.5 + offset) % 1.0
                r,g,b=colorsys.hsv_to_rgb(h_val,1,1)
            pat=cairo.RadialGradient(cx,cy,0,cx,cy,w*0.25); pat.add_color_stop_rgba(0,r,g,b,0.8*bri*f); pat.add_color_stop_rgba(1,r,g,b,0); cr.set_source(pat); cr.paint()
    
    def act_pwr(self, w, s): 
        self.power=s; self.glow.queue_draw()
        if self.service and self.ready: self.service.SetGlobal(s, int(self.sc_b.get_value()), self.direction)
    def act_bri(self, w): 
        if self.service and self.ready: self.service.SetGlobal(self.power, int(w.get_value()), self.direction)
    def act_spd(self, w): 
        if self.service and self.ready: self.service.SetMode(self.mode, int(w.get_value()))
    def act_mode(self, w, _): 
        self.mode=["static","breathing","wave","cycle"][w.get_selected()]; self.glow.queue_draw()
        if self.service and self.ready: self.service.SetMode(self.mode, int(self.sc_s.get_value()))
    def act_dir(self, w, _):
        self.direction="ltr" if w.get_selected()==0 else "rtl"
        if self.service and self.ready: self.service.SetGlobal(self.power, int(self.sc_b.get_value()), self.direction)
    def act_col(self, h):
        c=Gdk.RGBA(); c.parse(h)
        if self.selected_zone==4: [self.zone_rgba.__setitem__(i,c) for i in range(4)]; [self.service.SetColor(i, h) if self.service else None for i in range(4)]
        else: self.zone_rgba[self.selected_zone]=c; [self.service.SetColor(self.selected_zone, h) if self.service else None]
        self.glow.queue_draw()
    def open_picker(self, b): d=Gtk.ColorDialog(); d.choose_rgba(self,None,None,self.picked)
    def picked(self,d,r): 
        try: c=d.choose_rgba_finish(r); self.act_col(f"#{int(c.red*255):02X}{int(c.green*255):02X}{int(c.blue*255):02X}")
        except: pass
    def act_mux(self, m):
        if self.service:
            dia=Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO, text=T("reboot_tit")); dia.set_secondary_text(T("reboot_msg"))
            dia.connect("response", lambda d,resp: (self.service.SetGpuMode(m), os.system("systemctl reboot")) if resp==Gtk.ResponseType.YES else d.destroy()); dia.present()

class OmenApp(Adw.Application):
    def __init__(self, **kwargs): super().__init__(**kwargs); self.connect('activate', lambda app: OmenMainWindow(application=app).present())

if __name__ == "__main__": OmenApp(application_id="com.yyl.hpcontrolcenter").run(sys.argv)
