import asyncio
import os
import re
import sys
import time

# --- PATH SETUP ---
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(script_dir, "deps"))

from bleak import BleakClient, BleakScanner
from dicts import CHARACTERISTICS, COMMANDS, AUDIO_GROUPS

class DroidConnection:
    def __init__(self, bt_controller):
        self.bt = bt_controller
        self.client = None
        self.cmd_uuid = CHARACTERISTICS["COMMAND"]["uuid"]
        
    @property
    def is_connected(self):
        return self.client is not None and self.client.is_connected

    async def send_audio(self, group, clip):
        """Sends the two-step audio command."""
        if not self.client or not self.client.is_connected:
            return False
        try:
            base = COMMANDS["AUDIO_BASE"]
            # Set Group
            await self.client.write_gatt_char(self.cmd_uuid, bytearray(base + [0x1f, group]), response=False)
            await asyncio.sleep(0.1)
            # Play Clip
            await self.client.write_gatt_char(self.cmd_uuid, bytearray(base + [0x18, clip]), response=False)
            return True
        except:
            return False

    async def run_script(self, script_id):
        """Sends a script execution packet."""
        if not self.client or not self.client.is_connected or script_id in [19, 0x13]:
            return False
        try:
            packet = bytearray([0x25, 0x00, 0x0C, 0x42, script_id, 0x02])
            await self.client.write_gatt_char(self.cmd_uuid, packet, response=False)
            return True
        except:
            return False

    async def connect(self, mac):
        """Handles connection and auth, returns success bool."""
        device = await BleakScanner.find_device_by_address(mac, timeout=5.0)
        if not device:
            return False

        self.client = BleakClient(device, timeout=10.0)
        await self.client.connect()
        
        # Auth handshake
        for _ in range(3):
            await self.client.write_gatt_char(self.cmd_uuid, bytearray(COMMANDS["LOGON"]), response=False)
            await asyncio.sleep(0.1)
        
        # Success sound
        await self.send_audio(0, 0x02)
        return True

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.client = None