from dicts import BEACON_PROTOCOL, BEACON_TYPE, RSSI_THRESHOLD, FACTIONS

class DroidBeacon:
    def __init__(self, bt_controller):
        self.bt = bt_controller
        self.current_active = "None"
        self.debug_payload = ""

    def send_payload(self, name, payload):
        """Formats and broadcasts the raw hex payload."""
        raw = payload.replace("0x", "").replace(" ", "")
        mfg_id = f"0x{raw[:4]}"
        mfg_data = " ".join(f"0x{raw[i:i+2]}" for i in range(4, len(raw), 2))

        self.bt.broadcast_mfg(mfg_id, mfg_data)
        self.current_active = name
        self.debug_payload = f"{mfg_id} {mfg_data}"

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

    def activate_droid(self, p_id, p_name, faction_name):
        aff_id = FACTIONS[faction_name]
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
        self.send_payload(f"{faction_name}: {p_name}", payload)

    def stop(self):
        self.bt.stop_advertising()
        self.current_active = "None (Stopped)"
        self.debug_payload = ""