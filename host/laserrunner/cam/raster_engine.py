import numpy as np
from PIL import Image
from typing import List, Dict, Any, Tuple

class RasterEngine:
    """
    LightBurn kalitesinde Lazer Raster & Fotoğraf Kazıma Motoru.
    Dithering, Gri Tonlama, Serpentine Tarama ve Overscan (İvmelenme Boşluğu) desteği.
    """
    @staticmethod
    def process_image(
        image_path: str,
        target_width_mm: float,
        target_height_mm: float,
        dpi: int = 254, # 254 DPI = 0.1mm piksel/nokta boyutu (diyot lazer standartı)
        mode: str = "floyd_steinberg", # "floyd_steinberg", "atkinson", "grayscale"
        invert: bool = True
    ) -> np.ndarray:
        """
        Resmi verilen boyutlara ve DPI değerine göre boyutlandırıp
        dithering/gri tonlama matrisine dönüştürür.
        """
        img = Image.open(image_path).convert("L") # 8-bit Gri Tonlama
        
        # Hedef piksel çözünürlüğü
        px_w = int(round(target_width_mm * (dpi / 25.4)))
        px_h = int(round(target_height_mm * (dpi / 25.4)))
        img = img.resize((px_w, px_h), Image.Resampling.LANCZOS)
        
        arr = np.array(img, dtype=np.float32)

        if invert:
            arr = 255.0 - arr

        if mode == "grayscale":
            return np.clip(arr, 0, 255).astype(np.uint8)

        elif mode == "floyd_steinberg":
            # Floyd-Steinberg Hata Yayılımı (Error Diffusion)
            h, w = arr.shape
            out = np.zeros((h, w), dtype=np.uint8)
            for y in range(h):
                for x in range(w):
                    old_val = arr[y, x]
                    new_val = 255 if old_val >= 128 else 0
                    out[y, x] = new_val
                    err = old_val - new_val
                    if x + 1 < w:
                        arr[y, x + 1] += err * (7.0 / 16.0)
                    if y + 1 < h:
                        if x - 1 >= 0:
                            arr[y + 1, x - 1] += err * (3.0 / 16.0)
                        arr[y + 1, x] += err * (5.0 / 16.0)
                        if x + 1 < w:
                            arr[y + 1, x + 1] += err * (1.0 / 16.0)
            return out

        elif mode == "atkinson":
            # Atkinson Dithering (Daha kontrastlı ve temiz noktalar)
            h, w = arr.shape
            out = np.zeros((h, w), dtype=np.uint8)
            for y in range(h):
                for x in range(w):
                    old_val = arr[y, x]
                    new_val = 255 if old_val >= 128 else 0
                    out[y, x] = new_val
                    err = (old_val - new_val) / 8.0
                    if x + 1 < w: arr[y, x + 1] += err
                    if x + 2 < w: arr[y, x + 2] += err
                    if y + 1 < h:
                        if x - 1 >= 0: arr[y + 1, x - 1] += err
                        arr[y + 1, x] += err
                        if x + 1 < w: arr[y + 1, x + 1] += err
                    if y + 2 < h:
                        arr[y + 2, x] += err
            return out

        return arr.astype(np.uint8)

    @staticmethod
    def generate_toolpath(
        matrix: np.ndarray,
        origin_x: float,
        origin_y: float,
        pixel_size_mm: float,
        scan_speed_mm_s: float,
        max_power_raw: int = 4095, # 12-bit
        overscan_mm: float = 3.0   # Kenarlarda ivmelenme/yavaşlama payı
    ) -> List[Dict[str, Any]]:
        """
        Piksel matrisini yüksek hızlı iki yönlü (serpentine)
        lazer tarama çizgilerine dönüştürür.
        """
        h, w = matrix.shape
        moves: List[Dict[str, Any]] = []

        for row in range(h):
            y_pos = origin_y + row * pixel_size_mm
            direction = 1 if (row % 2 == 0) else -1 # Sağa / Sola

            x_start = origin_x if direction == 1 else origin_x + (w - 1) * pixel_size_mm
            x_end   = origin_x + (w - 1) * pixel_size_mm if direction == 1 else origin_x

            # Satır başlangıcına hızlı hareket (G0 eşdeğeri)
            moves.append({
                "type": "RAPID",
                "x": x_start - (overscan_mm * direction),
                "y": y_pos,
                "power": 0,
                "speed": scan_speed_mm_s
            })

            # Overscan ivmelenme alanı (lazer kapalı)
            moves.append({
                "type": "LEAD_IN",
                "x": x_start,
                "y": y_pos,
                "power": 0,
                "speed": scan_speed_mm_s
            })

            # Piksel verisini bloklar halinde sıkıştırarak çiz
            col_range = range(w) if direction == 1 else range(w - 1, -1, -1)
            current_pwr = None
            seg_start_x = x_start

            for col in col_range:
                val = matrix[row, col]
                pwr = int((val / 255.0) * max_power_raw) if val > 0 else 0
                cur_x = origin_x + col * pixel_size_mm

                if current_pwr is None:
                    current_pwr = pwr
                    seg_start_x = cur_x
                elif pwr != current_pwr:
                    moves.append({
                        "type": "ENGRAVE",
                        "x": cur_x,
                        "y": y_pos,
                        "power": current_pwr,
                        "speed": scan_speed_mm_s
                    })
                    current_pwr = pwr
                    seg_start_x = cur_x

            # Satır sonu pikseli
            if current_pwr is not None:
                moves.append({
                    "type": "ENGRAVE",
                    "x": x_end,
                    "y": y_pos,
                    "power": current_pwr,
                    "speed": scan_speed_mm_s
                })

            # Overscan yavaşlama alanı (lazer kapalı)
            moves.append({
                "type": "LEAD_OUT",
                "x": x_end + (overscan_mm * direction),
                "y": y_pos,
                "power": 0,
                "speed": scan_speed_mm_s
            })

        return moves
