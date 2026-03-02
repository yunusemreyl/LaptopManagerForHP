#!/bin/bash
# HP Laptop Manager - Uninstaller script

LANG_CODE=${LANG:0:2}

if [ "$(id -u)" -ne 0 ]; then
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Bu scripti root olarak çalıştırın: sudo $0"
    else
        echo "Run this script as root: sudo $0"
    fi
    exit 1
fi

UNINSTALLER="/usr/bin/hp-manager-uninstall"

if [ -f "$UNINSTALLER" ]; then
    "$UNINSTALLER"
else
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Kaldırma aracı $UNINSTALLER konumunda bulunamadı."
        echo "Manuel kaldırma yapılıyor..."
    else
        echo "Uninstaller not found at $UNINSTALLER."
        echo "Falling back to manual removal..."
    fi

    systemctl stop hp-manager.service 2>/dev/null
    systemctl disable hp-manager.service 2>/dev/null
    rm -f /etc/systemd/system/hp-manager.service
    rm -f /usr/bin/hp-manager
    rm -rf /usr/libexec/hp-manager
    rm -rf /usr/share/hp-manager
    rm -f /etc/dbus-1/system.d/com.yyl.hpmanager.conf
    rm -f /usr/share/polkit-1/actions/com.yyl.hpmanager.policy
    rm -f /usr/share/applications/com.yyl.hpmanager.desktop
    rm -f /usr/share/icons/hicolor/48x48/apps/hp_logo.png
    rm -f /etc/modprobe.d/hp-omen-core.conf
    rm -f /etc/modules-load.d/hp-omen-core.conf
    systemctl daemon-reload
    
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Manuel kaldırma tamamlandı."
    else
        echo "Manual removal complete."
    fi
fi
