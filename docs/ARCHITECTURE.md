# LaserRunner Mimari ve Sistem Tasarımı

## 1. Dağıtık Sistem Mimarisi (Klipper Felsefesi)

LaserRunner iki ana katmandan oluşur:
1. **Host (Raspberry Pi 4B - Linux):** Ağır matematiksel hesaplamaları, G-code ayrıştırmayı, yörünge/ivme planlamasını (look-ahead planner), dinamik lazer güç eğrilerini ($P(v)$), CAM/vektör/raster işlemlerini ve Web arayüzünü yönetir.
2. **Firmware (BTT Octopus Pro - STM32F446ZET6):** Donanıma en yakın katmandır. Host'tan gelen zaman damgalı adım ve lazer bloklarını mikrosaniye hassasiyetli donanım zamanlayıcılarıyla (Hardware Timers) titreşimsiz (jitter-free) olarak darbelere dönüştürür.

```
 +-------------------------------------------------------------------------+
 |                          RASPBERRY PI 4B (HOST)                         |
 |                                                                         |
 |  [ Web Studio UI ] <---> [ FastAPI / WebSocket ]                        |
 |                                  ▲                                      |
 |                                  ▼                                      |
 |  [ CAM Motoru ] (SVG / DXF / Raster Dithering / Framing)                |
 |                                  ▲                                      |
 |                                  ▼                                      |
 |  [ Kinematik Motoru ] (Kartezyen, Dual-Y, CoreXY, AWD CoreXY)          |
 |                                  ▲                                      |
 |                                  ▼                                      |
 |  [ Yörünge & Hız Planlayıcı ] (Look-Ahead, Trapezoidal Profil, P(v))   |
 |                                  ▲                                      |
 |                                  ▼                                      |
 |  [ Adım Sıkıştırıcı & Zamanlayıcı ] (Microsecond Step Generator)        |
 |                                  ▲                                      |
 |                                  ▼                                      |
 |  [ USB-CDC Protokol Yöneticisi ] (High-Speed Binary Protocol, CRC16)    |
 +-------------------------------------------------------------------------+
                                    │
                       (Yerel USB-FS CDC, 12 Mbps)
                                    ▼
 +-------------------------------------------------------------------------+
 |                   BTT OCTOPUS PRO (STM32F446 FIRMWARE)                  |
 |                                                                         |
 |  [ USB-CDC Endpoint & Ring Buffer ]                                     |
 |  [ Paket Doğrulayıcı & Komut Kuyruğu ]                                  |
 |  [ 32-bit Donanım Timer (TIM2 / TIM5) Step Kesmesi ]                    |
 |  [ 16-bit Donanım Timer (TIM3) Lazer PWM (PB0 Çıkışı) ]                 |
 |  [ Donanımsal Watchdog & Acil Durdurma (Deadman's Switch) ]              |
 +-------------------------------------------------------------------------+
```

---

## 2. Zamanlama ve Gerçek Zamanlılık (Real-time Determinism)

Geleneksel GRBL/FluidNC gibi sistemlerde mikrodenetleyici hem G-code parse eder, hem ivme hesabı yapar, hem de motor sürer. Bu durum özellikle yüksek hızlı gravürde (raster engraving) veya çok kısa çizgilerden oluşan vektör kesimlerinde işlemcinin tıkanmasına (*planner starvation*) ve lazerin duraksayarak malzemeyi yakmasına neden olur.

LaserRunner'da:
* Host, tüm ivme ve adım zamanlamalarını önceden mikrosaniye hassasiyetinde hesaplar.
* STM32'ye **"Blok: 5000 adım, ilk adım aralığı 200µs, ivmelenme ile son aralık 80µs, Lazer Gücü %65"** şeklinde sıkıştırılmış komut paketleri gönderilir.
* STM32 bu paketleri bir döngüsel tamponda (Ring Buffer) tutar ve sadece donanım kesmesiyle (ISR) pinleri açıp kapatır.
* Sonuç: **Sıfır işlemci darboğazı, mikrosaniyelik darbe hassasiyeti ve sıfır yanık izi.**

---

## 3. Güvenlik ve Lazer Emniyet Sistemi (Deadman's Switch)

Diyot lazerler yüksek güçte optik radyasyon yayar. Herhangi bir kilitlenmede veya USB kablosunun kopmasında lazerin açık kalması yangın çıkarır.

1. **Host Heartbeat (Yaşam Sinyali):** Host, her 100 milisaniyede bir STM32'ye `PING` paketi gönderir.
2. **Firmware Hardware Watchdog:** Eğer STM32 son 250ms içinde geçerli bir hareket veya heartbeat paketi alamazsa:
   * Donanımsal PWM çıkışı (`PB0`) anında `LOW` (0V) yapılır.
   * Tüm step motor sürücüleri `ENABLE = HIGH` yapılarak serbest bırakılır.
   * Kırmızı alarm durumuna geçilir.
3. **Acil Durdurma (Hard Emergency Stop):** Host'tan gönderilen tek baytlık `0xFF` acil durdurma sinyali, STM32'nin USB alıcı kesmesinde tampona dahi girmeden doğrudan donanım seviyesinde lazeri ve motorları milisaniyeler içinde kapatır.
