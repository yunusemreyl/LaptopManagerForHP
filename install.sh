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
    # Show detected distro for debugging
    if [ -f /etc/os-release ]; then
        _DISTRO_NAME=$(. /etc/os-release && echo "${PRETTY_NAME:-$NAME}")
        info "Detected distro: $_DISTRO_NAME"
    fi

    if [ -f /etc/fedora-release ] || [ -f /etc/nobara-release ] || command -v dnf &>/dev/null; then
        PM="dnf"
        INSTALL_CMD="dnf install -y"
    elif command -v pacman &>/dev/null; then
        PM="pacman"
        INSTALL_CMD="pacman -S --noconfirm --needed"
    elif command -v apt &>/dev/null; then
        PM="apt"
        INSTALL_CMD="apt install -y"
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
            $INSTALL_CMD python python-gobject gtk4 libadwaita python-pydbus python-cairo power-profiles-daemon evtest
            ;;
        apt)
            $INSTALL_CMD python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-pydbus python3-cairo power-profiles-daemon evtest
            ;;
        dnf)
            # Prioritize 'tuned' (especially on Fedora 41+). If tuned is present, we skip power-profiles-daemon.
            if rpm -q tuned &>/dev/null || rpm -q tuned-ppd &>/dev/null; then
                info "Tuned detected, skipping power-profiles-daemon installation."
                $INSTALL_CMD python3 python3-gobject gtk4 libadwaita python3-pydbus python3-cairo evtest
            else
                $INSTALL_CMD python3 python3-gobject gtk4 libadwaita python3-pydbus python3-cairo power-profiles-daemon evtest
            fi
            ;;
        zypper)
            $INSTALL_CMD python3 python3-gobject gtk4 libadwaita python3-pydbus python3-cairo power-profiles-daemon evtest
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

    # ── Driver build and installation ──
    if [ -d "driver" ] && [ -f "driver/install.sh" ]; then
        info "Integrating driver build process..."
        (cd driver && chmod +x install.sh && ./install.sh install) || warn "Driver installation failed, please check driver/ directory manually."
    else
        warn "Driver directory or install script not found! Manual driver installation may be required."
    fi

    # ── Language Selection Menu ──
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Language / Dil Selection         ║${NC}"
    echo -e "${CYAN}╠═══════════════════════════════════╣${NC}"
    echo -e "${CYAN}║  0) All languages (default)        ║${NC}"
    echo -e "${CYAN}║  1) English                        ║${NC}"
    echo -e "${CYAN}║  2) Türkçe                         ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════╝${NC}"
    echo ""
    read -t 15 -p "Select [0-2, default=0]: " LANG_CHOICE || LANG_CHOICE=0
    LANG_CHOICE=${LANG_CHOICE:-0}
    echo ""

    # ── GPU Switching Tool Selection ──
    _HAS_PRIME=$(command -v prime-select 2>/dev/null && echo 1 || echo 0)
    _HAS_ENVY=$(command -v envycontrol 2>/dev/null && echo 1 || echo 0)

    if [ "$_HAS_PRIME" -eq 0 ] && [ "$_HAS_ENVY" -eq 0 ]; then
        echo ""
        if [ "$LANG_CODE" == "tr" ]; then
            echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
            echo -e "${CYAN}║   GPU Switching Aracı Seçimi               ║${NC}"
            echo -e "${CYAN}╠═══════════════════════════════════════════╣${NC}"
            echo -e "${CYAN}║  0) Hiçbiri (varsayılan)                   ║${NC}"
            echo -e "${CYAN}║  1) envycontrol (önerilen, tüm dağıtımlar) ║${NC}"
            echo -e "${CYAN}║  2) prime-select (sadece Ubuntu/Mint)      ║${NC}"
            echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "${YELLOW}Not: NVIDIA dGPU yoksa veya GPU modları ile${NC}"
            echo -e "${YELLOW}ilgilenmiyorsanız 0 (Hiçbiri) seçebilirsiniz.${NC}"
        else
            echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
            echo -e "${CYAN}║   GPU Switching Tool Selection             ║${NC}"
            echo -e "${CYAN}╠═══════════════════════════════════════════╣${NC}"
            echo -e "${CYAN}║  0) None (default)                         ║${NC}"
            echo -e "${CYAN}║  1) envycontrol (recommended, all distros) ║${NC}"
            echo -e "${CYAN}║  2) prime-select (Ubuntu/Mint only)        ║${NC}"
            echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "${YELLOW}Note: If you don't have an NVIDIA dGPU or${NC}"
            echo -e "${YELLOW}don't need GPU mode switching, choose 0.${NC}"
        fi
        echo ""
        read -t 15 -p "Select [0-2, default=0]: " MUX_CHOICE || MUX_CHOICE=0
        MUX_CHOICE=${MUX_CHOICE:-0}
        echo ""

        case $MUX_CHOICE in
            1)
                info "Installing envycontrol..."
                case $PM in
                    pacman)
                        # Try from AUR helper or pip
                        if command -v yay &>/dev/null; then
                            sudo -u "${SUDO_USER:-$USER}" yay -S --noconfirm envycontrol 2>/dev/null || pip install envycontrol 2>/dev/null || true
                        elif command -v paru &>/dev/null; then
                            sudo -u "${SUDO_USER:-$USER}" paru -S --noconfirm envycontrol 2>/dev/null || pip install envycontrol 2>/dev/null || true
                        else
                            pip install envycontrol 2>/dev/null || true
                        fi
                        ;;
                    apt)
                        pip install envycontrol 2>/dev/null || pip3 install envycontrol 2>/dev/null || true
                        ;;
                    dnf)
                        pip install envycontrol 2>/dev/null || pip3 install envycontrol 2>/dev/null || true
                        ;;
                    *)
                        pip install envycontrol 2>/dev/null || pip3 install envycontrol 2>/dev/null || true
                        ;;
                esac
                if command -v envycontrol &>/dev/null; then
                    log "envycontrol installed successfully!"
                else
                    warn "envycontrol installation failed. You can install it manually later."
                fi
                ;;
            2)
                info "Installing prime-select..."
                case $PM in
                    apt)
                        $INSTALL_CMD nvidia-prime 2>/dev/null || true
                        ;;
                    *)
                        warn "prime-select is only available on Ubuntu/Mint with apt. Skipping."
                        ;;
                esac
                ;;
            *)
                info "No GPU switching tool will be installed."
                ;;
        esac
    else
        if [ "$_HAS_ENVY" -eq 1 ]; then
            log "GPU switching tool found: envycontrol"
        elif [ "$_HAS_PRIME" -eq 1 ]; then
            log "GPU switching tool found: prime-select"
        fi
    fi

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
        cp images/hplogolight.png "$DATA_DIR/images/hp_logo.png" 2>/dev/null || true
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

    # Install Omen Key handler
    mkdir -p /usr/libexec/hp-manager
    if [ -f data/90-hp-omen-key.rules ]; then
        cp data/90-hp-omen-key.rules /etc/udev/rules.d/
    fi
    if [ -f data/hp-omen-key.service ]; then
        cp data/hp-omen-key.service /etc/systemd/system/
    fi
    if [ -f data/omen-key-listener.sh ]; then
        cp data/omen-key-listener.sh /usr/libexec/hp-manager/
        chmod +x /usr/libexec/hp-manager/omen-key-listener.sh
    fi
    # Enable Omen Key system service
    systemctl daemon-reload
    systemctl enable hp-omen-key.service 2>/dev/null || true
    systemctl restart hp-omen-key.service 2>/dev/null || true
    log "Omen Key handler installed (system service)"

    # ── Driver module management ──
    # Enable automatic loading of hp-rgb-lighting on boot
    MODULES_LOAD_FILE="/etc/modules-load.d/hp-rgb-lighting.conf"
    cat > "$MODULES_LOAD_FILE" << 'MODCONF'
