import time
from typing import Dict, Any, Optional

class VerificationManager:
    """
    Klipper uyumlu Donanım Tanılama ve Doğrulama Yöneticisi (Diagnostics & Verification).
    Komutlar:
    - QUERY_ENDSTOPS: Limit switch ve güvenlik sensörlerinin durumunu doğrular.
    - STEPPER_BUZZ: Motorun doğru yöne döndüğünü ve kablolamasını test etmek için 1mm ileri-geri titreştirir.
    - DUMP_TMC: TMC sürücünün akım, mod (SpreadCycle/StealthChop) ve StallGuard registerlarını raporlar.
    - VERIFY_STEPPER_ENABLE: Motor tutma torkunu kontrol eder.
    """
    def __init__(self, controller=None, config_manager=None):
        self.controller = controller
        self.config_manager = config_manager

    def query_endstops(self) -> Dict[str, Any]:
        """Tüm limit anahtarlarının ve güvenlik sensörlerinin canlı durumunu sorgular"""
        # Kontrolörden en güncel sensör durumlarını al
        endstop_mask = getattr(self.controller, "endstops_mask", 0x00) if self.controller else 0x00
        lid_open = getattr(self.controller, "lid_open", False) if self.controller else False
        flame_alert = getattr(self.controller, "flame_alert", False) if self.controller else False
        estop_active = (getattr(self.controller, "state", None) == "ESTOP") if self.controller else False

        # Bit 0: X, Bit 1: Y1, Bit 2: Y2, Bit 3: Z
        states = {
            "x": "TRIGGERED" if (endstop_mask & 0x01) else "open",
            "y1": "TRIGGERED" if (endstop_mask & 0x02) else "open",
            "y2": "TRIGGERED" if (endstop_mask & 0x04) else "open",
            "z": "TRIGGERED" if (endstop_mask & 0x08) else "open",
            "lid": "OPEN" if lid_open else "closed",
            "flame": "ALARM" if flame_alert else "clear",
            "estop": "TRIGGERED" if estop_active else "clear"
        }
        return states

    def stepper_buzz(self, stepper_name: str, distance_mm: float = 1.0) -> Dict[str, Any]:
        """
        Klipper STEPPER_BUZZ komutu:
        İlgili motoru 1mm ileri ve geri hareket ettirerek kablolama ve yön kontrolü sağlar.
        Kinematikten ve diğer motorlardan TAMAMEN İZOLE şekilde sadece hedef sürücüyü test eder.
        """
        stepper_name = stepper_name.lower().replace("stepper_", "")
        if not self.controller or not self.controller.transport.is_connected:
            return {"success": False, "message": "Cihaz bağlı değil!"}

        spm = self.config_manager.get_steps_per_mm() if self.config_manager else {}

        if stepper_name == "x":
            bitmask = 0x01
            steps = int(round(distance_mm * spm.get("x", 80.0)))
            target_axis = "x"
        elif stepper_name == "y":
            bitmask = 0x02
            steps = int(round(distance_mm * spm.get("y", 80.0)))
            target_axis = "y1"
        elif stepper_name == "y1":
            bitmask = 0x04
            steps = int(round(distance_mm * spm.get("y", 80.0)))
            target_axis = "y2"
        elif stepper_name == "z":
            bitmask = 0x08
            steps = int(round(distance_mm * spm.get("z", 400.0)))
            target_axis = "z"
        else:
            return {"success": False, "message": f"Geçersiz step motor adı: {stepper_name}"}

        if steps <= 0:
            steps = 80

        # Adım aralığı (20 mm/s hızında, mikrosaniye)
        interval_us = int(round(1_000_000.0 / (20.0 * (steps / distance_mm))))
        interval_us = max(200, min(10000, interval_us))

        try:
            # SADECE test edilen motor sürücüsünü enerjilendir!
            self.controller.enable_motors(bitmask)
            time.sleep(0.05)

            for _ in range(3):
                # 1. İleri Yönde Adım Bloğu
                fwd_block = {
                    "total_steps": steps,
                    "steps_x": steps if target_axis == "x" else 0,
                    "steps_y1": steps if target_axis == "y1" else 0,
                    "steps_y2": steps if target_axis == "y2" else 0,
                    "steps_z": steps if target_axis == "z" else 0,
                    "dir_bits": (0x01 if target_axis == "x" else (0x02 if target_axis == "y1" else (0x04 if target_axis == "y2" else 0x08))),
                    "start_interval_us": interval_us,
                    "end_interval_us": interval_us,
                    "laser_power_start": 0,
                    "laser_power_end": 0
                }
                self.controller.transport.send_motion_block(fwd_block)
                time.sleep(0.3)

                # 2. Geri Yönde Adım Bloğu
                rev_block = {
                    "total_steps": steps,
                    "steps_x": steps if target_axis == "x" else 0,
                    "steps_y1": steps if target_axis == "y1" else 0,
                    "steps_y2": steps if target_axis == "y2" else 0,
                    "steps_z": steps if target_axis == "z" else 0,
                    "dir_bits": 0,
                    "start_interval_us": interval_us,
                    "end_interval_us": interval_us,
                    "laser_power_start": 0,
                    "laser_power_end": 0
                }
                self.controller.transport.send_motion_block(rev_block)
                time.sleep(0.3)

            # Test bitince tüm motorları tekrar normal idle modunda tut
            self.controller.enable_motors(True)

            return {
                "success": True,
                "message": f"{stepper_name.upper()} motoru (Driver) {distance_mm}mm bağımsız ileri-geri hareket ettirildi."
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def dump_tmc(self, stepper_name: str) -> Dict[str, Any]:
        """
        Klipper DUMP_TMC komutu:
        TMC sürücünün yapılandırmasını, çalışma modunu ve StallGuard eşiğini raporlar.
        """
        stepper_key = stepper_name.lower().replace("stepper_", "")
        full_key = f"stepper_{stepper_key}"

        if not self.config_manager:
            return {"success": False, "message": "ConfigManager yüklenemedi"}

        tmc_drivers = self.config_manager.get_tmc_drivers()
        if full_key not in tmc_drivers:
            return {"success": False, "message": f"{full_key} için TMC yapılandırması bulunamadı"}

        cfg = tmc_drivers[full_key]
        return {
            "success": True,
            "driver": full_key,
            "driver_type": cfg.get("type", "TMC2209").upper(),
            "uart_pin": cfg.get("uart_pin"),
            "mode": cfg.get("mode", "spreadcycle").upper(),
            "run_current_ma": int(cfg.get("run_current", 0.8) * 1000),
            "hold_current_ma": int(cfg.get("hold_current", 0.4) * 1000),
            "microsteps": cfg.get("microsteps", 16),
            "interpolate": cfg.get("interpolate", True),
            "stallguard_threshold": cfg.get("sgthrs", 65),
            "sense_resistor": cfg.get("sense_resistor", 0.110)
        }

    def verify_stepper_enable(self, enable: bool = True) -> Dict[str, Any]:
        """Motor tutma akımını açıp kapatarak sürücü enable hatlarını test eder"""
        if self.controller:
            self.controller.enable_motors(enable)
            return {
                "success": True,
                "steppers_enabled": enable,
                "message": "Motor tutma akımı aktif (Kilitli)" if enable else "Motorlar serbest bırakıldı"
            }
        return {"success": False, "message": "Denetleyici aktif değil"}
