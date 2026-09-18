import os
import asyncio
import threading
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import serial.tools.list_ports

from ..core.controller import LaserRunnerController, MachineState
from ..core.config_manager import ConfigManager
from ..cam.framing import FramingEngine
from ..cam.vector_engine import VectorEngine, LayerSettings
from ..cam.raster_engine import RasterEngine

app = FastAPI(title="LaserRunner Studio OS", version="0.1.0")

# CORS izinleri
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Kontrolcü Örneği
controller = LaserRunnerController()
current_available_ports = []

@app.on_event("startup")
async def auto_connect_device():
    async def supervisor_loop():
        global current_available_ports
        await asyncio.sleep(1.0)
        while True:
            try:
                # 1. Mevcut seri portları tara
                current_available_ports = [p.device for p in serial.tools.list_ports.comports()]

                # 2. Donanım takılı mı kontrol et (Kablo çekildiğinde anında düşmesi için)
                if controller.state != MachineState.DISCONNECTED:
                    curr_port = controller.transport.port
                    # Linux aygıt düğümü (/dev/ttyACM0 vb.) sistemden silindiyse anında disconnect et
                    if curr_port.startswith("/dev/") and not os.path.exists(curr_port):
                        print(f"[Supervisor] Aygıt portu sistemden ayrıldı: {curr_port}")
                        controller.transport._trigger_disconnect()

                # 3. Bağlantı yoksa ve uygun cihaz varsa otomatik yeniden bağlan
                if controller.state == MachineState.DISCONNECTED:
                    for target in ["/dev/ttyACM0", "/dev/ttyUSB0", "COM3"]:
                        if target in current_available_ports:
                            try:
                                if controller.connect(target):
                                    print(f"[Supervisor] {target} algılandı ve otomatik bağlandı.")
                                    break
                            except Exception as e:
                                pass
            except Exception:
                pass
            await asyncio.sleep(0.5)

    asyncio.create_task(supervisor_loop())

# Pydantic İstek Modelleri
class ConnectRequest(BaseModel):
    port: str

class JogRequest(BaseModel):
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    speed: float = 40.0

class LaserPowerRequest(BaseModel):
    power_percent: float

