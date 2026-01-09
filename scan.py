import os
import re
import subprocess
import time

from dicts import FACTIONS, DROIDS

class DroidScanner:
    def __init__(self, bt_controller):
        self.bt = bt_controller
        self.base_dir = os.path.dirname(os.path.realpath(__file__))
        self.namefile = os.path.join(self.base_dir, ".names")

    def get_found_macs(self):
        """Returns list of MACs from bluetoothctl with 'DROID' in the name."""
        devices = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout
        return [l.split()[1] for l in devices.splitlines() if "DROID" in l.upper()]

    def decode_info(self, mac):
        """Gets info for a MAC and decodes the personality/faction."""
        info_text = self.bt.get_info(mac)
        if "ManufacturerData.Value" not in info_text:
            return None

        try:
            parts = info_text.split("ManufacturerData.Value:")[1].split("AdvertisingFlags:")[0]
            clean_hex = "".join(re.findall(r'[0-9a-fA-F]+', parts)).lower()

            # Look for that Disney Magic(tm)
            if "0304" in clean_hex:
                start = clean_hex.find("0304")
                payload = clean_hex[start:start+12]
                if len(payload) == 12:
                    raw_aff_byte = int(payload[8:10], 16)
                    raw_pers_val = int(payload[10:12], 16)
                    derived_aff_id = (raw_aff_byte - 0x80) // 2

                    chip_name = f"Unknown (0x{raw_pers_val:02X})"
                    faction_label = f"Unknown ({derived_aff_id})"

                    for f_label, droids_dict in DROIDS.items():
                        if FACTIONS.get(f_label) == derived_aff_id:
                            faction_label = f_label
                            for d_info in droids_dict.values():
                                if d_info["id"] == raw_pers_val:
                                    chip_name = d_info["name"]
                                    break
                            break
                    return f"{faction_label} | {chip_name}"
        except:
            return "Parse Error"
        return None

    def load_names(self):
        names = {}
        if os.path.exists(self.namefile):
            with open(self.namefile, "r") as f:
                for line in f:
                    if "|" in line:
                        mac, name = line.strip().split("|", 1)
                        names[mac.upper()] = name
        return names

    def save_name(self, mac, name):
        names = self.load_names()
        names[mac.upper()] = name
        with open(self.namefile, "w") as f:
            for mac_addr, n in names.items():
                f.write(f"{mac_addr}|{n}\n")