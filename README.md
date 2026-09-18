# 🚀 LaserRunner Studio OS

> **Klipper Mantığında Dağıtık CNC & Diyot Lazer Kontrol Sistemi ve Dahili LightBurn Tarzı Web Stüdyosu**

LaserRunner; Raspberry Pi 4B (Host) üzerinde çalışan yüksek yetenekli bir Lazer CAM ve hareket planlayıcı ile BigTreeTech Octopus Pro (STM32F446ZET6) üzerinde çalışan mikrosaniye hassasiyetli bir donanım darbe üretecini (Firmware) birleştiren açık kaynaklı bir lazer işletim sistemidir.

---

## 🌟 Öne Çıkan Özellikler

1. **Klipper Benzeri Dağıtık Mimari:**
   - **Host (Raspberry Pi 4B):** Tüm G-code ayrıştırma, look-ahead yörünge/ivme planlama, dinamik lazer gücü senkronizasyonu ($P(v)$), CAM/vektör/raster dönüşümleri ve Web arayüzü Linux üzerinde çalışır.
   - **Firmware (BTT Octopus Pro):** Donanıma en yakın seviyede, 32-bit STM32 Timer'ları (`TIM2`/`TIM5`) ile titreşimsiz (jitter-free) step üretir; `PB0` pininde donanımsal 5 kHz PWM ile lazeri sürer.
2. **12 Mbps Yerel USB-CDC İletişimi:**
   - Standart CH340 seri çiplerinin yarattığı darboğaz ve tampon gecikmeleri tamamen ortadan kaldırılmıştır.
3. **Tüm Mekanik Kinematik Desteği:**
   - Kartezyen & Bağımsız Çift Y (Dual-Y Auto-Squaring)
   - CoreXY & H-Bot
   - AWD CoreXY (All-Wheel Drive / 4 Motorlu CoreXY)
4. **Dinamik Lazer Güç Senkronizasyonu ($P(v)$):**
   - İvmelenme ve yavaşlama anlarında veya dar köşelerde güç hıza oranlanarak düşürülür; malzemede yanık noktaları oluşmaz.
5. **Dahili LightBurn Tarzı Web Stüdyosu:**
   - Vektör kesim (Line) ve çizim (Fill) katmanları.
   - Fotoğraf / Raster gravür motoru (Floyd-Steinberg ve Atkinson hata yayılımlı dithering).
   - İş parçasını hizalamak için düşük güçlü Çerçeveleme (Framing).
   - Canlı lazer kafası takibi, D-Pad Jog kontrolleri ve acil durdurma.

---

## 🔌 Donanım ve Kablolama (BTT Octopus Pro V1.0.1)

| Lazer Pini | Octopus Pro Soketi | STM32 Pini | Açıklama |
| :--- | :--- | :--- | :--- |
| **PWM / TTL** | **PROBE / SERVO** | **`PB0`** | 3.3V / 5V TTL Temiz Lojik Donanımsal PWM |
| **GND (Şase)**| Kart Şasesi | **GND** | Güç kaynağı ve Octopus GND ortaklanmalıdır |
| **VCC (+12V/24V)**| Harici Güç Kaynağı | - | Lazer gücü doğrudan PSU'dan beslenmelidir |

*Motor Yuvaları:*
- Motor 1: X Ekseni (`PF13` Step, `PF12` Dir, `PF14` En)
- Motor 2: Y1 Ekseni (`PG0` Step, `PG1` Dir, `PF15` En)
- Motor 3: Y2 / Dual-Y (`PF11` Step, `PG3` Dir, `PG5` En)
- Motor 4: Z Ekseni (`PG4` Step, `PC1` Dir, `PA0` En)

---

## 🛠️ Raspberry Pi Kurulumu (KIAUH Tarzı TUI Yükleyici)

Sıfır bir Raspberry Pi 4B'ye SSH ile bağlandıktan sonra sistemi tek bir interaktif komutla kurabilir, güncelleyebilir ve Octopus Pro firmware'ini derleyebilirsiniz:

```bash
# 1. Depoyu klonlayın
git clone https://github.com/Kokbudak/LaserRunner.git
cd LaserRunner

# 2. Kurulum ve Yönetim Yardımcısını (LIAUH) çalıştırın
chmod +x laserrunner-installer.sh
./laserrunner-installer.sh
```

### 🖥️ LIAUH Arayüzü Neler Yapar?
* **[1] LaserRunner Kur:** İşletim sistemi paketlerini (Python, udev, derleyiciler) yükler, sanal ortamı (.venv) kurar, USB izinlerini yapılandırır ve otomatik başlayan `systemd` servisini aktif eder.
* **[2] Güncelle:** Depodan son değişiklikleri çeker, paketleri günceller ve servisi yeniden başlatır.
* **[3] Firmware Derle & Yükle:** Octopus Pro (STM32F446) için PlatformIO ile firmware derler; SD karta atılacak `firmware.bin` dosyasını hazırlar veya doğrudan DFU üzerinden yükler.
* **[4] Servis Kontrolü:** Servisi başlatma, durdurma ve durumunu inceleme.
* **[5] Canlı Günlük Kayıtları:** Sistem loglarını anlık olarak terminalden izleme (`journalctl`).

### 2. Firmware Derleme ve Yükleme (STM32F446)

PlatformIO kurulu bir bilgisayarda:
```bash
cd firmware
pio run -e octopus_pro_f446 --target upload
```
*Veya derlenen `firmware.bin` dosyasını bir microSD karta atıp Octopus Pro'ya takarak açılışta otomatik güncelleyebilirsiniz.*

---

## 🧪 Testlerin Çalıştırılması

Tüm kinematik, protokol, hız planlayıcı ve dinamik lazer güç algoritmalarını test etmek için:
```bash
python -m unittest discover -s tests
```
