#!/usr/bin/env python3
"""
connect.py - Performs the logic in droid connections
"""

import asyncio
import os
import random
import re
import sys
import threading
import time

from bleak import BleakClient, BleakScanner
from dicts import CHARACTERISTICS, COMMANDS, AUDIO_GROUPS

# ----------------------------------------------------------------------
# Droid Connection (Low Level)
# ----------------------------------------------------------------------
class DroidConnection:
    def __init__(self):
        self.client = None
        self.loop = None
        self.lock = asyncio.Lock()
        self._cmd_uuid = CHARACTERISTICS["COMMAND"]["uuid"]
        
    @property
    def is_connected(self):
        """Status check for the UI"""
        return self.client is not None and self.client.is_connected

    async def _write(self, data: bytearray) -> bool:
        """Low-level GATT write with safety checks and concurrency locking"""
        if not self.is_connected:
            print("[BLE-TX] Write failed: Not connected.")
            return False
        async with self.lock:
            try:
                await self.client.write_gatt_char(self._cmd_uuid, data, response=False)
                return True
            except Exception as e:
                print(f"[BLE ERROR] Failed to send: {e}")
                return False

    async def connect(self, mac: str, on_disconnect=None) -> bool:
        print(f"[BLE] Attempting to find device: {mac}")
        device = await BleakScanner.find_device_by_address(mac, timeout=5.0)
        if not device:
            print(f"[BLE] Device {mac} not found in range.")
            return False

        # In Bleak 0.19.x, the callback is passed here
        self.client = BleakClient(device, timeout=10.0, disconnected_callback=on_disconnect)
        
        try:
            await self.client.connect()
            print(f"[BLE] Connected to {mac}. Sending LOGON handshake...")
            
            for _ in range(3):
                await self._write(bytearray(COMMANDS["LOGON"]))
                await asyncio.sleep(0.2)
            
            await self.send_audio(0, 0x02)
            return True
        except Exception as e:
            print(f"[BLE] Connection failed: {e}")
            self.client = None
            return False

    async def send_audio(self, group: int, clip: int) -> bool:
        """Triggers a droid audio clip by setting the active group followed by the clip ID"""
        base = COMMANDS["AUDIO_BASE"]
        # Set Audio Group
        if await self._write(bytearray(base + [0x1f, group])):
            await asyncio.sleep(0.1)
            # Play Specific Clip
            return await self._write(bytearray(base + [0x18, clip]))
        return False

    async def run_script(self, script_id: int) -> bool:
        """Executes a pre-defined animation/movement script stored on the droid"""            
        packet = bytearray([0x25, 0x00, 0x0C, 0x42, script_id, 0x02])
        return await self._write(packet)

    async def disconnect(self):
        """Graceful teardown of the BLE link"""
        if self.is_connected:
            await self.client.disconnect()
        self.client = None
        
