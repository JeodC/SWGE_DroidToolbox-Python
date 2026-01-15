#!/usr/bin/env python3
"""
connect.py - Performs the logic in droid connections
"""

import asyncio
import os
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
            return False
        async with self.lock:
            try:
                await self.client.write_gatt_char(self._cmd_uuid, data, response=False)
                return True
            except Exception:
                return False

    async def connect(self, mac: str) -> bool:
        """Connects and performs the mandatory LOGON handshake"""
        device = await BleakScanner.find_device_by_address(mac, timeout=5.0)
        if not device:
            return False

        self.client = BleakClient(device, timeout=10.0)
        try:
            await self.client.connect()
            
            # Auth handshake: Needs a few repetitions to guarantee pickup
            for _ in range(3):
                await self._write(bytearray(COMMANDS["LOGON"]))
                await asyncio.sleep(0.1)
            
            # Success sound (Group 0, Clip 2)
            await self.send_audio(0, 0x02)
            return True
        except Exception:
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
        """Thread worker that manages the asyncio event loop required for BLE operations"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.conn.loop = loop 
        
        try:
            success = loop.run_until_complete(asyncio.wait_for(self.conn.connect(mac), timeout=15.0))
            
            if not success:
                self.last_error = f"Failed to connect to {name}"
                self.is_connecting = False
                return

            loop.run_forever()
        except asyncio.TimeoutError:
            self.last_error = f"Connection to {name} timed out"
        except Exception as e:
            self.last_error = f"Connection Error: {str(e)}"
        finally:
            self.is_connecting = False
            self.conn.client = None

    def run_action(self, label, category):
        """Parses UI button labels and categories to trigger corresponding Bluetooth commands"""
        if not self.is_connected or not self.conn.loop:
            return

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
        """Asynchronous wrapper to prevent multiple audio commands from overlapping"""
        try:
            self.audio_in_progress = True
            group_idx = group         
            await self.conn.send_audio(group_idx, clip)
        except Exception as e:
            print(f"Audio Task Error: {e}")
        finally:
            self.audio_in_progress = False

    def disconnect_droid(self):
        """Thread-safe request to disconnect the droid and stop the background event loop"""
        if self.is_connected and self.conn.loop and not self.conn.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.conn.disconnect(), self.conn.loop)
            self.conn.loop.call_soon_threadsafe(self.conn.loop.stop)
        
        self.is_connecting = False
        self.active_mac = None
        self.active_name = None