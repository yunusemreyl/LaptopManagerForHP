#!/bin/bash

# Renkler
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}>>> OMEN CONTROL KURULUMU BAŞLIYOR...${NC}"

# Root kontrolü
if [ "$EUID" -ne 0 ]; then
  echo "Lütfen sudo ile çalıştırın: sudo ./install.sh"
  exit
fi

# 1. Bağımlılıkları Yükle (Fedora için)
echo -e "${GREEN}>>> Bağımlılıklar yükleniyor...${NC}"
dnf install python3-psutil python3-gobject gtk4 libadwaita kernel-devel gcc make -y

# 2. Driver Derle ve Yükle
echo -e "${GREEN}>>> Sürücü derleniyor...${NC}"
cd driver
make clean
make
make install
cd ..

# 3. Dosyaları Kopyala
echo -e "${GREEN}>>> Dosyalar kopyalanıyor...${NC}"
mkdir -p /opt/omen-control/images
mkdir -p /etc/omen-control
chmod 777 /etc/omen-control

cp backend.py /opt/omen-control/
cp gui.py /opt/omen-control/
cp images/* /opt/omen-control/images/

chmod +x /opt/omen-control/backend.py
chmod +x /opt/omen-control/gui.py

# 4. Servisi Oluştur
echo -e "${GREEN}>>> Servis oluşturuluyor...${NC}"
cat <<EOF > /etc/systemd/system/omen-control.service
[Unit]
Description=Omen Control RGB Service
After=multi-user.target

[Service]
ExecStart=/usr/bin/python3 /opt/omen-control/backend.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# 5. Kısayol Oluştur
echo -e "${GREEN}>>> Kısayol oluşturuluyor...${NC}"
cat <<EOF > /usr/share/applications/omen-control.desktop
[Desktop Entry]
Name=Omen Control
Comment=HP Victus RGB Controller
Exec=/opt/omen-control/gui.py
Icon=/opt/omen-control/images/omen_logo.png
Terminal=false
Type=Application
Categories=Utility;Settings;
EOF

# 6. Başlat
echo -e "${GREEN}>>> Servisler başlatılıyor...${NC}"
systemctl daemon-reload
systemctl enable --now omen-control.service

echo -e "${GREEN}>>> KURULUM TAMAMLANDI! Uygulamalar menüsünden 'Omen Control'ü açabilirsiniz.${NC}"
