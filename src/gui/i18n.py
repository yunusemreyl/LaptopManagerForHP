#!/usr/bin/env python3
"""
Centralized i18n module for OMEN Command Center for Linux.
This module is imported by all pages — never run as __main__,
so there's only one copy of active_lang in memory.
"""

import os as _os


def _detect_system_lang():
    """Detect the system language from environment variables."""
    for var in ("LC_MESSAGES", "LC_ALL", "LANG", "LANGUAGE"):
        val = _os.environ.get(var, "")
        if val:
            code = val.split(".")[0].split("_")[0].lower()
            if code in TRANSLATIONS:
                return code
    return "en"

TRANSLATIONS = {
    "tr": {
        # Nav
        "fan": "Performans",
        "lighting": "Aydınlatma", "mux": "MUX", "settings": "Ayarlar",
        "keyboard": "Kısayollar", "app_profiles": "Uygulama Profilleri",
        # Fan page
        "fan_control": "Fan Kontrolü", "system_status": "SİSTEM DURUMU",
        "power_profile": "GÜÇ PROFİLİ", "fan_mode": "FAN MODU",
        "fan_curve": "FAN EĞRİSİ", "all_sensors": "Tüm Sensörler",
        "fan_disabled": "Fan kontrolü devre dışı",
        "checking": "Kontrol ediliyor...", "no_ppd": "PPD yok",
        "active_profile": "Aktif profil", "mode": "Mod",
        "active": "Aktif", "inactive": "Pasif",
        "saver": "Tasarruf", "balanced": "Dengeli", "performance": "Performans",
        "auto": "Otomatik", "max": "Maksimum", "custom": "Özel", "standard": "Standart",
        "curve_desc": "Noktaları sürükleyerek fan eğrisini özelleştirin. X: Sıcaklık (°C), Y: Fan Hızı (%)",
        "no_sensor": "Sensör verisi bulunamadı",
        # Lighting page
        "keyboard_lighting": "Klavye Aydınlatma", "keyboard_light": "KLAVYE IŞIĞI",
        "zone": "Bölge", "all_zones": "Tümü",
        "effect": "EFEKT", "direction": "YÖN", "speed": "HIZ", "brightness": "PARLAKLIK",
        "static_eff": "Sabit", "breathing": "Nefes Alma", "wave": "Dalga", "cycle": "Renk Döngüsü",
        "ltr": "Sol → Sağ", "rtl": "Sağ → Sol",
        "win_lock": "Süper Tuş Kilidi",
        # Keyboard page
        "keyboard_shortcuts": "Kısayollar", "special_keys": "ÖZEL TUŞLAR",
        "omen_key": "Omen Tuşu", "victus_key": "Omen Tuşu",
        "calc_key": "Hesap Makinesi", "prt_sc_fix": "Print Screen (PrtSc) Düzelt",
        "prt_sc_desc": "PrtSc tuşunun ekran alıntısı aracı yerine gerçek 'Print Screen' olarak çalışmasını sağlar (Büyük kolaylık!).",
        "f1_fix": "F1 (Sunum) Tuşunu Düzelt",
        "f1_desc": "F1 tuşunun Super+P (Sunum modu) yerine standart F1 olarak çalışmasını sağlar.",
        "apply_shortcuts": "Değişiklikleri Uygula",
        "shortcuts_desc": "Cihazınızdaki bazı tuşların davranışını buradan kalıcı olarak değiştirebilirsiniz.",
        "hwdb_applied": "Klavye düzeltmeleri hwdb üzerinden başarıyla uygulandı.",
        "macros_title": "Makrolar ve Komutlar",
        "macros_desc": "Özel tuşlara terminal komutları atayın veya ikon üzerinden uygulama seçin.",
        "term_cmd": "Terminal komutu...",
        "choose_app": "Yüklü uygulamalardan seç",
        "sel_app": "Uygulama Seç",
        "or_custom_cmd": "Veya özel bash komutu yazın...",
        # MUX page
        "mux_switch": "MUX Anahtarlayıcı", "gpu_info": "GPU BİLGİSİ",
        "gpu_card": "Ekran Kartı", "driver_ver": "Sürücü Sürümü",
        "gpu_mode": "GPU MODU", "hybrid": "Hibrit", "discrete": "Harici GPU",
        "integrated": "Dahili GPU",
        "hybrid_desc": "NVIDIA Optimus (Hibrit)", "discrete_desc": "NVIDIA GeForce RTX",
        "integrated_desc": "Intel Iris Xe / AMD Radeon Graphics",
        "gpu_checking": "GPU modu kontrol ediliyor...",
        "restart_warn": "GPU modunu değiştirmek için sistem yeniden başlatılmalıdır.",
        "mux_not_found": "MUX aracı bulunamadı",
        "mux_install_hint": "envycontrol, supergfxctl veya prime-select yüklü olmalıdır.",
        "restart": "Yeniden Başlat",
        "restart_confirm": "GPU modunu '{mode}' olarak değiştirmek için sistem yeniden başlatılacak. Devam edilsin mi?",
        "mode_set": "Mod '{mode}' olarak ayarlandı. Yeniden başlatılıyor...",
        "mux_backend_label": "MUX Aracı (Backend)", "mux_auto": "Otomatik Algıla",
        # Settings page
        "appearance": "GÖRÜNÜM", "theme": "Tema", "lang_label": "Dil / Language",
        "dark": "Koyu", "light": "Açık", "system": "Sistem Uyarlanır",
        "updates": "GÜNCELLEMELER", "current_ver": "Mevcut sürüm",
        "per_key_wizard": "Per-Key RGB Eşleştirme Sihirbazı",
        "wizard_start_desc": "Hangi tuşun hangi sıraya denk geldiğini bulmak için klavyenizdeki tuşlar sırayla kırmızı yanacaktır. Yanan tuşa klavyeden basarak eşleştirin.",
        "wizard_btn": "Sihirbazı Başlat",
        "wizard_progress": "Tuş Bekleniyor...",
        "wizard_instruction": "Klavyenizde şu an kırmızı yanan tuşa basın. Eğer kırmızı yanan bir tuş yoksa veya bulamadıysanız 'Atla' butonuna basın.",
        "wizard_skip": "Atla",
        "wizard_cancel": "İptal",
        "wizard_complete": "Eşleştirme Tamamlandı!",
        # Dashboard
        "dashboard": "Gösterge Paneli", "quick_status": "Hızlı Durum",
        "hardware_profile": "Donanım Profili", "resources": "Kaynak Kullanımı",
        "quick_actions": "Hızlı Aksiyonlar", "clean_memory": "Belleği Temizle",
        "max_fan": "Turbo Fan", "eco_mode": "Eko Modu",
        "go_performance": "Performans sekmesine git",
        "fan_metric": "Fan",
        "disk": "Disk", "ram": "RAM",
        "cpu_load_30s": "CPU Yükü (Son 30 sn)",
        "power_profile_label": "Güç Profili", "fan_mode_label": "Fan Modu",
        "gpu_mux_label": "GPU / MUX",
        "battery": "Batarya", "ac_power": "Güç Kablosu",
        "health": "Sağlık",
        "power_saver_lbl": "Enerji Tasarrufu",
        "balanced_lbl": "Dengeli", "performance_lbl": "Performans",
        "check_update": "Güncelleme Kontrol Et", "download": "İndir",
        "sys_info": "SİSTEM BİLGİSİ",
        "computer": "Bilgisayar", "kernel": "Çekirdek",
        "os_name": "İşletim Sistemi", "arch": "Mimari",
        "driver_status": "SÜRÜCÜ DURUMU",
        "loaded": "✓ Yüklü", "not_loaded": "✗ Yüklü Değil",
        "developer": "Geliştirici",
        "home_subtitle": "Modül seçerek devam edin",
        "debug_info_title": "Tanılama ve Hata Ayıklama",
        "show_debug_info": "Hata Ayıklama Bilgilerini Göster",
        "copy_debug_log": "Tanı Bilgilerini Kopyala",
        "copied_to_clipboard": "Panoya kopyalandı",
        "create_github_issue": "GitHub Issue Oluştur",
        "github_issue_desc": "Tanı bilgileriyle otomatik hata raporu oluştur",
        "github_issue_generating": "Issue hazırlanıyor...",
        "github_issue_opened": "Tarayıcıda açıldı",
        "debug_console_title": "Sistem Tanı Konsolu",
        "debug_collecting": "Sistem bilgileri toplanıyor...\nACPI tabloları analiz ediliyor...\nDMI tabloları okunuyor...\nSysfs yolları taranıyor...\nKernel logları analiz ediliyor...\n\nLütfen bekleyin...",
        "disclaimer": "Bu aracın <b>Hewlett Packard</b> ile resmi bir bağlantısı bulunmamaktadır.",
        "update_checking": "Kontrol ediliyor...",
        "new_ver_available": "Yeni sürüm mevcut",
        "up_to_date": "Güncel", "conn_failed": "Bağlantı sağlanamadı",
        "error": "Hata",
        "install_update": "Güncellemeyi Kur",
        "downloading_update": "İndiriliyor...",
        "installing_update": "Kuruluyor...",
        "update_success": "Güncelleme başarıyla kuruldu! Uygulamayı yeniden başlatın.",
        "update_failed": "Güncelleme başarısız",
        "restart_app": "Uygulamayı Yeniden Başlat",

        # Temperature unit
        "temp_unit": "Sıcaklık Birimi", "celsius": "Celsius (°C)", "fahrenheit": "Fahrenheit (°F)",
        # Fan curve widget
        "temp_axis": "Sıcaklık (°C)", "fan_speed_axis": "Fan Hızı (%)",
        # Sensor categories
        "other_sensors": "Diğer",
        # Profile tooltips
        "saver_tooltip": "Maksimum pil ömrü için enerji tasarrufu sağlar. (Düşük Güç Limitleri)",
        "balanced_tooltip": "Güç ve tasarruf arasında denge kurar. (Optimize Güç Limitleri)",
        "performance_tooltip": "Tüm limitleri kaldırır ve en yüksek performansı almanızı sağlar.",
        "power_managed_by": "Güç modu {tool} tarafından yönetilmektedir.",

        # App Profiles
        "app_profiles_desc": "Oyun veya uygulama çalıştığında güç profili otomatik değişir.",
        "add": "Ekle", "delete": "Sil",
        "placeholder_app": "Uygulama adı (Örn: steam, cs2.exe, studio)",
        "game": "Oyun", "program": "Program", "other": "Diğer",
        "fan_default": "Fan: Varsayılan", "fan_auto": "Fan: Otomatik", "fan_max": "Fan: Maksimum",
        "theme_default": "Tema: Varsayılan", "theme_dark": "Tema: Koyu", "theme_light": "Tema: Açık",
        "theme_label": "Uygulama açıldığında tema değiştir",
        "no_profiles": "Henüz bir uygulama profili eklenmedi.",

        "power_tuning": "Güç ve Voltaj",
        "power_tuning_desc": "Gelişmiş voltaj ve termal limit ayarları ile cihazınızın ısınmasını önleyin ve verimliliğini artırın.",
        "undervolt_label": "CPU Undervolt (Voltaj Düşürme)",
        "undervolt_desc": "Daha düşük voltaj, performans kaybı olmadan işlemcinizin daha serin çalışmasını sağlar.",
        "tcc_label": "TCC Offset (Sıcaklık Limiti)",
        "tcc_desc": "Maksimum çalışma sıcaklığını düşürerek işlemcinin erken kısılmasını ve aşırı ısınmasını engeller (Hedef Sıcaklık: 100 - TCC).",
        "power_limits_label": "Güç Limitleri (PL1 / PL2)",
        "power_limits_desc": "İşlemcinin çekeceği uzun süreli (PL1) ve kısa süreli (PL2) maksimum watt değerlerini belirleyin.",
        "pl1_w": "Uzun Süreli Güç Limiti (PL1 - Watt)",
        "pl2_w": "Kısa Süreli Güç Limiti (PL2 - Watt)",
        "apply_power": "Ayarları Uygula",
        "power_applied": "Güç ve voltaj ayarları başarıyla uygulandı.",
        "unsupported_power": "Cihazınız bu gelişmiş güç yönetim fonksiyonlarını desteklemiyor.",
        
        # Troubleshooting & Dump
        "troubleshooting_dump": "Sorun Giderme ve Dump",
        "thanks_for_using": "OmenCtl'i kullandığınız için teşekkür ederiz.",
        "send_to_github": "Raporu Github Issue'ye Gönder",
        "back": "Geri",
    },
    "en": {
        # Nav
        "fan": "Performance",
        "lighting": "Lighting", "mux": "MUX", "settings": "Settings",
        "keyboard": "Shortcuts", "app_profiles": "App Profiles",
        # Fan page
        "fan_control": "Fan Control", "system_status": "SYSTEM STATUS",
        "power_profile": "POWER PROFILE", "fan_mode": "FAN MODE",
        "fan_curve": "FAN CURVE", "all_sensors": "All Sensors",
        "fan_disabled": "Fan control unavailable",
        "checking": "Checking...", "no_ppd": "No PPD",
        "active_profile": "Active profile", "mode": "Mode",
        "active": "Active", "inactive": "Inactive",
        "saver": "Power Saver", "balanced": "Balanced", "performance": "Performance",
        "auto": "Automatic", "max": "Maximum", "custom": "Custom", "standard": "Standard",
        "curve_desc": "Drag points to customize fan curve. X: Temperature (°C), Y: Fan Speed (%)",
        "no_sensor": "No sensor data found",
        # Lighting page
        "keyboard_lighting": "Keyboard Lighting", "keyboard_light": "KEYBOARD LIGHT",
        "zone": "Zone", "all_zones": "All",
        "effect": "EFFECT", "direction": "DIRECTION", "speed": "SPEED", "brightness": "BRIGHTNESS",
        "static_eff": "Static", "breathing": "Breathing", "wave": "Wave", "cycle": "Cycle",
        "ltr": "Left → Right", "rtl": "Right → Left",
        "win_lock": "Super Key Lock",
        # Keyboard page
        "keyboard_shortcuts": "Shortcuts", "special_keys": "SPECIAL KEYS",
        "omen_key": "Omen Key", "victus_key": "Omen Key",
        "calc_key": "Calculator Key", "prt_sc_fix": "Fix Print Screen (PrtSc)",
        "prt_sc_desc": "Makes PrtSc key work as real Print Screen instead of triggering Screenshot Tool.",
        "f1_fix": "Fix F1 (Presentation) Key",
        "f1_desc": "Makes F1 key work as standard F1 instead of Super+P (Presentation mode).",
        "apply_shortcuts": "Apply Changes",
        "shortcuts_desc": "You can permanently change the behavior of certain keys on your laptop here.",
        "hwdb_applied": "Keyboard fixes have been applied successfully.",
        "macros_title": "Macros & Commands",
        "macros_desc": "Assign terminal commands or click the icon to choose an application.",
        "term_cmd": "Terminal command...",
        "choose_app": "Choose installed application",
        "sel_app": "Select Application",
        "or_custom_cmd": "Or type custom bash command...",
        # MUX page
        "mux_switch": "MUX Switch", "gpu_info": "GPU INFO",
        "gpu_card": "Graphics Card", "driver_ver": "Driver Version",
        "gpu_mode": "GPU MODE", "hybrid": "Hybrid", "discrete": "Discrete GPU",
        "integrated": "Integrated GPU",
        "hybrid_desc": "NVIDIA Optimus (Hybrid)", "discrete_desc": "NVIDIA GeForce RTX",
        "integrated_desc": "Intel Iris Xe / AMD Radeon Graphics",
        "gpu_checking": "Checking GPU mode...",
        "restart_warn": "System restart required to change GPU mode.",
        "mux_not_found": "MUX tool not found",
        "mux_install_hint": "envycontrol, supergfxctl or prime-select must be installed.",
        "restart": "Restart",
        "restart_confirm": "System will restart to change GPU mode to '{mode}'. Continue?",
        "mode_set": "Mode set to '{mode}'. Restarting...",
        "mux_backend_label": "MUX Backend Tool", "mux_auto": "Auto Detect",
        # Settings page
        "appearance": "APPEARANCE", "theme": "Theme", "lang_label": "Language",
        "dark": "Dark", "light": "Light", "system": "System Default",
        "updates": "UPDATES", "current_ver": "Current version",
        "per_key_wizard": "Per-Key RGB Mapping Wizard",
        "wizard_start_desc": "To find out which key corresponds to which index, the keys on your keyboard will light up red one by one. Press the illuminated key on your keyboard to map it.",
        "wizard_btn": "Start Wizard",
        "wizard_progress": "Waiting for key...",
        "wizard_instruction": "Press the key currently glowing red on your keyboard. If no key is glowing red or you can't find it, press 'Skip'.",
        "wizard_skip": "Skip",
        "wizard_cancel": "Cancel",
        "wizard_complete": "Mapping Complete!",
        # Dashboard
        "dashboard": "Dashboard", "quick_status": "Quick Status",
        "hardware_profile": "Hardware Profile", "resources": "Resources",
        "quick_actions": "Quick Actions", "clean_memory": "Clean Memory",
        "max_fan": "MAX Fan", "eco_mode": "Eco Mode",
        "go_performance": "Go to Performance",
        "fan_metric": "Fan",
        "disk": "Disk", "ram": "RAM",
        "cpu_load_30s": "CPU Load (Last 30s)",
        "power_profile_label": "Power Profile", "fan_mode_label": "Fan Mode",
        "gpu_mux_label": "GPU / MUX",
        "battery": "Battery", "ac_power": "Power Cable",
        "health": "Health",
        "power_saver_lbl": "Power Saver",
        "balanced_lbl": "Balanced", "performance_lbl": "Performance",
        "check_update": "Check for Updates", "download": "Download",
        "sys_info": "SYSTEM INFO",
        "computer": "Computer", "kernel": "Kernel",
        "os_name": "Operating System", "arch": "Architecture",
        "driver_status": "DRIVER STATUS",
        "loaded": "✓ Loaded", "not_loaded": "✗ Not Loaded",
        "developer": "Developer",
        "home_subtitle": "Choose a module to continue",
        "debug_info_title": "Diagnostic and Debug",
        "show_debug_info": "Show Debug Info",
        "copy_debug_log": "Copy Debug Info",
        "copied_to_clipboard": "Copied to clipboard",
        "create_github_issue": "Create GitHub Issue",
        "github_issue_desc": "Auto-create bug report with diagnostics",
        "github_issue_generating": "Generating issue...",
        "github_issue_opened": "Opened in browser",
        "debug_console_title": "System Diagnostic Console",
        "debug_collecting": "Gathering system information...\nAnalyzing ACPI tables...\nReading DMI tables...\nScanning sysfs paths...\nAnalyzing kernel logs...\n\nPlease wait...",
        "disclaimer": "This tool has no official affiliation with <b>Hewlett Packard</b>.",
        "update_checking": "Checking...",
        "new_ver_available": "New version available",
        "up_to_date": "Up to date", "conn_failed": "Connection failed",
        "error": "Error",
        "install_update": "Install Update",
        "downloading_update": "Downloading...",
        "installing_update": "Installing...",
        "update_success": "Update installed successfully! Please restart the application.",
        "update_failed": "Update failed",
        "restart_app": "Restart Application",

        # Temperature unit
        "temp_unit": "Temperature Unit", "celsius": "Celsius (°C)", "fahrenheit": "Fahrenheit (°F)",
        # Fan curve widget
        "temp_axis": "Temperature (°C)", "fan_speed_axis": "Fan Speed (%)",
        # Sensor categories
        "other_sensors": "Other",
        # Profile tooltips
        "saver_tooltip": "Maximum battery life with reduced power limits.",
        "balanced_tooltip": "Balance between power and efficiency.",
        "performance_tooltip": "Remove all power limits for maximum performance.",
        "power_managed_by": "Power mode is managed by {tool}.",

        # App Profiles
        "app_profiles_desc": "Automatically switch power profile when an app or game is launched.",
        "add": "Add", "delete": "Delete",
        "placeholder_app": "App name (e.g. steam, cs2.exe, studio)",
        "game": "Game", "program": "Program", "other": "Other",
        "fan_default": "Fan: Default", "fan_auto": "Fan: Auto", "fan_max": "Fan: Max",
        "theme_default": "Theme: Default", "theme_dark": "Theme: Dark", "theme_light": "Theme: Light",
        "theme_label": "Switch theme when application starts",
        "no_profiles": "No app profiles added yet.",

        "power_tuning": "Power & Voltage",
        "power_tuning_desc": "Prevent overheating and improve efficiency with advanced undervolt and thermal limit settings.",
        "undervolt_label": "CPU Undervolt",
        "undervolt_desc": "Lowering CPU voltage reduces operating temperatures without sacrificing performance.",
        "tcc_label": "TCC Offset (Thermal Limit)",
        "tcc_desc": "Lowers the maximum operating temperature to prevent extreme overheating (Target Temp: 100 - TCC).",
        "power_limits_label": "Power Limits (PL1 / PL2)",
        "power_limits_desc": "Configure the long-duration (PL1) and short-duration (PL2) maximum watt limits.",
        "pl1_w": "Long Duration Power Limit (PL1 - Watts)",
        "pl2_w": "Short Duration Power Limit (PL2 - Watts)",
        "apply_power": "Apply Settings",
        "power_applied": "Power and voltage settings applied successfully.",
        "unsupported_power": "Your system does not support these advanced power tuning features.",

        # Troubleshooting & Dump
        "troubleshooting_dump": "Troubleshooting & Dump",
        "thanks_for_using": "Thank you for using OmenCtl.",
        "send_to_github": "Send report to Github Issue",
        "back": "Back",
    },
}

try:
    from extra_langs import EXTRA_TRANSLATIONS
    TRANSLATIONS.update(EXTRA_TRANSLATIONS)
except ImportError:
    pass

def T(key):
    """Get translation for key using current active_lang."""
    return TRANSLATIONS.get(active_lang, TRANSLATIONS["en"]).get(key, key)


def set_lang(lang):
    """Set the active language globally."""
    global active_lang
    normalized = str(lang or "").strip().lower()
    if not normalized:
        # No explicit language — keep current (auto-detected) setting
        return
    if normalized.startswith("tr") or "türk" in normalized or "turk" in normalized:
        active_lang = "tr"
        return
    if normalized.startswith("en") or "english" in normalized:
        active_lang = "en"
        return
    active_lang = normalized if normalized in TRANSLATIONS else _detect_system_lang()


def get_lang():
    """Get the current active language."""
    return active_lang

active_lang = _detect_system_lang()
