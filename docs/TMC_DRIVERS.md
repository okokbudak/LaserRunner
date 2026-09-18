# LaserRunner - TMC Sürücü Optimizasyon ve Yapılandırma Kılavuzu

Bu kılavuz; BigTreeTech Octopus Pro V1.0.1 kartı üzerinde **TMC2209**, **TMC5160**, **TMC2208** ve **TMC2226** step motor sürücülerinin UART/SPI üzerinden en yüksek hassasiyet, tork ve sıfır adım kaçırma garantisiyle nasıl yapılandırılacağını açıklar.

---

## 1. Lazer Kesim/Kazıma İçin En Kritik Ayar: StealthChop vs SpreadCycle

3D yazıcılarda motor sesini tamamen kesmek için **StealthChop** tercih edilir. Ancak **yüksek hızlı diyot lazer makinelerinde (100 - 300 mm/s hız ve 3000 - 5000 mm/s² ivmelerde) StealthChop kullanılmamalıdır!**

### Neden SpreadCycle?
* **Ani Yön Değişimleri:** Lazer tarama (raster engraving) yaparken kafa her satır sonunda anında yön değiştirir. StealthChop'un dinamik akım algoritması bu ani yön değişimlerinde gecikerek **adım kaçırmaya (layer shift / satır kayması)** neden olur.
* **Maksimum Tork:** `SpreadCycle`, motorun her adımda maksimum tork üretmesini sağlar.
* **Konfigürasyon Kuralı:** `laserrunner.cfg` dosyasında X ve Y eksenleri için:
  ```ini
  stealthchop_threshold: 0  ; 0 = Daima SpreadCycle (Lazer için altın kural)
  ```

---

## 2. Octopus Pro Kartı Üzerindeki Jumper Ayarları (TMC2209 UART Modu)

TMC sürücülerinin yazılımdan kontrol edilebilmesi için Octopus Pro yuvalarındaki jumper'ların doğru takılması şarttır:

```
          [ MOTOR YUVASI ]
   +------------------------------+
   |  [ ] [ ] [ ] [ ]             |  <-- Standart Microstep Jumperları (BOŞ BIRAKIN)
   |  [■]                          |  <-- UART Jumperı (SADECE SOLDAKİ 1 ÇİFTİ KÖPRÜLEYİN)
   +------------------------------+
```
* **TMC2209:** Sürücü yuvasının altındaki 4 jumper sırasından **sadece en soldaki çifti** (kırmızı jumper) takın. Diğerlerini boş bırakın.
* **TMC5160 Pro:** SPI modunda çalışır. Kartın SPI pinleri aktiftir.

---

## 3. Akım (Current) Hesaplama ve Optimizasyonu

LaserRunner, Klipper gibi doğrudan **RMS Amper** değerini kabul eder ve çip üzerindeki akım ölçekleme (`IRUN` / `IHOLD`) register'ını otomatik hesaplar.

### Standart NEMA 17 Motorlar İçin Önerilen Değerler:
* **X Ekseni (Hafif Kafa Taşıyıcı):**
  * `run_current: 0.800` (800 mA RMS)
  * `hold_current: 0.400` (Beklemede motorun ısınmasını engeller)
* **Y Ekseni (Ağır Köprü / Gantry):**
  * Tek Motorlu Sistem: `run_current: 1.000` (1000 mA)
  * Çift Motorlu Dual-Y: Motor başına `run_current: 0.850 - 0.900`
* **Z Ekseni (Varsa):**
  * `run_current: 0.600`

> [!TIP]
> **Motor Sıcaklığı Kuralı:** Lazer çalışırken motor gövdelerine elinizi dokundurduğunuzda elinizi 5 saniye rahatça tutabiliyorsanız (sıcaklık < 55°C) akım ayarınız mükemmeldir. Eğer motorlar çok ısınıyorsa akımı 0.050A (50mA) düşürün.

---

## 4. Sensörsüz Homing (Sensorless Homing - StallGuard)

TMC2209 sürücüler, motorda mekanik bir dirençle (şasenin sonuna çarpma) karşılaştığında geri indüklenen voltajı (Back-EMF) ölçerek mekanik limit switch'e ihtiyaç duymadan sıfırlama yapabilir.

### Octopus Pro'da Sensörsüz Homing'i Aktif Etme:
1. Sürücü yuvasının hemen yanında bulunan **DIAG Jumper'ını** takın (Bu jumper sürücünün `DIAG` bacağını STM32'nin `PG6` / `PG9` pinlerine bağlar).
2. `laserrunner.cfg` dosyasında eşik değerini tanımlayın:
   ```ini
   [tmc2209 stepper_x]
   diag_pin: PG6
   driver_SGTHRS: 65   ; Hassasiyet eşiği (0 - 255)
   ```

### SGTHRS Kalibrasyonu:
* Değer **255** en hassastır (en ufak sürtünmede çarpmış gibi durur).
* Değer **0** en duyarsızdır (şaseye sert çarpsa bile durmayabilir).
* **Başlangıç Değeri:** `60 - 75` arası idealdir.
  * Eğer eksen sona ulaşmadan yolda duruyorsa değeri **düşürün** (örn: 55).
  * Eğer sona ulaştığı halde çarpmayı algılamayıp motor zırıldıyorsa değeri **artırın** (örn: 75).

---

## 5. Mikro-Adım (Microstepping) ve Enterpolasyon

* Lazer makinelerinde yüksek hızlarda (200 - 300 mm/s) MCU'nun adım frekansı sınırına takılmaması için fiziksel adım:
  ```ini
  microsteps: 16
  interpolate: True
  ```
* `interpolate: True` ayarı, TMC sürücünün donanımsal 256 adım enterpolatörünü devreye sokar. Böylece STM32'ye fazladan darbe hesaplama yükü bindirmeden motorlar 256 mikro-adım pürüzsüzlüğünde ve sessizliğinde döner.
