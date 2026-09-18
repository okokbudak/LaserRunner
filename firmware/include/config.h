#pragma once
#include <Arduino.h>

// ============================================================
// LASERRUNNER BTT OCTOPUS PRO (STM32F446ZET6) PIN YAPILANDIRMASI
// ============================================================

// --- 1. Lazer Çıkışları ---
#define PIN_LASER_PWM        PB0      // Ana Lazer Donanımsal PWM (TIM3_CH3 - BLTouch Servo)
#define PIN_RED_POINTER      PB10     // 3.3V Kılavuz / Çerçeveleme Kırmızı Nokta Lazer (RGB Soketi)
#define PIN_LASER2_PWM       PE8      // İkinci Lazer PWM (Opsiyonel Çift Kafa / UV)
#define LASER_PWM_FREQ_HZ    5000     // 5 kHz standart diyot lazer frekansı
#define LASER_PWM_RES_BITS   12       // 12-bit donanımsal çözünürlük (0 - 4095)

// --- 2. Yardımcı Çıkışlar, Hava Motoru ve Fanlar ---
#define PIN_AIR_ASSIST       PA8      // FAN0: Hava Üfleme Motoru / Solenoid Valf (M7/M8/M9)
#define PIN_EXHAUST_FAN      PE5      // FAN1: Duman Tahliye / Koku Emiş Fanı (PWM)
#define PIN_HEAD_COOLING_FAN PD12     // FAN2: Lazer Kafa Gövde Fanı
#define PIN_CASE_FAN         PD13     // FAN3: Anakart Soğutma Fanı
#define PIN_HIGH_POWER_RELAY PA3      // HE1: Yüksek Güçlü Kompresör / Harici AC Röle

// --- 3. Step Motor Sürücüleri (Motor 1 - Motor 5) ---
// Eksen X (Motor 1)
#define PIN_X_STEP           PF13
#define PIN_X_DIR            PF12
#define PIN_X_ENABLE         PF14
#define PIN_X_UART           PC4
#define PIN_X_DIAG           PG6      // Limit / Sensörsüz Homing

// Eksen Y1 - Birincil Y (Motor 2)
#define PIN_Y1_STEP          PG0
#define PIN_Y1_DIR           PG1
#define PIN_Y1_ENABLE        PF15
#define PIN_Y1_UART          PD11
#define PIN_Y1_DIAG          PG9      // Y1 Limit Switch

// Eksen Y2 - İkincil Y (Motor 3 - Dual-Y Auto Squaring)
#define PIN_Y2_STEP          PF11
#define PIN_Y2_DIR           PG3
#define PIN_Y2_ENABLE        PG5
#define PIN_Y2_UART          PC6
#define PIN_Y2_DIAG          PG10     // Y2 Bağımsız Limit Switch (Otomatik Gönyeleme)

// Eksen Z (Motor 4 - Odaklama / Yatak)
#define PIN_Z_STEP           PG4
#define PIN_Z_DIR            PC1
#define PIN_Z_ENABLE         PA0
#define PIN_Z_UART           PC7
#define PIN_Z_DIAG           PG11

// Eksen A / Rotary (Motor 5 - Bardak / Silindir Aparatı)
#define PIN_A_STEP           PF9
#define PIN_A_DIR            PF10
#define PIN_A_ENABLE         PG2
#define PIN_A_UART           PF2

// --- 4. Güvenlik, Sensörler ve Korumalar ---
#define PIN_ESTOP            PC0      // Acil Durdurma Butonu (Normalde Kapalı / Açık)
#define PIN_LID_SAFETY       PG12     // Lazer Kabin Kapağı Güvenlik Switchi (Kapak açılınca lazer durur)
#define PIN_FLAME_SENSOR     PC2      // Optik Alev / Yangın Dedektörü
#define PIN_DIODE_TEMP       PF3      // Lazer Kafası NTC100K Sıcaklık Sensörü (ADC3_IN9)
#define PIN_WATER_FLOW       PG15     // Su Soğutma / Akış Sensörü

// Durum Bildirim LED'i
#define PIN_LED_STATUS       PA13

// --- 5. Zamanlayıcı ve Eşik Değerleri ---
#define WATCHDOG_TIMEOUT_MS  250      // 250ms paket gecikmesinde lazer anında kapanır
#define STEP_QUEUE_SIZE      64       // Ring buffer derinliği
#define MIN_STEP_INTERVAL_US 5        // Max 200 kHz adım frekansı
#define MAX_DIODE_TEMP_C     55.0f    // Lazer diyot maksimum izin verilen çalışma sıcaklığı
