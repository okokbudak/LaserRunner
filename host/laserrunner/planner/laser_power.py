import math

class LaserPowerController:
    """
    Dinamik Lazer Güç Ölçekleyici P(v).
    Lazer kafası ivmelenirken veya köşelerde yavaşlarken,
    birim alana düşen enerjiyi (J/mm) sabit tutmak için gücü hız ile orantılı olarak ölçekler.
    
    Formül: P_anlik = P_min + (P_max - P_min) * (v_anlik / v_nominal)
    """
    def __init__(self, min_power_ratio: float = 0.05):
        self.min_power_ratio = min_power_ratio

    def calculate_power(
        self,
        current_speed_mm_s: float,
        nominal_speed_mm_s: float,
        target_power_raw: int,  # 0 - 4095
        dynamic_mode: bool = True
    ) -> int:
        if not dynamic_mode or nominal_speed_mm_s <= 0.001 or target_power_raw <= 0:
            return target_power_raw

        ratio = current_speed_mm_s / nominal_speed_mm_s
        ratio = max(0.0, min(1.0, ratio))

        # Diyot lazerin eşik voltajının altına düşmemesi için min taban oranı
        effective_ratio = self.min_power_ratio + (1.0 - self.min_power_ratio) * ratio
        power = int(round(target_power_raw * effective_ratio))
        return max(0, min(4095, power))
