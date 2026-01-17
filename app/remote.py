#!/usr/bin/env python3

import time
import math

from dicts import CONTROLLER_PROFILES

DEADZONE = 0.15
BB_DRIVE_LIMIT = 0.8
BB_TURN_LIMIT = 0.35

class RemoteControl:
    def __init__(self, conn_mgr):
        self.conn_mgr = conn_mgr
        self.state = {}

    def stop_all(self):
        self.conn_mgr.remote_throttle_left(0.0)
        self.conn_mgr.remote_throttle_right(0.0)
        self.conn_mgr.remote_head(0.0)
        
        self.conn_mgr.bb_drive(0x00, 0x00)
        self.conn_mgr.bb_rotate(0x00, 0x00)
        
        self.state = {}

    def process(self, profile_name, input_mgr):
        profile = CONTROLLER_PROFILES.get(profile_name)
        if not profile:
            return

        intents = {}
        for intent_key, config in profile.items():
            btn_mapping = config.get("btn")
            
            if intent_key in ["THROTTLE", "STEER", "HEAD", "THROTTLE_L", "THROTTLE_R"]:
                if btn_mapping == "R2/L2":
                    val = input_mgr.get_axis_float("R2") - input_mgr.get_axis_float("L2")
                else:
                    val = input_mgr.get_axis_float(btn_mapping)
                    if btn_mapping in ["DY", "RY"]:
                        val = -val
                
                intents[intent_key] = self._dz(val)

            elif btn_mapping in ["A", "B", "X", "Y", "R1", "L1"]:
                if input_mgr.ui_key(btn_mapping):
                    state_key = f"BTN_{btn_mapping}_PRESSED"
                    if not self.state.get(state_key):
                        m_name = config.get("method")
                        if hasattr(self.conn_mgr, m_name):
                            getattr(self.conn_mgr, m_name)()
                        self.state[state_key] = True
                else:
                    self.state[f"BTN_{btn_mapping}_PRESSED"] = False

        self._apply_intents(intents, profile_name)

    def _apply_intents(self, intents, profile_name):
        if profile_name.startswith("R-"):
            t = intents.get("THROTTLE", 0.0)
            s = intents.get("STEER", 0.0)
            h = intents.get("HEAD", 0.0)
            
            tl = intents.get("THROTTLE_L")
            tr = intents.get("THROTTLE_R")

            if tl is not None or tr is not None:
                left_speed = tl if tl is not None else t
                right_speed = tr if tr is not None else t
            else:
                left_speed = t + s
                right_speed = t - s

            self._update_motor("LEFT", left_speed)
            self._update_motor("RIGHT", right_speed)
            self._update_motor("HEAD", h)
            
        elif profile_name.startswith("BB-"):
            drive = intents.get("THROTTLE", 0.0)
            head = intents.get("HEAD", 0.0)
            self._handle_bb_movement(drive, head)

    def _handle_bb_movement(self, drive, head):
        last_d = self.state.get("LAST_BB_DRIVE", 0.0)
        last_h = self.state.get("LAST_BB_HEAD", 0.0)

        if drive == 0 and head == 0:
            if last_d != 0 or last_h != 0:
                self.conn_mgr.bb_drive(0x00, 0x00)
                self.state.update({"LAST_BB_DRIVE": 0.0, "LAST_BB_HEAD": 0.0})
            return

        if abs(drive) > 0.05:
            if abs(drive - last_d) > 0.02:
                heading = 0x00 if drive > 0 else 0x80
                speed = int(abs(drive) * 255 * BB_DRIVE_LIMIT)
                self.conn_mgr.bb_drive(heading, speed)
                self.state["LAST_BB_DRIVE"] = drive
        elif last_d != 0:
            self.conn_mgr.bb_drive(0x00, 0x00)
            self.state["LAST_BB_DRIVE"] = 0.0

        if abs(head) > 0.05:
            if abs(head - last_h) > 0.02:
                rot_speed = int(abs(head) * 255 * BB_TURN_LIMIT)
                direction = 0x00 if head > 0 else 0xFF
                self.conn_mgr.bb_rotate(direction, rot_speed)
                self.state["LAST_BB_HEAD"] = head
        elif last_h != 0:
            self.conn_mgr.bb_rotate(0x00, 0x00)
            self.state["LAST_BB_HEAD"] = 0.0

    def _dz(self, v):
        return 0.0 if abs(v) < DEADZONE else v
        
    def _update_motor(self, key, speed):
        last_spd = self.state.get(f"LAST_{key}", 0.0)
        safe_speed = max(-1.0, min(1.0, speed))
        
        should_update = (abs(safe_speed - last_spd) > 0.05) or (safe_speed == 0.0 and last_spd != 0.0)

        if should_update:
            if key == "LEFT":
                self.conn_mgr.remote_throttle_left(safe_speed)
            elif key == "RIGHT":
                self.conn_mgr.remote_throttle_right(safe_speed)
            elif key == "HEAD":
                self.conn_mgr.remote_head(safe_speed)
            self.state[f"LAST_{key}"] = safe_speed

    def get_hints(self, profile_name):
        profile = CONTROLLER_PROFILES.get(profile_name, {})
        hints = {}
        for intent, config in profile.items():
            btn = config.get("btn")
            label = intent.replace("THROTTLE", "DRIVE").replace("STEER", "TURN")
            hints[btn] = label.title()
        return hints