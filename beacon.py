import os
import time
from bluetoothctl import BluetoothCtl

from dicts import LOCATIONS, FACTIONS, DROIDS

BEACON_PROTOCOL = {
    "MFG_ID": 0x0183,        # Manufacturer ID
    "DATA_LEN": 0x04,        # The length of the remaining data after the header
    "DROID_HEADER": 0x44,    # This byte is probably a guard in addition to the beacon type, to prevent accidental triggers by unrelated beacons
    "STATUS_FLAG": 0x81,     # 0x01 if droid is not paired with a remote, 0x81 if it is
    "ACTIVE_FLAG": 0x01,     # Possibly a receiver-facing active flag; would allow beacons to be logically enabled/disabled without relying on radio silence
}

BEACON_TYPE = {
    "LOCATION": 0x0A,
    "DROID":    0x03,
}

RSSI_THRESHOLD = {
    "NEAR": 0xBA,    # (-70 dBm): Very close, high signal
    "MID":  0xA6,    # (-90 dBm): Small room/standard distance
    "FAR":  0x9C,    # (-100 dBm): Large room or through light obstruction
    "MAX":  0x8C,    # (-116 dBm): Maximum range before drop-off
}

class DroidController:
    def __init__(self, bt: BluetoothCtl):
        self.bt = bt
        self.current_active = "None"
        self.hw_status = "Unknown"
        self.adapter_info = "N/A"
        self.check_capabilities()
        self.bt.send("scan off")
        self.debug_msg = ""

    def check_capabilities(self):
        try:
            import subprocess
            res = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True, timeout=2)
            self.hw_status = "READY" if "Powered: yes" in res.stdout else "OFF"
            for line in res.stdout.splitlines():
                if line.strip().startswith("Controller"):
                    self.adapter_info = line.replace("Controller", "").strip()
                    break
        except Exception:
            self.hw_status = "ERROR"

    def send_payload(self, name, payload):
        # Format raw payload into parts for the BT controller
        raw = payload.replace("0x", "").replace(" ", "")
        mfg_id = f"0x{raw[:4]}"
        mfg_data = " ".join(f"0x{raw[i:i+2]}" for i in range(4, len(raw), 2))

        # Broadcast it
        self.bt.broadcast_mfg(mfg_id, mfg_data)

        # Update UI
        self.current_active = name
        self.debug_msg = f"{mfg_id} {mfg_data}"

    def activate_location(self, loc_id, name, cooldown_byte):
        payload = (
            f"0x{BEACON_PROTOCOL['MFG_ID']:04X} "
            f"0x{BEACON_TYPE['LOCATION']:02X} "
            f"0x{BEACON_PROTOCOL['DATA_LEN']:02X} "
            f"0x{loc_id:02X} "
            f"0x{cooldown_byte:02X} "
            f"0x{RSSI_THRESHOLD['MID']:02X} "
            f"0x{BEACON_PROTOCOL['ACTIVE_FLAG']:02X} "
        )
        self.send_payload(name, payload)

    def activate_droid(self, p_id, p_name, aff_id):
        aff_byte = 0x80 + (aff_id * 2)
        payload = (
            f"0x{BEACON_PROTOCOL['MFG_ID']:04X} "
            f"0x{BEACON_TYPE['DROID']:02X} "
            f"0x{BEACON_PROTOCOL['DATA_LEN']:02X} "
            f"0x{BEACON_PROTOCOL['DROID_HEADER']:02X} "
            f"0x{BEACON_PROTOCOL['STATUS_FLAG']:02X} "
            f"0x{aff_byte:02X} "
            f"0x{p_id:02X}"
        )

        aff_label = next((name for name, id in FACTIONS.items() if id == aff_id), "Unknown")
        self.send_payload(f"{aff_label}: {p_name}", payload)

    def stop(self):
        self.bt.stop_advertising()
        self.current_active = "None (Stopped)"
        self.debug_msg = ""

    def shutdown(self):
        self.bt.close()
        self.current_active = "System Offline"

# UI functions
def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def show_header(droid):
    clear_screen()
    debug_str = f"{droid.debug_msg}"
    print(f"--- DROID BEACON CONTROL ---")
    print(f"Status: {droid.hw_status} | Active: {droid.current_active}")
    print(f"Payload: {debug_str}")
    print("-" * 48)

def submenu(droid, title, data_dict, is_location=False):
    while True:
        show_header(droid)
        print(f"\n[{title}]\n")
        # Display menu
        for key, val in sorted(data_dict.items()):
            display_name = val[1] if is_location else val['name']
            print(f" {key}. {display_name}")

        print(f"\n S. Stop Advertising")
        print(f" B. Back to Main Menu")
        print(f" Q. Stop & Exit to Main Menu")

        choice = input("\nSelect > ").upper().strip()

        if choice == 'B':
            return "CONTINUE"
        if choice == 'Q':
            droid.stop()
            return "QUIT_SUBMENU"
        if choice == 'S':
            droid.stop()
        elif choice in map(str, data_dict.keys()):
            # Convert key to correct type
            first_key = next(iter(data_dict))
            key = int(choice) if isinstance(first_key, int) else choice
            selected = data_dict[key]

            if is_location:
                loc_id, loc_name, cooldown = selected
                droid.activate_location(loc_id, loc_name, cooldown)
            else:
                aff_id = FACTIONS[title]
                droid.activate_droid(selected['id'], selected['name'], aff_id)


def beacon_menu(droid: DroidController):
    try:
        while True:
            show_header(droid)
            print("\n1. Location Beacons")
            faction_keys = list(DROIDS.keys())
            for i, faction in enumerate(faction_keys, start=2):
                print(f"{i}. {faction} Droids")

            print("\nS. Stop Advertising")
            print("Q. Quit Application")

            choice = input("\nSelect Category > ").upper().strip()

            if choice == '1':
                res = submenu(droid, "LOCATIONS", LOCATIONS, is_location=True)
            elif choice in map(str, range(2, 2 + len(faction_keys))):
                faction = faction_keys[int(choice)-2]
                res = submenu(droid, faction, DROIDS[faction])
            elif choice == 'S':
                droid.stop()
            elif choice == 'Q':
                break
            else:
                continue

            if res == "QUIT_SUBMENU":
                continue

    finally:
        droid.stop()
