#!/bin/bash
# HP Laptop Manager - Multi-distro Installer
set -e

APP_NAME="HP Laptop Manager"
INSTALL_DIR="/usr/libexec/hp-manager"
DATA_DIR="/usr/share/hp-manager"
BIN_LINK="/usr/bin/hp-manager"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info()  { echo -e "${CYAN}[i]${NC} $1"; }

# --- LANGUAGE ---
LANG_CODE=${LANG:0:2}

msg() {
    local key=$1
    if [ "$LANG_CODE" == "tr" ]; then
        case $key in
            "root_check") echo "Bu scripti root olarak çalıştırın: sudo $0" ;;
            "pm_not_found") echo "Desteklenen paket yöneticisi bulunamadı (pacman/apt/dnf/zypper)" ;;
            "pm_name") echo "Paket yöneticisi: $2" ;;
            "installing_deps") echo "Bağımlılıklar yükleniyor..." ;;
            "deps_installed") echo "Bağımlılıklar yüklendi" ;;
            "installing_app") echo "Uygulama kuruluyor..." ;;
            "daemon_installed") echo "Daemon kuruldu: $2" ;;
            "gui_installed") echo "GUI kuruldu: $2" ;;
            "images_copied") echo "Resimler kopyalandı" ;;
            "launcher_created") echo "Başlatıcı oluşturuldu: $2" ;;
            "sys_files_installed") echo "Sistem dosyaları kuruldu" ;;
            "daemon_start_fail") echo "Daemon başlatılamadı (sürücü yüklü olmayabilir)" ;;
            "daemon_enabled") echo "Daemon etkinleştirildi" ;;
            "uninstaller_created") echo "Kaldırma aracı oluşturuldu: hp-manager-uninstall" ;;
            "uninstalling") echo "Uygulama kaldırılıyor..." ;;
            "uninstalled") echo "Uygulama kaldırıldı" ;;
            "success") echo "${APP_NAME} başarıyla kuruldu!" ;;
            "start_hint") echo "Başlatmak için: hp-manager" ;;
            "usage") echo "Kullanım: $0 [install|uninstall]" ;;
            "uninstall_complete") echo "Kaldırma tamamlandı!" ;;
            "trouble_title") echo "OLASI SORUNLAR VE ÇÖZÜMLER:" ;;
            "trouble_1") echo "Daemon başlatılamadı hatası:" ;;
            "trouble_1_sol_1") echo "'sudo systemctl status hp-manager' ile detayları kontrol edin." ;;
            "trouble_1_sol_2") echo "HP sürücülerinin (hp-wmi) yüklü olduğundan emin olun." ;;
            "trouble_2") echo "Arayüz açılmıyor:" ;;
            "trouble_2_sol") echo "Terminalden 'hp-manager' yazarak çıktıdaki hataları inceleyin." ;;
            "trouble_3") echo "Fan/Işık kontrolü çalışmıyor:" ;;
            "trouble_3_sol") echo "Cihazınızın desteklendiğinden emin olun (Victus/Omen)." ;;
            *) echo "$key" ;;
        esac
    else
        case $key in
            "root_check") echo "Run this script as root: sudo $0" ;;
            "pm_not_found") echo "Supported package manager not found (pacman/apt/dnf/zypper)" ;;
            "pm_name") echo "Package manager: $2" ;;
            "installing_deps") echo "Installing dependencies..." ;;
            "deps_installed") echo "Dependencies installed" ;;
            "installing_app") echo "Installing application..." ;;
            "daemon_installed") echo "Daemon installed: $2" ;;
            "gui_installed") echo "GUI installed: $2" ;;
            "images_copied") echo "Images copied" ;;
            "launcher_created") echo "Launcher created: $2" ;;
            "sys_files_installed") echo "System files installed" ;;
            "daemon_start_fail") echo "Daemon failed to start (driver might be missing)" ;;
            "daemon_enabled") echo "Daemon enabled" ;;
            "uninstaller_created") echo "Uninstaller created: hp-manager-uninstall" ;;
            "uninstalling") echo "Uninstalling application..." ;;
            "uninstalled") echo "Application uninstalled" ;;
            "success") echo "${APP_NAME} successfully installed!" ;;
            "start_hint") echo "To start: hp-manager" ;;
            "usage") echo "Usage: $0 [install|uninstall]" ;;
            "uninstall_complete") echo "Uninstall complete!" ;;
            "trouble_title") echo "POSSIBLE ISSUES & SOLUTIONS:" ;;
            "trouble_1") echo "Daemon failed to start:" ;;
            "trouble_1_sol_1") echo "Check details with 'sudo systemctl status hp-manager'." ;;
            "trouble_1_sol_2") echo "Ensure HP drivers (hp-wmi) are installed." ;;
            "trouble_2") echo "Interface does not open:" ;;
            "trouble_2_sol") echo "Run 'hp-manager' in terminal to see errors." ;;
            "trouble_3") echo "Fan/Light control not working:" ;;
            "trouble_3_sol") echo "Ensure your device is supported (Victus/Omen)." ;;
            *) echo "$key" ;;
        esac
    fi
}

