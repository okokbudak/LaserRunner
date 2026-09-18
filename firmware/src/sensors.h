#pragma once
#include <Arduino.h>
#include "config.h"

class SafetySensors {
public:
    static void init();
    static void update(); // Döngüde düzenli çağrılır

    static bool isLidOpen();
    static bool isFlameDetected();
    static bool isWaterFlowOk();
    static float getDiodeTemperature();
    static uint8_t getEndstopStates();

    // Güvenlik bayrakları
    static bool hasSafetyTrip(); // Kapak açıldı veya yangın algılandı mı?

private:
    static bool _lid_open;
    static bool _flame_detected;
    static bool _water_flow_ok;
    static float _diode_temperature;
    static uint8_t _endstops;
};
