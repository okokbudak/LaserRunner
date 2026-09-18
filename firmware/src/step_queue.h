#pragma once
#include "protocol_def.h"
#include "config.h"

class StepQueue {
public:
    static void init();
    static bool push(const MotionBlockPayload& block);
    static bool pop(MotionBlockPayload* block);
    static bool peek(MotionBlockPayload* block);
    static void clear();
    static uint8_t freeSlots();
    static uint8_t count();
    static bool isEmpty();
    static bool isFull();

private:
    static MotionBlockPayload _buffer[STEP_QUEUE_SIZE];
    static volatile uint8_t _head;
    static volatile uint8_t _tail;
    static volatile uint8_t _count;
};