# ----------------------------------------------------------------------
# Connection Manager (High Level)
# ----------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.conn = DroidConnection()
        self.audio_in_progress = False
        
        # New State Tracking
        self.is_connecting = False
        self.last_error = None
        self.active_mac = None
        self.active_name = None

    @property
    def is_connected(self):
        """Check if the droid is currently linked"""
        return self.conn.is_connected if self.conn else False

    def connect_droid(self, mac, name):
        """Initiates a background thread to handle the asynchronous Bleak connection process"""
        if self.is_connecting:
            return
        
        self.is_connecting = True
        self.last_error = None
        self.active_mac = mac
        self.active_name = name
        
        threading.Thread(target=self._connect_thread, args=(mac, name), daemon=True).start()

    def _connect_thread(self, mac, name):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.conn.loop = loop 
        
        stop_event = asyncio.Event()

        def handle_disconnect(_):
            print(f"[BLE] {name} disconnected. Resetting remote state.")
            
            # Clean slate
            if self.remote_control:
                self.remote_control.stop_all()
            
            loop.call_soon_threadsafe(stop_event.set)

        async def run_connection():
            try:
                # Pass the handler into our modified connect method
                success = await asyncio.wait_for(self.conn.connect(mac, on_disconnect=handle_disconnect), timeout=15.0)
                self.is_connecting = False
                
                if not success:
                    self.last_error = f"Failed to connect to {name}"
                    stop_event.set()
                    return

                await stop_event.wait()

            except Exception as e:
                self.last_error = f"Connection Error: {str(e)}"
                stop_event.set()

        try:
            loop.run_until_complete(run_connection())
        finally:
            self.is_connecting = False
            # Hard stop packets for safety if still physically connected
            if self.conn.client and self.conn.client.is_connected:
                loop.run_until_complete(self._emergency_stop_packets())
                loop.run_until_complete(self.conn.disconnect())
            loop.close()

    def run_action(self, label, category):
        """Parses UI button labels and categories to trigger corresponding Bluetooth commands"""
        if not self.is_connected or not self.conn.loop:
            print(f"[CONN] Action '{label}' ignored: No active loop/connection.")
            return

        print(f"[CONN] Dispatching {category} action: {label}")
        if category == "Audio":
            if self.audio_in_progress:
                return
            match = re.match(r"G(\d+)C(\d+)", label)
            if match:
                g, c = map(int, match.groups())
                asyncio.run_coroutine_threadsafe(self._play_audio(g, c), self.conn.loop)
        
        elif category == "Scripts":
            match = re.search(r'\d+', label)
            if match:
                script_id = int(match.group())
                asyncio.run_coroutine_threadsafe(self.conn.run_script(script_id), self.conn.loop)

    async def _play_audio(self, group, clip):
        try:
            self.audio_in_progress = True
            # The 'await' here allows the motor commands to 
            # slip in between the group set and the clip play
            await self.conn.send_audio(group, clip)
        except Exception as e:
            print(f"Audio Task Error: {e}")
        finally:
            # Short cooldown to prevent command overlapping
            await asyncio.sleep(0.2)
            self.audio_in_progress = False

    def disconnect_droid(self):
        """Thread-safe request to disconnect the droid and stop the background event loop"""
        if self.is_connected and self.conn.loop and not self.conn.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.conn.disconnect(), self.conn.loop)
            self.conn.loop.call_soon_threadsafe(self.conn.loop.stop)
        
        self.is_connecting = False
        self.active_mac = None
        self.active_name = None

    def remote_throttle_left(self, speed: float):
        self._send_motor_direct(0, speed) # Motor 0

    def remote_throttle_right(self, speed: float):
        self._send_motor_direct(1, speed) # Motor 1

    def _send_motor_direct(self, motor_id, speed):
        if not self.is_connected:
            return

        mag = abs(speed)
        if mag < 0.05:
            # 27 00 05 44 [MotorID] 00 00 00 00
            packet = bytearray([0x27, 0x00, 0x05, 0x44, motor_id, 0x00, 0x00, 0x00])
            asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)
            return

        # Direction: 0x0 for Fwd, 0x8 for Rev
        dir_nibble = 0x00 if speed > 0 else 0x80
        dm_byte = dir_nibble | motor_id
        
        # SS = Speed (0x60 to 0xFF)
        byte_speed = int(0x60 + (mag * (0xFF - 0x60)))
        
        # Format: 27 00 05 44 DM SS RR RR (RRRR = Ramp 0x012C)
        packet = bytearray([0x27, 0x00, 0x05, 0x44, dm_byte, byte_speed, 0x01, 0x2C])
        asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)

    def bb_drive(self, direction, speed):
        packet = [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x05]
        packet.append(direction)
        packet.append(speed)
        packet.extend([0x01, 0x90, 0x00, 0x00])
        asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)

    def bb_rotate(self, direction, speed):
        packet = [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x04]
        packet.append(direction)
        packet.append(speed)
        packet.extend([0x00, 0x05, 0x00, 0x00])
        asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)

    def remote_head(self, value: float):
        if not self.is_connected:
            return

        mag = abs(value)
        if mag < 0.05:
            # 0x02 is Head Motor ID
            packet = bytearray([0x27, 0x00, 0x05, 0x44, 0x02, 0x00, 0x00, 0x00])
            asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)
            return

        # Use Command 0x0F Type 2 for Head (smoother R2 rotation)
        # Format: 2B 42 0F 48 44 02 XX YY AA AA BB BB
        # XX: 00=Right, FF=Left | YY: Speed | AA: Ramp | BB: Delay
        direction = 0x00 if value > 0 else 0xFF
        byte_speed = int(mag * 0xFF)
        
        packet = bytearray([
            0x2B, 0x42, 0x0F, 0x48, 0x44, 0x02, 
            direction, byte_speed, 0x00, 0x64, 0x00, 0x01
        ])
        asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)

    def remote_sound_random(self):
        """Play a random sound clip (Groups 1–7, Clips 1–7)"""
        if not self.is_connected:
            return

        if self.audio_in_progress:
            return

        group = random.randint(1, 3)
        clip = random.randint(1, 3)
        
        asyncio.run_coroutine_threadsafe(self._play_audio(group, clip), self.conn.loop)
        
    def remote_accessory(self):
        if not self.is_connected:
            return

        # Using the Audio Controller command (0x0F) to trigger accessory logic
        # Command 0x00 CC PP where CC is the command and PP is the parameter
        # Based on typical droid accessory behavior:
        # 27 42 0f 44 44 00 [CMD] [PARAM]
        
        # We send the "Trigger Accessory" signal. 
        # If hardware is present, it moves/sounds. If not, the droid ignores it.
        packet = bytearray([0x27, 0x42, 0x0F, 0x44, 0x44, 0x00, 0x10, 0x08])
        asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)
        
    def remote_stop(self):
        if not self.is_connected:
            return

        # 27 00 05 44 [MotorID] 00 00 00 00
        # Motor IDs: 0 = Left, 1 = Right, 2 = Head
        for motor_id in [0, 1, 2]:
            packet = bytearray([0x27, 0x00, 0x05, 0x44, motor_id, 0x00, 0x00, 0x00])
            asyncio.run_coroutine_threadsafe(self.conn._write(packet), self.conn.loop)
