#!/usr/bin/env bash

# ==============================================================================
#  LaserRunner Installation And Update Helper (LIAUH)
#  KIAUH-Style TUI Installer & Manager for Raspberry Pi (Debian/Ubuntu/RPi OS)
# ==============================================================================

set -e

# Renk Tanımları
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_DIM="\033[2m"
CLR_RED="\033[0;31m"
CLR_GREEN="\033[0;32m"
CLR_YELLOW="\033[0;33m"
CLR_BLUE="\033[0;34m"
CLR_CYAN="\033[0;36m"
CLR_WHITE="\033[1;37m"

# Git ve Depo Ayarları
DEFAULT_REPO_URL="https://github.com/okokbudak/LaserRunner.git"
REPO_URL="${LASERRUNNER_REPO:-$DEFAULT_REPO_URL}"

# Dizin ve Dosya Yolları
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME=$(eval echo "~$TARGET_USER")
INSTALL_DIR="$TARGET_HOME/LaserRunner"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/laserrunner.service"
RULES_FILE="/etc/udev/rules.d/99-laserrunner.rules"

# Yardımcı Fonksiyonlar
print_banner() {
    clear
    echo -e "${CLR_CYAN}${CLR_BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════════════════╗"
    echo "  ║      _                               ____                             ║"
    echo "  ║     | |    __ _ ___  ___ _ __       |  _ \ _   _ _ __  _ __   ___ _ __║"
    echo "  ║     | |   / _\` / __|/ _ \ '__|_____ | |_) | | | | '_ \| '_ \ / _ \ '__║"
    echo "  ║     | |__| (_| \__ \  __/ | |_____| |  _ <| |_| | | | | | | |  __/ |  ║"
    echo "  ║     |_____\__,_|___/\___|_|         |_| \_\\__,_|_| |_|_| |_|\___|_|  ║"
    echo "  ║                                                                       ║"
    echo "  ║          LaserRunner Installation & Update Helper (LIAUH)             ║"
    echo "  ║             Klipper-Style Laser OS & LightBurn Web Studio             ║"
    echo "  ╚═══════════════════════════════════════════════════════════════════════╝"
    echo -e "${CLR_RESET}"
}

get_local_ip() {
    hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1"
}

get_service_status() {
    if [ ! -f "$SERVICE_FILE" ]; then
        echo -e "${CLR_RED}Kurulu Değil${CLR_RESET}"
    elif systemctl is-active --quiet laserrunner; then
        echo -e "${CLR_GREEN}Çalışıyor (Active)${CLR_RESET}"
    else
        echo -e "${CLR_YELLOW}Durduruldu (Inactive)${CLR_RESET}"
    fi
}

get_git_status() {
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo -e "${CLR_RED}Depo Bulunamadı${CLR_RESET}"
        return
    fi
    
    cd "$INSTALL_DIR" 2>/dev/null || return
    local local_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "Bilinmiyor")
    
    # Arka planda uzaktan commit kontrolü (1 saniye zaman aşımı ile)
    git fetch origin main --quiet 2>/dev/null || true
    local remote_commit=$(git rev-parse --short origin/main 2>/dev/null || echo "$local_commit")

    if [ "$local_commit" = "$remote_commit" ]; then
        echo -e "${CLR_GREEN}Güncel ($local_commit)${CLR_RESET}"
    else
        echo -e "${CLR_YELLOW}Güncelleme Mevcut ($local_commit -> $remote_commit)${CLR_RESET}"
    fi
}

get_venv_status() {
    if [ -f "$VENV_DIR/bin/python" ]; then
        echo -e "${CLR_GREEN}Hazır ($($VENV_DIR/bin/python --version 2>/dev/null | awk '{print $2}'))${CLR_RESET}"
    else
        echo -e "${CLR_RED}Yok${CLR_RESET}"
    fi
}

get_pio_status() {
    if command -v pio &> /dev/null || [ -f "$TARGET_HOME/.platformio/penv/bin/pio" ]; then
        echo -e "${CLR_GREEN}Kurulu${CLR_RESET}"
    else
        echo -e "${CLR_YELLOW}Kurulu Değil${CLR_RESET}"
    fi
}

