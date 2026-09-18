# BTT Octopus Pro V1.0.1 (STM32F446ZET6) Kapsamlı Donanım ve Eklenti (Addon) Pin Haritası

Bu doküman, LaserRunner Firmware'i için BigTreeTech Octopus Pro V1.0.1 kartının tüm motor, lazer, fan, hava motoru, sensör ve güvenlik eklentilerinin pin atamalarını tanımlar.

---

## 1. Lazer Modülleri ve Kılavuz İşaretleyiciler

| Fonksiyon | Pin Adı | STM32 Pini | Donanım Özelliği | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| **Ana Lazer PWM (Sinyal)** | **PROBE / SERVO** | **`PB0`** | **TIM3_CH3 (Donanımsal PWM)** | 3.3V / 5V TTL Lojik Sinyal (0 - 100% duty, 1 - 20 kHz) |
| **Kılavuz Lazer / Kırmızı Nokta (Red Dot / Crosshair)** | **RGB / NEOPIXEL** | **`PB10`** | 3.3V Lojik PWM / Dijital | 3.3V Kılavuz işaretleyici / Çerçeveleme lazeri |
| **İkinci Lazer PWM (Çift Kafa / Fiber / UV)** | **EXP1_PIN7** | **`PE8`** | Donanımsal PWM | Opsiyonel 2. Lazer kafası TTL girişi |
| **Lazer Besleme (VCC)** | Harici Klemens | - | 12V / 24V DC | Güç kaynağından doğrudan (Ortak GND ile) |

---

## 2. Hava Motoru, Duman Tahliyesi ve MOSFET Çıkışları

Octopus Pro üzerinde voltajı jumper ile 5V / 12V / 24V seçilebilen 6 adet kontrollü fan çıkışı ve yüksek güçlü MOSFET'ler bulunur:

| Fonksiyon | Kart Etiketi | STM32 Pini | Çıkış Tipi | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| **Air Assist (Hava Pompası / Solenoid Valf)** | **FAN0** | **`PA8`** | Kontrollü MOSFET | `M7`/`M8` ile açılır, `M9` ile kapanır (Kesim sırasında üfleme) |
| **Duman Tahliye Emiş Fanı (Exhaust Fan)** | **FAN1** | **`PE5`** | Kontrollü MOSFET | İş başlangıcında açılır, iş bitiminden 30s sonra otomatik kapanır |
| **Lazer Kafa Soğutma Fanı** | **FAN2** | **`PD12`** | Kontrollü PWM | Lazer diyot gövdesini soğutan fan |
| **Elektronik Kutu Fanı** | **FAN3** | **`PD13`** | Kontrollü PWM | Octopus Pro ve step sürücüleri soğutan fan |
| **Yüksek Güçlü Hava Kompresör Rölesi** | **HE1 / BED_OUT** | **`PA3` / `PA1`** | Yüksek Akım MOSFET | 12V/24V büyük kompresör veya harici AC röle tetikleme |

---

## 3. Step Motor Sürücüleri (TMC2209 / TMC5160 UART / SPI)

Octopus Pro üzerindeki 8 adet sürücü yuvası:

| Eksen / Slot | STEP | DIR | ENABLE | UART / CS Pini | Sensörsüz Homing (DIAG) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Motor 1: X Ekseni** | `PF13` | `PF12` | `PF14` | `PC4` | `PG6` (DIAG0) |
| **Motor 2: Y1 Ekseni (Sol Motor)** | `PG0` | `PG1` | `PF15` | `PD11` | `PG9` (DIAG1) |
| **Motor 3: Y2 Ekseni (Sağ Motor - Auto Squaring)** | `PF11` | `PG3` | `PG5` | `PC6` | `PG10` (DIAG2) |
| **Motor 4: Z Ekseni (Yatak Yüksekliği / Odak)** | `PG4` | `PC1` | `PA0` | `PC7` | `PG11` (DIAG3) |
| **Motor 5: Rotary Ekseni (Döner Rulo / Bardak Aparatı)** | `PF9` | `PF10` | `PG2` | `PF2` | `PG12` (DIAG4) |
| **Motor 6: AWD CoreXY İkincil A Motoru** | `PC13` | `PF0` | `PF1` | `PE4` | `PG13` (DIAG5) |
| **Motor 7: AWD CoreXY İkincil B Motoru** | `PE2` | `PE3` | `PD4` | `PE1` | `PG14` (DIAG6) |

---

## 4. Güvenlik, Sensörler ve Koruma Girişleri

| Sensör / Fonksiyon | Kart Etiketi | STM32 Pini | Mod | Güvenlik Davranışı |
| :--- | :--- | :--- | :--- | :--- |
| **Kapak Güvenlik Anahtarı (Lid Safety Interlock)** | **STOP_Z+ / DIAG3** | **`PG11`** | Input (Pull-up) | Kapak açıldığında **Lazer anında kapanır**, hareket duraklar! |
| **Alev / Yangın Sensörü (Flame Detector)** | **PWR_DET** | **`PC0`** | Input (Pull-up) | Alev algılandığında **ACİL DURDURMA** tetiklenir, alarm çalar! |
| **Lazer Kafa Sıcaklık Sensörü (NTC100K)** | **TB / T0** | **`PF3`** | Analog ADC (ADC3_IN9) | Lazer sıcaklığı > 50°C olursa güç kısılır / durdurulur |
| **Su Akış Sensörü (Water Flow / Chiller OK)** | **DIAG7 / STOP7** | **`PG15`** | Input (Pull-up) | Su soğutmalı lazerlerde akış kesilirse lazer durdurulur |
