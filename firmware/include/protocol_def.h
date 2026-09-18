#pragma once
#include <stdint.h>
#include <string.h>

// Protokol Senkronizasyon Bayrakları
#define PROTOCOL_SYNC1        0xAA
#define PROTOCOL_SYNC2        0x55
#define PROTOCOL_URGENT_ESTOP 0xFF

// Host -> Firmware Komut Kodları
enum CommandOpcode : uint8_t {
    CMD_PING              = 0x01,
    CMD_EMERGENCY_STOP    = 0x02,
    CMD_ENABLE_MOTORS     = 0x03,
    CMD_SET_LASER_POWER   = 0x04,
    CMD_QUEUE_MOTION      = 0x05,
    CMD_HOME_AXIS         = 0x06,
    CMD_QUERY_STATUS      = 0x07,
    CMD_SET_AUX_OUTPUT    = 0x08,  // Hava Motoru, Duman Fanı, Kırmızı Nokta Lazer vb.
    CMD_START_HOMING      = 0x09,  // Dual-Y Auto-Squaring destekli hassas homing
    CMD_CONFIG_TMC        = 0x0A   // TMC2209/5160 Akım, Microstep, StallGuard ayarları
};

// Firmware -> Host Yanıt Kodları
enum ResponseOpcode : uint8_t {
    RESP_ACK              = 0x81,
    RESP_STATUS           = 0x82,
    RESP_ERROR            = 0x83
};

// Hata Kodları
enum SystemErrorCode : uint8_t {
    ERR_NONE              = 0x00,
    ERR_CRC_FAIL          = 0x01,
    ERR_QUEUE_OVERFLOW    = 0x02,
    ERR_WATCHDOG_TRIGGER  = 0x03,
    ERR_ESTOP_ACTIVE      = 0x04,
    ERR_INVALID_OPCODE    = 0x05,
    ERR_LID_OPEN          = 0x06,  // Güvenlik kapağı açıkken ateşleme engeli
    ERR_FLAME_DETECTED    = 0x07,  // Yangın / Alev algılandı
    ERR_DIODE_OVERTEMP    = 0x08   // Lazer kafası aşırı ısındı
};

// Yardımcı Donanım ID'leri
enum AuxDeviceID : uint8_t {
    AUX_AIR_ASSIST        = 0x01,  // Hava Motoru / Solenoid Valf (M7/M8/M9)
    AUX_EXHAUST_FAN       = 0x02,  // Duman Tahliye Fanı
    AUX_RED_POINTER       = 0x03,  // 3.3V Kılavuz / Çerçeveleme Kırmızı Lazer
    AUX_HEAD_COOLING_FAN  = 0x04,  // Lazer Kafa Soğutma Fanı
    AUX_HIGH_POWER_RELAY  = 0x05,  // Yüksek Güçlü Kompresör / Harici Röle
    AUX_LASER2_POWER      = 0x06   // İkinci Lazer Gücü
};

// Hareket Bloğu Veri Paketi (22 Bayt)
struct __attribute__((packed)) MotionBlockPayload {
    uint32_t total_steps;         // Ana eksenin toplam adımı
    uint16_t steps_x;             // X adım sayısı
    uint16_t steps_y1;            // Y1 adım sayısı
    uint16_t steps_y2;            // Y2 adım sayısı (Dual-Y)
    uint16_t steps_z;             // Z / A adım sayısı
    uint8_t  dir_bits;            // Yönler (bit 0: X, bit 1: Y1, bit 2: Y2, bit 3: Z)
    uint16_t start_interval_us;   // Başlangıç adım periyodu (mikrosaniye)
    uint16_t end_interval_us;     // Bitiş adım periyodu (mikrosaniye)
    uint16_t laser_power_start;   // Başlangıç lazer PWM (0 - 4095)
    uint16_t laser_power_end;     // Bitiş lazer PWM (0 - 4095)
};

// Genişletilmiş Canlı Telemetri ve Durum Paketi
struct __attribute__((packed)) StatusPayload {
    uint32_t uptime_ms;
    int32_t  pos_x;
    int32_t  pos_y;
    int32_t  pos_z;
    uint16_t current_laser_pwm;
    uint8_t  queue_free_slots;
    uint8_t  system_flags;        // bit 0: motors on, bit 1: running, bit 2: estop, bit 3: homed
    int16_t  diode_temp_c_x10;    // Lazer başlığı sıcaklığı (örn: 345 = 34.5°C)
    uint8_t  sensor_flags;        // bit 0: Lid Open, bit 1: Flame Alert, bit 2: Air Assist ON, bit 3: Red Pointer ON
    uint8_t  endstop_states;      // bit 0: X min, bit 1: Y1 min, bit 2: Y2 min, bit 3: Z min
};

// CRC16-CCITT (Polinom 0x1021, Başlangıç 0xFFFF)
inline uint16_t calculate_crc16(const uint8_t *data, uint16_t length) {
    uint16_t crc = 0xFFFF;
    for (uint16_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc = (crc << 1);
            }
        }
    }
    return crc;
}
