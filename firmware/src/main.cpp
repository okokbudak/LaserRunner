#include <Arduino.h>
#include "config.h"
#include "protocol_def.h"
#include "laser_pwm.h"
#include "step_queue.h"
#include "step_timer.h"
#include "aux_io.h"
#include "sensors.h"
#include "homing.h"
#include "tmc_control.h"

// Octopus Pro V1.0.1 (STM32F446ZET6) - 12 MHz Harici Kristal (HSE) ve 48 MHz USB Clock Yapılandırması
extern "C" void SystemClock_Config(void) {
    // 32KiB Bootloader sonrası Vector Table adresini 0x08008000'e sabitle
    SCB->VTOR = 0x08008000;

    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
    RCC_PeriphCLKInitTypeDef PeriphClkInitStruct = {0};

    // 1. Güç Kontrol Birimini Etkinleştir
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    // 2. 12 MHz HSE Kristali ve Ana PLL:
    // HSE = 12 MHz
    // PLLM = 6   -> VCO IN = 12 / 6 = 2.0 MHz (Önerilen çalışma aralığı: 1 - 2 MHz)
    // PLLN = 168 -> VCO OUT = 2.0 * 168 = 336.0 MHz (Donanım limit aralığı: 100 - 432 MHz)
    // PLLP = DIV2 -> SYSCLK = 336 / 2 = 168 MHz
    // PLLQ = 7   -> USB OTG FS = 336 / 7 = 48.0 MHz (Doğrudan ve kesin 48 MHz USB saati)
    // PLLR = 2   -> 168 MHz
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState = RCC_HSE_ON;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLM = 6;
    RCC_OscInitStruct.PLL.PLLN = 168;
    RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
    RCC_OscInitStruct.PLL.PLLQ = 7;
    RCC_OscInitStruct.PLL.PLLR = 2;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) {
        while (1);
    }

    // 3. Veri Yolları (AHB, APB1, APB2) Saatlerini Ayarla
    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;  // 168 MHz
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;   // 42 MHz (Max 45 MHz)
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;   // 84 MHz (Max 90 MHz)

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK) {
        while (1);
    }

    // 4. USB 48 MHz Saat Kaynağını PLLQ Olarak Seç
    PeriphClkInitStruct.PeriphClockSelection = RCC_PERIPHCLK_CLK48;
    PeriphClkInitStruct.Clk48ClockSelection = RCC_CLK48CLKSOURCE_PLLQ;
    if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInitStruct) != HAL_OK) {
        while (1);
    }
}

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
            if (len == 1) {
                estop_triggered = false;
                digitalWrite(PIN_LED_STATUS, LOW);
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

        case CMD_CONFIG_TMC: {
            if (len >= 11) {
                TMCDriverConfig cfg;
                cfg.motor_id = payload[0];
                cfg.driver_type = TMC_TYPE_2209;
                cfg.sense_resistor = 0.110f;
                cfg.mode = (TMCMode)payload[1];
                cfg.run_current_ma = (payload[2] << 8) | payload[3];
                cfg.hold_current_ma = (payload[4] << 8) | payload[5];
                cfg.microsteps = (payload[6] << 8) | payload[7];
                cfg.interpolate = (payload[8] != 0);
                cfg.stealthchop_threshold_speed = (payload[9] << 8) | payload[10];
                cfg.stallguard_thresh = (len >= 12) ? payload[11] : 65;
                TMCDriverManager::configureDriver(cfg);
                send_ack(seq_id);
            }
            break;
        }

        case CMD_QUEUE_MOTION: {
            if (len == sizeof(MotionBlockPayload)) {
                if (estop_triggered) {
                    send_error(ERR_ESTOP_ACTIVE, 0);
                    return;
                }

                MotionBlockPayload block;
                memcpy(&block, payload, sizeof(MotionBlockPayload));

                // Kapak açıksa lazer ateşlemeyi kapat, fakat motor hareketine izin ver
                if (SafetySensors::isLidOpen()) {
                    block.laser_power_start = 0;
                    block.laser_power_end = 0;
                }

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
    TMCDriverManager::init();

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

        // Anlık Out-of-band Acil Durdurma Byte (Sadece paket bekleme durumunda geçerlidir)
        if (byte_in == PROTOCOL_URGENT_ESTOP && parse_state == WAIT_SYNC1) {
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
