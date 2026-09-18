#include "homing.h"
#include "step_timer.h"
#include "sensors.h"

void HomingManager::init() {
    // Endstoplar SafetySensors::init() içinde yapılandırılır
}

bool HomingManager::runHoming(uint8_t axis_mask) {
    // 1. Z Ekseni (Varsa güvenlik için önce Z kaldırılabilir)
    if (axis_mask & 0x04) {
        homeZ();
    }

    // 2. Y Ekseni (Dual-Y Auto-Squaring Bağımsız Hizalama)
    if (axis_mask & 0x02) {
        homeDualY();
    }

    // 3. X Ekseni
    if (axis_mask & 0x01) {
        homeX();
    }

    return true;
}

void HomingManager::homeX() {
    // Yönü X- e ayarla (0x00)
    digitalWrite(PIN_X_DIR, LOW);
    digitalWrite(PIN_X_ENABLE, LOW); // Motor aktif

    // Switch'e doğru hızlı yaklaşım
    uint32_t max_steps = 100000;
    while (digitalRead(PIN_X_DIAG) == HIGH && max_steps--) {
        digitalWrite(PIN_X_STEP, HIGH);
        delayMicroseconds(2);
        digitalWrite(PIN_X_STEP, LOW);
        delayMicroseconds(100); // Hızlı arama hızı
    }

    // 3mm geri çekil (Bounce back)
    digitalWrite(PIN_X_DIR, HIGH);
    for (int i = 0; i < 240; i++) { // ~3mm (80 step/mm)
        digitalWrite(PIN_X_STEP, HIGH);
        delayMicroseconds(2);
        digitalWrite(PIN_X_STEP, LOW);
        delayMicroseconds(200);
    }
    delay(50);

    // Yavaş hassas dokunuş
    digitalWrite(PIN_X_DIR, LOW);
    max_steps = 2000;
    while (digitalRead(PIN_X_DIAG) == HIGH && max_steps--) {
        digitalWrite(PIN_X_STEP, HIGH);
        delayMicroseconds(2);
        digitalWrite(PIN_X_STEP, LOW);
        delayMicroseconds(300); // Yavaş hassas dokunuş
    }

    StepTimer::current_pos_x = 0;
}

void HomingManager::homeDualY() {
    // Dual-Y Auto-Squaring: İki motor bağımsız sürülür
    digitalWrite(PIN_Y1_DIR, LOW);
    digitalWrite(PIN_Y2_DIR, LOW);
    digitalWrite(PIN_Y1_ENABLE, LOW);
    digitalWrite(PIN_Y2_ENABLE, LOW);

    bool y1_hit = false;
    bool y2_hit = false;
    uint32_t max_steps = 100000;

    // Her iki switch de tetiklenene kadar adım at
    while ((!y1_hit || !y2_hit) && max_steps--) {
        if (digitalRead(PIN_Y1_DIAG) == LOW) {
            y1_hit = true;
        }
        if (digitalRead(PIN_Y2_DIAG) == LOW) {
            y2_hit = true;
        }

        if (!y1_hit) digitalWrite(PIN_Y1_STEP, HIGH);
        if (!y2_hit) digitalWrite(PIN_Y2_STEP, HIGH);
        delayMicroseconds(2);
        digitalWrite(PIN_Y1_STEP, LOW);
        digitalWrite(PIN_Y2_STEP, LOW);
        delayMicroseconds(120);
    }

    // 3mm geri çekil (Her iki motor eşit geri çekilir)
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

    // Yavaş hassas gönyeleme dokunuşu
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

    // Köprü artık lazer yatağına tam 90 derece dik hizalandı!
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