class FramingRequest(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    speed: float = 40.0
    power_percent: float = 0.5

class TMCConfigRequest(BaseModel):
    motor_id: int # 0 for X (Driver 0), 1 for Y (Driver 1)
    run_current_ma: int = 800
    hold_current_ma: int = 400
    microsteps: int = 16
    mode: int = 0 # 0: SpreadCycle, 1: StealthChop, 2: Hybrid
    interpolate: bool = True
    stealthchop_threshold_speed: int = 0
    sg_thresh: int = 65

class ConfigRequest(BaseModel):
    kinematics: str = "cartesian"
    steps_per_mm_x: float = 80.0
    steps_per_mm_y: float = 80.0
    steps_per_mm_z: float = 400.0
    acceleration: float = 3000.0

class AuxToggleRequest(BaseModel):
    active: bool

class ExhaustFanRequest(BaseModel):
    duty: int # 0 - 255

class HomingRequest(BaseModel):
    axis_mask: int = 0x03 # bit 0: X, bit 1: Dual-Y, bit 2: Z

# ==========================================
# REST API UÇ NOKTALARI
# ==========================================
@app.get("/api/ports")
def get_ports():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    return {"ports": ports}

@app.get("/api/status")
def get_status():
    return {
        "state": controller.state,
        "pos_x": round(controller.pos_x, 2),
        "pos_y": round(controller.pos_y, 2),
        "pos_z": round(controller.pos_z, 2),
        "progress": round(controller.job_progress, 1),
        "free_slots": controller.transport.free_slots,
        "kinematics": controller.kinematics_type,
        "diode_temp": controller.diode_temperature,
        "lid_open": controller.lid_open,
        "flame_alert": controller.flame_alert,
        "air_assist": controller.air_assist_active,
        "red_pointer": controller.red_pointer_active,
        "exhaust_fan": controller.exhaust_fan_duty
    }

@app.post("/api/connect")
def connect_device(req: ConnectRequest):
    success = controller.connect(req.port)
    if not success:
        raise HTTPException(status_code=500, detail="Cihaza bağlanılamadı.")
    return {"status": "connected", "port": req.port}

@app.post("/api/disconnect")
def disconnect_device():
    controller.disconnect()
    return {"status": "disconnected"}

@app.post("/api/jog")
def jog_machine(req: JogRequest):
    try:
        controller.jog(dx=req.dx, dy=req.dy, dz=req.dz, speed_mm_s=req.speed)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/home")
def home_machine(req: HomingRequest):
    if controller.state == MachineState.ESTOP:
        raise HTTPException(status_code=400, detail="Makine ESTOP durumunda!")
    controller.start_homing(req.axis_mask)
    return {"status": "homing_started"}

@app.post("/api/laser/test")
def test_laser(req: LaserPowerRequest):
    controller.set_manual_laser(req.power_percent)
    return {"status": "ok", "power": req.power_percent}

@app.post("/api/aux/air_assist")
def toggle_air_assist(req: AuxToggleRequest):
    controller.set_air_assist(req.active)
    return {"status": "ok", "air_assist": req.active}

@app.post("/api/aux/exhaust_fan")
def set_exhaust_fan(req: ExhaustFanRequest):
    controller.set_exhaust_fan(req.duty)
    return {"status": "ok", "duty": req.duty}

@app.post("/api/aux/red_pointer")
def toggle_red_pointer(req: AuxToggleRequest):
    controller.set_red_pointer(req.active)
    return {"status": "ok", "red_pointer": req.active}

@app.post("/api/estop")
def emergency_stop():
    controller.emergency_stop()
    return {"status": "estop_triggered"}

@app.post("/api/estop/reset")
@app.post("/api/estop/clear")
def reset_emergency_stop():
    controller.reset_estop()
    return {"status": "ok", "state": controller.state}

@app.post("/api/frame")
def frame_job(req: FramingRequest):
    moves = FramingEngine.generate_bounding_box_frame(
        min_x=req.min_x,
        min_y=req.min_y,
        max_x=req.max_x,
        max_y=req.max_y,
        framing_speed_mm_s=req.speed,
        laser_power_percent=req.power_percent
    )
    controller.run_job_async(moves, framing=True)
    return {"status": "framing_started", "points": len(moves)}

@app.post("/api/config")
def update_config(req: ConfigRequest):
    spm = {
        "x": req.steps_per_mm_x,
        "y": req.steps_per_mm_y,
        "z": req.steps_per_mm_z,
        "xy": req.steps_per_mm_x
    }
    controller.kinematics_type = req.kinematics
    controller.kinematics = controller._build_kinematics(req.kinematics, spm)
    controller.planner.accel = req.acceleration
    controller.step_generator.kinematics = controller.kinematics
    return {"status": "config_updated"}

# ==========================================
# MAKROLAR & KLIPPER KOMUTLARI
# ==========================================
class MacroExecuteRequest(BaseModel):
    macro: str
    params: Optional[Dict[str, Any]] = None

@app.get("/api/macros")
def list_macros():
    return {
        "macros": controller.macro_engine.macros
    }

@app.post("/api/macros/execute")
def execute_macro(req: MacroExecuteRequest):
    try:
        lines = controller.macro_engine.execute_macro(req.macro, req.params)
        return {"status": "ok", "macro": req.macro, "executed_lines": lines}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/tmc/configure")
def configure_tmc(req: TMCConfigRequest):
    controller.configure_tmc_driver(
        motor_id=req.motor_id,
        run_current_ma=req.run_current_ma,
        hold_current_ma=req.hold_current_ma,
        microsteps=req.microsteps,
        mode=req.mode,
        interpolate=req.interpolate,
        stealthchop_threshold_speed=req.stealthchop_threshold_speed,
        sg_thresh=req.sg_thresh
    )
    return {"status": "ok", "motor_id": req.motor_id}

@app.get("/api/tmc/drivers")
def get_tmc_drivers():
    return controller.config_manager.get_tmc_drivers()

# ==========================================
# DONANIM DOĞRULAMA & TANILAMA (VERIFICATIONS)
# ==========================================
class StepperBuzzRequest(BaseModel):
    stepper: str
    distance: float = 1.0

class EnableSteppersRequest(BaseModel):
    enable: bool = True

@app.get("/api/verify/endstops")
def query_endstops():
    states = controller.verification.query_endstops()
    return {"status": "ok", "endstops": states}

@app.post("/api/verify/stepper_buzz")
def stepper_buzz(req: StepperBuzzRequest):
    if controller.state == MachineState.ESTOP:
        controller.reset_estop()
    result = controller.verification.stepper_buzz(req.stepper, req.distance)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result

@app.get("/api/verify/dump_tmc")
def dump_tmc(stepper: str = "stepper_x"):
    result = controller.verification.dump_tmc(stepper)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result

@app.post("/api/verify/enable_steppers")
def verify_steppers(req: EnableSteppersRequest):
    if controller.state == MachineState.ESTOP and req.enable:
        controller.reset_estop()
    return controller.verification.verify_stepper_enable(req.enable)

@app.get("/api/input_shaper")
def get_input_shaper_status():
    shaper = controller.input_shaper
    return {
        "enabled": shaper.enabled,
        "x": {
            "type": shaper.type_x,
            "freq": shaper.freq_x,
            "damping": shaper.damping_x,
            "delay_sec": shaper.get_shaping_delay("x"),
            "pulses": shaper.pulses_x
        },
        "y": {
            "type": shaper.type_y,
            "freq": shaper.freq_y,
            "damping": shaper.damping_y,
            "delay_sec": shaper.get_shaping_delay("y"),
            "pulses": shaper.pulses_y
        }
    }

# ==========================================
# KLIPPER TARZI CANLI YAPILANDIRMA (laserrunner.cfg)
# ==========================================
class SaveConfigRequest(BaseModel):
    content: str

def _get_cfg_path() -> str:
    # 1. Proje içi config/laserrunner.cfg
    p1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "laserrunner.cfg"))
    if os.path.exists(p1):
        return p1
    # 2. Çalışma dizini config/laserrunner.cfg
    p2 = os.path.abspath(os.path.join(os.getcwd(), "config", "laserrunner.cfg"))
    if os.path.exists(p2):
        return p2
    return p1

