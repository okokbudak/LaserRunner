# LaserRunner Yapılandırma Referans Kılavuzu (laserrunner.cfg)

Bu doküman, Klipper felsefesinde tasarlanmış `config/laserrunner.cfg` dosyasındaki tüm parametreleri, birimlerini ve kullanım amaçlarını tanımlar.

---

## 1. `[machine]` Bölümü (Makine & Kinematik)

* **`kinematics`:** Makinenin mekanik yapısını belirler.
  * `cartesian`: Klasik Kartezyen ve Bağımsız Çift Y (Dual-Y).
  * `corexy`: Standart CoreXY veya H-Bot.
  * `awd_corexy`: 4 motorlu All-Wheel Drive CoreXY.
* **`max_velocity`:** Makinenin erişebileceği maksimum doğrusal hız (mm/s cinsinden). Lazer gravür makineleri için tipik değer: `200 - 400`.
* **`max_acceleration`:** Maksimum ivme ($mm/s^2$ cinsinden). Hafif kafa yapısına sahip makinelerde `3000 - 6000` arası ayarlanabilir.
* **`corner_velocity`:** Köşelerden geçerken izin verilen minimum geçiş hızı (mm/s).

---

## 2. `[laser]` Bölümü (Diyot Lazer & PWM)

* **`pwm_pin`:** Lazerin TTL/PWM girişine bağlanan donanımsal zamanlayıcı pini (Octopus Pro için: `PB0`).
* **`frequency`:** Donanımsal PWM frekansı (Hz cinsinden). Diyot lazerler için önerilen değer: `5000` (5 kHz).
* **`max_power_raw`:** Donanımın PWM çözünürlüğü. 12-bit STM32 zamanlayıcısı için `4095`'tir.
* **`dynamic_power`:** `true` olduğunda lazer gücü hareket hızına göre dinamik olarak ölçeklenir ($P(v)$). İvmelenme ve yavaşlama rampalarında aşırı yanmayı engeller.
* **`min_power_ratio`:** Lazer diyotunun ateşleme eşiğini korumak için minimum güç tabanı (örn: `0.05` = %5).

---

## 3. `[stepper_<axis>]` ve `[tmc2209 stepper_<axis>]` Bölümleri

Her eksen için motor pinleri ve TMC sürücü register ayarları:

```ini
[stepper_x]
step_pin: PF13          ; Adım pini
dir_pin: PF12           ; Yön pini
enable_pin: PF14        ; Sürücü aktif/pasif pini
steps_per_mm: 80.0      ; 1 mm ilerleme için gereken adım sayısı (GT2 kayış + 20T kasnak için 80)
homing_speed: 40.0      ; Sıfırlama hızı (mm/s)
endstop_pin: PG6        ; Limit switch veya sensörsüz homing pini

[tmc2209 stepper_x]
uart_pin: PC4           ; Tek hatlı yazılımsal UART pini
run_current: 0.800      ; Çalışma akımı (Amper RMS)
hold_current: 0.400     ; Motor dururken çekilen akım
microsteps: 16          ; Fiziksel mikro-adım
interpolate: True       ; Donanımsal 256 microstep enterpolasyonu
stealthchop_threshold: 0 ; 0 = SpreadCycle (Lazer için kesinlikle 0 önerilir)
diag_pin: PG6           ; Sensörsüz homing tetik pini
driver_SGTHRS: 65       ; StallGuard hassasiyeti (0-255)
sense_resistor: 0.110   ; Ölçüm direnci (TMC2209 için 0.110 ohm)
```

---

## 4. `[air_assist]` (Hava Motoru / Solenoid Valf)

* **`pin`:** Hava motorunu veya röleyi süren MOSFET pini (`PA8` - FAN0).
* **`auto_enable`:** `true` olduğunda kesim başladığında hava otomatik açılır, iş bitince kapanır.
* **`pre_delay`:** Lazer ateşlenmeden önce havanın basınç kazanması için beklenecek süre (saniye).
* **`post_delay`:** Lazer söndükten sonra kalan dumanı temizlemek için üflemeye devam edilecek süre.

---

## 5. `[exhaust_fan]` (Duman Tahliye Fanı)

* **`pin`:** Fan MOSFET çıkış pini (`PE5` - FAN1).
* **`default_speed`:** `0.0 - 1.0` arası varsayılan çalışma hızı (`1.0` = %100 PWM).
* **`off_delay`:** Kesim tamamlandıktan sonra kabindeki artık dumanı dışarı atmak için fanın çalışmaya devam edeceği süre (saniye).

---

## 6. `[safety]` (Güvenlik ve Koruma)

* **`lid_switch_pin`:** Kabin kapağı switch pini (`PG11`). Kapak açıldığında lazer derhal kapatılır.
* **`flame_sensor_pin`:** Optik yangın dedektörü pini (`PC2`). Alev algılandığında sistem acil durdurmaya geçer.
* **`max_diode_temp`:** Lazer başlığı için maksimum izin verilen sıcaklık (°C). Bu sıcaklık aşılırsa lazer korumaya alınır.
