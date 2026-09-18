import os
import configparser
from typing import Dict, Any, Optional

class ConfigManager:
    """
    Klipper tarzı laserrunner.cfg dosyasını okuyan, ayrıştıran ve
    denetleyiciye aktaran yapılandırma yöneticisi.
    """
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "config", "laserrunner.cfg"
            )
        self.config_path = os.path.abspath(config_path)
        self.parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            self.parser.read(self.config_path, encoding="utf-8")
        else:
            print(f"[ConfigManager] Dosya bulunamadı: {self.config_path}")

    def get_machine_config(self) -> Dict[str, Any]:
        cfg = self.parser["machine"] if "machine" in self.parser else {}
        return {
            "kinematics": cfg.get("kinematics", "cartesian"),
            "max_velocity": float(cfg.get("max_velocity", "300")),
            "max_acceleration": float(cfg.get("max_acceleration", "3000")),
            "corner_velocity": float(cfg.get("corner_velocity", "15"))
        }

    def get_steps_per_mm(self) -> Dict[str, float]:
        spm = {"x": 80.0, "y": 80.0, "z": 400.0, "xy": 80.0}
        if "stepper_x" in self.parser:
            spm["x"] = float(self.parser["stepper_x"].get("steps_per_mm", "80.0"))
        if "stepper_y" in self.parser:
            spm["y"] = float(self.parser["stepper_y"].get("steps_per_mm", "80.0"))
        if "stepper_z" in self.parser:
            spm["z"] = float(self.parser["stepper_z"].get("steps_per_mm", "400.0"))
        spm["xy"] = spm["x"]
        return spm

    def get_tmc_drivers(self) -> Dict[str, Dict[str, Any]]:
        tmc_configs = {}
        for section in self.parser.sections():
            if section.startswith("tmc2209 ") or section.startswith("tmc5160 "):
                driver_type, stepper_name = section.split(" ", 1)
                sec = self.parser[section]
                tmc_configs[stepper_name] = {
                    "type": driver_type,
                    "uart_pin": sec.get("uart_pin", ""),
                    "run_current": float(sec.get("run_current", "0.800")),
                    "hold_current": float(sec.get("hold_current", "0.400")),
                    "microsteps": int(sec.get("microsteps", "16")),
                    "interpolate": sec.getboolean("interpolate", True),
                    "stealthchop": (int(sec.get("stealthchop_threshold", "0")) > 0),
                    "sgthrs": int(sec.get("driver_sgthrs", "65")),
                    "sense_resistor": float(sec.get("sense_resistor", "0.110"))
                }
        return tmc_configs
