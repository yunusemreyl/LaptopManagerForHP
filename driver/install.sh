#!/usr/bin/env bash
# install.sh — Multi-distro installer for hp-wmi-fan-and-backlight-control
# https://github.com/TUXOV/hp-wmi-fan-and-backlight-control
#
# Supports: Debian/Ubuntu, Fedora/RHEL, Arch, openSUSE, Void, Gentoo
# Usage: sudo ./install.sh [install|uninstall]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

MODNAME="hp-omen-core"
MODVER=$(grep -oP 'PACKAGE_VERSION="\K[^"]+' dkms.conf 2>/dev/null || echo "1.0.0")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Kernel version detection ──────────────────────────────────────────────────
# Kernel 6.18+ has Omen/Victus fan control in the stock hp-wmi module.
# On those kernels we only need hp-omen-core (RGB). On older kernels we
# install both hp-wmi and hp-omen-core.
KERNEL_VER=$(uname -r | grep -oP '^\d+\.\d+')
KERNEL_MAJOR=$(echo "$KERNEL_VER" | cut -d. -f1)
KERNEL_MINOR=$(echo "$KERNEL_VER" | cut -d. -f2)
STOCK_FAN_SUPPORT=false
if [ "$KERNEL_MAJOR" -gt 6 ] 2>/dev/null || \
   { [ "$KERNEL_MAJOR" -eq 6 ] && [ "$KERNEL_MINOR" -ge 18 ]; } 2>/dev/null; then
    STOCK_FAN_SUPPORT=true
fi

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Distro detection ──────────────────────────────────────────────────────────

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-$DISTRO_ID}"
    elif [ -f /etc/arch-release ]; then
        DISTRO_ID="arch"
        DISTRO_LIKE="arch"
    elif [ -f /etc/gentoo-release ]; then
        DISTRO_ID="gentoo"
        DISTRO_LIKE="gentoo"
    else
        DISTRO_ID="unknown"
        DISTRO_LIKE="unknown"
    fi
}

# ── Dependency installation per distro ────────────────────────────────────────

install_deps() {
    info "Detected distro: ${DISTRO_ID}"

    case "$DISTRO_ID" in
        ubuntu|debian|linuxmint|pop|elementary|zorin|kali)
            info "Installing dependencies (apt)..."
            apt-get update -qq
            apt-get install -y dkms build-essential linux-headers-"$(uname -r)"
            ;;
        fedora)
            info "Installing dependencies (dnf)..."
            dnf install -y dkms kernel-devel kernel-headers gcc make
            ;;
        rhel|centos|rocky|alma)
            info "Installing dependencies (dnf/yum)..."
            if command -v dnf &>/dev/null; then
                dnf install -y dkms kernel-devel kernel-headers gcc make
            else
                yum install -y dkms kernel-devel kernel-headers gcc make
            fi
            ;;
        arch|manjaro|endeavouros|garuda|cachyos)
            info "Installing dependencies (pacman)..."
            pacman -S --needed --noconfirm dkms linux-headers base-devel
            ;;
        opensuse*|suse*)
            info "Installing dependencies (zypper)..."
            zypper install -y dkms kernel-devel kernel-default-devel gcc make
            ;;
        void)
            info "Installing dependencies (xbps)..."
            xbps-install -Sy dkms linux-headers base-devel
            ;;
        gentoo)
            info "Gentoo detected. Ensure sys-kernel/dkms and linux-headers are installed."
            command -v dkms &>/dev/null || error "dkms not found. Install it with: emerge sys-kernel/dkms"
            ;;
        *)
            # Try ID_LIKE as fallback
            case "$DISTRO_LIKE" in
                *debian*|*ubuntu*)
                    info "Debian-like distro detected, using apt..."
                    apt-get update -qq
                    apt-get install -y dkms build-essential linux-headers-"$(uname -r)"
                    ;;
                *fedora*|*rhel*)
                    info "Fedora-like distro detected, using dnf..."
                    dnf install -y dkms kernel-devel kernel-headers gcc make
                    ;;
                *arch*)
                    info "Arch-like distro detected, using pacman..."
                    pacman -S --needed --noconfirm dkms linux-headers base-devel
                    ;;
                *suse*)
                    info "SUSE-like distro detected, using zypper..."
                    zypper install -y dkms kernel-devel kernel-default-devel gcc make
                    ;;
                *)
                    warn "Unknown distro '${DISTRO_ID}'. Attempting generic install..."
                    warn "Make sure you have installed: dkms, gcc, make, kernel-headers"
                    command -v dkms &>/dev/null || error "dkms not found. Please install it manually."
                    ;;
            esac
            ;;
    esac
}

