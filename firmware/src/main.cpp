#include <Arduino.h>
#include "config.h"
#include "protocol_def.h"
#include "laser_pwm.h"
#include "step_queue.h"
#include "step_timer.h"
#include "aux_io.h"
#include "sensors.h"
#include "homing.h"

// Paket Ayrıştırma Durum Makinesi
enum ParseState {
    WAIT_SYNC1,
    WAIT_SYNC2,
    READ_LEN,
    READ_SEQ,
    READ_OPCODE,
    READ_PAYLOAD,
    READ_CRC_H,
    READ_CRC_L
};

static ParseState parse_state = WAIT_SYNC1;
static uint8_t rx_len = 0;
static uint8_t rx_seq = 0;
static uint8_t rx_opcode = 0;
static uint8_t rx_payload[64];
static uint8_t rx_payload_index = 0;
static uint16_t rx_crc = 0;

static uint32_t last_packet_time_ms = 0;
static bool estop_triggered = false;

// ==========================================
// YANIT GÖNDERME FONKSİYONLARI
// ==========================================
void send_response(uint8_t opcode, const uint8_t* payload, uint8_t len) {
    uint8_t header[5];
    header[0] = PROTOCOL_SYNC1;
    header[1] = PROTOCOL_SYNC2;
    header[2] = len;
    header[3] = 0; // Sequence ID
    header[4] = opcode;

    // CRC hesaplama (Sync hariç)
    uint8_t crc_buffer[5 + 64];
    crc_buffer[0] = len;
    crc_buffer[1] = 0;
    crc_buffer[2] = opcode;
    if (len > 0 && payload != nullptr) {
        memcpy(&crc_buffer[3], payload, len);
    }
    uint16_t crc = calculate_crc16(crc_buffer, 3 + len);

    Serial.write(header, 5);
    if (len > 0 && payload != nullptr) {
        Serial.write(payload, len);
    }
    Serial.write((uint8_t)(crc >> 8));
    Serial.write((uint8_t)(crc & 0xFF));
}

void send_ack(uint8_t seq_id) {
    uint8_t payload[2];
    payload[0] = seq_id;
    payload[1] = StepQueue::freeSlots();
    send_response(RESP_ACK, payload, 2);
}

void send_error(uint8_t error_code, uint8_t detail) {
    uint8_t payload[2] = { error_code, detail };
    send_response(RESP_ERROR, payload, 2);
}

void trigger_emergency_stop() {
    estop_triggered = true;
    LaserController::emergencyKill();
    AuxIOManager::emergencyKill();
    StepTimer::stop();
    StepTimer::disableAllMotors();
    StepQueue::clear();
    digitalWrite(PIN_LED_STATUS, HIGH); // Alarm LED'i
}

// ==========================================
// KOMUT İŞLEYİCİ
// ==========================================
void dispatch_command(uint8_t opcode, const uint8_t* payload, uint8_t len, uint8_t seq_id) {
    last_packet_time_ms = millis();

    switch (opcode) {
        case CMD_PING: {
            send_ack(seq_id);
            break;
        }

        case CMD_EMERGENCY_STOP: {
            trigger_emergency_stop();
            send_ack(seq_id);
            break;
        }

        case CMD_ENABLE_MOTORS: {
            if (len >= 1) {
                StepTimer::enableMotors(payload[0]);
                send_ack(seq_id);
            }
            break;
        }

        case CMD_SET_LASER_POWER: {
            if (len >= 2) {
                // Güvenlik kapağı açıkken ateşleme engeli
                if (SafetySensors::isLidOpen()) {
                    send_error(ERR_LID_OPEN, 0);
                    return;
                }
                uint16_t pwr = (payload[0] << 8) | payload[1];
                LaserController::setPower(pwr);
                send_ack(seq_id);
            }
            break;
        }

        case CMD_SET_AUX_OUTPUT: {
            if (len >= 3) {
                uint8_t dev_id = payload[0];
                uint16_t val = (payload[1] << 8) | payload[2];
                AuxIOManager::setDevice(dev_id, val);
                send_ack(seq_id);
            }
            break;
        }

        case CMD_START_HOMING:
        case CMD_HOME_AXIS: {
            uint8_t axis_mask = (len >= 1) ? payload[0] : 0x03; // Varsayılan X ve Y
            LaserController::setPower(0);
            HomingManager::runHoming(axis_mask);
            send_ack(seq_id);
            break;
        }

        case CMD_QUEUE_MOTION: {
            if (len == sizeof(MotionBlockPayload)) {
                if (estop_triggered) {
                    send_error(ERR_ESTOP_ACTIVE, 0);
                    return;
                }

                // Kapak açıksa lazeri kilitle
                if (SafetySensors::isLidOpen()) {
                    send_error(ERR_LID_OPEN, 0);
                    return;
                }

                MotionBlockPayload block;
                memcpy(&block, payload, sizeof(MotionBlockPayload));

                if (StepQueue::push(block)) {
                    send_ack(seq_id);
                    if (!StepTimer::isBusy()) {
                        StepTimer::start();
                    }
                } else {
                    send_error(ERR_QUEUE_OVERFLOW, 0);
                }
            }
            break;
        }

        case CMD_QUERY_STATUS: {
            StatusPayload status;
            status.uptime_ms = millis();
            status.pos_x = StepTimer::current_pos_x;
            status.pos_y = StepTimer::current_pos_y;
            status.pos_z = StepTimer::current_pos_z;
            status.current_laser_pwm = LaserController::getCurrentPower();
            status.queue_free_slots = StepQueue::freeSlots();
            
            status.system_flags = 0;
            if (StepTimer::isBusy()) status.system_flags |= 0x02;
            if (estop_triggered) status.system_flags |= 0x04;

            status.diode_temp_c_x10 = (int16_t)(SafetySensors::getDiodeTemperature() * 10.0f);
            
            status.sensor_flags = 0;
            if (SafetySensors::isLidOpen()) status.sensor_flags |= 0x01;
            if (SafetySensors::isFlameDetected()) status.sensor_flags |= 0x02;
            if (AuxIOManager::isAirAssistActive()) status.sensor_flags |= 0x04;
            if (AuxIOManager::isRedPointerActive()) status.sensor_flags |= 0x08;

            status.endstop_states = SafetySensors::getEndstopStates();

            send_response(RESP_STATUS, (const uint8_t*)&status, sizeof(StatusPayload));
            break;
        }

        default:
            send_error(ERR_INVALID_OPCODE, opcode);
            break;
    }
}

