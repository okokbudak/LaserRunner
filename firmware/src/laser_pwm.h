#pragma once
#include <Arduino.h>
#include "config.h"

class LaserController {
public:
    static void init();
    static void setPower(uint16_t raw_power); // 0 - 4095
    static void emergencyKill();
    static uint16_t getCurrentPower();

private:
    static uint16_t _current_power;
    static bool _killed;
};
