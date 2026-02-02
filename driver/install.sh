#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
MODULE_NAME="hp-omen-rgb"
KERNEL_MODULE_NAME="hp_omen_rgb"
VERSION="1.0"
if [[ $EUID -ne 0 ]]; then exec sudo "$0" "$@"; exit $?; fi
echo -e "${GREEN}>>> Bağımlılıklar kuruluyor...${NC}"
apt update -qq && apt install -y dkms linux-headers-$(uname -r) build-essential
dkms remove ${MODULE_NAME}/${VERSION} --all >/dev/null 2>&1
rm -rf /usr/src/${MODULE_NAME}-${VERSION}
mkdir -p /usr/src/${MODULE_NAME}-${VERSION}
cp -r . /usr/src/${MODULE_NAME}-${VERSION}/
echo -e "${GREEN}>>> DKMS Derleme Başlıyor...${NC}"
dkms add -m ${MODULE_NAME} -v ${VERSION}
dkms build -m ${MODULE_NAME} -v ${VERSION}
dkms install -m ${MODULE_NAME} -v ${VERSION}
depmod -a
modprobe ${KERNEL_MODULE_NAME}
echo "${KERNEL_MODULE_NAME}" > /etc/modules-load.d/${MODULE_NAME}.conf
if lsmod | grep -q "${KERNEL_MODULE_NAME}"; then
    echo -e "${GREEN}>>> BAŞARILI! Sürücü aktif.${NC}"
else
    echo -e "${RED}>>> HATA! Modül yüklenemedi.${NC}"
fi