// ==========================================
// ARDUINO SETUP & LOOP
// ==========================================
void setup() {
    pinMode(PIN_LED_STATUS, OUTPUT);
    digitalWrite(PIN_LED_STATUS, LOW);

    // Yerel USB-CDC başlatma (12 Mbps)
    Serial.begin(115200);

    // Alt sistemleri başlat
    LaserController::init();
    AuxIOManager::init();
    SafetySensors::init();
    StepQueue::init();
    StepTimer::init();
    HomingManager::init();

    last_packet_time_ms = millis();
}

void loop() {
    // 1. Güvenlik Sensörlerini Oku
    SafetySensors::update();

    // Alev algılandıysa anında acil durdurma
    if (SafetySensors::isFlameDetected() && !estop_triggered) {
        trigger_emergency_stop();
    }

    // Kapak açıldıysa lazeri hemen kapat
    if (SafetySensors::isLidOpen()) {
        if (LaserController::getCurrentPower() > 0) {
            LaserController::setPower(0);
        }
    }

    // Lazer aşırı ısındıysa korumaya al
    if (SafetySensors::getDiodeTemperature() > MAX_DIODE_TEMP_C) {
        if (LaserController::getCurrentPower() > 0) {
            LaserController::setPower(0);
        }
    }

    // 2. Güvenlik Watchdog Kontrolü
    if (millis() - last_packet_time_ms > WATCHDOG_TIMEOUT_MS) {
        if (LaserController::getCurrentPower() > 0) {
            LaserController::setPower(0);
        }
    }

    // 3. USB Veri Akışı ve Paket Ayrıştırma
    while (Serial.available()) {
        uint8_t byte_in = Serial.read();

        // Anlık Out-of-band Acil Durdurma Byte
        if (byte_in == PROTOCOL_URGENT_ESTOP) {
            trigger_emergency_stop();
            continue;
        }

        switch (parse_state) {
            case WAIT_SYNC1:
                if (byte_in == PROTOCOL_SYNC1) parse_state = WAIT_SYNC2;
                break;

            case WAIT_SYNC2:
                if (byte_in == PROTOCOL_SYNC2) {
                    parse_state = READ_LEN;
                } else {
                    parse_state = WAIT_SYNC1;
                }
                break;

            case READ_LEN:
                rx_len = byte_in;
                if (rx_len > sizeof(rx_payload)) {
                    parse_state = WAIT_SYNC1;
                } else {
                    parse_state = READ_SEQ;
                }
                break;

            case READ_SEQ:
                rx_seq = byte_in;
                parse_state = READ_OPCODE;
                break;

            case READ_OPCODE:
                rx_opcode = byte_in;
                rx_payload_index = 0;
                if (rx_len == 0) {
                    parse_state = READ_CRC_H;
                } else {
                    parse_state = READ_PAYLOAD;
                }
                break;

            case READ_PAYLOAD:
                rx_payload[rx_payload_index++] = byte_in;
                if (rx_payload_index >= rx_len) {
                    parse_state = READ_CRC_H;
                }
                break;

            case READ_CRC_H:
                rx_crc = ((uint16_t)byte_in) << 8;
                parse_state = READ_CRC_L;
                break;

            case READ_CRC_L:
                rx_crc |= byte_in;

                // CRC Doğrulama
                uint8_t check_buf[3 + 64];
                check_buf[0] = rx_len;
                check_buf[1] = rx_seq;
                check_buf[2] = rx_opcode;
                if (rx_len > 0) {
                    memcpy(&check_buf[3], rx_payload, rx_len);
                }

                if (calculate_crc16(check_buf, 3 + rx_len) == rx_crc) {
                    dispatch_command(rx_opcode, rx_payload, rx_len, rx_seq);
                } else {
                    send_error(ERR_CRC_FAIL, rx_seq);
                }

                parse_state = WAIT_SYNC1;
                break;
        }
    }
}
