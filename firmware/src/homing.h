#pragma once
#include <Arduino.h>
#include "config.h"

class HomingManager {
public:
    static void init();
    static bool runHoming(uint8_t axis_mask); // bit 0: X, bit 1: Y (Dual-Y Auto-Squaring), bit 2: Z

private:
    static void homeX();
    static void homeDualY();
    static void homeZ();
};
