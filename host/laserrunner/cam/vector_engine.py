import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

@dataclass
class LayerSettings:
    name: str = "Layer 0"
    color: str = "#000000"
    speed_mm_s: float = 30.0     # Kesim veya çizim hızı
    power_percent: float = 80.0   # % güç
    passes: int = 1               # Pas sayısı
    is_cut: bool = True           # True: Kesim, False: Yüzey kazıma

class VectorEngine:
    """
    LightBurn benzeri Vektör (SVG / Geometri) CAM Motoru.
    Katman yönetimi, hız/güç parametreleri ve takım yolu optimizasyonu.
    """
    @staticmethod
    def parse_svg_simple(svg_content: str) -> List[List[Tuple[float, float]]]:
        """
        SVG içeriğindeki temel poligon, çizgi ve yolları ayrıştırır.
        """
        paths: List[List[Tuple[float, float]]] = []
        try:
            root = ET.fromstring(svg_content)
            # Namespace temizliği
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]

            # 1. <line x1="" y1="" x2="" y2="" />
            for line in root.iter("line"):
                x1 = float(line.get("x1", 0))
                y1 = float(line.get("y1", 0))
                x2 = float(line.get("x2", 0))
                y2 = float(line.get("y2", 0))
                paths.append([(x1, y1), (x2, y2)])

            # 2. <rect x="" y="" width="" height="" />
            for rect in root.iter("rect"):
                rx = float(rect.get("x", 0))
                ry = float(rect.get("y", 0))
                rw = float(rect.get("width", 0))
                rh = float(rect.get("height", 0))
                paths.append([
                    (rx, ry),
                    (rx + rw, ry),
                    (rx + rw, ry + rh),
                    (rx, ry + rh),
                    (rx, ry)
                ])

            # 3. <path d="..." /> temel M (moveto) ve L (lineto) desteği
            for p in root.iter("path"):
                d = p.get("d", "")
                tokens = re.findall(r'([a-zA-Z])|([-+]?[0-9]*\.?[0-9]+)', d)
                current_poly: List[Tuple[float, float]] = []
                cur_cmd = ""
                coords: List[float] = []

                for token in tokens:
                    letter, num = token
                    if letter:
                        if coords and cur_cmd in ('M', 'm', 'L', 'l'):
                            for i in range(0, len(coords) - 1, 2):
                                current_poly.append((coords[i], coords[i+1]))
                            coords = []
                        cur_cmd = letter
                        if cur_cmd in ('Z', 'z') and current_poly:
                            current_poly.append(current_poly[0])
                            paths.append(current_poly)
                            current_poly = []
                    elif num:
                        coords.append(float(num))

                if coords and cur_cmd in ('M', 'm', 'L', 'l'):
                    for i in range(0, len(coords) - 1, 2):
                        current_poly.append((coords[i], coords[i+1]))
                if current_poly:
                    paths.append(current_poly)

        except Exception as e:
            print(f"SVG ayrıştırma hatası: {e}")

        return paths

    @staticmethod
    def generate_vector_toolpath(
        polylines: List[List[Tuple[float, float]]],
        layer: LayerSettings,
        scale: float = 1.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Vektör yollarını lazer takım yoluna dönüştürür.
        """
        moves: List[Dict[str, Any]] = []
        target_power = int((layer.power_percent / 100.0) * 4095)

        for _ in range(layer.passes):
            for poly in polylines:
                if len(poly) < 2:
                    continue

                # İlk noktaya lazer kapalı hızlı yaklaşım (G0)
                start_pt = poly[0]
                moves.append({
                    "type": "RAPID",
                    "x": start_pt[0] * scale + offset_x,
                    "y": start_pt[1] * scale + offset_y,
                    "power": 0,
                    "speed": 80.0 # Hızlı hareket hızı
                })

                # Çizgileri kesim/kazıma gücüyle takip et (G1)
                for pt in poly[1:]:
                    moves.append({
                        "type": "CUT" if layer.is_cut else "ENGRAVE",
                        "x": pt[0] * scale + offset_x,
                        "y": pt[1] * scale + offset_y,
                        "power": target_power,
                        "speed": layer.speed_mm_s
                    })

        return moves