@app.get("/api/config")
def get_config_file():
    cfg_path = _get_cfg_path()
    if not os.path.exists(cfg_path):
        raise HTTPException(status_code=404, detail=f"Yapılandırma dosyası bulunamadı: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"path": cfg_path, "content": content}

@app.post("/api/config")
def save_config_file(req: SaveConfigRequest):
    cfg_path = _get_cfg_path()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(req.content)

        # Yapılandırmayı belleğe yeniden yükle
        controller.config_manager = ConfigManager(cfg_path)
        spm = controller.config_manager.get_steps_per_mm()
        mach = controller.config_manager.get_machine_config()
        controller.kinematics_type = mach.get("kinematics", "cartesian")
        controller.kinematics = controller._build_kinematics(controller.kinematics_type, spm)
        controller.step_generator.kinematics = controller.kinematics
        controller.macro_engine.load_macros_from_config(controller.config_manager.get_macros())

        # TMC sürücü register ayarlarını UART üzerinden hemen güncelle
        if controller.transport.is_connected:
            controller.apply_tmc_configurations()

        return {
            "success": True,
            "message": "laserrunner.cfg başarıyla kaydedildi ve TMC/Kinematik ayarları güncellendi!"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/config/restart")
def restart_laserrunner_service():
    def _do_restart():
        time.sleep(0.5)
        # Linux systemd servisini yeniden başlat
        os.system("echo 19852357 | sudo -S systemctl restart laserrunner")

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"success": True, "message": "LaserRunner servisi yeniden başlatılıyor..."}

# ==========================================
# CANLI TELEMETRİ WEBSOCKET
# ==========================================
@app.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            telemetry = {
                "state": controller.state,
                "connected": (controller.state != MachineState.DISCONNECTED),
                "port": controller.transport.port if (controller.state != MachineState.DISCONNECTED and controller.transport.serial) else "",
                "available_ports": current_available_ports,
                "x": round(controller.pos_x, 2),
                "y": round(controller.pos_y, 2),
                "z": round(controller.pos_z, 2),
                "progress": controller.job_progress,
                "slots": controller.transport.free_slots,
                "diode_temp": controller.diode_temperature,
                "lid_open": controller.lid_open,
                "flame_alert": controller.flame_alert,
                "air_assist": controller.air_assist_active,
                "red_pointer": controller.red_pointer_active,
                "exhaust_fan": controller.exhaust_fan_duty
            }
            await websocket.send_json(telemetry)
            await asyncio.sleep(0.05) # 20 Hz canlı akış
    except WebSocketDisconnect:
        pass

# Web UI Statik Dosya Dağıtımı
web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
