import os
import subprocess
import time
import re

from dicts import FACTIONS, DROIDS

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
NAMEFILE = os.path.join(BASE_DIR, ".names")

def decode_droid_packet(info_text):
    if "ManufacturerData.Value" not in info_text:
        return None

    try:
        # Isolate and clean hex from multi-line output
        parts = info_text.split("ManufacturerData.Value:")[1].split("AdvertisingFlags:")[0]
        clean_hex = "".join(re.findall(r'[0-9a-fA-F]+', parts)).lower()

        if "0304" in clean_hex:
            start = clean_hex.find("0304")
            payload = clean_hex[start:start+12]

            if len(payload) == 12:
                raw_aff_byte = int(payload[8:10], 16)
                raw_pers_val = int(payload[10:12], 16)
                derived_aff_id = (raw_aff_byte - 0x80) // 2

                chip_name = f"Unknown Chip (0x{raw_pers_val:02X})"
                faction_label = "Unknown Faction"

                for faction_label_candidate, droids_dict in DROIDS.items():
                    for droid_info in droids_dict.values():
                        if droid_info["id"] == raw_pers_val and FACTIONS.get(faction_label_candidate) == derived_aff_id:
                            chip_name = droid_info["name"]
                            faction_label = faction_label_candidate
                            break
                    if faction_label != "Unknown Faction":
                        break

                return f"Faction: {faction_label} | {chip_name}"

    except Exception as e:
        return f"Parse Error: {e}"

    return None

def scan_for_data(bt, target_mac):
    for attempt in range(6):
        bt.send("scan on")
        time.sleep(1.2)
        bt.send("scan off")
        info_text = bt.get_info(target_mac)
        decoded = decode_droid_packet(info_text)
        if decoded:
            return decoded

        time.sleep(0.4)
    return None

def load_friendly_names():
    names = {}
    if os.path.exists(NAMEFILE):
        with open(NAMEFILE, "r") as f:
            for line in f:
                if ":" in line:
                    mac, name = line.strip().split("|")
                    names[mac.upper()] = name
    return names

def save_friendly_name(mac, name):
    names = load_friendly_names()
    names[mac.upper()] = name
    with open(NAMEFILE, "w") as f:
        for mac_addr, n in names.items():
            f.write(f"{mac_addr}|{n}\n")

def scanning_menu(droid):
    friendly_names = load_friendly_names()

    while True:
        os.system('clear')
        print("--- DROID SCANNER ---")

        print("\nScanning for Droids...\n")
        subprocess.run(["bluetoothctl", "--timeout", "4", "scan", "le"], capture_output=True)

        devices = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
        found_macs = [l.split()[1] for l in devices.splitlines() if "DROID" in l.upper()]

        session_droids = []

        if not found_macs:
            print("No Droids found. Try 'R' to Rescan.")
        else:
            for index, mac in enumerate(found_macs, 1):
                mac_upper = mac.upper()
                session_droids.append(mac_upper)
                name = friendly_names.get(mac_upper, "New Droid")

                print(f"[{index}] {name} ({mac_upper})")
                data = scan_for_data(droid.bt, mac)
                if data:
                    print(f"    {data}")
                else:
                    print("    Pulse not captured.")

        print("-" * 50)
        print("R. Rescan | N# Name Droid (e.g. N1) | Q. Back")

        cmd = input("\nSelect > ").lower().strip()

        if not cmd: continue

        if cmd == 'q':
            break
        elif cmd == 'r':
            continue
        elif cmd.startswith('n'):
            try:
                # Extracts the number immediately following 'n' (e.g., 'n1' -> '1')
                num_str = cmd[1:]
                idx = int(num_str) - 1
                target_mac = session_droids[idx]

                new_name = input(f"Enter name for {target_mac}: ").strip()
                if new_name:
                    save_friendly_name(target_mac, new_name)
                    friendly_names = load_friendly_names()
            except (IndexError, ValueError):
                print("!! Invalid format. Use N1, N2, etc.")
                time.sleep(1.5)
