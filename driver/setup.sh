#!/usr/bin/env bash
# setup.sh — Multi-distro installer for hp-wmi-fan-and-backlight-control
# https://github.com/TUXOV/hp-wmi-fan-and-backlight-control
#
# Supports: Debian/Ubuntu, Fedora/RHEL, Arch, openSUSE, Void, Gentoo
# Usage: sudo ./setup.sh [install|uninstall]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

MODNAME="hp-rgb-lighting"
MODVER=$(grep -oP 'PACKAGE_VERSION="\K[^"]+' dkms.conf 2>/dev/null || echo "1.3.5")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# MOK_DIR — initialised here so it is always defined (avoids unbound variable
# errors in the MOK_PENDING check when Secure Boot is disabled)
MOK_DIR="/var/lib/hp-manager/mok"

# ── Kernel version detection ──────────────────────────────────────────────────
# Kernel 7.0+ has Omen/Victus fan control in the stock hp-wmi module.
KVER_MAJOR=$(uname -r | cut -d. -f1)
KVER_MINOR=$(uname -r | cut -d. -f2)
BOARD_NAME=$(cat /sys/devices/virtual/dmi/id/board_name 2>/dev/null | tr '[:lower:]' '[:upper:]' || echo "")
FORCE_CUSTOM_HPWMI=true

STOCK_FAN_SUPPORT=false
if [ "$KVER_MAJOR" -gt 7 ] || { [ "$KVER_MAJOR" -eq 7 ] && [ "$KVER_MINOR" -ge 0 ]; }; then
    STOCK_FAN_SUPPORT=true
    # Verify stock hp-wmi actually exists in the kernel tree (e.g. some Zen/Arch kernels omit it)
    if ! modinfo hp-wmi &>/dev/null; then
        # Check if the kernel tree is simply missing due to a pending reboot (common on Arch/CachyOS)
        if [ ! -e "/lib/modules/$(uname -r)/modules.dep" ] && [ ! -e "/usr/lib/modules/$(uname -r)/modules.dep" ]; then
            echo -e "${RED}[ERROR] Kernel modules for $(uname -r) are missing or broken.${NC}"
            echo -e "${RED}[ERROR] This usually means you updated your kernel but haven't rebooted.${NC}"
            echo -e "${RED}[ERROR] Please reboot your system and run the installer again.${NC}"
            exit 1
        fi
        echo -e "${YELLOW}[WARN] Kernel >= 7.0 detected but stock hp-wmi module is missing. Forcing custom hp-wmi build.${NC}"
        STOCK_FAN_SUPPORT=false
        FORCE_CUSTOM_HPWMI=true
    fi
fi
if $FORCE_CUSTOM_HPWMI; then
    STOCK_FAN_SUPPORT=false
fi
# Allow the parent installer to request RGB-only mode (e.g. user declined patched hp-wmi).
if [ "${FORCE_RGB_ONLY:-false}" = true ]; then
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
            apt-get update -qq || true
            apt-get install -y dkms build-essential linux-headers-"$(uname -r)"
            ;;
        fedora|nobara)
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
            local HEADERS_PKG=""
            local RUNNING_KVER
            RUNNING_KVER=$(uname -r)

            if [[ $RUNNING_KVER == *"-cachyos"* ]]; then
                # CachyOS can have multiple kernel flavours (bore, deckify, …)
                local SUFFIX
                SUFFIX=$(echo "$RUNNING_KVER" | sed 's/^[0-9.]*-[0-9]*-\(.*\)/\1/')
                if [[ -n "$SUFFIX" ]] && pacman -Si "linux-$SUFFIX-headers" &>/dev/null 2>&1; then
                    HEADERS_PKG="linux-$SUFFIX-headers"
                elif pacman -Si linux-cachyos-headers &>/dev/null 2>&1; then
                    HEADERS_PKG="linux-cachyos-headers"
                else
                    HEADERS_PKG="linux-headers"
                fi
            elif [[ $RUNNING_KVER == *"-zen"* ]]; then
                HEADERS_PKG="linux-zen-headers"
            elif [[ $RUNNING_KVER == *"-lts"* ]]; then
                HEADERS_PKG="linux-lts-headers"
            elif [[ $RUNNING_KVER == *"-hardened"* ]]; then
                HEADERS_PKG="linux-hardened-headers"
            elif [[ $RUNNING_KVER == *"-rt"* ]]; then
                HEADERS_PKG="linux-rt-headers"
            else
                HEADERS_PKG="linux-headers"
            fi

            info "Attempting to install: dkms $HEADERS_PKG base-devel"
            if ! pacman -S --needed --noconfirm dkms "$HEADERS_PKG" base-devel; then
                warn "Could not install $HEADERS_PKG. Trying generic linux-headers..."
                pacman -S --needed --noconfirm dkms linux-headers base-devel \
                    || warn "Header installation failed. DKMS might not work without headers."
            fi
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
            # Fallback: try ID_LIKE
            case "$DISTRO_LIKE" in
                *debian*|*ubuntu*)
                    info "Debian-like distro detected, using apt..."
                    apt-get update -qq || true
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