print_status_box() {
    local ip=$(get_local_ip)
    echo -e "${CLR_BOLD}═════════════════════════════════════════════════════════════════════════${CLR_RESET}"
    echo -e " ${CLR_WHITE}Sistem Durumu:${CLR_RESET}"
    echo -e "   • LaserRunner Git Sürümü: $(get_git_status)"
    echo -e "   • LaserRunner Servisi   : $(get_service_status)"
    echo -e "   • Python Sanal Ortamı   : $(get_venv_status)"
    echo -e "   • PlatformIO (F/W)      : $(get_pio_status)"
    echo -e "   • Web Arayüzü Adresi    : ${CLR_CYAN}http://${ip}:8080${CLR_RESET}"
    echo -e "${CLR_BOLD}═════════════════════════════════════════════════════════════════════════${CLR_RESET}"
    echo ""
}

# ==============================================================================
# 1. TAM KURULUM İŞLEMİ (INSTALL)
# ==============================================================================
install_laserrunner() {
    echo -e "\n${CLR_CYAN}[+] LaserRunner Kurulumu Başlatılıyor...${CLR_RESET}\n"

    # 1. İşletim Sistemi Paketleri
    echo -e "${CLR_YELLOW}[1/7] Gerekli sistem paketleri yükleniyor (apt-get)...${CLR_RESET}"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
        git curl build-essential libjpeg-dev zlib1g-dev udev

    # 2. Git Deposunu Klonla (Eğer dizin yoksa)
    echo -e "${CLR_YELLOW}[2/7] LaserRunner GitHub deposu kontrol ediliyor...${CLR_RESET}"
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo -e "Depo klonlanıyor: ${CLR_CYAN}$REPO_URL${CLR_RESET}"
        sudo -u "$TARGET_USER" git clone "$REPO_URL" "$INSTALL_DIR"
    else
        echo -e "${CLR_GREEN}Depo zaten mevcut ($INSTALL_DIR).${CLR_RESET}"
    fi

    # 3. Kullanıcıyı dialout grubuna ekle (USB seri port izinleri)
    echo -e "${CLR_YELLOW}[3/7] Kullanıcı izinleri yapılandırılıyor (dialout grubu)...${CLR_RESET}"
    sudo usermod -a -G dialout "$TARGET_USER"

    # 4. Udev Kurallarını Yükle
    echo -e "${CLR_YELLOW}[4/7] Octopus Pro USB udev kuralları yükleniyor...${CLR_RESET}"
    if [ -f "$INSTALL_DIR/scripts/99-laserrunner.rules" ]; then
        sudo cp "$INSTALL_DIR/scripts/99-laserrunner.rules" /etc/udev/rules.d/
        sudo udevadm control --reload-rules
        sudo udevadm trigger
    fi

    # 5. Python Sanal Ortamını (venv) Oluştur
    echo -e "${CLR_YELLOW}[5/7] Python sanal ortamı (.venv) oluşturuluyor...${CLR_RESET}"
    if [ ! -d "$VENV_DIR" ]; then
        sudo -u "$TARGET_USER" python3 -m venv "$VENV_DIR"
    fi

    # 6. Bağımlılıkları Yükle
    echo -e "${CLR_YELLOW}[6/7] Python kütüphaneleri yükleniyor (FastAPI, PySerial, Pillow, NumPy)...${CLR_RESET}"
    sudo -u "$TARGET_USER" "$VENV_DIR/bin/pip" install --upgrade pip
    sudo -u "$TARGET_USER" "$VENV_DIR/bin/pip" install pyserial fastapi uvicorn websockets pillow numpy

    # 6. Systemd Servisini Yapılandır ve Başlat
    echo -e "${CLR_YELLOW}[6/6] Systemd otomatik başlatma servisi kuruluyor...${CLR_RESET}"
    
    # Servis dosyasını dinamik olarak kullanıcının ev dizinine uyarla
    sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=LaserRunner Studio OS (Klipper-Style Laser Host)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$TARGET_USER
Group=dialout
WorkingDirectory=$INSTALL_DIR
Environment=\"PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
ExecStart=$VENV_DIR/bin/python run.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"

    sudo systemctl daemon-reload
    sudo systemctl enable laserrunner
    sudo systemctl restart laserrunner

    echo -e "\n${CLR_GREEN}${CLR_BOLD}[✔] TEBRİKLER! LaserRunner başarıyla kuruldu ve başlatıldı!${CLR_RESET}"
    echo -e "Web tarayıcınızdan ${CLR_CYAN}http://$(get_local_ip):8080${CLR_RESET} adresine bağlanabilirsiniz.\n"
    read -p "Ana menüye dönmek için [Enter] tuşuna basın..."
}

