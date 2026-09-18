#pragma once
#include <Arduino.h>
#include "protocol_def.h"
#include "config.h"

class StepTimer {
public:
    static void init();
    static void enableMotors(uint8_t bitmask);
    static void disableAllMotors();
    static void start();
    static void stop();
    static bool isBusy();

    static void isrHandler(); // Donanımsal Timer Kesme Fonksiyonu

    // Gerçek zamanlı koordinat takibi
    static volatile int32_t current_pos_x;
    static volatile int32_t current_pos_y;
    static volatile int32_t current_pos_z;

private:
    static void applyDirections(uint8_t dir_bits);
    static volatile bool _running;
    static MotionBlockPayload _active_block;
    static volatile uint32_t _step_index;
    static volatile int32_t _acc_x, _acc_y1, _acc_y2, _acc_z;
    static HardwareTimer* _timer;
};
