# LaserRunner - Klipper Uyumluluk, Makrolar ve Rezonans Telafi Kılavuzu

LaserRunner, 3D yazıcı dünyasının altın standardı olan Klipper mimarisini ve komut setini yüksek hızlı lazer kazıma ve kesim sistemlerine uyarlar.

---

## 1. Rotation Distance (Adım/mm Yerine Modern Klipper Standardı)

Klasik `steps_per_mm` yerine Klipper'ın fiziksel mekaniğe dayalı `rotation_distance` standardı kullanılır:

$$\text{steps\_per\_mm} = \frac{\text{full\_steps\_per\_rotation} \times \text{microsteps}}{\text{rotation\_distance}}$$

### Standart Hesaplamalar:
* **GT2 Kayış & 20 Dişli Kasnak (X ve Y Eksenleri):**
  * Diş hatvesi (pitch): 2mm
  * Diş sayısı: 20
  * $\text{rotation\_distance} = 20 \times 2\text{mm} = 40$
  * 1.8° step motor (200 adım) ve 16 mikro-adım ile:
    $$\frac{200 \times 16}{40} = 80.0\text{ adım/mm}$$
* **0.9° Yüksek Hassasiyetli Motor:**
  * `full_steps_per_rotation: 400`
  * $\text{rotation\_distance: 40}$
  * Adım/mm: $\frac{400 \times 16}{40} = 160.0\text{ adım/mm}$
* **T8 Vidalı Mil (Z Ekseni):**
  * Hatve (Lead): 8mm $\rightarrow$ `rotation_distance: 8`
  * Adım/mm: $\frac{200 \times 16}{8} = 400.0\text{ adım/mm}$

---

## 2. Rezonans Telafi / Titreşim Önleme ([input_shaper])

Yüksek hızlarda (300 - 600 mm/s) ve sert ivmelerde (3000 - 10000 mm/s²) CoreXY lazer kafası keskin köşelerde ve yön değişimlerinde ataletten ötürü titreşir (ghosting/ringing). LaserRunner, donanım adımlarını frekans süzgecinden geçirerek titreşimi yok eder.

### Desteklenen Filtre Tipleri:
* **ZV (Zero Vibration):** En düşük gecikme süresi, dar bant sönümleme.
* **ZVD (Zero Vibration and Derivative):** 3-darbeli filtre, frekans değişimlerine karşı daha dayanıklı.
* **MZV (Modified Zero Vibration - Önerilen):** Minimum aşım ve mükemmel köşe netliği.
* **EI (Extra Insensitive):** Şasede yük değişimleri varsa geniş tolerans bandı.
* **2HUMP_EI:** Çift tepe noktalı geniş rezonans sönümleyici.

### Konfigürasyon:
```ini
[input_shaper]
enabled: True
shaper_type_x: mzv
shaper_freq_x: 54.2            ; X ekseni rezonans frekansı (Hz)
damping_ratio_x: 0.1
shaper_type_y: mzv
shaper_freq_y: 48.6            ; Y ekseni rezonans frekansı (Hz)
damping_ratio_y: 0.1
```

---

## 3. G-Code Makro Desteği ([gcode_macro])

`laserrunner.cfg` içinde Klipper Jinja2 sözdizimiyle özel makrolar tanımlayabilir, parametre gönderebilirsiniz:

```ini
[gcode_macro START_CUT]
description: Kesim öncesi hazırlık
gcode:
    M7                         ; Hava yardımını aç
    M106 S255                  ; Duman fanını tam hızda çalıştır
    G4 P500                    ; 500ms hava basıncının oturmasını bekle
    M3 S{params.POWER|default(1000)}

[gcode_macro CLEAN_LENS]
description: Lazer merceğini temizlemek için kafayı öne getir
gcode:
    G0 X200 Y50 F3000
```

### Parametre İkamesi:
* `{params.DEGISKEN}`: Gönderilen parametreyi alır.
* `{params.DEGISKEN|default(DEGER)}`: Parametre verilmemişse varsayılan değeri kullanır.

---

## 4. Özel Homing Sıralaması ([homing_override])

`G28` veya arayüzden "Home All" dendiğinde sıfırlama sırasını özelleştirmenizi sağlar:

```ini
[homing_override]
axes: xyz
gcode:
    SET_AIR_ASSIST ACTIVE=0
    G28 Y                      ; Önce Dual-Y Auto-Squaring ile köprüyü dikleştir
    G28 X                      ; Ardından X eksenini sıfırla
```

---

## 5. Donanım Doğrulama ve Tanılama Komutları (Verifications)

Klipper tarzı hata ayıklama ve ilk çalıştırma testleri:

| Komut / API | Açıklama |
| :--- | :--- |
| **`QUERY_ENDSTOPS`** | X, Y1, Y2, Z limit switch'leri, kabin kapağı, alev dedektörü ve acil durdurma butonunun anlık tetiklenme durumunu gösterir. |
| **`STEPPER_BUZZ STEPPER=x`** | Motor yönünü ve kablo sırasını doğrulamak için motoru 1mm ileri ve 1mm geri 3 kez hareket ettirir. |
| **`DUMP_TMC STEPPER=x`** | TMC sürücünün UART iletişimini, modunu (SpreadCycle/StealthChop), akımını ve StallGuard değerini raporlar. |
| **`ENABLE_STEPPERS` / `M17`** | Motorlara tutma akımı vererek kilitlenmeyi doğrular. `M84` ile serbest bırakır. |
