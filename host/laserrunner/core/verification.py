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
        """
        stepper_name = stepper_name.lower().replace("stepper_", "")
        if not self.controller or not self.controller.transport.is_connected:
            return {"success": False, "message": "Cihaz bağlı değil!"}

        dx = 0.0
        dy = 0.0
        dz = 0.0

        if stepper_name == "x":
            dx = distance_mm
        elif stepper_name in ("y", "y1"):
            dy = distance_mm
        elif stepper_name == "z":
            dz = distance_mm
        else:
            return {"success": False, "message": f"Geçersiz step motor adı: {stepper_name}"}

        # 3 kez ileri-geri döngüsü (titreşim/buzz testi)
        try:
            self.controller.enable_motors(True)
            for _ in range(3):
                # İleri
                self.controller.jog(dx, dy, dz, speed=20.0)
                time.sleep(0.3)
                # Geri
                self.controller.jog(-dx, -dy, -dz, speed=20.0)
                time.sleep(0.3)

            return {
                "success": True,
                "message": f"{stepper_name.upper()} motoru {distance_mm}mm ileri-geri hareket ettirildi. Yönü kontrol edin."
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
