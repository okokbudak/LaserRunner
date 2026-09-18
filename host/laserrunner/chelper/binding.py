import os
import sys
import ctypes
import subprocess
from typing import List, Dict, Any, Optional

# C Kütüphanesi Yolları
CHELPER_DIR = os.path.dirname(os.path.abspath(__file__))
C_SRC = os.path.join(CHELPER_DIR, "step_compressor.c")
SO_PATH = os.path.join(CHELPER_DIR, "libchelper.so" if sys.platform != "win32" else "chelper.dll")

class NativeMotionBlock(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("total_steps", ctypes.c_uint32),
        ("steps_x", ctypes.c_uint16),
        ("steps_y1", ctypes.c_uint16),
        ("steps_y2", ctypes.c_uint16),
        ("steps_z", ctypes.c_uint16),
        ("dir_bits", ctypes.c_uint8),
        ("start_interval_us", ctypes.c_uint16),
        ("end_interval_us", ctypes.c_uint16),
        ("laser_power_start", ctypes.c_uint16),
        ("laser_power_end", ctypes.c_uint16),
    ]

class CHelperBinding:
    _lib = None
    _compiled_tried = False

    @classmethod
    def get_lib(cls):
        if cls._lib is not None:
            return cls._lib

        if not os.path.exists(SO_PATH) and not cls._compiled_tried:
            cls._compiled_tried = True
            cls.compile()

        if os.path.exists(SO_PATH):
            try:
                cls._lib = ctypes.CDLL(SO_PATH)
                cls._lib.fast_corexy_plan_move.argtypes = [
                    ctypes.c_double, # dx
                    ctypes.c_double, # dy
                    ctypes.c_double, # steps_per_mm
                    ctypes.c_double, # target_speed
                    ctypes.c_double, # accel
                    ctypes.c_int,    # target_power
                    ctypes.POINTER(NativeMotionBlock), # out_blocks
                    ctypes.c_int     # max_blocks
                ]
                cls._lib.fast_corexy_plan_move.restype = ctypes.c_int
                print("[CHelper] C Hızlandırma Motoru Aktif (Klipper-chelper modu)!")
            except Exception as e:
                print(f"[CHelper] Yükleme hatası: {e}")
                cls._lib = None

        return cls._lib

    @classmethod
    def compile(cls) -> bool:
        """Raspberry Pi veya Linux üzerinde C kütüphanesini gcc ile optimize derler."""
        if not os.path.exists(C_SRC):
            return False
        try:
            cmd = ["gcc", "-O3", "-fPIC", "-shared", "-o", SO_PATH, C_SRC, "-lm"]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"[CHelper] Derleme başarılı: {SO_PATH}")
            return True
        except Exception:
            return False

    @classmethod
    def plan_corexy_c(
        cls,
        dx: float,
        dy: float,
        spm: float,
        speed: float,
        accel: float,
        power: int
    ) -> Optional[List[Dict[str, Any]]]:
        lib = cls.get_lib()
        if lib is None:
            return None # Python fallback kullan

        out_blocks = (NativeMotionBlock * 4)()
        count = lib.fast_corexy_plan_move(
            ctypes.c_double(dx),
            ctypes.c_double(dy),
            ctypes.c_double(spm),
            ctypes.c_double(speed),
            ctypes.c_double(accel),
            ctypes.c_int(power),
            out_blocks,
            4
        )

        blocks = []
        for i in range(count):
            b = out_blocks[i]
            blocks.append({
                "total_steps": b.total_steps,
                "steps_x": b.steps_x,
                "steps_y1": b.steps_y1,
                "steps_y2": b.steps_y2,
                "steps_z": b.steps_z,
                "dir_bits": b.dir_bits,
                "start_interval_us": b.start_interval_us,
                "end_interval_us": b.end_interval_us,
                "laser_power_start": b.laser_power_start,
                "laser_power_end": b.laser_power_end
            })
        return blocks
