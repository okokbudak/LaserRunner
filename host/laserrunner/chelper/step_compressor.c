#include <stdint.h>
#include <math.h>
#include <stdlib.h>

// ==============================================================================
// LaserRunner C-Helper Engine (Klipper-Style chelper)
// Yüksek Hızlı CoreXY Kinematiği, İvmelenme ve Mikrosaniyelik Adım Sıkıştırıcı
// ==============================================================================

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

// Donanımsal Adım Bloğu Veri Yapısı (22 Bayt - STM32 Paketine Birebir Eşdeğer)
#pragma pack(push, 1)
typedef struct {
    uint32_t total_steps;
    uint16_t steps_x;
    uint16_t steps_y1;
    uint16_t steps_y2;
    uint16_t steps_z;
    uint8_t  dir_bits;
    uint16_t start_interval_us;
    uint16_t end_interval_us;
    uint16_t laser_power_start;
    uint16_t laser_power_end;
} NativeMotionBlock;
#pragma pack(pop)

/**
 * CoreXY Kinematiği Hızlı Dönüşümü:
 * Delta A = Delta X + Delta Y (Motor 1)
 * Delta B = Delta X - Delta Y (Motor 2)
 */
EXPORT int fast_corexy_plan_move(
    double dx_mm,
    double dy_mm,
    double steps_per_mm,
    double target_speed,      // mm/s
    double accel,             // mm/s²
    int target_power,         // 0 - 4095
    NativeMotionBlock* out_blocks,
    int max_blocks
) {
    if (max_blocks < 3) return 0;

    double dist = sqrt(dx_mm * dx_mm + dy_mm * dy_mm);
    if (dist < 0.0001) return 0;

    // CoreXY Motor Yer Değiştirmeleri
    double da_mm = dx_mm + dy_mm;
    double db_mm = dx_mm - dy_mm;

    double raw_a = da_mm * steps_per_mm;
    double raw_b = db_mm * steps_per_mm;

    uint8_t dir_bits = 0;
    if (raw_a > 0) dir_bits |= 0x01;
    if (raw_b > 0) dir_bits |= 0x02;

    uint32_t steps_a = (uint32_t)(fabs(raw_a) + 0.5);
    uint32_t steps_b = (uint32_t)(fabs(raw_b) + 0.5);
    uint32_t total_steps = (steps_a > steps_b) ? steps_a : steps_b;
    if (total_steps == 0) return 0;

    // Trapezoidal Hız Profili (Tepe Hız, İvmelenme Mesafesi)
    double max_reach = sqrt(accel * dist);
    double peak_v = (target_speed < max_reach) ? target_speed : max_reach;
    double accel_d = (peak_v * peak_v) / (2.0 * accel);
    double cruise_d = dist - (2.0 * accel_d);
    if (cruise_d < 0) {
        cruise_d = 0;
        accel_d = dist / 2.0;
    }

    int block_count = 0;

    // 1. İvmelenme Bloğu (Start -> Peak)
    if (accel_d > 0.001) {
        double ratio = accel_d / dist;
        uint32_t seg_total = (uint32_t)(total_steps * ratio + 0.5);
        if (seg_total > 0) {
            NativeMotionBlock* b = &out_blocks[block_count++];
            b->total_steps = seg_total;
            b->steps_x = (uint16_t)(steps_a * ratio + 0.5);
            b->steps_y1 = (uint16_t)(steps_b * ratio + 0.5);
            b->steps_y2 = 0;
            b->steps_z = 0;
            b->dir_bits = dir_bits;
            
            // Başlangıç ve bitiş adım periyotları (mikrosaniye)
            double step_rate_start = (10.0 / dist) * total_steps; // min 10 mm/s
            double step_rate_end   = (peak_v / dist) * total_steps;
            b->start_interval_us = (uint16_t)(1000000.0 / step_rate_start);
            b->end_interval_us   = (uint16_t)(1000000.0 / step_rate_end);

            // Dinamik Lazer Güç Oranı P(v)
            b->laser_power_start = (uint16_t)(target_power * 0.1);
            b->laser_power_end   = (uint16_t)(target_power * (peak_v / target_speed));
        }
    }

    // 2. Sabit Hız Bloğu (Cruise)
    if (cruise_d > 0.001) {
        double ratio = cruise_d / dist;
        uint32_t seg_total = (uint32_t)(total_steps * ratio + 0.5);
        if (seg_total > 0) {
            NativeMotionBlock* b = &out_blocks[block_count++];
            b->total_steps = seg_total;
            b->steps_x = (uint16_t)(steps_a * ratio + 0.5);
            b->steps_y1 = (uint16_t)(steps_b * ratio + 0.5);
            b->steps_y2 = 0;
            b->steps_z = 0;
            b->dir_bits = dir_bits;

            double step_rate = (peak_v / dist) * total_steps;
            uint16_t interval = (uint16_t)(1000000.0 / step_rate);
            b->start_interval_us = interval;
            b->end_interval_us   = interval;

            uint16_t pwr = (uint16_t)(target_power * (peak_v / target_speed));
            b->laser_power_start = pwr;
            b->laser_power_end   = pwr;
        }
    }

    // 3. Yavaşlama Bloğu (Peak -> End)
    if (accel_d > 0.001) {
        double ratio = accel_d / dist;
        uint32_t seg_total = (uint32_t)(total_steps * ratio + 0.5);
        if (seg_total > 0) {
            NativeMotionBlock* b = &out_blocks[block_count++];
            b->total_steps = seg_total;
            b->steps_x = (uint16_t)(steps_a * ratio + 0.5);
            b->steps_y1 = (uint16_t)(steps_b * ratio + 0.5);
            b->steps_y2 = 0;
            b->steps_z = 0;
            b->dir_bits = dir_bits;

            double step_rate_start = (peak_v / dist) * total_steps;
            double step_rate_end   = (10.0 / dist) * total_steps;
            b->start_interval_us = (uint16_t)(1000000.0 / step_rate_start);
            b->end_interval_us   = (uint16_t)(1000000.0 / step_rate_end);

            b->laser_power_start = (uint16_t)(target_power * (peak_v / target_speed));
            b->laser_power_end   = (uint16_t)(target_power * 0.1);
        }
    }

    return block_count;
}
