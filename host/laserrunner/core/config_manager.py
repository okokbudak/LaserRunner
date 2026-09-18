import os
import configparser
from typing import Dict, Any, Optional, List

class ConfigManager:
    """
    Klipper tarzı laserrunner.cfg dosyasını okuyan, ayrıştıran ve
    makine yapılandırmasını (kinematik, rotation_distance, input_shaper,
    makrolar ve homing_override) yöneten sınıf.
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

    def _calc_axis_spm(self, stepper_sec_name: str, default_spm: float) -> float:
        """
        Klipper standardında rotation_distance veya klasik steps_per_mm üzerinden
        adım/mm oranını hesaplar.
        Formül: steps_per_mm = (full_steps_per_rotation * microsteps) / rotation_distance
        """
        if stepper_sec_name not in self.parser:
            return default_spm

        sec = self.parser[stepper_sec_name]
        
        # 1. Klipper Tarzı rotation_distance Tanımı
        if "rotation_distance" in sec:
            rot_dist = float(sec.get("rotation_distance"))
            full_steps = int(sec.get("full_steps_per_rotation", "200")) # 1.8° = 200, 0.9° = 400
            
            # Mikro-adım: önce stepper sekmesinden, yoksa ilgili tmc sekmesinden ara
            microsteps = 16
            if "microsteps" in sec:
                microsteps = int(sec.get("microsteps"))
            else:
                for tmc_prefix in ["tmc2209 ", "tmc5160 ", "tmc2208 "]:
                    tmc_sec = tmc_prefix + stepper_sec_name
                    if tmc_sec in self.parser and "microsteps" in self.parser[tmc_sec]:
                        microsteps = int(self.parser[tmc_sec].get("microsteps"))
                        break

            # Dişli redüksiyonu (örn: 50:17 veya 5:1)
            if "gear_ratio" in sec:
                parts = sec.get("gear_ratio").split(":")
                if len(parts) == 2:
                    ratio = float(parts[0]) / float(parts[1])
                    rot_dist = rot_dist / ratio

            if rot_dist > 0:
                return (full_steps * microsteps) / rot_dist

        # 2. Klasik steps_per_mm Doğrudan Tanımı
        if "steps_per_mm" in sec:
            return float(sec.get("steps_per_mm"))

        return default_spm

    def get_steps_per_mm(self) -> Dict[str, float]:
        spm = {
            "x": self._calc_axis_spm("stepper_x", 80.0),
            "y": self._calc_axis_spm("stepper_y", 80.0),
            "z": self._calc_axis_spm("stepper_z", 400.0),
        }
        spm["xy"] = spm["x"]
        return spm

    def get_tmc_drivers(self) -> Dict[str, Dict[str, Any]]:
        tmc_configs = {}
        for section in self.parser.sections():
            if section.startswith("tmc2209 ") or section.startswith("tmc5160 "):
                driver_type, stepper_name = section.split(" ", 1)
                sec = self.parser[section]

                # Çalışma modu: 'spreadcycle', 'stealthchop', veya 'hybrid'
                # Klipper tarzı stealthchop_threshold ile tam uyumlu
                mode_str = sec.get("mode", "").strip().lower()
                stealth_thresh = int(sec.get("stealthchop_threshold", "0"))

                if mode_str == "stealthchop" or stealth_thresh >= 999999:
                    mode_val = 1  # TMC_MODE_STEALTHCHOP
                    mode_name = "stealthchop"
                elif mode_str == "hybrid" or (stealth_thresh > 0 and stealth_thresh < 999999):
                    mode_val = 2  # TMC_MODE_HYBRID
                    mode_name = "hybrid"
                else:
                    mode_val = 0  # TMC_MODE_SPREADCYCLE (Lazer için altın standart)
                    mode_name = "spreadcycle"

                tmc_configs[stepper_name] = {
                    "type": driver_type,
                    "uart_pin": sec.get("uart_pin", ""),
                    "mode": mode_name,
                    "mode_code": mode_val,
                    "run_current": float(sec.get("run_current", "0.800")),
                    "hold_current": float(sec.get("hold_current", "0.400")),
                    "microsteps": int(sec.get("microsteps", "16")),
                    "interpolate": sec.getboolean("interpolate", True),
                    "stealthchop_threshold": stealth_thresh,
                    "sgthrs": int(sec.get("driver_sgthrs", "65")),
                    "sense_resistor": float(sec.get("sense_resistor", "0.110"))
                }
        return tmc_configs

    def get_input_shaper_config(self) -> Dict[str, Any]:
        """Klipper Resonance Compensation (Input Shaping) Yapılandırması"""
        sec = self.parser["input_shaper"] if "input_shaper" in self.parser else {}
        return {
            "enabled": sec.getboolean("enabled", True),
            "shaper_type_x": sec.get("shaper_type_x", "mzv").strip().lower(),
            "shaper_freq_x": float(sec.get("shaper_freq_x", "54.2")),
            "damping_ratio_x": float(sec.get("damping_ratio_x", "0.1")),
            "shaper_type_y": sec.get("shaper_type_y", "mzv").strip().lower(),
            "shaper_freq_y": float(sec.get("shaper_freq_y", "48.6")),
            "damping_ratio_y": float(sec.get("damping_ratio_y", "0.1"))
        }

    def get_macros(self) -> Dict[str, Dict[str, Any]]:
        """Klipper Tarzı [gcode_macro ADI] Tanımları"""
        macros = {}
        for section in self.parser.sections():
            if section.startswith("gcode_macro "):
                macro_name = section.split(" ", 1)[1].strip().upper()
                sec = self.parser[section]
                gcode_content = sec.get("gcode", "")
                description = sec.get("description", "")
                
                # Özel değişkenler (vars)
                variables = {}
                for k, v in sec.items():
                    if k.startswith("variable_"):
                        var_name = k.replace("variable_", "")
                        variables[var_name] = v

                macros[macro_name] = {
                    "name": macro_name,
                    "gcode": gcode_content,
                    "description": description,
                    "variables": variables
                }
        return macros

    def get_homing_override(self) -> Optional[Dict[str, Any]]:
        """Klipper Tarzı [homing_override] Yapılandırması"""
        if "homing_override" in self.parser:
            sec = self.parser["homing_override"]
            return {
                "axes": sec.get("axes", "xyz").lower(),
                "gcode": sec.get("gcode", ""),
                "set_position_z": sec.get("set_position_z", None)
            }
        return None
