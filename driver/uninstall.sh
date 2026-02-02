#!/bin/bash

# Renk Tanımlamaları
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

MODULE_NAME="hp-omen-rgb"
KERNEL_MODULE_NAME="hp_omen_rgb"
MODULE_VERSION="1.0"

# Root Yetkisi Kontrolü
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Lütfen sudo şifrenizi girin:${NC}"
   exec sudo "$0" "$@"
   exit $?
fi

echo -e "${RED}>>> HP Omen/Victus RGB Driver Kaldırılıyor...${NC}"

# 1. Modülü Durdur ve Çıkar
modprobe -r ${KERNEL_MODULE_NAME} 2>/dev/null

# 2. DKMS Kaydını Sil
echo ">>> DKMS kaydı siliniyor..."
dkms remove ${MODULE_NAME}/${MODULE_VERSION} --all >/dev/null 2>&1

# 3. Kaynak Dosyaları Temizle
echo ">>> Kaynak dosyalar temizleniyor..."
rm -rf /usr/src/${MODULE_NAME}-${MODULE_VERSION}

# 4. Başlangıç Ayarını (Autoload) Sil
rm -f /etc/modules-load.d/${MODULE_NAME}.conf

echo -e "${GREEN}>>> BAŞARILI! Sürücü sistemden tamamen kaldırıldı.${NC}"
