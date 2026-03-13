#!/bin/bash
# HP Laptop Manager - Automatic Updater

LANG_CODE=${LANG:0:2}

if [ "$(id -u)" -ne 0 ]; then
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Bu scripti root olarak çalıştırın: sudo $0"
    else
        echo "Run this script as root: sudo $0"
    fi
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Update from GitHub if it's a git repo
if [ -d ".git" ]; then
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Git deposu güncelleniyor (git pull)..."
    else
        echo "Updating git repository (git pull)..."
    fi
    git stash
    git pull
else
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Uyarı: Bu dizin bir git deposu değil. Sadece yeniden kurulum yapılacak."
    else
        echo "Warning: This directory is not a git repository. Proceeding with reinstall."
    fi
fi

# 2. Uninstall old versions
if [ -x "./uninstall.sh" ]; then
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Eski sürümler ve modüller kaldırılıyor (hp-omen-core / hp-rgb-lighting)..."
    else
        echo "Removing old versions and modules (hp-omen-core / hp-rgb-lighting)..."
    fi
    ./uninstall.sh
fi

# 3. Clean and reinstall
if [ -x "./install.sh" ]; then
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Yeni sürüm (v1.1.0) kuruluyor..."
    else
        echo "Installing new version (v1.1.0)..."
    fi
    
    # Also clean up any old build files
    if [ -d "driver" ]; then
        (cd driver && make clean >/dev/null 2>&1)
    fi

    ./install.sh
else
    if [ "$LANG_CODE" == "tr" ]; then
        echo "Hata: install.sh bulunamadı veya çalıştırılabilir değil."
    else
        echo "Error: install.sh not found or not executable."
    fi
    exit 1
fi

if [ "$LANG_CODE" == "tr" ]; then
    echo "Güncelleme tamamlandı! Yeni sürümü (v1.1.0) özellikleriyle kullanmaya başlayabilirsiniz."
else
    echo "Update complete! You can now start using the new version (v1.1.0) and its features."
fi
