import os
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import serial.tools.list_ports

from ..core.controller import LaserRunnerController, MachineState
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

class ConfigRequest(BaseModel):
    kinematics: str = "cartesian"
    steps_per_mm_x: float = 80.0
    steps_per_mm_y: float = 80.0
    steps_per_mm_z: float = 400.0
    acceleration: float = 3000.0

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
        "kinematics": controller.kinematics_type
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
    controller.jog(dx=req.dx, dy=req.dy, dz=req.dz, speed_mm_s=req.speed)
    return {"status": "ok"}

@app.post("/api/laser/test")
def test_laser(req: LaserPowerRequest):
    controller.set_manual_laser(req.power_percent)
    return {"status": "ok", "power": req.power_percent}

@app.post("/api/estop")
def emergency_stop():
    controller.emergency_stop()
    return {"status": "estop_triggered"}

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
# CANLI TELEMETRİ WEBSOCKET
# ==========================================
@app.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            telemetry = {
                "state": controller.state,
                "x": controller.pos_x,
                "y": controller.pos_y,
                "z": controller.pos_z,
                "progress": controller.job_progress,
                "slots": controller.transport.free_slots
            }
            await websocket.send_json(telemetry)
            await asyncio.sleep(0.05) # 20 Hz canlı akış
    except WebSocketDisconnect:
        pass

# Web UI Statik Dosya Dağıtımı
web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