on_error() {
    echo ""
    warn "$(msg trouble_title)"
    echo -e "  1. ${YELLOW}$(msg trouble_1)${NC}"
    echo "     -> $(msg trouble_1_sol_1)"
    echo "     -> $(msg trouble_1_sol_2)"
    echo -e "  2. ${YELLOW}$(msg trouble_2)${NC}"
    echo "     -> $(msg trouble_2_sol)"
    echo -e "  3. ${YELLOW}$(msg trouble_3)${NC}"
    echo "     -> $(msg trouble_3_sol)"
    echo ""
    exit 1
}

trap on_error ERR

# --- ROOT CHECK ---
if [ "$(id -u)" -ne 0 ]; then
    err "$(msg root_check)"
fi

# --- DETECT PACKAGE MANAGER ---
detect_pm() {
    if command -v pacman &>/dev/null; then
        PM="pacman"
        INSTALL_CMD="pacman -S --noconfirm --needed"
    elif command -v apt &>/dev/null; then
        PM="apt"
        INSTALL_CMD="apt install -y"
    elif command -v dnf &>/dev/null; then
        PM="dnf"
        INSTALL_CMD="dnf install -y"
    elif command -v zypper &>/dev/null; then
        PM="zypper"
        INSTALL_CMD="zypper install -y"
    else
        err "$(msg pm_not_found)"
    fi
    log "$(msg pm_name $PM)"
}

# --- INSTALL DEPENDENCIES ---
install_deps() {
    info "$(msg installing_deps)"

    case $PM in
        pacman)
            $INSTALL_CMD python python-gobject gtk4 libadwaita python-pydbus python-cairo power-profiles-daemon
            ;;
        apt)
            $INSTALL_CMD python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-pydbus python3-cairo power-profiles-daemon
            ;;
        dnf)
            $INSTALL_CMD python3 python3-gobject gtk4 libadwaita python3-pydbus python3-cairo power-profiles-daemon
            ;;
        zypper)
            $INSTALL_CMD python3 python3-gobject gtk4 libadwaita python3-pydbus python3-cairo power-profiles-daemon
            ;;
    esac

    log "$(msg deps_installed)"
}

