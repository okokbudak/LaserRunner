#pragma once
#include <Arduino.h>

// ==========================================
// LASERRUNNER BTT OCTOPUS PRO PIN AYARLARI
// ==========================================

// Lazer Donanımsal PWM Çıkışı (BLTouch Servo pini - TIM3_CH3)
#define PIN_LASER_PWM       PB0
#define LASER_PWM_FREQ_HZ   5000     // 5 kHz standart diyot lazer frekansı
#define LASER_PWM_RES_BITS  12       // 12-bit çözünürlük (0 - 4095)

// Acil Durdurma Pini (Harici switch)
#define PIN_ESTOP           PC0

// Eksen 1: Motor 1 (X Ekseni)
#define PIN_X_STEP          PF13
#define PIN_X_DIR           PF12
#define PIN_X_ENABLE        PF14
#define PIN_X_DIAG          PG6

// Eksen 2: Motor 2 (Y1 Ekseni - Birincil Y)
#define PIN_Y1_STEP         PG0
#define PIN_Y1_DIR          PG1
#define PIN_Y1_ENABLE       PF15
#define PIN_Y1_DIAG         PG9

// Eksen 3: Motor 3 (Y2 Ekseni - İkincil Y / Auto-Squaring)
#define PIN_Y2_STEP         PF11
#define PIN_Y2_DIR          PG3
#define PIN_Y2_ENABLE       PG5
#define PIN_Y2_DIAG         PG10

// Eksen 4: Motor 4 (Z Ekseni veya AWD İkincil Motorlar)
#define PIN_Z_STEP          PG4
#define PIN_Z_DIR           PC1
#define PIN_Z_ENABLE        PA0
#define PIN_Z_DIAG          PG11

// Durum LED'i
#define PIN_LED_STATUS      PA13

// ==========================================
// ZAMANLAYICI VE GÜVENLİK SINIRLARI
// ==========================================
#define WATCHDOG_TIMEOUT_MS 250      // 250ms içinde paket gelmezse lazer derhal kapanır
#define STEP_QUEUE_SIZE     64       // Ring buffer derinliği
#define MIN_STEP_INTERVAL_US 5       // Max 200 kHz adım frekansı
