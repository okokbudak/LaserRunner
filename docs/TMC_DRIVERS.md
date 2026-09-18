# LaserRunner - TMC Sürücü Optimizasyon ve Yapılandırma Kılavuzu

Bu kılavuz; BigTreeTech Octopus Pro V1.0.1 kartı üzerinde **TMC2209**, **TMC5160**, **TMC2208** ve **TMC2226** step motor sürücülerinin UART/SPI üzerinden en yüksek hassasiyet, tork ve sıfır adım kaçırma garantisiyle nasıl yapılandırılacağını açıklar.

---

## 1. TMC Çalışma Modları: StealthChop vs SpreadCycle vs Hybrid

LaserRunner, Klipper tarzı modüler yapılandırma ile her motor için 3 farklı Trinamic çalışma modunu destekler:

| Mod | `mode` Ayarı | `stealthchop_threshold` | Ses Seviyesi | Dinamik Tork | Önerilen Eksen |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SpreadCycle** | `mode: spreadcycle` | `0` | Duyulabilir (kıyıcı sesi) | **Maksimum** (Sıfır satır kayması) | **X, Y, Y1 (Lazer Kazıma/Kesim)** |
| **StealthChop** | `mode: stealthchop` | `999999` | **Fısıltı Sessizliğinde** | Düşük/Orta (ani ivmelerde gecikmeli) | **Z (Odaklama/Yatak Tablası)** |
| **Dinamik Hybrid** | `mode: hybrid` | `örn: 60` (mm/s) | Gezinmede sessiz, hızda torklu | Hıza bağlı otomatik geçiş | Jog / Gezinme / Hafif CNC |

### Neden X ve Y Eksenlerinde Daima SpreadCycle?
* **Ani Yön Değişimleri (Raster Engraving):** Lazer kazıma yaparken kafa 200 - 400 mm/s hızla satır sonuna gelir ve 3000 - 10000 mm/s² ivmeyle anında zıt yöne döner. StealthChop'un PWM gerilim döngüsü bu ani yön değişimlerinde bobin akımını yeterince hızlı ayarlayamaz ve **adım kaçırma (layer shift / satır kayması)** meydana gelir.
* **Maksimum Tork:** `SpreadCycle`, sabit off-time akım kıyıcı mimarisi sayesinde her adım darbesinde motor bobinlerine anında tam manyetik alan uygular.
* **StallGuard Zorunluluğu:** TMC2209'un sensörsüz homing (Back-EMF algılama) donanımı olan StallGuard4 **sadece SpreadCycle modunda** çalışabilir.

### `laserrunner.cfg` Örnek Konfigürasyonu:
```ini
# X Ekseni: Lazer kesim torku için SpreadCycle
[tmc2209 stepper_x]
uart_pin: PC4
mode: spreadcycle              ; spreadcycle | stealthchop | hybrid
run_current: 0.800             ; RMS Akım (0.8A)
hold_current: 0.400            ; Bekleme Akımı (0.4A)
microsteps: 16
interpolate: True              ; Donanımsal 256 mikro-adım enterpolasyonu
stealthchop_threshold: 0       ; 0 = SpreadCycle
diag_pin: PG6
driver_SGTHRS: 65              ; Sensörsüz homing hassasiyeti

# Z Ekseni: Yatak tablasında sessizlik için StealthChop
[tmc2209 stepper_z]
uart_pin: PC7
mode: stealthchop              ; Fısıltı sessizliğinde
run_current: 0.600
hold_current: 0.300
microsteps: 16
interpolate: True
stealthchop_threshold: 999999
```

### Firmware ve Register Seviyesinde Çalışma Mantığı:
1. **GCONF (Register 0x00):**
   - Bit 2 (`en_SpreadCycle`): `1` olduğunda SpreadCycle aktif edilir, `0` olduğunda StealthChop PWM aktif olur.
   - Bit 7 (`mstep_reg_select`): Daima `1` yapılır, böylece mikro-adım oranları CHOPCONF register'ından okunur.
2. **TPWMTHRS (Register 0x13):**
   - Hibrit modda belirlenen hız eşiği (`stealthchop_threshold_speed`) adım frekansına dönüştürülür:
     $$TPWMTHRS = \frac{f_{clk}}{v \cdot \text{steps\_per\_mm}} = \frac{12\,000\,000}{\text{hız} \cdot 80}$$
   - Motor hızı eşiğin altındayken StealthChop devrededir; hızı aşınca sürücü otomatik olarak sıfır gecikmeyle SpreadCycle torkuna geçer.
3. **Sensörsüz Homing Güvenliği:**
   - Eğer kullanıcı X veya Y için `mode: stealthchop` veya `mode: hybrid` seçmiş olsa bile, LaserRunner firmware'i homing başladığı anda geçici olarak motoru `SpreadCycle` moduna alır, StallGuard homing'ini tamamlar, 5mm geri çekilir (retract) ve kullanıcının orijinal modunu geri yükler!

---

## 2. Octopus Pro Kartı Üzerindeki Jumper Ayarları (TMC2209 UART Modu)

TMC sürücülerinin yazılımdan kontrol edilebilmesi için Octopus Pro yuvalarındaki jumper'ların doğru takılması şarttır:

```
          [ MOTOR YUVASI ]
   +------------------------------+
   |  [ ] [ ] [ ] [ ]             |  <-- Standart Microstep Jumperları (BOŞ BIRAKIN)
   |  [■]                         |  <-- UART Jumperı (SADECE SOLDAKİ 1 ÇİFTİ KÖPRÜLEYİN)
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