# ── Install ───────────────────────────────────────────────────────────────────

do_install() {
    [[ $EUID -ne 0 ]] && error "This script must be run as root (use sudo)."

    detect_distro
    install_deps

    # Detect if the running kernel was compiled with Clang and automatically set LLVM=1
    if grep -iq "clang" /proc/version; then
        info "Kernel built with Clang/LLVM detected. Automatically setting LLVM=1 for build..."
        export LLVM=1
    fi

    cd "$SCRIPT_DIR"

    if $STOCK_FAN_SUPPORT; then
        info "Kernel $(uname -r) detected (>= 6.18) — stock hp-wmi already has Omen fan control."
        info "Only building hp-omen-core (RGB keyboard control)..."

        # Create an RGB-only DKMS config
        cat > "$SCRIPT_DIR/dkms.conf.auto" <<'DKMSRGB'
PACKAGE_NAME="hp-omen-core"
PACKAGE_VERSION="1.0.0"
MAKE[0]="grep -iq clang /proc/version && make LLVM=1 -C $kernel_source_dir M=$dkms_tree/$module/$module_version/build EXTRA_CFLAGS='' modules || make -C $kernel_source_dir M=$dkms_tree/$module/$module_version/build EXTRA_CFLAGS='' modules"
CLEAN=true
BUILT_MODULE_NAME[0]="hp-omen-core"
DEST_MODULE_LOCATION[0]="/kernel/drivers/platform/x86/hp"
AUTOINSTALL="yes"
DKMSRGB
        # Build only hp-omen-core
        make clean 2>/dev/null || true
        make -C /lib/modules/$(uname -r)/build M="$SCRIPT_DIR" obj-m=hp-omen-core.o modules || error "Build failed."
    else
        info "Kernel $(uname -r) detected (< 6.18) — installing both hp-wmi and hp-omen-core..."
        make clean 2>/dev/null || true
        make || error "Build failed. Check that kernel headers are installed."
    fi

    # Remove old DKMS entry if exists
    if dkms status "$MODNAME/$MODVER" 2>/dev/null | grep -q "$MODNAME"; then
        warn "Removing existing DKMS entry ($MODNAME/$MODVER)..."
        dkms remove -m "$MODNAME" -v "$MODVER" --all 2>/dev/null || true
    fi

    # Install via DKMS with the appropriate config
    info "Installing via DKMS..."
    if $STOCK_FAN_SUPPORT && [ -f "$SCRIPT_DIR/dkms.conf.auto" ]; then
        # Backup original and use RGB-only config
        cp "$SCRIPT_DIR/dkms.conf" "$SCRIPT_DIR/dkms.conf.full"
        cp "$SCRIPT_DIR/dkms.conf.auto" "$SCRIPT_DIR/dkms.conf"
    fi
    dkms add "$SCRIPT_DIR"
    dkms build -m "$MODNAME" -v "$MODVER"
    dkms install -m "$MODNAME" -v "$MODVER"
    # Restore original dkms.conf
    if [ -f "$SCRIPT_DIR/dkms.conf.full" ]; then
        mv "$SCRIPT_DIR/dkms.conf.full" "$SCRIPT_DIR/dkms.conf"
        rm -f "$SCRIPT_DIR/dkms.conf.auto"
    fi

    # ── Secure Boot check ───────────────────────────────────────────────────────
    SECUREBOOT=false
    if command -v mokutil &>/dev/null; then
        if mokutil --sb-state 2>/dev/null | grep -qi "SecureBoot enabled"; then
            SECUREBOOT=true
        fi
    fi

    if $SECUREBOOT; then
        echo ""
        echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║  ⚠  Secure Boot is ENABLED                               ║${NC}"
        echo -e "${YELLOW}║                                                           ║${NC}"
        echo -e "${YELLOW}║  The hp-omen-core module (keyboard RGB control) cannot    ║${NC}"
        echo -e "${YELLOW}║  be loaded while Secure Boot is active.                   ║${NC}"
        echo -e "${YELLOW}║                                                           ║${NC}"
        echo -e "${YELLOW}║  To use keyboard lighting control, please disable         ║${NC}"
        echo -e "${YELLOW}║  Secure Boot from your BIOS/UEFI settings.               ║${NC}"
        echo -e "${YELLOW}║                                                           ║${NC}"
        echo -e "${YELLOW}║  Fan control and other features work normally.            ║${NC}"
        echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
        echo ""
        warn "Skipping module load due to Secure Boot. Keyboard RGB will be unavailable."
    fi

    # Load the modules
    if $SECUREBOOT; then
        info "Secure Boot active — skipping module load (hp-omen-core requires Secure Boot disabled)."
        ok "DKMS installation complete. Modules will load after Secure Boot is disabled and system is rebooted."
    elif $STOCK_FAN_SUPPORT; then
        info "Loading modules..."
        # Only load hp-omen-core; fan control uses stock hp-wmi
        modprobe led_class_multicolor 2>/dev/null || true
        if ! modprobe hp_omen_core 2>/dev/null; then
            insmod "$SCRIPT_DIR/hp-omen-core.ko" 2>/dev/null || warn "hp-omen-core could not be loaded."
        fi
        ok "hp-omen-core (RGB) installed. Stock hp-wmi handles fan control."
    else
        info "Loading modules..."
        rmmod hp_wmi 2>/dev/null || true
        modprobe led_class_multicolor 2>/dev/null || true
        if ! modprobe hp_wmi 2>/dev/null; then
            insmod "$SCRIPT_DIR/hp-wmi.ko" || warn "hp-wmi could not be loaded."
        fi
        ok "Both hp-wmi and hp-omen-core installed."
    fi

    echo ""
    info "The module will be automatically rebuilt on kernel updates via DKMS."
    if ! $STOCK_FAN_SUPPORT; then
        info "Fan control: /sys/devices/platform/hp-wmi/hwmon/hwmon*/pwm1_enable"
        info "Fan speed:   /sys/devices/platform/hp-wmi/hwmon/hwmon*/fan*_target"
    fi
    echo ""
}

# ── Uninstall ─────────────────────────────────────────────────────────────────

do_uninstall() {
    [[ $EUID -ne 0 ]] && error "This script must be run as root (use sudo)."

    info "Unloading module..."
    rmmod hp_wmi 2>/dev/null || true

    info "Removing DKMS entry..."
    if dkms status "$MODNAME/$MODVER" 2>/dev/null | grep -q "$MODNAME"; then
        dkms remove -m "$MODNAME" -v "$MODVER" --all
        rm -rf "/usr/src/${MODNAME}-${MODVER}"
        ok "Uninstalled successfully."
    else
        warn "DKMS entry not found. Nothing to remove."
    fi

    # Reload original kernel module
    info "Reloading original hp-wmi module..."
    modprobe hp_wmi 2>/dev/null || warn "Could not reload original hp-wmi module."
}

# ── Main ──────────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: sudo $0 [install|uninstall]"
    echo ""
    echo "  install     Build and install the module via DKMS"
    echo "  uninstall   Remove the module and restore the original"
    echo ""
    echo "If no argument is given, 'install' is assumed."
}

case "${1:-install}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    -h|--help) usage ;;
    *)         usage; exit 1 ;;
esac
