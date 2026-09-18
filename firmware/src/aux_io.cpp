#include "aux_io.h"

bool AuxIOManager::_air_assist_on = false;
bool AuxIOManager::_red_pointer_on = false;
uint8_t AuxIOManager::_exhaust_fan_duty = 0;

void AuxIOManager::init() {
    // Air Assist (FAN0)
    pinMode(PIN_AIR_ASSIST, OUTPUT);
    digitalWrite(PIN_AIR_ASSIST, LOW);

    // Duman Tahliye Fanı (FAN1)
    pinMode(PIN_EXHAUST_FAN, OUTPUT);
    digitalWrite(PIN_EXHAUST_FAN, LOW);

    // 3.3V Kılavuz / Çerçeveleme Kırmızı Nokta Lazer (PB10)
    pinMode(PIN_RED_POINTER, OUTPUT);
    digitalWrite(PIN_RED_POINTER, LOW);

    // Lazer Kafa Soğutma Fanı (FAN2) - Varsayılan güvenli modda açık tutulabilir
    pinMode(PIN_HEAD_COOLING_FAN, OUTPUT);
    digitalWrite(PIN_HEAD_COOLING_FAN, HIGH);

    // Yüksek Güçlü Kompresör / Harici Röle (HE1)
    pinMode(PIN_HIGH_POWER_RELAY, OUTPUT);
    digitalWrite(PIN_HIGH_POWER_RELAY, LOW);

    // İkinci Lazer PWM (PE8)
    pinMode(PIN_LASER2_PWM, OUTPUT);
    digitalWrite(PIN_LASER2_PWM, LOW);

    _air_assist_on = false;
    _red_pointer_on = false;
    _exhaust_fan_duty = 0;
}

void AuxIOManager::setDevice(uint8_t device_id, uint16_t value) {
    switch (device_id) {
        case AUX_AIR_ASSIST:
            _air_assist_on = (value > 0);
            digitalWrite(PIN_AIR_ASSIST, _air_assist_on ? HIGH : LOW);
            // Eğer yüksek güçlü harici kompresör rölesi de tanımlıysa tetikle
            digitalWrite(PIN_HIGH_POWER_RELAY, _air_assist_on ? HIGH : LOW);
            break;

        case AUX_EXHAUST_FAN: {
            // PWM hız kontrolü (0 - 255)
            uint8_t duty = (value > 255) ? 255 : (uint8_t)value;
            _exhaust_fan_duty = duty;
            analogWrite(PIN_EXHAUST_FAN, duty);
            break;
        }

        case AUX_RED_POINTER:
            _red_pointer_on = (value > 0);
            digitalWrite(PIN_RED_POINTER, _red_pointer_on ? HIGH : LOW);
            break;

        case AUX_HEAD_COOLING_FAN:
            digitalWrite(PIN_HEAD_COOLING_FAN, (value > 0) ? HIGH : LOW);
            break;

        case AUX_HIGH_POWER_RELAY:
            digitalWrite(PIN_HIGH_POWER_RELAY, (value > 0) ? HIGH : LOW);
            break;

        case AUX_LASER2_POWER: {
            uint16_t raw = (value > 4095) ? 4095 : value;
            analogWrite(PIN_LASER2_PWM, raw);
            break;
        }

        default:
            break;
    }
}

void AuxIOManager::emergencyKill() {
    // Tüm çıkışları ve lazerleri derhal kapat
    digitalWrite(PIN_AIR_ASSIST, LOW);
    digitalWrite(PIN_EXHAUST_FAN, LOW);
    digitalWrite(PIN_RED_POINTER, LOW);
    digitalWrite(PIN_HIGH_POWER_RELAY, LOW);
    digitalWrite(PIN_LASER2_PWM, LOW);
    // Not: Kafa soğutma fanı soğumaya yardımcı olmak için açık tutulur
    digitalWrite(PIN_HEAD_COOLING_FAN, HIGH);

    _air_assist_on = false;
    _red_pointer_on = false;
    _exhaust_fan_duty = 0;
}

bool AuxIOManager::isAirAssistActive() {
    return _air_assist_on;
}

bool AuxIOManager::isRedPointerActive() {
    return _red_pointer_on;
}

uint8_t AuxIOManager::getExhaustFanDuty() {
    return _exhaust_fan_duty;
}
