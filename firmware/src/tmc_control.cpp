#include "tmc_control.h"

// Aktif sürücü yapılandırmaları
TMCDriverConfig TMCDriverManager::active_configs[5];

// Trinamic Standart CRC8 Fonksiyonu
static uint8_t tmc_crc8(const uint8_t* data, size_t length) {
    uint8_t crc = 0;
    for (size_t i = 0; i < length; i++) {
        uint8_t byte = data[i];
        for (int b = 0; b < 8; b++) {
            if ((crc >> 7) ^ (byte & 0x01)) {
                crc = (crc << 1) ^ 0x07;
            } else {
                crc = (crc << 1);
            }
            byte >>= 1;
        }
    }
    return crc;
}

void TMCDriverManager::init() {
    applyDefaults();
}

uint8_t TMCDriverManager::getUartPinForMotor(uint8_t motor_id) {
    switch (motor_id) {
        case 0: return PIN_X_UART;
        case 1: return PIN_Y1_UART;
        case 2: return PIN_Y2_UART;
        case 3: return PIN_Z_UART;
        case 4: return PIN_A_UART;
        default: return PIN_X_UART;
    }
}

uint8_t TMCDriverManager::calculateCurrentScale(uint16_t current_ma, float rsense) {
    // Trinamic RMS akım formülü: I_rms = (CS + 1) / 32 * (Vfs / Rsense) * (1 / sqrt(2))
    // Standart Vfs = 0.325V. Rsense = 0.110 ohm için CS max 31'dir.
    float vfs = 0.325f;
    float target_amps = current_ma / 1000.0f;
    float peak_amps = target_amps * 1.4142f;
    int cs = (int)round((peak_amps * 32.0f * rsense / vfs) - 1.0f);
    return (uint8_t)constrain(cs, 0, 31);
}

uint8_t TMCDriverManager::getMicrostepMRES(uint16_t microsteps) {
    // CHOPCONF.MRES: 0=256, 1=128, 2=64, 3=32, 4=16, 5=8, 6=4, 7=2, 8=Fullstep
    switch (microsteps) {
        case 256: return 0;
        case 128: return 1;
        case 64:  return 2;
        case 32:  return 3;
        case 16:  return 4;
        case 8:   return 5;
        case 4:   return 6;
        case 2:   return 7;
        case 1:   return 8;
        default:  return 4; // Varsayılan 1/16
    }
}

void TMCDriverManager::writeTMC2209Register(uint8_t uart_pin, uint8_t reg_addr, uint32_t value) {
    // Tek hatlı yazılımsal UART (Single-wire Half-Duplex)
    // Trinamic 8-bayt yazma paketi
    uint8_t packet[8];
    packet[0] = 0x05;             // Sync
    packet[1] = 0x00;             // Slave Address (0)
    packet[2] = reg_addr | 0x80;  // Yazma bayrağı (bit 7 = 1)
    packet[3] = (value >> 24) & 0xFF;
    packet[4] = (value >> 16) & 0xFF;
    packet[5] = (value >> 8) & 0xFF;
    packet[6] = value & 0xFF;
    packet[7] = tmc_crc8(packet, 7);

    // Yazılımsal bit-banging ile gönderim (19200 baud, 1 bit = 52µs)
    pinMode(uart_pin, OUTPUT);
    digitalWrite(uart_pin, HIGH);
    delayMicroseconds(100);

    for (int i = 0; i < 8; i++) {
        uint8_t b = packet[i];
        // Start bit (LOW)
        digitalWrite(uart_pin, LOW);
        delayMicroseconds(52);
        // 8 Data bit (LSB first)
        for (int bit = 0; bit < 8; bit++) {
            digitalWrite(uart_pin, (b & (1 << bit)) ? HIGH : LOW);
            delayMicroseconds(52);
        }
        // Stop bit (HIGH)
        digitalWrite(uart_pin, HIGH);
        delayMicroseconds(52);
    }
    pinMode(uart_pin, INPUT_PULLUP);
}

