# LaserRunner İkili (Binary) Haberleşme Protokolü Spesifikasyonu

Bu doküman, Raspberry Pi 4B (Host) ile STM32F446 (Firmware) arasındaki yüksek hızlı, düşük gecikmeli USB-CDC veri paketlerinin yapısını tanımlar.

---

## 1. Paket Yapısı (Frame Structure)

Tüm standart paketler aşağıdaki formatı takip eder:

```text
+--------+--------+--------+--------+--------+------------------+--------+--------+
| SYNC 1 | SYNC 2 | LENGTH | SEQ_ID | OPCODE |     PAYLOAD      | CRC_H  | CRC_L  |
| (0xAA) | (0x55) | (1 B)  | (1 B)  | (1 B)  |    (N Bayt)      | (1 B)  | (1 B)  |
+--------+--------+--------+--------+--------+------------------+--------+--------+
```

* **SYNC (2 Bayt):** `0xAA, 0x55` - Paket başlangıç bayrakları.
* **LENGTH (1 Bayt):** Payload bayt uzunluğu (0 - 64 bayt).
* **SEQ_ID (1 Bayt):** 0-255 arası döngüsel paket sıra numarası (Kayıp paket tespiti için).
* **OPCODE (1 Bayt):** Komut veya yanıt tipi.
* **PAYLOAD (N Bayt):** Komuta özel ikili veri.
* **CRC16 (2 Bayt):** CRC16-CCITT (Polinom: `0x1021`, Başlangıç: `0xFFFF`). `SYNC` hariç tüm baytları kapsar.

> [!IMPORTANT]
> **Acil Durdurma İstisnası (Out-of-band Urgent Byte):**
> Eğer USB akışı içinde tek bir `0xFF` baytı yakalanırsa, paket senkronizasyonu beklenmeksizin STM32 kesme seviyesinde **Lazer PWM'ini anında sıfırlar** ve motorları durdurur.

---

## 2. Komut Kodları (Opcodes: Host -> Firmware)

| Opcode | İsim | Açıklama | Payload Yapısı |
| :--- | :--- | :--- | :--- |
| `0x01` | **CMD_PING / HEARTBEAT** | Yaşam sinyali. Her 100ms'de bir gönderilmelidir. | `uint32_t host_timestamp_ms` |
| `0x02` | **CMD_EMERGENCY_STOP** | Acil durdurma ve kilitlenme. | Yok (Length = 0) |
| `0x03` | **CMD_ENABLE_MOTORS** | Motor sürücülerini aktif/pasif yapar. | `uint8_t enable_bitmask` (Bit 0: X, Bit 1: Y1, Bit 2: Y2, Bit 3: Z) |
| `0x04` | **CMD_SET_LASER_POWER** | Anlık manuel lazer gücü (Çerçeveleme / Test için). | `uint16_t power` (0 - 65535, %0 - %100) |
| `0x05` | **CMD_QUEUE_MOTION** | **Zaman Damgalı Hareket Bloğu.** Step kuyruğuna eklenir. | *(Aşağıdaki Tabloya Bakınız)* |
| `0x06` | **CMD_HOME_AXIS** | Belirtilen eksenlerde homing başlatır. | `uint8_t axis_mask` |
| `0x07` | **CMD_QUERY_STATUS** | Gerçek zamanlı durum raporu ister. | Yok |

### `CMD_QUEUE_MOTION` (0x05) Payload Detayı (22 Bayt):
```c
struct MotionBlockPayload {
    uint32_t total_steps;         // Bu bloktaki ana eksenin toplam adım sayısı
    uint16_t steps_x;             // X ekseni adım sayısı
    uint16_t steps_y1;            // Y1 ekseni adım sayısı
    uint16_t steps_y2;            // Y2 ekseni adım sayısı
    uint16_t steps_z;             // Z ekseni adım sayısı
    uint8_t  dir_bits;            // Yön bitleri (Bit 0: DirX, Bit 1: DirY1, vb.)
    uint16_t start_interval_us;   // Bloğun başındaki adım periyodu (mikrosaniye)
    uint16_t end_interval_us;     // Bloğun sonundaki adım periyodu (mikrosaniye)
    uint16_t laser_power_start;   // Başlangıç lazer gücü (0-65535)
    uint16_t laser_power_end;     // Bitiş lazer gücü (0-65535)
} __attribute__((packed));
```

---

## 3. Yanıt Kodları (Responses: Firmware -> Host)

| Opcode | İsim | Açıklama | Payload Yapısı |
| :--- | :--- | :--- | :--- |
| `0x81` | **RESP_ACK** | Paket başarıyla alındı ve kuyruğa girdi. | `uint8_t ack_seq_id`, `uint8_t queue_free_slots` |
| `0x82` | **RESP_STATUS** | Canlı telemetri verisi. | Durum bayrakları, anlık X/Y/Z pozisyonu, lazer anlık PWM değeri, endstop tetik durumları |
| `0x83` | **RESP_ERROR** | Hata durumu (CRC hatası, tampon taşması, acil stop, limit anahtarı vuruşu). | `uint8_t error_code`, `uint8_t error_detail` |

---

## 4. Akış Kontrolü (Flow Control / Ring Buffer)

1. STM32 firmware'inde **64 blokluk bir Step Ring Buffer** bulunur.
2. Her `RESP_ACK` paketi, STM32 tamponunda kaç boş yer kaldığını (`queue_free_slots`) Host'a bildirir.
3. Host tampon boşluğu 5'in altına düştüğünde veri göndermeyi yavaşlatır; tampon doluluğu arttıkça hızı artırır. Böylece veri akışı hiçbir zaman kesintiye uğramaz ve tampon taşması önlenir.
