import unittest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "host"))

from laserrunner.protocol.codec import (
    ProtocolCodec, calculate_crc16,
    CMD_PING, RESP_ACK, RESP_STATUS, CMD_QUEUE_MOTION
)
from laserrunner.kinematics.cartesian import CartesianKinematics
from laserrunner.kinematics.corexy import CoreXYKinematics
from laserrunner.kinematics.awd_corexy import AWDCoreXYKinematics
from laserrunner.planner.laser_power import LaserPowerController
from laserrunner.planner.trajectory import TrajectoryPlanner
from laserrunner.planner.step_generator import StepGenerator
from laserrunner.cam.framing import FramingEngine
from laserrunner.cam.raster_engine import RasterEngine

class TestLaserRunner(unittest.TestCase):
    def setUp(self):
        self.codec = ProtocolCodec()

    def test_crc16(self):
        data = b"123456789"
        crc = calculate_crc16(data)
        # 123456789 için bilinen CRC16-CCITT değeri: 0x29B1
        self.assertEqual(crc, 0x29B1)

    def test_protocol_packet_encoding(self):
        frame = self.codec.encode_ping(123456)
        self.assertEqual(frame[0], 0xAA)
        self.assertEqual(frame[1], 0x55)
        self.assertEqual(frame[2], 4) # Payload len
        self.assertEqual(frame[4], CMD_PING)

    def test_protocol_packet_decoding(self):
        ack_payload = bytes([12, 48]) # seq 12, free slots 48
        decoded = self.codec.decode_packet(RESP_ACK, ack_payload)
        self.assertEqual(decoded["type"], "ACK")
        self.assertEqual(decoded["seq_id"], 12)
        self.assertEqual(decoded["free_slots"], 48)

    def test_cartesian_kinematics(self):
        k = CartesianKinematics({"x": 80.0, "y": 80.0, "z": 400.0}, dual_y=True)
        # 10 mm X, 20 mm Y hareketi
        sx, sy1, sy2, sz, dir_bits = k.cartesian_to_actuators(10.0, 20.0, 0.0)
        self.assertEqual(sx, 800)
        self.assertEqual(sy1, 1600)
        self.assertEqual(sy2, 1600)
        self.assertEqual(sz, 0)
        self.assertEqual(dir_bits, 0x07) # X+, Y1+, Y2+

    def test_corexy_kinematics(self):
        k = CoreXYKinematics({"x": 80.0, "y": 80.0, "z": 400.0})
        # Sadece X ekseninde 10mm hareket: Delta A = 10, Delta B = 10
        sa, sb, _, _, _ = k.cartesian_to_actuators(10.0, 0.0, 0.0)
        self.assertEqual(sa, 800)
        self.assertEqual(sb, 800)

    def test_awd_corexy_kinematics(self):
        k = AWDCoreXYKinematics({"xy": 80.0})
        sa1, sb1, sa2, sb2, _ = k.cartesian_to_actuators(5.0, 5.0, 0.0)
        # Delta A = 10mm (800 step), Delta B = 0mm (0 step)
        self.assertEqual(sa1, 800)
        self.assertEqual(sa2, 800)
        self.assertEqual(sb1, 0)
        self.assertEqual(sb2, 0)

    def test_laser_dynamic_power_scaling(self):
        lp = LaserPowerController(min_power_ratio=0.1)
        # Tam hızda nominal güç %100 olmalı
        full_pwr = lp.calculate_power(current_speed_mm_s=50.0, nominal_speed_mm_s=50.0, target_power_raw=4095)
        self.assertEqual(full_pwr, 4095)

        # Yarı hızda güç lineer düşmeli
        half_pwr = lp.calculate_power(current_speed_mm_s=25.0, nominal_speed_mm_s=50.0, target_power_raw=4095)
        self.assertTrue(2200 <= half_pwr <= 2300)

        # Sıfır hızda taban güç oranına inmeli
        min_pwr = lp.calculate_power(current_speed_mm_s=0.0, nominal_speed_mm_s=50.0, target_power_raw=4095)
        self.assertEqual(min_pwr, 410)

    def test_trajectory_planner_and_step_generator(self):
        planner = TrajectoryPlanner(acceleration_mm_s2=2000.0)
        kinematics = CartesianKinematics({"x": 80.0, "y": 80.0, "z": 400.0})
        step_gen = StepGenerator(kinematics)

        segments = planner.plan_move(
            dx=50.0, dy=0.0, dz=0.0,
            target_speed=100.0,
            target_power=3000
        )
        self.assertTrue(len(segments) >= 2) # En az ivmelenme ve yavaşlama

        blocks = [step_gen.segment_to_motion_block(s) for s in segments]
        total_steps = sum(b["total_steps"] for b in blocks if b)
        self.assertEqual(total_steps, 50 * 80) # 4000 adım

    def test_framing_engine(self):
        moves = FramingEngine.generate_bounding_box_frame(0, 0, 100, 50)
        self.assertEqual(len(moves), 5) # 1 yaklaşım + 4 kenar
        self.assertEqual(moves[0]["type"], "RAPID")
        self.assertEqual(moves[1]["type"], "FRAME")

    def test_aux_output_and_sensors(self):
        # 1. Aux Çıkış Paketi Kodlama (Air assist ON)
        frame = self.codec.encode_set_aux_output(1, 1)
        self.assertEqual(frame[4], 0x08) # CMD_SET_AUX_OUTPUT
        self.assertEqual(frame[5], 1)    # AUX_AIR_ASSIST
        self.assertEqual(frame[6], 0)
        self.assertEqual(frame[7], 1)

        # 2. Genişletilmiş Durum Paketi Çözümleme (Sıcaklık 38.5°C, Kapak Açık, Alev Yok)
        import struct
        status_payload = struct.pack(
            "<IiiiHBBhBB",
            1000, 0, 0, 0, 0, 32, 0, 385, 0x01, 0x03
        )
        decoded = self.codec.decode_packet(0x82, status_payload)
        self.assertEqual(decoded["type"], "STATUS")
        self.assertEqual(decoded["diode_temp_c"], 38.5)
        self.assertTrue(decoded["lid_open"])
        self.assertFalse(decoded["flame_alert"])
        self.assertEqual(decoded["endstops"], 0x03)

    def test_config_manager(self):
        from laserrunner.core.config_manager import ConfigManager
        cfg = ConfigManager()
        mach = cfg.get_machine_config()
        self.assertEqual(mach["kinematics"], "cartesian")
        self.assertEqual(mach["max_acceleration"], 3000.0)

        spm = cfg.get_steps_per_mm()
        self.assertEqual(spm["x"], 80.0)
        self.assertEqual(spm["y"], 80.0)

        tmc = cfg.get_tmc_drivers()
        self.assertIn("stepper_x", tmc)
        self.assertEqual(tmc["stepper_x"]["run_current"], 0.800)
        self.assertEqual(tmc["stepper_x"]["sgthrs"], 65)
        self.assertEqual(tmc["stepper_x"]["mode"], "spreadcycle")
        self.assertEqual(tmc["stepper_x"]["mode_code"], 0)

        self.assertIn("stepper_z", tmc)
        self.assertEqual(tmc["stepper_z"]["mode"], "stealthchop")
        self.assertEqual(tmc["stepper_z"]["mode_code"], 1)

    def test_tmc_packet_encoding(self):
        # Motor 0 (X), SpreadCycle (0), 800mA, 400mA, 16 microsteps, interpolate, 0 thresh, 65 sgthrs
        frame = self.codec.encode_config_tmc(0, 0, 800, 400, 16, True, 0, 65)
        self.assertEqual(frame[4], 0x0A) # CMD_CONFIG_TMC
        self.assertEqual(frame[2], 12)   # 12 bytes payload
        self.assertEqual(frame[5], 0)    # motor_id 0
        self.assertEqual(frame[6], 0)    # mode SpreadCycle

    def test_rotation_distance(self):
        from laserrunner.core.config_manager import ConfigManager
        cfg = ConfigManager()
        spm = cfg.get_steps_per_mm()
        # rotation_distance: 40, full_steps: 200, microsteps: 16 -> (200 * 16) / 40 = 80.0
        self.assertEqual(spm["x"], 80.0)
        self.assertEqual(spm["y"], 80.0)
        # Z: rotation_distance: 8, (200 * 16) / 8 = 400.0
        self.assertEqual(spm["z"], 400.0)

    def test_input_shaper(self):
        from laserrunner.planner.input_shaper import InputShaper
        shaper = InputShaper({"shaper_type_x": "mzv", "shaper_freq_x": 50.0, "damping_ratio_x": 0.1})
        pulses = shaper.pulses_x
        self.assertEqual(len(pulses), 3) # MZV 3 darbeli
        total_amp = sum(p[0] for p in pulses)
        self.assertAlmostEqual(total_amp, 1.0, places=4)
        self.assertTrue(shaper.get_shaping_delay("x") > 0)

    def test_macro_engine(self):
        from laserrunner.planner.macro_engine import MacroEngine
        me = MacroEngine()
        me.register_macro("TEST_CUT", "M7\nM3 S{params.POWER|default(1000)}\nG4 P{params.WAIT|default(200)}")
        
        # 1. Varsayılan parametrelerle çalıştırma
        lines = me.execute_macro("TEST_CUT")
        self.assertEqual(lines[0], "M7")
        self.assertEqual(lines[1], "M3 S1000")
        self.assertEqual(lines[2], "G4 P200")

        # 2. Özel parametrelerle çalıştırma
        lines_custom = me.execute_macro("TEST_CUT", {"POWER": 2500, "WAIT": 500})
        self.assertEqual(lines_custom[1], "M3 S2500")
        self.assertEqual(lines_custom[2], "G4 P500")

    def test_verification_manager(self):
        from laserrunner.core.verification import VerificationManager
        from laserrunner.core.config_manager import ConfigManager
        cfg = ConfigManager()
        vm = VerificationManager(controller=None, config_manager=cfg)
        
        # Endstop testi
        endstops = vm.query_endstops()
        self.assertIn("x", endstops)
        self.assertIn("lid", endstops)

        # TMC dökümü
        tmc_dump = vm.dump_tmc("stepper_x")
        self.assertTrue(tmc_dump["success"])
        self.assertEqual(tmc_dump["mode"], "SPREADCYCLE")
        self.assertEqual(tmc_dump["run_current_ma"], 800)

if __name__ == "__main__":
    unittest.main()
