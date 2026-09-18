#include "homing.h"
#include "step_timer.h"
#include "sensors.h"
#include "tmc_control.h"

HomingMode HomingManager::x_mode = HOMING_SENSORLESS;
HomingMode HomingManager::y_mode = HOMING_SENSORLESS;
HomingMode HomingManager::z_mode = HOMING_MECHANICAL;

uint16_t HomingManager::x_homing_current = 500;
uint16_t HomingManager::x_run_current = 800;
uint8_t  HomingManager::x_sgthrs = 65;

uint16_t HomingManager::y_homing_current = 600;
uint16_t HomingManager::y_run_current = 900;
uint8_t  HomingManager::y_sgthrs = 70;

void HomingManager::init() {
    // DIAG ve limit pinleri SafetySensors::init() içinde INPUT_PULLUP yapılır
}

void HomingManager::configureHoming(
    uint8_t axis,
    HomingMode mode,
    uint16_t homing_current_ma,
    uint16_t run_current_ma,
    uint8_t sg_threshold
) {
    if (axis == 0) {
        x_mode = mode;
        x_homing_current = homing_current_ma;
        x_run_current = run_current_ma;
        x_sgthrs = sg_threshold;
    } else if (axis == 1 || axis == 2) {
        y_mode = mode;
        y_homing_current = homing_current_ma;
        y_run_current = run_current_ma;
        y_sgthrs = sg_threshold;
    } else if (axis == 3) {
        z_mode = mode;
    }
}

bool HomingManager::runHoming(uint8_t axis_mask) {
    // 1. Z Ekseni (Varsa güvenlik için)
    if (axis_mask & 0x04) {
        homeZ();
    }

    // 2. Y Ekseni (Dual-Y Auto-Squaring / Sensörsüz veya Mekanik)
    if (axis_mask & 0x02) {
        homeDualY();
    }

    // 3. X Ekseni
    if (axis_mask & 0x01) {
        homeX();
    }

    return true;
}

// ==============================================================================
// X EKSENİ HOMING (KLIPPER TARZI SENSÖRSÜZ STALLGUARD VEYA MEKANİK SWITCH)
// ==============================================================================
void HomingManager::homeX() {
    digitalWrite(PIN_X_ENABLE, LOW); // Motor aktif

    if (x_mode == HOMING_SENSORLESS) {
        // --- 1. SENSÖRSÜZ HOMING (TMC2209 StallGuard) ---
        // Şaseye sert çarpmayı önlemek için akımı homing seviyesine düşür
        TMCDriverConfig original_cfg = TMCDriverManager::active_configs[0];

        TMCDriverConfig cfg = original_cfg;
        cfg.motor_id = 0;
        cfg.driver_type = TMC_TYPE_2209;
        cfg.sense_resistor = 0.110f;
        cfg.run_current_ma = x_homing_current;
        cfg.hold_current_ma = x_homing_current / 2;
        cfg.microsteps = 16;
        cfg.interpolate = true;
        cfg.mode = TMC_MODE_SPREADCYCLE; // StallGuard sadece SpreadCycle modunda çalışır!
        cfg.stallguard_thresh = x_sgthrs;
        TMCDriverManager::configureDriver(cfg);

        // Sürücünün Stall bayrağını temizlemesi için bekleme (Klipper kuralı)
        delay(200);

        // X- yönünde sabit hızda arama hareketi (~40 mm/s)
        digitalWrite(PIN_X_DIR, LOW);
        uint32_t max_steps = 100000;
        
        // TMC2209 DIAG pini çarpma (stall) anında HIGH olur!
        while (digitalRead(PIN_X_DIAG) == LOW && max_steps--) {
            digitalWrite(PIN_X_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_X_STEP, LOW);
            delayMicroseconds(160); // Sabit 40 mm/s hız
        }

        // Çarpma algılandı! Motoru gevşetmek için 5mm geri çek (Retract)
        digitalWrite(PIN_X_DIR, HIGH);
        for (int i = 0; i < 400; i++) { // 5mm (80 step/mm)
            digitalWrite(PIN_X_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_X_STEP, LOW);
            delayMicroseconds(200);
        }
        delay(100);

        // Normal çalışma akımını ve modunu geri yükle
        TMCDriverManager::configureDriver(original_cfg);

    } else {
        // --- 2. MEKANİK LİMİT SWITCH HOMING ---
        digitalWrite(PIN_X_DIR, LOW);
        uint32_t max_steps = 100000;
        while (digitalRead(PIN_X_DIAG) == HIGH && max_steps--) {
            digitalWrite(PIN_X_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_X_STEP, LOW);
            delayMicroseconds(100);
        }

        // 3mm geri çekil
        digitalWrite(PIN_X_DIR, HIGH);
        for (int i = 0; i < 240; i++) {
            digitalWrite(PIN_X_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_X_STEP, LOW);
            delayMicroseconds(200);
        }
        delay(50);

        // Hassas dokunuş
        digitalWrite(PIN_X_DIR, LOW);
        max_steps = 2000;
        while (digitalRead(PIN_X_DIAG) == HIGH && max_steps--) {
            digitalWrite(PIN_X_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_X_STEP, LOW);
            delayMicroseconds(300);
        }
    }

    StepTimer::current_pos_x = 0;
}

