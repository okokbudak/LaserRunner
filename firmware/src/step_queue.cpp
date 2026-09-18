#include "step_queue.h"

MotionBlockPayload StepQueue::_buffer[STEP_QUEUE_SIZE];
volatile uint8_t StepQueue::_head = 0;
volatile uint8_t StepQueue::_tail = 0;
volatile uint8_t StepQueue::_count = 0;

void StepQueue::init() {
    clear();
}

void StepQueue::clear() {
    noInterrupts();
    _head = 0;
    _tail = 0;
    _count = 0;
    interrupts();
}

bool StepQueue::push(const MotionBlockPayload& block) {
    if (_count >= STEP_QUEUE_SIZE) {
        return false; // Tampon dolu
    }

    _buffer[_head] = block;
    _head = (_head + 1) % STEP_QUEUE_SIZE;

    noInterrupts();
    _count++;
    interrupts();

    return true;
}

bool StepQueue::pop(MotionBlockPayload* block) {
    if (_count == 0) {
        return false; // Tampon boş
    }

    *block = _buffer[_tail];
    _tail = (_tail + 1) % STEP_QUEUE_SIZE;

    noInterrupts();
    _count--;
    interrupts();

    return true;
}

bool StepQueue::peek(MotionBlockPayload* block) {
    if (_count == 0) return false;
    *block = _buffer[_tail];
    return true;
}

uint8_t StepQueue::freeSlots() {
    return STEP_QUEUE_SIZE - _count;
}

uint8_t StepQueue::count() {
    return _count;
}

bool StepQueue::isEmpty() {
    return (_count == 0);
}

bool StepQueue::isFull() {
    return (_count >= STEP_QUEUE_SIZE);
}