# HP Laptop Manager: load the companion driver for Omen/Victus
hp-rgb-lighting
MODCONF
    # Remove old blacklist if it exists
    rm -f /etc/modprobe.d/hp-rgb-lighting.conf 2>/dev/null || true
    log "hp-rgb-lighting set to load on boot ($MODULES_LOAD_FILE)"

    # Detect kernel version for smart module management
    _KERN_VER=$(uname -r | grep -oP '^\d+\.\d+')
    _KERN_MAJOR=$(echo "$_KERN_VER" | cut -d. -f1)
    _KERN_MINOR=$(echo "$_KERN_VER" | cut -d. -f2)
    _STOCK_FAN=false
    if [ "$_KERN_MAJOR" -ge 7 ] 2>/dev/null; then
        _STOCK_FAN=true
    fi

    if $_STOCK_FAN; then
        # Kernel 7.0+: stock hp-wmi already has Omen fan control
        info "Kernel $(uname -r) (>= 7.0): using stock hp-wmi for fan control."
        # Only load hp-rgb-lighting for RGB
        rmmod hp_rgb_lighting 2>/dev/null || true
        modprobe hp-rgb-lighting 2>/dev/null || true
    else
        # Kernel < 7.0: replace stock module with custom one
        rmmod hp_wmi 2>/dev/null || true
        rmmod hp_rgb_lighting 2>/dev/null || true
        modprobe hp-wmi 2>/dev/null || true
        modprobe hp-rgb-lighting 2>/dev/null || true
    fi

    # Enable and start daemon
    systemctl daemon-reload
    systemctl enable hp-manager.service
    systemctl restart hp-manager.service || warn "$(msg daemon_start_fail)"
    log "$(msg daemon_enabled)"

    # Enable power management service: Prioritize Tuned, fallback to PPD
    if systemctl list-unit-files | grep -q tuned.service; then
        info "Enabling tuned service..."
        systemctl enable tuned 2>/dev/null || true
        systemctl start tuned 2>/dev/null || true
        # Stop conflicting PPD if it's running
        systemctl stop power-profiles-daemon 2>/dev/null || true
        systemctl disable power-profiles-daemon 2>/dev/null || true
    elif systemctl list-unit-files | grep -q power-profiles-daemon; then
        info "Enabling power-profiles-daemon service..."
        systemctl enable power-profiles-daemon 2>/dev/null || true
        systemctl start power-profiles-daemon 2>/dev/null || true
    fi

    # Install icon to system theme for better integration
    mkdir -p /usr/share/icons/hicolor/48x48/apps/
    cp images/hplogodark.png /usr/share/icons/hicolor/48x48/apps/hp_logo.png
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
systemctl stop hp-omen-key.service 2>/dev/null
systemctl disable hp-omen-key.service 2>/dev/null
rm -f /etc/systemd/system/hp-manager.service
rm -f /etc/systemd/system/hp-omen-key.service
rm -f /usr/bin/hp-manager
rm -f /usr/bin/hp-manager-uninstall
rm -rf /usr/libexec/hp-manager
rm -rf /usr/share/hp-manager
rm -f /etc/dbus-1/system.d/com.yyl.hpmanager.conf
rm -f /usr/share/polkit-1/actions/com.yyl.hpmanager.policy
rm -f /usr/share/applications/com.yyl.hpmanager.desktop
rm -f /usr/share/icons/hicolor/48x48/apps/hp_logo.png
rm -f /etc/udev/rules.d/90-hp-omen-key.rules
rm -f /usr/lib/systemd/user/hp-omen-key.service
rm -f /etc/modprobe.d/hp-omen-core.conf
rm -f /etc/modules-load.d/hp-omen-core.conf
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
echo "  ║    HP Laptop Manager Installer    ║"
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
        # Show Secure Boot warning if active
        if command -v mokutil &>/dev/null && mokutil --sb-state 2>/dev/null | grep -qi "SecureBoot enabled"; then
            echo ""
            echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
            echo -e "${YELLOW}║  ⚠  Secure Boot is ENABLED                               ║${NC}"
            echo -e "${YELLOW}║                                                           ║${NC}"
            echo -e "${YELLOW}║  Keyboard RGB control (hp-rgb-lighting) is unavailable.  ║${NC}"
            echo -e "${YELLOW}║  Disable Secure Boot in BIOS to use keyboard lighting.   ║${NC}"
            echo -e "${YELLOW}║  All other features work normally.                        ║${NC}"
            echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
            echo ""
        fi
        ;;
    uninstall|remove)
        uninstall_app
        log "$(msg uninstall_complete)"
        ;;
    *)
        echo "$(msg usage)"
        ;;
esac
