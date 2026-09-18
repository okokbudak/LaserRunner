from typing import List, Dict, Any, Tuple

class FramingEngine:
    """
    İş parçasının lazer tablası üzerindeki konumunu ve sınırlarını
    fiziksel olarak doğrulamak için Çerçeveleme (Framing) yolları üretir.
    """
    @staticmethod
    def generate_bounding_box_frame(
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        framing_speed_mm_s: float = 40.0,
        laser_power_percent: float = 0.5 # Gözle görülür ama yakmayan düşük güç
    ) -> List[Dict[str, Any]]:
        target_power = int((laser_power_percent / 100.0) * 4095)

        # Dikdörtgen köşe noktaları
        corners = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
            (min_x, min_y)
        ]

        moves: List[Dict[str, Any]] = []

        # Başlangıç noktasına lazer kapalı hızlı git
        moves.append({
            "type": "RAPID",
            "x": min_x,
            "y": min_y,
            "power": 0,
            "speed": framing_speed_mm_s
        })

        # Çerçeveyi düşük güçte çiz
        for pt in corners[1:]:
            moves.append({
                "type": "FRAME",
                "x": pt[0],
                "y": pt[1],
                "power": target_power,
                "speed": framing_speed_mm_s
            })

        return moves
