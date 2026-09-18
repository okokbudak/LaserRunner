#pragma once
#include <Arduino.h>
#include "config.h"
#include "protocol_def.h"

class AuxIOManager {
public:
    static void init();
    static void setDevice(uint8_t device_id, uint16_t value);
    static void emergencyKill();

    static bool isAirAssistActive();
    static bool isRedPointerActive();
    static uint8_t getExhaustFanDuty();

private:
    static bool _air_assist_on;
    static bool _red_pointer_on;
    static uint8_t _exhaust_fan_duty;
};