# ==============================================================================
# 2. GÜNCELLEME İŞLEMİ (UPDATE)
# ==============================================================================
update_laserrunner() {
    echo -e "\n${CLR_CYAN}[+] LaserRunner Güncelleniyor...${CLR_RESET}\n"
    cd "$INSTALL_DIR"
    
    echo -e "${CLR_YELLOW}[1/3] Git güncellemeleri çekiliyor...${CLR_RESET}"
    sudo -u "$TARGET_USER" git pull || echo "Git güncellemesi atlandı."

    echo -e "${CLR_YELLOW}[2/3] Python bağımlılıkları güncelleniyor...${CLR_RESET}"
    sudo -u "$TARGET_USER" "$VENV_DIR/bin/pip" install --upgrade pyserial fastapi uvicorn websockets pillow numpy

    echo -e "${CLR_YELLOW}[3/3] Servis yeniden başlatılıyor...${CLR_RESET}"
    sudo systemctl restart laserrunner

    echo -e "\n${CLR_GREEN}[✔] Güncelleme tamamlandı ve servis yeniden başlatıldı!${CLR_RESET}\n"
    read -p "Ana menüye dönmek için [Enter] tuşuna basın..."
}

# ==============================================================================
# 3. FIRMWARE DERLEME & YÜKLEME (PLATFORMIO)
# ==============================================================================
build_firmware() {
    echo -e "\n${CLR_CYAN}[+] Octopus Pro (STM32F446) Firmware Derleyici${CLR_RESET}\n"

    # PlatformIO kontrolü
    if ! command -v pio &> /dev/null && [ ! -f "$TARGET_HOME/.platformio/penv/bin/pio" ]; then
        echo -e "${CLR_YELLOW}PlatformIO bulunamadı, yükleniyor (birkaç dakika sürebilir)...${CLR_RESET}"
        sudo -u "$TARGET_USER" curl -fsSL -o /tmp/get-platformio.py https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py
        sudo -u "$TARGET_USER" python3 /tmp/get-platformio.py
    fi

    local PIO_BIN="pio"
    if [ -f "$TARGET_HOME/.platformio/penv/bin/pio" ]; then
        PIO_BIN="$TARGET_HOME/.platformio/penv/bin/pio"
    fi

    echo -e "${CLR_YELLOW}Firmware derleniyor (BTT Octopus Pro F446)...${CLR_RESET}"
    cd "$INSTALL_DIR/firmware"
    sudo -u "$TARGET_USER" "$PIO_BIN" run -e octopus_pro_f446

    local BIN_SRC="$INSTALL_DIR/firmware/.pio/build/octopus_pro_f446/firmware.bin"
    if [ -f "$BIN_SRC" ]; then
        local BIN_DEST="$TARGET_HOME/firmware.bin"
        cp "$BIN_SRC" "$BIN_DEST"
        chown "$TARGET_USER:$TARGET_USER" "$BIN_DEST"
        echo -e "\n${CLR_GREEN}${CLR_BOLD}[✔] DERLEME BAŞARILI!${CLR_RESET}"
        echo -e "Derlenen dosya: ${CLR_CYAN}$BIN_DEST${CLR_RESET}"
        echo -e "\n${CLR_WHITE}Yükleme Seçenekleri:${CLR_RESET}"
        echo -e " 1) ${CLR_YELLOW}SD Kart ile Yükleme:${CLR_RESET} Bu 'firmware.bin' dosyasını FAT32 formatlı microSD karta atıp Octopus Pro'ya takın ve kartı yeniden başlatın."
        echo -e " 2) ${CLR_YELLOW}DFU ile Doğrudan Yükleme:${CLR_RESET} Kartı BOOT0 tuşuna basılı tutarak RPi'ye USB ile bağlayın ve alttaki seçenekten doğrudan yükleyin."
        echo ""
        read -p "Doğrudan DFU ile karta yüklemek istiyor musunuz? (e/H): " dfu_ans
        if [[ "$dfu_ans" =~ ^[eE]$ ]]; then
            sudo -u "$TARGET_USER" "$PIO_BIN" run -e octopus_pro_f446 --target upload
        fi
    else
        echo -e "${CLR_RED}[X] Derleme başarısız oldu!${CLR_RESET}"
    fi

    read -p "Ana menüye dönmek için [Enter] tuşuna basın..."
}