# --- INSTALL APP ---
install_app() {
    info "$(msg installing_app)"

    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR/images"
    mkdir -p /etc/hp-manager

    # Copy daemon
    cp -r src/daemon/* "$INSTALL_DIR/"
    log "$(msg daemon_installed $INSTALL_DIR)"

    # Copy GUI
    mkdir -p "$DATA_DIR/gui/pages"
    mkdir -p "$DATA_DIR/gui/widgets"
    cp src/gui/main_window.py "$DATA_DIR/gui/"
    cp src/gui/i18n.py "$DATA_DIR/gui/"
    cp src/gui/pages/*.py "$DATA_DIR/gui/pages/"
    cp src/gui/widgets/*.py "$DATA_DIR/gui/widgets/"
    log "$(msg gui_installed "$DATA_DIR/gui")"

    # Copy images if exist
    if [ -d "images" ] && [ "$(ls -A images/ 2>/dev/null)" ]; then
        cp images/* "$DATA_DIR/images/" 2>/dev/null || true
        log "$(msg images_copied)"
    fi

    # Create launcher script
    cat > "$BIN_LINK" << 'LAUNCHER'
#!/bin/bash
cd /usr/share/hp-manager/gui
exec python3 /usr/share/hp-manager/gui/main_window.py "$@"
LAUNCHER
    chmod +x "$BIN_LINK"
    log "$(msg launcher_created $BIN_LINK)"

    # Create required directories for system files (fixes Arch issue)
    mkdir -p /etc/dbus-1/system.d
    mkdir -p /usr/share/polkit-1/actions
    mkdir -p /usr/share/applications

    # Install system files
    cp data/com.yyl.hpmanager.conf /etc/dbus-1/system.d/
    cp data/com.yyl.hpmanager.service /etc/systemd/system/hp-manager.service
    cp data/com.yyl.hpmanager.policy /usr/share/polkit-1/actions/
    cp data/com.yyl.hpmanager.desktop /usr/share/applications/
    log "$(msg sys_files_installed)"

    # Enable and start daemon
    systemctl daemon-reload
    systemctl enable hp-manager.service
    systemctl restart hp-manager.service || warn "$(msg daemon_start_fail)"
    log "$(msg daemon_enabled)"

    # Enable power-profiles-daemon
    systemctl enable power-profiles-daemon 2>/dev/null || true
    systemctl start power-profiles-daemon 2>/dev/null || true

    # Install icon to system theme for better integration
    mkdir -p /usr/share/icons/hicolor/48x48/apps/
    cp images/hp_logo.png /usr/share/icons/hicolor/48x48/apps/hp_logo.png
    gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
    # Create uninstaller
    cat > "/usr/bin/hp-manager-uninstall" << 'UNINSTALLER'
#!/bin/bash
if [ "$(id -u)" -ne 0 ]; then
    echo "Bu işlem root yetkisi gerektirir (sudo)."
    exit 1
fi
echo "HP Laptop Manager kaldırılıyor..."
systemctl stop hp-manager.service 2>/dev/null
systemctl disable hp-manager.service 2>/dev/null
rm -f /etc/systemd/system/hp-manager.service
rm -f /usr/bin/hp-manager
rm -f /usr/bin/hp-manager-uninstall
rm -rf /usr/libexec/hp-manager
rm -rf /usr/share/hp-manager
rm -f /etc/dbus-1/system.d/com.yyl.hpmanager.conf
rm -f /usr/share/polkit-1/actions/com.yyl.hpmanager.policy
rm -f /usr/share/applications/com.yyl.hpmanager.desktop
rm -f /usr/share/icons/hicolor/48x48/apps/hp_logo.png
systemctl daemon-reload
echo "Kaldırma işlemi tamamlandı."
UNINSTALLER
    chmod +x "/usr/bin/hp-manager-uninstall"
    log "$(msg uninstaller_created)"
}

# --- UNINSTALL ---
uninstall_app() {
    info "$(msg uninstalling)"
    /usr/bin/hp-manager-uninstall
}

# --- MAIN ---
echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════╗"
echo "  ║     HP Laptop Manager Installer    ║"
echo "  ╚═══════════════════════════════════╝"
echo -e "${NC}"

case "${1:-install}" in
    install)
        detect_pm
        install_deps
        install_app
        echo ""
        log "$(msg success)"
        info "$(msg start_hint)"
        ;;
    uninstall|remove)
        uninstall_app
        log "$(msg uninstall_complete)"
        ;;
    *)
        echo "$(msg usage)"
        ;;
esac
