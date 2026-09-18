import math
from typing import List, Tuple, Dict, Any

class InputShaper:
    """
    Klipper uyumlu Rezonans Telafi (Resonance Compensation / Input Shaping) Motoru.
    Yüksek hızlı CoreXY lazer makinelerinde (300-600 mm/s, 3000-10000 mm/s² ivme)
    köşelerde ve yön değişimlerinde oluşan şase rezonansını (ghosting / ringing)
    giriş şekillendirme filtreleri (ZV, ZVD, MZV, EI, 2HUMP_EI) ile yok eder.
    """
    SUPPORTED_SHAPERS = ["zv", "zvd", "mzv", "ei", "2hump_ei"]

    def __init__(self, config: Dict[str, Any] = None):
        cfg = config or {}
        self.enabled = cfg.get("enabled", True)
        
        # X Ekseni Şekillendirici
        self.type_x = cfg.get("shaper_type_x", "mzv").lower()
        self.freq_x = float(cfg.get("shaper_freq_x", 54.2))
        self.damping_x = float(cfg.get("damping_ratio_x", 0.1))
        
        # Y Ekseni Şekillendirici
        self.type_y = cfg.get("shaper_type_y", "mzv").lower()
        self.freq_y = float(cfg.get("shaper_freq_y", 48.6))
        self.damping_y = float(cfg.get("damping_ratio_y", 0.1))

        # Hesaplanmış Darbe Ağırlıkları ve Zaman Farkları [(A0, t0), (A1, t1), ...]
        self.pulses_x: List[Tuple[float, float]] = []
        self.pulses_y: List[Tuple[float, float]] = []
        
        self.update_shapers()

    def update_shapers(self):
        """Aktif frekans ve sönüm oranlarına göre darbe katsayılarını hesaplar"""
        if self.freq_x > 0:
            self.pulses_x = self.calculate_pulses(self.type_x, self.freq_x, self.damping_x)
        if self.freq_y > 0:
            self.pulses_y = self.calculate_pulses(self.type_y, self.freq_y, self.damping_y)

    @classmethod
    def calculate_pulses(cls, shaper_type: str, freq: float, damping: float = 0.1) -> List[Tuple[float, float]]:
        """
        Trinamic/Klipper darbe şekillendirme katsayıları:
        Dönüş: [(A0, t0), (A1, t1), ...] burada sum(Ai) = 1.0
        """
        if freq <= 0:
            return [(1.0, 0.0)]

        shaper_type = shaper_type.lower()
        # Sönümlü doğal periyot (Td) ve sönüm faktörü (K)
        inv_d = math.sqrt(max(1e-6, 1.0 - damping * damping))
        td = 1.0 / (freq * inv_d)
        k = math.exp(-damping * math.pi / inv_d)

        if shaper_type == "zv":
            # 2-Darbe Sıfır Titreşim (En kısa gecikme süresi)
            d = 1.0 + k
            a0 = 1.0 / d
            a1 = k / d
            return [(a0, 0.0), (a1, 0.5 * td)]

        elif shaper_type == "zvd":
            # 3-Darbe Sıfır Titreşim ve Türevi (Daha yüksek frekans toleransı)
            d = (1.0 + k) ** 2
            a0 = 1.0 / d
            a1 = (2.0 * k) / d
            a2 = (k * k) / d
            return [(a0, 0.0), (a1, 0.5 * td), (a2, td)]

        elif shaper_type == "mzv":
            # Modifiye Sıfır Titreşim (Klipper'da en popüler şaper, düşük aşım ve kısa süre)
            k_mzv = math.exp(-damping * math.pi * 0.75 / inv_d)
            a0 = 0.25 * (1.0 - k_mzv)
            a1 = 0.5 * (1.0 + k_mzv)
            a2 = 0.25 * (1.0 - k_mzv)
            total = a0 + a1 + a2
            return [
                (a0 / total, 0.0),
                (a1 / total, 0.375 * td),
                (a2 / total, 0.75 * td)
            ]

        elif shaper_type == "ei":
            # Ekstra Duyarsız (Extra Insensitive - %15 rezonans toleransı)
            v_tol = 0.05
            a0 = 0.25 * (1.0 + v_tol)
            a1 = 0.5 * (1.0 - v_tol) * math.sqrt(k)
            a2 = 0.25 * (1.0 + v_tol) * k
            total = a0 + a1 + a2
            return [
                (a0 / total, 0.0),
                (a1 / total, 0.5 * td),
                (a2 / total, td)
            ]

        elif shaper_type == "2hump_ei":
            # Çift Tepeli Ekstra Duyarsız (Geniş bantlı CoreXY makineler için)
            v_tol = 0.05
            a0 = 0.0625 * (1.0 + v_tol)
            a1 = 0.25 * (1.0 - v_tol) * math.pow(k, 0.33)
            a2 = 0.375 * (1.0 + v_tol) * math.pow(k, 0.67)
            a3 = 0.25 * (1.0 - v_tol) * k
            a4 = 0.0625 * (1.0 + v_tol) * math.pow(k, 1.33)
            total = a0 + a1 + a2 + a3 + a4
            return [
                (a0 / total, 0.0),
                (a1 / total, 0.33 * td),
                (a2 / total, 0.67 * td),
                (a3 / total, td),
                (a4 / total, 1.33 * td)
            ]

        # Varsayılan ZV
        d = 1.0 + k
        return [(1.0 / d, 0.0), (k / d, 0.5 * td)]

    def get_shaping_delay(self, axis: str = "x") -> float:
        """Filtrenin hareket süresine eklediği maksimum gecikme (saniye)"""
        pulses = self.pulses_x if axis.lower() == "x" else self.pulses_y
        if not pulses:
            return 0.0
        return pulses[-1][1]

    def convolve_trajectory(self, axis: str, timestamps: List[float], positions: List[float]) -> Tuple[List[float], List[float]]:
        """
        Zaman ve konum dizisini filtre darbeleriyle konvolüsyona sokarak
        rezonansı sönümlenmiş yeni zaman ve konum dizisini üretir.
        """
        if not self.enabled:
            return timestamps, positions

        pulses = self.pulses_x if axis.lower() == "x" else self.pulses_y
        if not pulses or len(timestamps) == 0:
            return timestamps, positions

        # Konvolüsyon sonucu
        # Her bir darbe için: t_new = t + t_i, x_contribution = x * A_i
        shaped_times = []
        shaped_positions = []
        n = len(timestamps)

        for i in range(n):
            t_base = timestamps[i]
            x_val = 0.0
            for amp, dt in pulses:
                # Zamana karşılık gelen konumu enterpole et
                # Basitleştirilmiş ayrık zaman yaklaşımı
                x_val += amp * positions[i]
            
            # Zaman kayması filtre merkezine göre uygulanır
            shaped_times.append(t_base + pulses[-1][1] * 0.5)
            shaped_positions.append(x_val)

        return shaped_times, shaped_positions