// ==============================================================================
// DUAL-Y HOMING & AUTO-SQUARING (SENSÖRSÜZ VEYA ÇİFT SWITCH)
// ==============================================================================
void HomingManager::homeDualY() {
    digitalWrite(PIN_Y1_ENABLE, LOW);
    digitalWrite(PIN_Y2_ENABLE, LOW);

    if (y_mode == HOMING_SENSORLESS) {
        // --- DUAL-Y SENSÖRSÜZ HOMING ---
        TMCDriverConfig orig_y1 = TMCDriverManager::active_configs[1];
        TMCDriverConfig orig_y2 = TMCDriverManager::active_configs[2];

        TMCDriverConfig cfg1 = orig_y1;
        cfg1.motor_id = 1;
        cfg1.driver_type = TMC_TYPE_2209;
        cfg1.sense_resistor = 0.110f;
        cfg1.run_current_ma = y_homing_current;
        cfg1.hold_current_ma = y_homing_current / 2;
        cfg1.microsteps = 16;
        cfg1.interpolate = true;
        cfg1.mode = TMC_MODE_SPREADCYCLE;
        cfg1.stallguard_thresh = y_sgthrs;
        TMCDriverManager::configureDriver(cfg1);

        TMCDriverConfig cfg2 = orig_y2;
        cfg2.motor_id = 2;
        cfg2.driver_type = TMC_TYPE_2209;
        cfg2.sense_resistor = 0.110f;
        cfg2.run_current_ma = y_homing_current;
        cfg2.hold_current_ma = y_homing_current / 2;
        cfg2.microsteps = 16;
        cfg2.interpolate = true;
        cfg2.mode = TMC_MODE_SPREADCYCLE;
        cfg2.stallguard_thresh = y_sgthrs;
        TMCDriverManager::configureDriver(cfg2);

        delay(200);

        digitalWrite(PIN_Y1_DIR, LOW);
        digitalWrite(PIN_Y2_DIR, LOW);

        bool y1_hit = false;
        bool y2_hit = false;
        uint32_t max_steps = 100000;

        // Her iki motorun DIAG pini HIGH olana kadar bağımsız adım at (Auto-Squaring)
        while ((!y1_hit || !y2_hit) && max_steps--) {
            if (digitalRead(PIN_Y1_DIAG) == HIGH) y1_hit = true;
            if (digitalRead(PIN_Y2_DIAG) == HIGH) y2_hit = true;

            if (!y1_hit) digitalWrite(PIN_Y1_STEP, HIGH);
            if (!y2_hit) digitalWrite(PIN_Y2_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_Y1_STEP, LOW);
            digitalWrite(PIN_Y2_STEP, LOW);
            delayMicroseconds(160);
        }

        // 5mm geri çekil
        digitalWrite(PIN_Y1_DIR, HIGH);
        digitalWrite(PIN_Y2_DIR, HIGH);
        for (int i = 0; i < 400; i++) {
            digitalWrite(PIN_Y1_STEP, HIGH);
            digitalWrite(PIN_Y2_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_Y1_STEP, LOW);
            digitalWrite(PIN_Y2_STEP, LOW);
            delayMicroseconds(200);
        }
        delay(100);

        // Normal çalışma akımını ve modunu geri yükle
        TMCDriverManager::configureDriver(orig_y1);
        TMCDriverManager::configureDriver(orig_y2);

    } else {
        // --- DUAL-Y MEKANİK ÇİFT SWITCH AUTO-SQUARING ---
        digitalWrite(PIN_Y1_DIR, LOW);
        digitalWrite(PIN_Y2_DIR, LOW);

        bool y1_hit = false;
        bool y2_hit = false;
        uint32_t max_steps = 100000;

        while ((!y1_hit || !y2_hit) && max_steps--) {
            if (digitalRead(PIN_Y1_DIAG) == LOW) y1_hit = true;
            if (digitalRead(PIN_Y2_DIAG) == LOW) y2_hit = true;

            if (!y1_hit) digitalWrite(PIN_Y1_STEP, HIGH);
            if (!y2_hit) digitalWrite(PIN_Y2_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_Y1_STEP, LOW);
            digitalWrite(PIN_Y2_STEP, LOW);
            delayMicroseconds(120);
        }

        // 3mm geri çekil
        digitalWrite(PIN_Y1_DIR, HIGH);
        digitalWrite(PIN_Y2_DIR, HIGH);
        for (int i = 0; i < 240; i++) {
            digitalWrite(PIN_Y1_STEP, HIGH);
            digitalWrite(PIN_Y2_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_Y1_STEP, LOW);
            digitalWrite(PIN_Y2_STEP, LOW);
            delayMicroseconds(200);
        }
        delay(50);

        // Hassas dokunuş
        digitalWrite(PIN_Y1_DIR, LOW);
        digitalWrite(PIN_Y2_DIR, LOW);
        y1_hit = false;
        y2_hit = false;
        max_steps = 2000;

        while ((!y1_hit || !y2_hit) && max_steps--) {
            if (digitalRead(PIN_Y1_DIAG) == LOW) y1_hit = true;
            if (digitalRead(PIN_Y2_DIAG) == LOW) y2_hit = true;

            if (!y1_hit) digitalWrite(PIN_Y1_STEP, HIGH);
            if (!y2_hit) digitalWrite(PIN_Y2_STEP, HIGH);
            delayMicroseconds(2);
            digitalWrite(PIN_Y1_STEP, LOW);
            digitalWrite(PIN_Y2_STEP, LOW);
            delayMicroseconds(350);
        }
    }

    StepTimer::current_pos_y = 0;
}

void HomingManager::homeZ() {
    digitalWrite(PIN_Z_DIR, LOW);
    digitalWrite(PIN_Z_ENABLE, LOW);

    uint32_t max_steps = 50000;
    while (digitalRead(PIN_Z_DIAG) == HIGH && max_steps--) {
        digitalWrite(PIN_Z_STEP, HIGH);
        delayMicroseconds(2);
        digitalWrite(PIN_Z_STEP, LOW);
        delayMicroseconds(150);
    }
    StepTimer::current_pos_z = 0;
}
