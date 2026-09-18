from typing import List, Dict, Any, Optional

class HomingSequenceManager:
    """
    Klipper uyumlu Homing Sıralaması ve [homing_override] Yöneticisi.
    Eksen sıfırlama sırasını (Z -> Dual-Y -> X veya kullanıcı tanımlı sıra)
    ve özel G-code homing makrolarını yönetir.
    """
    def __init__(self, controller=None, macro_engine=None):
        self.controller = controller
        self.macro_engine = macro_engine
        self.default_order = ["z", "y", "x"]
        self.override_config: Optional[Dict[str, Any]] = None

    def configure_override(self, override_cfg: Optional[Dict[str, Any]]):
        self.override_config = override_cfg

    def execute_homing(self, axes: str = "xyz"):
        """
        İstenen eksenler için homing sekansını çalıştırır.
        Eğer [homing_override] tanımlıysa öncelikle o yürütülür.
        """
        axes = axes.lower()

        # 1. [homing_override] Tanımlı mı?
        if self.override_config and self.override_config.get("gcode"):
            override_axes = self.override_config.get("axes", "xyz").lower()
            # Eğer istenen eksenlerden en az biri override kapsamındaysa makroyu yürüt
            if any(a in override_axes for a in axes):
                gcode = self.override_config.get("gcode", "")
                if self.macro_engine:
                    for line in gcode.splitlines():
                        line = line.strip()
                        if line and not line.startswith(";") and not line.startswith("#"):
                            self.macro_engine._dispatch_command(line)
                    return True
                elif self.controller:
                    self.controller.start_homing(0x03)
                    return True

        # 2. Standart Sıralı Homing (Z -> Y -> X)
        axis_mask = 0
        if "x" in axes: axis_mask |= 0x01
        if "y" in axes: axis_mask |= 0x02
        if "z" in axes: axis_mask |= 0x04

        if self.controller:
            self.controller.start_homing(axis_mask)
            return True

        return False