# ── Helper: find module path in both /lib and /usr/lib ───────────────────────
# Some distros (Arch, CachyOS, Gentoo, newer Debian/Ubuntu) store kernel
# modules under /usr/lib/modules rather than /lib/modules.  Both paths are
# searched so backups and restores work on all distros.

find_module_paths() {
    local pattern="$1"
    local kver="${2:-$(uname -r)}"
    find \
        "/lib/modules/$kver" \
        "/usr/lib/modules/$kver" \
        -name "$pattern" 2>/dev/null | sort -u
}

# ── Install ───────────────────────────────────────────────────────────────────

do_install() {
    [[ $EUID -ne 0 ]] && error "This script must be run as root (use sudo)."
    local ORIG_WMI=""

    detect_distro
    install_deps

    if $FORCE_CUSTOM_HPWMI; then
        case "$BOARD_NAME" in
            8D41|8D42|8BCD) warn "Board ${BOARD_NAME:-unknown} detected — forcing custom hp-wmi install path on kernel $(uname -r)." ;;
            *) warn "Forcing custom hp-wmi install path on kernel $(uname -r)." ;;
        esac
    fi

    # Detect Clang-built kernel and set LLVM=1 automatically
    if grep -iq "clang" /proc/version; then
        info "Kernel built with Clang/LLVM detected. Automatically setting LLVM=1 for build..."
        export LLVM=1
    fi

    cd "$SCRIPT_DIR"

    # Create the source directory and copy files first so that dkms remove has a valid dkms.conf to read
    # (otherwise dkms remove fails with 'Missing the module source directory')
    rm -rf "/usr/src/${MODNAME}-${MODVER}"
    mkdir -p "/usr/src/${MODNAME}-${MODVER}"

    # Copy source files into the DKMS tree
    cp "$SCRIPT_DIR/dkms.conf" "$SCRIPT_DIR/Makefile" "$SCRIPT_DIR"/*.c \
       "/usr/src/${MODNAME}-${MODVER}/"
    cp "$SCRIPT_DIR"/*.h "/usr/src/${MODNAME}-${MODVER}/" 2>/dev/null || true

    # Purge stale .ko files from previous installs that may reference
    # removed symbols (e.g. hp_wmi_mutex).  Without this, modprobe may
    # find and load the old .ko instead of the freshly built one.
    info "Purging stale hp-rgb-lighting module files..."
    KVER=$(uname -r)
    find /lib/modules/"$KVER" /usr/lib/modules/"$KVER" \
        -name 'hp-rgb-lighting.ko*' -delete 2>/dev/null || true
    depmod -a 2>/dev/null || true

    # Tüm eski/artık DKMS girdilerini temizle
    if dkms status "$MODNAME" 2>/dev/null | grep -q "$MODNAME"; then
        warn "Removing existing DKMS entries for $MODNAME..."
        for v in $(dkms status "$MODNAME" | grep -oP '(?<='"$MODNAME"'[/, ])[^,:]+' | tr -d ' ' | sort -u); do
            [ -z "$v" ] && continue
            dkms remove -m "$MODNAME" -v "$v" --all 2>/dev/null || true
        done
    fi

    if $STOCK_FAN_SUPPORT; then
        info "Kernel $(uname -r) detected (>= 7.0) — stock hp-wmi already has Omen fan control."
        info "Only building hp-rgb-lighting (RGB keyboard control)..."

        # RGB-only DKMS config — pass RGB_ONLY=1 so Makefile only builds hp-rgb-lighting
        cat > "/usr/src/${MODNAME}-${MODVER}/dkms.conf" <<DKMSRGB
PACKAGE_NAME="hp-rgb-lighting"
PACKAGE_VERSION="$MODVER"
MAKE[0]="grep -iq clang /proc/version && make LLVM=1 RGB_ONLY=1 -C \$kernel_source_dir M=\$dkms_tree/\$module/\$module_version/build EXTRA_CFLAGS='' modules || make RGB_ONLY=1 -C \$kernel_source_dir M=\$dkms_tree/\$module/\$module_version/build EXTRA_CFLAGS='' modules"
CLEAN=true
BUILT_MODULE_NAME[0]="hp-rgb-lighting"
DEST_MODULE_LOCATION[0]="/kernel/drivers/platform/x86/hp"
AUTOINSTALL="yes"
DKMSRGB
    else
        if [ "$KVER_MAJOR" -gt 7 ] || { [ "$KVER_MAJOR" -eq 7 ] && [ "$KVER_MINOR" -ge 0 ]; }; then
            info "Kernel $(uname -r) detected (>= 7.0) but custom hp-wmi is forced — installing both hp-wmi and hp-rgb-lighting..."
        else
            info "Kernel $(uname -r) detected (< 7.0) — installing both hp-wmi and hp-rgb-lighting..."
        fi

        info "Checking for stock hp-wmi driver path..."
        # FIX: modinfo -n resolves symlinks and works on both /lib and /usr/lib
        ORIG_WMI=$(modinfo -n hp-wmi 2>/dev/null || true)
        if [[ -n "$ORIG_WMI" ]] && [[ -f "$ORIG_WMI" ]] && [[ ! "$ORIG_WMI" == *"updates"* ]] && [[ ! "$ORIG_WMI" == *"dkms"* ]]; then
            info "Stock driver detected at: $ORIG_WMI"
        else
            ORIG_WMI=""
        fi
    fi

    # Install via DKMS
    info "Installing via DKMS..."
    if ! dkms status "$MODNAME/$MODVER" 2>/dev/null | grep -Eq "^${MODNAME}/${MODVER}([,:]|$)"; then
        dkms add -m "$MODNAME" -v "$MODVER" || true
    else
        info "DKMS source already present for $MODNAME/$MODVER, skipping dkms add."
    fi
    dkms build   -m "$MODNAME" -v "$MODVER"          || error "DKMS build failed. Check logs."
    dkms install -m "$MODNAME" -v "$MODVER" --force   || error "DKMS install failed."

    # Refresh module dependency database so modprobe picks up the new .ko
    depmod -a

    # ── Post-install verification ────────────────────────────────────────────
    # Some distros (Nobara, certain Fedora spins) lack /usr/sbin/weak-modules,
    # which causes DKMS to silently skip the final copy step.  We verify that
    # the compiled .ko is actually reachable by modinfo; if not, force-reinstall
    # targeting the running kernel explicitly.
    info "Verifying DKMS module installation..."
    _dkms_verify_ok=true

    if ! modinfo hp-rgb-lighting &>/dev/null; then
        warn "hp-rgb-lighting not found by modinfo after DKMS install — retrying with --force..."
        dkms install -m "$MODNAME" -v "$MODVER" -k "$(uname -r)" --force 2>/dev/null || true
        depmod -a
        if ! modinfo hp-rgb-lighting &>/dev/null; then
            _dkms_verify_ok=false
            warn "hp-rgb-lighting STILL not found after forced reinstall."
            warn "Try manually: sudo dkms install $MODNAME/$MODVER -k $(uname -r) --force"
        fi
    fi

    if ! $STOCK_FAN_SUPPORT; then
        if ! modinfo hp-wmi 2>/dev/null | grep -q "dkms\|updates\|extra"; then
            warn "Custom hp-wmi not found in expected DKMS/updates path — retrying..."
            dkms install -m "$MODNAME" -v "$MODVER" -k "$(uname -r)" --force 2>/dev/null || true
            depmod -a
        fi
    fi

    if $_dkms_verify_ok; then
        ok "DKMS module verified: $(modinfo -n hp-rgb-lighting 2>/dev/null || echo 'path unknown')"
    fi

    # After DKMS install succeeds, archive stock hp-wmi so the DKMS module wins consistently.
    if ! $STOCK_FAN_SUPPORT && [[ -n "$ORIG_WMI" ]] && [[ -f "$ORIG_WMI" ]]; then
        if [[ ! -f "${ORIG_WMI}.backup" ]]; then
            info "Backing up stock driver: $ORIG_WMI"
            mv "$ORIG_WMI" "${ORIG_WMI}.backup"
        else
            info "Stock backup already exists: ${ORIG_WMI}.backup"
        fi
    fi

    # ── Secure Boot handling ─────────────────────────────────────────────────
    SECUREBOOT=false
    if command -v mokutil &>/dev/null; then
        if mokutil --sb-state 2>/dev/null | grep -qi "SecureBoot enabled"; then
            SECUREBOOT=true
        fi
    fi

    if $SECUREBOOT; then
        mkdir -p "$MOK_DIR"

        # Generate MOK key if missing
        if [ ! -f "$MOK_DIR/MOK.priv" ] || [ ! -f "$MOK_DIR/MOK.der" ]; then
            info "Generating MOK key for Secure Boot..."
            openssl req -new -x509 -newkey rsa:2048 \
                -keyout "$MOK_DIR/MOK.priv" \
                -outform DER -out "$MOK_DIR/MOK.der" \
                -days 36500 -subj "/CN=hp-manager-mok/" -nodes 2>/dev/null
            chmod 600 "$MOK_DIR/MOK.priv"
        fi

        # Sign installed modules
        KVER=$(uname -r)
        info "Signing custom modules for Secure Boot..."
        SIGN_SCRIPT=$(find \
            "/usr/src/linux-headers-$KVER/scripts" \
            "/usr/src/kernels/$KVER/scripts" \
            "/lib/modules/$KVER/build/scripts" \
            "/usr/lib/modules/$KVER/build/scripts" \
            "/usr/src/linux-headers-$KVER" \
            "/usr/lib/modules/$KVER" \
            -name "sign-file" -type f 2>/dev/null | head -n 1)

        if [ -n "$SIGN_SCRIPT" ]; then
            for MOD_NAME in "hp-rgb-lighting.ko" "hp-wmi.ko"; do
                if [ "$MOD_NAME" = "hp-wmi.ko" ] && $STOCK_FAN_SUPPORT; then
                    continue
                fi
                MOD_PATH=$(find_module_paths "$MOD_NAME" "$KVER" | grep -v "backup" | head -n 1)
                if [ -n "$MOD_PATH" ]; then
                    "$SIGN_SCRIPT" sha256 "$MOK_DIR/MOK.priv" "$MOK_DIR/MOK.der" "$MOD_PATH" \
                        || warn "Failed to sign $MOD_NAME"
                fi
            done
        else
            warn "sign-file script not found in kernel headers!"
            warn "Modules could not be signed. Secure Boot will block them unless you sign them manually or disable Secure Boot."
        fi

        # Enrol MOK if not yet enrolled
        if mokutil --test-key "$MOK_DIR/MOK.der" 2>/dev/null | grep -qi "not enrolled"; then
            info "Enrolling MOK key..."
            MOK_PASSWORD="omen"
            printf "%s\n%s\n" "$MOK_PASSWORD" "$MOK_PASSWORD" | mokutil --import "$MOK_DIR/MOK.der" 2>/dev/null \
                || warn "Failed to import MOK key."

            echo ""
            echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
            echo -e "${YELLOW}║  🔒 Secure Boot is ENABLED                                ║${NC}"
            echo -e "${YELLOW}║                                                           ║${NC}"
            echo -e "${YELLOW}║  A Machine Owner Key (MOK) has been registered to sign    ║${NC}"
            echo -e "${YELLOW}║  the custom drivers.                                      ║${NC}"
            echo -e "${YELLOW}║                                                           ║${NC}"
            echo -e "${YELLOW}║  ${RED}PLEASE REBOOT YOUR SYSTEM NOW.${YELLOW}                           ║${NC}"
            echo -e "${YELLOW}║  Upon reboot, a blue 'Perform MOK management' screen      ║${NC}"
            echo -e "${YELLOW}║  will appear. Follow these exact steps:                   ║${NC}"
            echo -e "${YELLOW}║                                                           ║${NC}"
            echo -e "${YELLOW}║  1. Select 'Enroll MOK'                                   ║${NC}"
            echo -e "${YELLOW}║  2. Select 'Continue'                                     ║${NC}"
            echo -e "${YELLOW}║  3. Select 'Yes'                                          ║${NC}"
            echo -e "${YELLOW}║  4. Enter password: ${GREEN}${MOK_PASSWORD}${YELLOW}$(printf '%*s' $((27 - ${#MOK_PASSWORD})) '')║${NC}"
            echo -e "${YELLOW}║  5. Select 'Reboot'                                       ║${NC}"
            echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
            echo ""
            warn "Skipping module load. Modules will load automatically after MOK enrollment."
        else
            ok "MOK key is already enrolled."
        fi
    fi

    # ── Load modules ─────────────────────────────────────────────────────────
    # FIX: MOK_PENDING check now always safe because MOK_DIR is always defined
    MOK_PENDING=false
    if $SECUREBOOT && mokutil --test-key "$MOK_DIR/MOK.der" 2>/dev/null | grep -qi "not enrolled"; then
        MOK_PENDING=true
    fi

    if $MOK_PENDING; then
        info "MOK enrollment pending — skipping module load until reboot."
    elif $STOCK_FAN_SUPPORT; then
        info "Loading modules..."
        # Unload any stale hp_rgb_lighting first so the freshly built one is loaded
        modprobe -r hp_rgb_lighting 2>/dev/null || true
        modprobe led_class_multicolor 2>/dev/null || true
        # FIX: use modprobe (not insmod) — searches DKMS-installed paths correctly
        if modprobe hp_rgb_lighting 2>/dev/null; then
            ok "hp-rgb-lighting loaded successfully"
        else
            warn "hp-rgb-lighting could not be loaded. (Secure Boot issue?)"
        fi
        ok "hp-rgb-lighting (RGB) installed. Stock hp-wmi handles fan control."
    else
        info "Loading modules..."
        # FIX: modprobe -r handles dependency unloading correctly (rmmod does not)
        modprobe -r hp_wmi 2>/dev/null || true
        modprobe led_class_multicolor 2>/dev/null || true
        # FIX: modprobe searches /lib/modules AND /usr/lib/modules (insmod cannot)
        if modprobe hp_wmi 2>/dev/null; then
            ok "hp-wmi loaded successfully"
        else
            warn "hp-wmi could not be loaded — check: dmesg | tail -20"
        fi
        if modprobe hp_rgb_lighting 2>/dev/null; then
            ok "hp-rgb-lighting loaded successfully"
        else
            warn "hp-rgb-lighting could not be loaded."
        fi
        ok "Both hp-wmi and hp-rgb-lighting installed."
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

    info "Unloading modules..."
    # FIX: modprobe -r handles inter-module dependencies; rmmod does not
    modprobe -r hp_rgb_lighting 2>/dev/null || true
    modprobe -r hp_wmi          2>/dev/null || true

    info "Removing DKMS entry..."
    if dkms status "$MODNAME/$MODVER" 2>/dev/null | grep -q "$MODNAME"; then
        dkms remove -m "$MODNAME" -v "$MODVER" --all
        rm -rf "/usr/src/${MODNAME}-${MODVER}"
        ok "Uninstalled successfully."
    else
        warn "DKMS entry not found. Nothing to remove."
    fi

    # Restore original driver backups
    info "Restoring original driver backups (if any)..."
    KVER=$(uname -r)
    FOUND_BACKUP=false

    # FIX: search both /lib/modules and /usr/lib/modules — Arch/CachyOS use the latter
    while IFS= read -r BU_FILE; do
        ORIG_FILE="${BU_FILE%.backup}"
        info "Restoring $ORIG_FILE from backup..."
        mv "$BU_FILE" "$ORIG_FILE"
        FOUND_BACKUP=true
    done < <(find_module_paths "hp-wmi.ko*.backup" "$KVER")

    if [ "$FOUND_BACKUP" = true ]; then
        depmod -a
        info "Reloading original hp-wmi module..."
        modprobe hp_wmi 2>/dev/null || warn "Could not reload original hp-wmi module."
    else
        info "No backup found — skipping restore."
    fi
}

# ── Helper (also used in uninstall) ──────────────────────────────────────────
find_module_paths() {
    local pattern="$1"
    local kver="${2:-$(uname -r)}"
    find \
        "/lib/modules/$kver" \
        "/usr/lib/modules/$kver" \
        -name "$pattern" 2>/dev/null | sort -u
}

# ── Main ──────────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: sudo $0 [install|uninstall]"
    echo ""
    echo "  install      Build and install the module via DKMS"
    echo "  uninstall    Remove the module and restore the original"
    echo ""
    echo "If no argument is given, 'install' is assumed."
}

case "${1:-install}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    -h|--help) usage ;;
    *)         usage; exit 1 ;;
esac
