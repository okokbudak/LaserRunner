#pragma once
#include <Arduino.h>
#include "config.h"

// TMC Sürücü Tipleri
enum TMCDriverType : uint8_t {
    TMC_TYPE_2209 = 0x01,
    TMC_TYPE_5160 = 0x02,
    TMC_TYPE_2208 = 0x03,
    TMC_TYPE_2226 = 0x04
};

// TMC Çalışma Modları (Klipper Modeli)
enum TMCMode : uint8_t {
    TMC_MODE_SPREADCYCLE = 0x00, // Daima Yüksek Tork (Lazer kesim/ivme için en güvenlisi)
    TMC_MODE_STEALTHCHOP = 0x01, // Daima Ultra Sessiz (Titreşimsiz sessiz çalışma)
    TMC_MODE_HYBRID      = 0x02  // Dinamik Hibrit (Düşük hızda sessiz, yüksek hızda SpreadCycle)
};

struct TMCDriverConfig {
    uint8_t  motor_id;                     // 0: X, 1: Y1, 2: Y2, 3: Z, 4: Rotary
    uint8_t  driver_type;                  // TMC_TYPE_2209 vb.
    TMCMode  mode;                         // SPREADCYCLE | STEALTHCHOP | HYBRID
    uint16_t run_current_ma;               // RMS Akım (örn: 800 mA)
    uint16_t hold_current_ma;              // Bekleme Akımı (örn: 400 mA)
    uint16_t microsteps;                   // 1, 2, 4, 8, 16, 32, 64, 128, 256
    bool     interpolate;                  // 256 mikro-adım enterpolasyonu
    uint32_t stealthchop_threshold_speed;   // Hibrit mod geçiş hızı (mm/s, örn: 80 mm/s)
    uint8_t  stallguard_thresh;            // Sensörsüz Homing Hassasiyeti (TMC2209 SGTHRS: 0-255)
    float    sense_resistor;               // Rsense (TMC2209 için 0.110 ohm, 5160 için 0.075 ohm)
};

class TMCDriverManager {
public:
    static void init();
    static bool configureDriver(const TMCDriverConfig& config);
    static void setDriverMode(uint8_t motor_id, TMCMode mode);
    static void applyDefaults();

    static TMCDriverConfig active_configs[5];

private:
    static uint8_t calculateCurrentScale(uint16_t current_ma, float rsense);
    static uint8_t getMicrostepMRES(uint16_t microsteps);
    static void writeTMC2209Register(uint8_t uart_pin, uint8_t reg_addr, uint32_t value);
    static uint8_t getUartPinForMotor(uint8_t motor_id);
};