void TMCDriverManager::setDriverMode(uint8_t motor_id, TMCMode mode) {
    if (motor_id >= 5) return;
    active_configs[motor_id].mode = mode;

    uint8_t uart_pin = getUartPinForMotor(motor_id);

    // GCONF: Reg 0x00
    // Bit 2: en_SpreadCycle (1 = SpreadCycle, 0 = StealthChop)
    // Bit 7: mstep_reg_select (1 = CHOPCONF.MRES register'ını kullan)
    uint32_t gconf = (1 << 7); // mstep_reg_select aktif

    if (mode == TMC_MODE_SPREADCYCLE) {
        gconf |= (1 << 2); // Daima SpreadCycle (Sabit off-time kıyıcı, en yüksek tork)
        writeTMC2209Register(uart_pin, 0x00, gconf);
        // TPWMTHRS: 0 (StealthChop eşiği kapalı, daima SpreadCycle)
        writeTMC2209Register(uart_pin, 0x13, 0);
    } 
    else if (mode == TMC_MODE_STEALTHCHOP) {
        // en_SpreadCycle = 0 (StealthChop daima devrede, ultra sessiz voltaj modülasyonu)
        writeTMC2209Register(uart_pin, 0x00, gconf);
        // TPWMTHRS = 0 (Geçiş yok, motor tüm hızlarda StealthChop'ta kalır)
        writeTMC2209Register(uart_pin, 0x13, 0);
    } 
    else if (mode == TMC_MODE_HYBRID) {
        // Dinamik Hibrit: Düşük hızda StealthChop, eşik hızın üstünde SpreadCycle
        writeTMC2209Register(uart_pin, 0x00, gconf); // en_SpreadCycle = 0
        
        // TPWMTHRS = fclk / (v * steps_per_mm)
        // Trinamic dahili osilatör ~12.000.000 Hz
        uint32_t speed_mm_s = active_configs[motor_id].stealthchop_threshold_speed;
        if (speed_mm_s == 0) speed_mm_s = 60; // Varsayılan 60 mm/s eşiği
        
        uint32_t f_step = speed_mm_s * 80; // 80 step/mm standart
        uint32_t tpwmthrs = 0;
        if (f_step > 0) {
            tpwmthrs = 12000000UL / f_step;
            if (tpwmthrs > 0xFFFFF) tpwmthrs = 0xFFFFF;
        }
        writeTMC2209Register(uart_pin, 0x13, tpwmthrs);
    }
}

bool TMCDriverManager::configureDriver(const TMCDriverConfig& config) {
    if (config.motor_id >= 5) return false;
    active_configs[config.motor_id] = config;

    uint8_t uart_pin = getUartPinForMotor(config.motor_id);

    // 1. Akım Ölçekleme (IHOLD_IRUN: Reg 0x10)
    uint8_t irun = calculateCurrentScale(config.run_current_ma, config.sense_resistor);
    uint8_t ihold = calculateCurrentScale(config.hold_current_ma, config.sense_resistor);
    uint32_t ihold_irun = (ihold & 0x1F) | ((irun & 0x1F) << 8) | (6 << 16); // IHOLDDELAY = 6
    writeTMC2209Register(uart_pin, 0x10, ihold_irun);

    // 2. Mod Yapılandırması (GCONF: 0x00 ve TPWMTHRS: 0x13)
    setDriverMode(config.motor_id, config.mode);

    // 3. CHOPCONF: Reg 0x6C (Microstep MRES & Enterpolasyon)
    uint8_t mres = getMicrostepMRES(config.microsteps);
    uint32_t chopconf = 0x10000053; // Standart TOFF=3, HSTRT=5, HEND=0, TBL=2
    chopconf &= ~(0x0F << 24);      // MRES temizle
    chopconf |= ((uint32_t)mres << 24);
    if (config.interpolate) {
        chopconf |= (1UL << 28);    // 256 microstep enterpolasyonu
    }
    writeTMC2209Register(uart_pin, 0x6C, chopconf);

    // 4. Sensörsüz Homing Hassasiyeti (SGTHRS: Reg 0x40)
    writeTMC2209Register(uart_pin, 0x40, (uint32_t)config.stallguard_thresh);

    // 5. TPOWERDOWN: Reg 0x11 (Bekleme akımına geçiş gecikmesi ~0.5s)
    writeTMC2209Register(uart_pin, 0x11, 20);

    return true;
}

void TMCDriverManager::applyDefaults() {
    // Varsayılan Lazer Optimizasyonlu TMC2209 Parametreleri
    TMCDriverConfig cfg;
    cfg.driver_type = TMC_TYPE_2209;
    cfg.sense_resistor = 0.110f;
    cfg.run_current_ma = 800;
    cfg.hold_current_ma = 400;
    cfg.microsteps = 16;
    cfg.interpolate = true;
    cfg.mode = TMC_MODE_SPREADCYCLE; // Lazer ivmelerinde ve ani yön değişimlerinde maksimum tork
    cfg.stealthchop_threshold_speed = 0;
    cfg.stallguard_thresh = 65;

    // Motor 0 (X) - SpreadCycle
    cfg.motor_id = 0;
    configureDriver(cfg);

    // Motor 1 (Y1) - SpreadCycle
    cfg.motor_id = 1;
    cfg.run_current_ma = 900;
    cfg.hold_current_ma = 450;
    cfg.stallguard_thresh = 70;
    configureDriver(cfg);

    // Motor 2 (Y2 - Dual-Y) - SpreadCycle
    cfg.motor_id = 2;
    cfg.run_current_ma = 900;
    cfg.hold_current_ma = 450;
    cfg.stallguard_thresh = 70;
    configureDriver(cfg);

    // Motor 3 (Z - Yatak/Odak) - Sessizlik için StealthChop
    cfg.motor_id = 3;
    cfg.run_current_ma = 600;
    cfg.hold_current_ma = 300;
    cfg.mode = TMC_MODE_STEALTHCHOP;
    cfg.stallguard_thresh = 0;
    configureDriver(cfg);
}