# ==============================================================================
# 4. SERVİS YÖNETİMİ
# ==============================================================================
manage_service() {
    while true; do
        print_banner
        echo -e "${CLR_BOLD}--- Servis Yönetimi ---${CLR_RESET}\n"
        echo -e " 1) Servisi Yeniden Başlat (Restart)"
        echo -e " 2) Servisi Durdur (Stop)"
        echo -e " 3) Servisi Başlat (Start)"
        echo -e " 4) Canlı Günlükleri İzle (journalctl -u laserrunner -f)"
        echo -e " B) Geri Dön"
        echo ""
        read -p "Seçiminiz: " s_choice
        case "$s_choice" in
            1) sudo systemctl restart laserrunner; echo "Yeniden başlatıldı."; sleep 1 ;;
            2) sudo systemctl stop laserrunner; echo "Durduruldu."; sleep 1 ;;
            3) sudo systemctl start laserrunner; echo "Başlatıldı."; sleep 1 ;;
            4) sudo journalctl -u laserrunner -f -n 50 ;;
            [bB]) break ;;
            *) echo "Geçersiz seçim!"; sleep 1 ;;
        esac
    done
}

# ==============================================================================
# 5. KALDIRMA İŞLEMİ (UNINSTALL)
# ==============================================================================
uninstall_laserrunner() {
    echo -e "\n${CLR_RED}[!] DİKKAT: LaserRunner servisi ve yapılandırmaları kaldırılacak.${CLR_RESET}"
    read -p "Devam etmek istediğinize emin misiniz? (e/H): " confirm
    if [[ "$confirm" =~ ^[eE]$ ]]; then
        sudo systemctl stop laserrunner || true
        sudo systemctl disable laserrunner || true
        sudo rm -f "$SERVICE_FILE"
        sudo rm -f "$RULES_FILE"
        sudo systemctl daemon-reload
        echo -e "${CLR_GREEN}[✔] LaserRunner servisi başarıyla kaldırıldı.${CLR_RESET}"
    fi
    read -p "Ana menüye dönmek için [Enter] tuşuna basın..."
}

# ==============================================================================
# ANA DÖNGÜ (MAIN MENU)
# ==============================================================================
main_menu() {
    while true; do
        print_banner
        print_status_box

        echo -e " ${CLR_WHITE}${CLR_BOLD}İşlemler:${CLR_RESET}"
        echo -e "   ${CLR_CYAN}[1]${CLR_RESET} LaserRunner Kur (Install)"
        echo -e "   ${CLR_CYAN}[2]${CLR_RESET} Güncelle (Update)"
        echo -e "   ${CLR_CYAN}[3]${CLR_RESET} Firmware Derle & Yükle (BTT Octopus Pro F446)"
        echo -e "   ${CLR_CYAN}[4]${CLR_RESET} Servis Kontrolü (Start / Stop / Restart)"
        echo -e "   ${CLR_CYAN}[5]${CLR_RESET} Canlı Günlük Kayıtları (Live Logs)"
        echo -e "   ${CLR_CYAN}[6]${CLR_RESET} LaserRunner Kaldır (Uninstall)"
        echo -e "   ${CLR_RED}[Q]${CLR_RESET} Çıkış (Quit)"
        echo ""
        read -p " Lütfen bir seçenek girin [1-6, Q]: " choice

        case "$choice" in
            1) install_laserrunner ;;
            2) update_laserrunner ;;
            3) build_firmware ;;
            4) manage_service ;;
            5) sudo journalctl -u laserrunner -f -n 50 ;;
            6) uninstall_laserrunner ;;
            [qQ]) 
                echo -e "\n${CLR_CYAN}LaserRunner Helper kapatıldı. İyi çalışmalar!${CLR_RESET}\n"
                exit 0
                ;;
            *)
                echo -e "${CLR_RED}Geçersiz seçenek!${CLR_RESET}"
                sleep 1
                ;;
        esac
    done
}

main_menu
