#include "step_timer.h"
#include "step_queue.h"
#include "laser_pwm.h"

volatile int32_t StepTimer::current_pos_x = 0;
volatile int32_t StepTimer::current_pos_y = 0;
volatile int32_t StepTimer::current_pos_z = 0;

volatile bool StepTimer::_running = false;
MotionBlockPayload StepTimer::_active_block;
volatile uint32_t StepTimer::_step_index = 0;
volatile int32_t StepTimer::_acc_x = 0;
volatile int32_t StepTimer::_acc_y1 = 0;
volatile int32_t StepTimer::_acc_y2 = 0;
volatile int32_t StepTimer::_acc_z = 0;
HardwareTimer* StepTimer::_timer = nullptr;

void StepTimer::init() {
    // Motor Pin Yapılandırmaları
    pinMode(PIN_X_STEP, OUTPUT);
    pinMode(PIN_X_DIR, OUTPUT);
    pinMode(PIN_X_ENABLE, OUTPUT);

    pinMode(PIN_Y1_STEP, OUTPUT);
    pinMode(PIN_Y1_DIR, OUTPUT);
    pinMode(PIN_Y1_ENABLE, OUTPUT);

    pinMode(PIN_Y2_STEP, OUTPUT);
    pinMode(PIN_Y2_DIR, OUTPUT);
    pinMode(PIN_Y2_ENABLE, OUTPUT);

    pinMode(PIN_Z_STEP, OUTPUT);
    pinMode(PIN_Z_DIR, OUTPUT);
    pinMode(PIN_Z_ENABLE, OUTPUT);

    // Başlangıçta tüm motorlar pasif (Enable pinleri HIGH iken TMC sürücüler boştadır)
    disableAllMotors();

    // STM32 TIM2 32-bit Donanım Zamanlayıcısı
    #if defined(TIM2)
    _timer = new HardwareTimer(TIM2);
    _timer->setMode(1, TIMER_OUTPUT_COMPARE);
    _timer->attachInterrupt(StepTimer::isrHandler);
    #endif
}

void StepTimer::enableMotors(uint8_t bitmask) {
    digitalWrite(PIN_X_ENABLE,  (bitmask & 0x01) ? LOW : HIGH);
    digitalWrite(PIN_Y1_ENABLE, (bitmask & 0x02) ? LOW : HIGH);
    digitalWrite(PIN_Y2_ENABLE, (bitmask & 0x04) ? LOW : HIGH);
    digitalWrite(PIN_Z_ENABLE,  (bitmask & 0x08) ? LOW : HIGH);
}

void StepTimer::disableAllMotors() {
    digitalWrite(PIN_X_ENABLE,  HIGH);
    digitalWrite(PIN_Y1_ENABLE, HIGH);
    digitalWrite(PIN_Y2_ENABLE, HIGH);
    digitalWrite(PIN_Z_ENABLE,  HIGH);
}

void StepTimer::applyDirections(uint8_t dir_bits) {
    digitalWrite(PIN_X_DIR,  (dir_bits & 0x01) ? HIGH : LOW);
    digitalWrite(PIN_Y1_DIR, (dir_bits & 0x02) ? HIGH : LOW);
    digitalWrite(PIN_Y2_DIR, (dir_bits & 0x04) ? HIGH : LOW);
    digitalWrite(PIN_Z_DIR,  (dir_bits & 0x08) ? HIGH : LOW);
}

void StepTimer::start() {
    if (_running) return;

    if (StepQueue::pop(&_active_block)) {
        _running = true;
        _step_index = 0;
        _acc_x = 0;
        _acc_y1 = 0;
        _acc_y2 = 0;
        _acc_z = 0;

        applyDirections(_active_block.dir_bits);
        LaserController::setPower(_active_block.laser_power_start);

        if (_timer) {
            uint32_t interval = _active_block.start_interval_us;
            if (interval < MIN_STEP_INTERVAL_US) interval = MIN_STEP_INTERVAL_US;
            _timer->setOverflow(interval, MICROSEC_FORMAT);
            _timer->resume();
        }
    }
}

void StepTimer::stop() {
    _running = false;
    if (_timer) {
        _timer->pause();
    }
    LaserController::setPower(0);
}

