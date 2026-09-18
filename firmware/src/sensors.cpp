#include "sensors.h"
#include <math.h>

bool SafetySensors::_lid_open = false;
bool SafetySensors::_flame_detected = false;
bool SafetySensors::_water_flow_ok = true;
float SafetySensors::_diode_temperature = 25.0f;
uint8_t SafetySensors::_endstops = 0;

void SafetySensors::init() {
    pinMode(PIN_LID_SAFETY, INPUT_PULLUP);
    pinMode(PIN_FLAME_SENSOR, INPUT_PULLUP);
    pinMode(PIN_WATER_FLOW, INPUT_PULLUP);

    // Limit anahtarları
    pinMode(PIN_X_DIAG, INPUT_PULLUP);
    pinMode(PIN_Y1_DIAG, INPUT_PULLUP);
    pinMode(PIN_Y2_DIAG, INPUT_PULLUP);
    pinMode(PIN_Z_DIAG, INPUT_PULLUP);

    // NTC Sıcaklık pini (Analog Giriş)
    pinMode(PIN_DIODE_TEMP, INPUT_ANALOG);

    update();
}

void SafetySensors::update() {
    // 1. Kapak Güvenlik Durumu (Normalde kapalı switch mantığı)
    _lid_open = (digitalRead(PIN_LID_SAFETY) == HIGH);

    // 2. Alev Dedektörü (Sensör aktif olduğunda LOW çeker)
    _flame_detected = (digitalRead(PIN_FLAME_SENSOR) == LOW);

    // 3. Su Akış Sensörü
    _water_flow_ok = (digitalRead(PIN_WATER_FLOW) == LOW);

    // 4. Limit Switch Durumları
    _endstops = 0;
    if (digitalRead(PIN_X_DIAG) == LOW)  _endstops |= 0x01;
    if (digitalRead(PIN_Y1_DIAG) == LOW) _endstops |= 0x02;
    if (digitalRead(PIN_Y2_DIAG) == LOW) _endstops |= 0x04;
    if (digitalRead(PIN_Z_DIAG) == LOW)  _endstops |= 0x08;

    // 5. NTC 100K Steinhart-Hart Sıcaklık Hesabı
    int raw_adc = analogRead(PIN_DIODE_TEMP);
    if (raw_adc > 10 && raw_adc < 1010) {
        // Standart 4.7k pull-up dirençli NTC formülü
        float resistance = 4700.0f / ((1023.0f / (float)raw_adc) - 1.0f);
        float steinhart;
        steinhart = resistance / 100000.0f;          // (R/Ro) 100k
        steinhart = log(steinhart);                  // ln(R/Ro)
        steinhart /= 3950.0f;                        // 1/B * ln(R/Ro) Beta = 3950
        steinhart += 1.0f / (25.0f + 273.15f);       // + (1/To)
        steinhart = 1.0f / steinhart;                // Tersini al (Kelvin)
        _diode_temperature = steinhart - 273.15f;    // Celsius'a çevir
    }
}

bool SafetySensors::isLidOpen() {
    return _lid_open;
}

bool SafetySensors::isFlameDetected() {
    return _flame_detected;
}

bool SafetySensors::isWaterFlowOk() {
    return _water_flow_ok;
}

float SafetySensors::getDiodeTemperature() {
    return _diode_temperature;
}

uint8_t SafetySensors::getEndstopStates() {
    return _endstops;
}

bool SafetySensors::hasSafetyTrip() {
    return _lid_open || _flame_detected || (_diode_temperature > MAX_DIODE_TEMP_C);
}
