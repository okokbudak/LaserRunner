from abc import ABC, abstractmethod
from typing import Tuple, Dict

class Kinematics(ABC):
    """
    Tüm mekanik kinematik yapıların (Kartezyen, CoreXY, AWD, H-Bot)
    türetildiği soyut temel sınıf.
    """
    def __init__(self, steps_per_mm: Dict[str, float]):
        self.steps_per_mm = steps_per_mm

    @abstractmethod
    def cartesian_to_actuators(
        self, dx_mm: float, dy_mm: float, dz_mm: float = 0.0
    ) -> Tuple[int, int, int, int, int]:
        """
        Kartezyen yer değiştirmeyi (dx, dy, dz mm)
        motor adımlarına ve yön bitlerine dönüştürür.
        
        Dönüş: (steps_m1, steps_m2, steps_m3, steps_m4, dir_bits)
        """
        pass

    @abstractmethod
    def actuators_to_cartesian(
        self, steps_m1: int, steps_m2: int, steps_m3: int, steps_m4: int
    ) -> Tuple[float, float, float]:
        """
        Motor adımlarını kartezyen koordinatlara (x, y, z mm) dönüştürür.
        """
        pass
