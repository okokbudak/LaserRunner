import re
import time
from typing import Dict, Any, List, Optional, Callable

class MacroEngine:
    """
    Klipper uyumlu G-Code Makro Yöneticisi ve Yürütme Motoru.
    [gcode_macro ADI] şablonlarını parametre ikamesiyle ({params.DEGISKEN|default(DEGER)})
    çalıştırılabilir komut dizilerine dönüştürür.
    """
    def __init__(self, controller=None):
        self.controller = controller
        self.macros: Dict[str, Dict[str, Any]] = {}
        self.register_builtin_macros()

    def register_builtin_macros(self):
        """Lazer operasyonları için hazır dahili makrolar"""
        self.register_macro("AIR_ON", "M7", "Hava yardımını (Air Assist) açar")
        self.register_macro("AIR_OFF", "M9", "Hava yardımını kapatır")
        self.register_macro("EXHAUST_ON", "M106 S255", "Duman tahliye fanını tam güçte çalıştırır")
        self.register_macro("EXHAUST_OFF", "M107", "Duman tahliye fanını durdurur")
        self.register_macro("POINTER_ON", "SET_RED_POINTER ACTIVE=1", "3.3V Kırmızı kılavuz lazerini açar")
        self.register_macro("POINTER_OFF", "SET_RED_POINTER ACTIVE=0", "3.3V Kırmızı kılavuz lazerini kapatır")
        self.register_macro("MOTORS_OFF", "M84", "Tüm step motorları serbest bırakır")
        self.register_macro("MOTORS_ON", "M17", "Tüm step motorlara tutma akımı uygular")

    def register_macro(self, name: str, gcode: str, description: str = "", variables: Optional[Dict[str, Any]] = None):
        self.macros[name.strip().upper()] = {
            "name": name.strip().upper(),
            "gcode": gcode,
            "description": description,
            "variables": variables or {}
        }

    def load_macros_from_config(self, config_macros: Dict[str, Dict[str, Any]]):
        for name, data in config_macros.items():
            self.macros[name.upper()] = data

    def expand_template(self, template_str: str, params: Dict[str, Any], variables: Dict[str, Any]) -> str:
        """
        Klipper Jinja2 benzeri parametre ikamesi:
        {params.POWER|default(1000)} -> 1000
        {params.SPEED} -> 150
        {laser_min_power} -> değişken değeri
        """
        # 1. params.NAME|default(VAL) eşleşmeleri
        def replace_param_with_default(match):
            key = match.group(1).upper()
            default_val = match.group(2)
            # Parametreler büyük/küçük harf duyarsız aranır
            for p_key, p_val in params.items():
                if p_key.upper() == key:
                    return str(p_val)
            return default_val

        pattern_with_default = r"\{\s*params\.([a-zA-Z0-9_]+)\s*\|\s*default\(([^)]+)\)\s*\}"
        result = re.sub(pattern_with_default, replace_param_with_default, template_str)

        # 2. Yalın params.NAME eşleşmeleri
        def replace_param_simple(match):
            key = match.group(1).upper()
            for p_key, p_val in params.items():
                if p_key.upper() == key:
                    return str(p_val)
            return ""

        pattern_simple = r"\{\s*params\.([a-zA-Z0-9_]+)\s*\}"
        result = re.sub(pattern_simple, replace_param_simple, result)

        # 3. Özel Makro Değişkenleri ({var_name})
        for v_key, v_val in variables.items():
            result = result.replace("{" + v_key + "}", str(v_val))

        return result

    def execute_macro(self, macro_name: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Makroyu çalıştırır ve genişletilmiş G-code satırlarını döndürür.
        """
        macro_name = macro_name.strip().upper()
        if macro_name not in self.macros:
            raise ValueError(f"Tanımsız makro: {macro_name}")

        macro = self.macros[macro_name]
        params = params or {}
        expanded_lines = []

        raw_gcode = macro["gcode"]
        for line in raw_gcode.splitlines():
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            
            expanded = self.expand_template(line, params, macro.get("variables", {}))
            expanded_lines.append(expanded)
            
            # Eğer doğrudan controller bağlıysa komutu yürüt
            if self.controller:
                self._dispatch_command(expanded)

        return expanded_lines

    def _dispatch_command(self, cmd_line: str):
        """Genişletilmiş komut satırını controller işlemlerine yönlendirir"""
        if not self.controller:
            return

        cmd = cmd_line.strip()
        parts = cmd.split()
        if not parts:
            return

        op = parts[0].upper()

        if op == "M7" or op == "M8":
            self.controller.set_air_assist(True)
        elif op == "M9":
            self.controller.set_air_assist(False)
        elif op == "M106":
            # M106 S<0-255>
            speed = 255
            for p in parts[1:]:
                if p.upper().startswith("S"):
                    speed = int(float(p[1:]))
            self.controller.set_exhaust_fan(speed)
        elif op == "M107":
            self.controller.set_exhaust_fan(0)
        elif op == "M17":
            self.controller.enable_motors(True)
        elif op == "M84" or op == "M18":
            self.controller.enable_motors(False)
        elif op == "M3" or op == "M4":
            # Lazer Aç
            pwr = 1000
            for p in parts[1:]:
                if p.upper().startswith("S"):
                    pwr = int(float(p[1:]))
            self.controller.set_manual_laser((pwr / 4095.0) * 100.0)
        elif op == "M5":
            self.controller.set_manual_laser(0.0)
        elif op == "G28":
            # Homing
            axis_mask = 0x03 # X ve Y
            if len(parts) > 1:
                axis_mask = 0
                for a in parts[1:]:
                    if "X" in a.upper(): axis_mask |= 0x01
                    if "Y" in a.upper(): axis_mask |= 0x02
                    if "Z" in a.upper(): axis_mask |= 0x04
            self.controller.start_homing(axis_mask)
        elif op.startswith("SET_AIR_ASSIST"):
            active = "ACTIVE=1" in cmd.upper()
            self.controller.set_air_assist(active)
        elif op.startswith("SET_RED_POINTER"):
            active = "ACTIVE=1" in cmd.upper()
            self.controller.set_red_pointer(active)
        elif op == "G4":
            # Bekleme (G4 P<ms> veya G4 S<sn>)
            ms = 0
            for p in parts[1:]:
                if p.upper().startswith("P"):
                    ms = float(p[1:])
                elif p.upper().startswith("S"):
                    ms = float(p[1:]) * 1000.0
            if ms > 0:
                time.sleep(ms / 1000.0)
