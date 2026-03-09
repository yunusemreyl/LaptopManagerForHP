#!/usr/bin/env python3
"""
Centralized i18n module for HP Laptop Manager.
This module is imported by all pages — never run as __main__,
so there's only one copy of active_lang in memory.
"""

active_lang = "tr"

TRANSLATIONS = {
    "tr": {
        # Nav
        "games": "Oyunlar", "tools": "Araçlar", "fan": "Performans",
        "lighting": "Aydınlatma", "mux": "MUX", "settings": "Ayarlar",
        # Fan page
        "fan_control": "Fan Kontrolü", "system_status": "SİSTEM DURUMU",
        "power_profile": "GÜÇ PROFİLİ", "fan_mode": "FAN MODU",
        "fan_curve": "FAN EĞRİSİ", "all_sensors": "Tüm Sensörler",
        "fan_disabled": "Fan kontrolü devre dışı",
        "checking": "Kontrol ediliyor...", "no_ppd": "PPD yok",
        "active_profile": "Aktif profil", "mode": "Mod",
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
        # Settings page
        "appearance": "GÖRÜNÜM", "theme": "Tema", "lang_label": "Dil / Language",
        "dark": "Koyu", "light": "Açık", "system": "Sistem Uyarlanır",
        "updates": "GÜNCELLEMELER", "current_ver": "Mevcut sürüm",
        # Dashboard
        "dashboard": "Gösterge Paneli", "quick_status": "Hızlı Durum",
        "hardware_profile": "Donanım Profili", "resources": "Kaynak Kullanımı",
        "quick_actions": "Hızlı Aksiyonlar", "clean_memory": "Belleği Temizle",
        "max_fan": "Turbo Fan", "eco_mode": "Eko Modu",
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
        # Tools page
        "game_library": "Oyun Kütüphanesi",
        "search_games": "Oyun ara...",
        "no_games_found": "Henüz yüklü oyun bulunamadı",
        "install_hint": "Steam veya Lutris yükleyerek oyunlarınızı buradan yönetin.",
        "start_game": "Başlat",
        "games_count": "{count} oyun",
        "gaming_tools": "Oyun Araçları",
        "tools_title": "Araçlar",
        "tools_desc": "Oyun araçlarını tek tıkla kurun ve yönetin.",
        "install": "Kur", "installed": "✓ Yüklü", "not_installed": "Yüklü Değil",
        "installing": "Kuruluyor...", "install_failed": "Kurulum başarısız",
        "retry": "Tekrar Dene",
        "steam_desc": "Valve'ın oyun platformu ve mağazası",
        "lutris_desc": "Açık kaynak oyun yöneticisi",
        "protonup_desc": "Proton/Wine-GE sürüm yöneticisi",
        "heroic_desc": "Epic Games ve GOG istemcisi",
        "mangohud_desc": "Vulkan/OpenGL performans overlay'i",
        "gamemode_desc": "Feral Interactive oyun optimizatörü",
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

    },
    "en": {
        # Nav
        "games": "Games", "tools": "Tools", "fan": "Performance",
        "lighting": "Lighting", "mux": "MUX", "settings": "Settings",
        # Fan page
        "fan_control": "Fan Control", "system_status": "SYSTEM STATUS",
        "power_profile": "POWER PROFILE", "fan_mode": "FAN MODE",
        "fan_curve": "FAN CURVE", "all_sensors": "All Sensors",
        "fan_disabled": "Fan control unavailable",
        "checking": "Checking...", "no_ppd": "No PPD",
        "active_profile": "Active profile", "mode": "Mode",
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
        # Settings page
        "appearance": "APPEARANCE", "theme": "Theme", "lang_label": "Language",
        "dark": "Dark", "light": "Light", "system": "System Default",
        "updates": "UPDATES", "current_ver": "Current version",
        # Dashboard
        "dashboard": "Dashboard", "quick_status": "Quick Status",
        "hardware_profile": "Hardware Profile", "resources": "Resources",
        "quick_actions": "Quick Actions", "clean_memory": "Clean Memory",
        "max_fan": "MAX Fan", "eco_mode": "Eco Mode",
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
        # Tools page
        "game_library": "Game Library",
        "search_games": "Search games...",
        "no_games_found": "No installed games found",
        "install_hint": "Install Steam or Lutris to manage your games here.",
        "start_game": "Launch",
        "games_count": "{count} game(s)",
        "gaming_tools": "Gaming Tools",
        "tools_title": "Tools",
        "tools_desc": "Install and manage gaming tools with one click.",
        "install": "Install", "installed": "✓ Installed", "not_installed": "Not Installed",
        "installing": "Installing...", "install_failed": "Installation failed",
        "retry": "Retry",
        "steam_desc": "Valve's gaming platform and store",
        "lutris_desc": "Open source game manager",
        "protonup_desc": "Proton/Wine-GE version manager",
        "heroic_desc": "Epic Games and GOG client",
        "mangohud_desc": "Vulkan/OpenGL performance overlay",
        "gamemode_desc": "Feral Interactive game optimizer",
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
    },
}


def T(key):
    """Get translation for key using current active_lang."""
    return TRANSLATIONS.get(active_lang, TRANSLATIONS["tr"]).get(key, key)


def set_lang(lang):
    """Set the active language globally."""
    global active_lang
    active_lang = lang


def get_lang():
    """Get the current active language."""
    return active_lang
