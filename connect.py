import os
import sys
import asyncio
import time
import re

# --- PATH SETUP ---
script_dir = os.path.dirname(os.path.abspath(__file__))
deps_path = os.path.join(script_dir, "deps")
if deps_path not in sys.path:
    sys.path.insert(0, deps_path)

from bleak import BleakClient, BleakScanner
from dicts import CHARACTERISTICS, COMMANDS, AUDIO_GROUPS

# --- HARDWARE COMMUNICATION  ---

def build_audio_packet(audio_cmd, parameter):
    return bytearray(COMMANDS["AUDIO_BASE"] + [audio_cmd, parameter])

async def send_audio_command(client, cmd_uuid, group, clip):
    try:
        await client.write_gatt_char(cmd_uuid, build_audio_packet(0x1f, group), response=False)
        await asyncio.sleep(0.2)
        await client.write_gatt_char(cmd_uuid, build_audio_packet(0x18, clip), response=False)
        return True
    except Exception as e:
        print(f"[*] Audio Command Failed: {e}")
        return False
        
# --- FEATURE LOGIC  ---

async def catalog_scan(client, cmd_uuid):
    for g in range(0, 12):
        print(f"\n[*] SWITCHING TO GROUP {g}...")
        
        for c in range(0, 15):
            if not client.is_connected: 
                print("\n[!] Connection lost during scan.")
                return "LOST"
            
            print(f"[*] Testing G{g} C{c}...")
            await send_audio_command(client, cmd_uuid, g, c)
            
            ans = await asyncio.get_event_loop().run_in_executor(
                None, input, "  Next? (y/n/stop): "
            )
            ans = ans.lower().strip()
            
            if ans == 'n':
                break
            elif ans == 'stop':
                return "STOPPED"
                
    return "FINISHED"

# --- UI & MENU HANDLING ---

def print_menu(current_group, mac, display_name):
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"--- {display_name.upper()} ---")
    print(f"--- ADDR: {mac} | LAST GROUP: {current_group} ---\n")
    
    for g_id, g_name in AUDIO_GROUPS.items():
        print(f"{g_id}: {g_name}")
    
    print("\n[Q] Quit | [SCAN] Catalog All | [G#C#] Play Specific")
    print("-" * 65)

async def droid_menu_loop(client, cmd_uuid, mac, display_name):
    current_group = 0
    
    while True:
        if not client.is_connected:
            print("\n[!] Connection lost.")
            break

        print_menu(current_group, mac, display_name)
        
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "Droid Command > ")
            user_input = user_input.upper().strip()
        except EOFError: break
        
        if user_input == 'Q': break

        if user_input == 'SCAN':
            result = await catalog_scan(client, cmd_uuid)
            if result == "LOST": break
            continue

        # Audio Command parsing
        match = re.match(r"G(\d+)C(\d+)", user_input)
        if match:
            g_val, c_val = map(int, match.groups())
            await send_audio_command(client, cmd_uuid, g_val, c_val)
            current_group = g_val
        elif user_input != '':
            print("[!] Format: G#C# (Example: G0C2)")
            await asyncio.sleep(1.2)

# --- SESSION MANAGEMENT ---

async def auth_sequence(mac: str, display_name: str):
    cmd_uuid = CHARACTERISTICS["COMMAND"]["uuid"]

    print(f"[*] Connecting to {display_name}...")
    device = await BleakScanner.find_device_by_address(mac, timeout=5.0)
    if not device: raise Exception("Droid not found.")

    async with BleakClient(device, timeout=10.0) as client:
        for _ in range(5):
            await client.write_gatt_char(cmd_uuid, bytearray(COMMANDS["LOGON"]), response=False)
            await asyncio.sleep(0.1)

        await send_audio_command(client, cmd_uuid, 0, 0x02) 
        await droid_menu_loop(client, cmd_uuid, mac, display_name)

def connection_menu(droid, target_mac, name=None):
    display_name = name if name else "Unknown Droid"
    try:
        asyncio.run(auth_sequence(target_mac, display_name))
    except Exception as e:
        print(f"\n[!] Session Ended: {e}")
        time.sleep(2)