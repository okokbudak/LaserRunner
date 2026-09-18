#pragma once
#include <Arduino.h>
#include "config.h"

// Homing Yöntemi
enum HomingMode : uint8_t {
    HOMING_MECHANICAL = 0x00,  // Mekanik Limit Switch (Switch tetiklenince LOW/HIGH)
    HOMING_SENSORLESS = 0x01   // TMC StallGuard Sensörsüz Homing (DIAG pini HIGH olunca durur)
};

class HomingManager {
public:
    static void init();
    
    // Homing Modu ve Akım Ayarları
    static void configureHoming(
        uint8_t axis,               // 0: X, 1: Y1, 2: Y2, 3: Z
        HomingMode mode,
        uint16_t homing_current_ma, // Şaseye yumuşak dokunması için düşürülen akım (örn: 500mA)
        uint16_t run_current_ma,    // Homing sonrası geri yüklenecek normal akım (örn: 800mA)
        uint8_t sg_threshold        // StallGuard hassasiyeti (SGTHRS: 0-255)
    );

    // Çok eksenli Homing Başlatıcı (bit 0: X, bit 1: Dual-Y, bit 2: Z)
    static bool runHoming(uint8_t axis_mask);

    // Eksen bazlı homing fonksiyonları
    static void homeX();
    static void homeDualY();
    static void homeZ();

    static HomingMode x_mode;
    static HomingMode y_mode;
    static HomingMode z_mode;

    static uint16_t x_homing_current;
    static uint16_t x_run_current;
    static uint8_t  x_sgthrs;

    static uint16_t y_homing_current;
    static uint16_t y_run_current;
    static uint8_t  y_sgthrs;
};
