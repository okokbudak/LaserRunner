#include "laser_pwm.h"

uint16_t LaserController::_current_power = 0;
bool LaserController::_killed = false;

void LaserController::init() {
    pinMode(PIN_LASER_PWM, OUTPUT);
    digitalWrite(PIN_LASER_PWM, LOW);

    // STM32 Donanımsal PWM yapılandırması
    // 5 kHz frekans ve 12-bit (0-4095) çözünürlük
    analogWriteResolution(LASER_PWM_RES_BITS);
    analogWriteFrequency(LASER_PWM_FREQ_HZ);
    analogWrite(PIN_LASER_PWM, 0);

    _current_power = 0;
    _killed = false;
}

void LaserController::setPower(uint16_t raw_power) {
    if (_killed) {
        digitalWrite(PIN_LASER_PWM, LOW);
        analogWrite(PIN_LASER_PWM, 0);
        _current_power = 0;
        return;
    }

    if (raw_power > 4095) raw_power = 4095;
    _current_power = raw_power;
    analogWrite(PIN_LASER_PWM, raw_power);
}

void LaserController::emergencyKill() {
    _killed = true;
    _current_power = 0;
    // Donanım seviyesinde pini anında toprağa çek
    digitalWrite(PIN_LASER_PWM, LOW);
    analogWrite(PIN_LASER_PWM, 0);
}

uint16_t LaserController::getCurrentPower() {
    return _current_power;
}