bool StepTimer::isBusy() {
    return _running || !StepQueue::isEmpty();
}

// ============================================================
// Donanımsal Kesme Servisi (ISR): Titreşimsiz Mikrosaniyelik Adım & Lazer
// ============================================================
void StepTimer::isrHandler() {
    if (!_running) return;

    // 1. Eksen Adımları (Bresenham Algoritması)
    bool step_x = false;
    bool step_y1 = false;
    bool step_y2 = false;
    bool step_z = false;

    uint32_t total = _active_block.total_steps;
    if (total == 0) total = 1;

    _acc_x += _active_block.steps_x;
    if ((uint32_t)_acc_x >= total) {
        _acc_x -= total;
        step_x = true;
        if (_active_block.dir_bits & 0x01) current_pos_x++; else current_pos_x--;
    }

    _acc_y1 += _active_block.steps_y1;
    if ((uint32_t)_acc_y1 >= total) {
        _acc_y1 -= total;
        step_y1 = true;
        if (_active_block.dir_bits & 0x02) current_pos_y++; else current_pos_y--;
    }

    _acc_y2 += _active_block.steps_y2;
    if ((uint32_t)_acc_y2 >= total) {
        _acc_y2 -= total;
        step_y2 = true;
    }

    _acc_z += _active_block.steps_z;
    if ((uint32_t)_acc_z >= total) {
        _acc_z -= total;
        step_z = true;
        if (_active_block.dir_bits & 0x08) current_pos_z++; else current_pos_z--;
    }

    // Step pinlerini HIGH yap
    if (step_x)  digitalWrite(PIN_X_STEP, HIGH);
    if (step_y1) digitalWrite(PIN_Y1_STEP, HIGH);
    if (step_y2) digitalWrite(PIN_Y2_STEP, HIGH);
    if (step_z)  digitalWrite(PIN_Z_STEP, HIGH);

    // Kısa darbe gecikmesi (TMC sürücüler için min 100ns yeterlidir, 2 mikrosaniye garanti)
    delayMicroseconds(2);

    // Step pinlerini LOW yap
    if (step_x)  digitalWrite(PIN_X_STEP, LOW);
    if (step_y1) digitalWrite(PIN_Y1_STEP, LOW);
    if (step_y2) digitalWrite(PIN_Y2_STEP, LOW);
    if (step_z)  digitalWrite(PIN_Z_STEP, LOW);

    _step_index++;

    // 2. Lazer Gücü ve İvme İnterpolasyonu
    if (_step_index < _active_block.total_steps) {
        // İvmelenme/Yavaşlama adım periyodu güncellemesi
        int32_t delta_int = (int32_t)_active_block.end_interval_us - (int32_t)_active_block.start_interval_us;
        uint32_t current_interval = _active_block.start_interval_us + (delta_int * (int32_t)_step_index) / (int32_t)total;
        if (current_interval < MIN_STEP_INTERVAL_US) current_interval = MIN_STEP_INTERVAL_US;

        // Dinamik Lazer Gücü güncellemesi
        int32_t delta_pwr = (int32_t)_active_block.laser_power_end - (int32_t)_active_block.laser_power_start;
        uint16_t current_pwr = _active_block.laser_power_start + (delta_pwr * (int32_t)_step_index) / (int32_t)total;
        LaserController::setPower(current_pwr);

        if (_timer) {
            _timer->setOverflow(current_interval, MICROSEC_FORMAT);
        }
    } else {
        // Aktif blok bitti, kuyrukta sonraki blok var mı?
        if (StepQueue::pop(&_active_block)) {
            _step_index = 0;
            _acc_x = 0;
            _acc_y1 = 0;
            _acc_y2 = 0;
            _acc_z = 0;

            applyDirections(_active_block.dir_bits);
            LaserController::setPower(_active_block.laser_power_start);

            if (_timer) {
                uint32_t interval = _active_block.start_interval_us;
                if (interval < MIN_STEP_INTERVAL_US) interval = MIN_STEP_INTERVAL_US;
                _timer->setOverflow(interval, MICROSEC_FORMAT);
            }
        } else {
            // Kuyruk boşaldı, hareketi durdur ve lazeri kapat
            _running = false;
            if (_timer) _timer->pause();
            LaserController::setPower(0);
        }
    }
}
