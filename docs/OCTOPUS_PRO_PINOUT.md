# BTT Octopus Pro V1.0.1 (STM32F446ZET6) Pin Haritası

Bu doküman, LaserRunner Firmware'i için BigTreeTech Octopus Pro V1.0.1 kartının pin atamalarını tanımlar.

---

## 1. Lazer ve Güvenlik Pinleri

| Fonksiyon | Pin Adı | STM32 Pini | Donanım Özelliği | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| **Lazer PWM (Sinyal)** | **PROBE / SERVO** | **`PB0`** | **TIM3_CH3 (Donanımsal PWM)** | 3.3V TTL Lojik Sinyal (0 - 100% duty cycle, 1 - 20 kHz) |
| **Lazer Besleme (VCC)** | PSU Harici Klemens | - | 12V / 24V DC | Güç kaynağından doğrudan (ortak GND ile) |
| **Lazer Şase (GND)** | Kart Şasesi | GND | Ortak Şase | PSU ve Kart GND ortaklanmalıdır |
| **Acil Durdurma Butonu** | PWR_DET / ESTOP | `PC0` | Dahili Pull-up, Kesme (EXTI) | Basıldığında anında PWM sıfırlanır |

---

## 2. Step Motor Sürücü Pinleri (Motor 1 - Motor 4)

LaserRunner varsayılan olarak şu motor slotlarını kullanır:
* **Motor 1 (Eksen X):**
  * STEP: `PF13`
  * DIR: `PF12`
  * ENABLE: `PF14`
  * UART / CS: `PC4`
* **Motor 2 (Eksen Y1 - Birincil Y):**
  * STEP: `PG0`
  * DIR: `PG1`
  * ENABLE: `PF15`
  * UART / CS: `PD11`
* **Motor 3 (Eksen Y2 - İkincil Y / Çift Y veya Z ekseni):**
  * STEP: `PF11`
  * DIR: `PG3`
  * ENABLE: `PG5`
  * UART / CS: `PC6`
* **Motor 4 (Eksen Z veya AWD CoreXY İkincil Motorlar):**
  * STEP: `PG4`
  * DIR: `PC1`
  * ENABLE: `PA0`
  * UART / CS: `PC7`

---

## 3. Limit Anahtarları (Endstops)

| Eksen | Pin Etiketi | STM32 Pini | Mod |
| :--- | :--- | :--- | :--- |
| **X Min** | DIAG0 / STOP0 | `PG6` | Giriş (Pull-up / Sensörsüz homing için) |
| **Y1 Min** | DIAG1 / STOP1 | `PG9` | Giriş (Pull-up / Sensörsüz homing için) |
| **Y2 Min** | DIAG2 / STOP2 | `PG10` | Bağımsız Auto-Squaring Hizalama Girişi |
| **Z Min** | DIAG3 / STOP3 | `PG11` | Z Eksen Probu / Limit |

---

## 4. İletişim Portu (Raspberry Pi Bağlantısı)

* **Yerel USB Portu (USB-C Girişi):**
  * PA11: `USB_DM`
  * PA12: `USB_DP`
  * Raspberry Pi 4B'nin herhangi bir USB 3.0 veya USB 2.0 portuna doğrudan USB kablosuyla bağlanır.
  * Kart `Virtual COM Port` (CDC-ACM) olarak tanınır (12 Mbps Full Speed).
