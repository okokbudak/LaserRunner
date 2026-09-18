#include "tmc_control.h"

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

bool TMCDriverManager::configureDriver(const TMCDriverConfig& config) {
    uint8_t uart_pin = PIN_X_UART;
    if (config.motor_id == 1) uart_pin = PIN_Y1_UART;
    else if (config.motor_id == 2) uart_pin = PIN_Y2_UART;
    else if (config.motor_id == 3) uart_pin = PIN_Z_UART;
    else if (config.motor_id == 4) uart_pin = PIN_A_UART;

    // 1. Akım Ölçekleme (IHOLD_IRUN: Reg 0x10)
    uint8_t irun = calculateCurrentScale(config.run_current_ma, config.sense_resistor);
    uint8_t ihold = calculateCurrentScale(config.hold_current_ma, config.sense_resistor);
    uint32_t ihold_irun = (ihold & 0x1F) | ((irun & 0x1F) << 8) | (6 << 16); // IHOLDDELAY = 6
    writeTMC2209Register(uart_pin, 0x10, ihold_irun);

    // 2. GCONF: Reg 0x00 (StealthChop vs SpreadCycle)
    // Lazerlerde dar köşelerde ve yüksek hızda adım kaçırmamak için SpreadCycle (en_spreadcycle=1) önerilir
    uint32_t gconf = 0x00;
    if (!config.stealthchop) {
        gconf |= (1 << 2); // en_SpreadCycle aktif
    }
    gconf |= (1 << 7);     // mstep_reg_select: microstep CHOPCONF'tan alınsın
    writeTMC2209Register(uart_pin, 0x00, gconf);

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
    cfg.stealthchop = false; // Lazer ivmelerinde SpreadCycle torku
    cfg.stallguard_thresh = 65;

    // Motor 1 (X)
    cfg.motor_id = 0;
    configureDriver(cfg);

    // Motor 2 (Y1)
    cfg.motor_id = 1;
    cfg.run_current_ma = 900;
    configureDriver(cfg);

    // Motor 3 (Y2 - Dual-Y)
    cfg.motor_id = 2;
    cfg.run_current_ma = 900;
    configureDriver(cfg);

    // Motor 4 (Z)
    cfg.motor_id = 3;
    cfg.run_current_ma = 600;
    configureDriver(cfg);
}
