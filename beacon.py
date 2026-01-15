import threading
import time

from dicts import BEACON_PROTOCOL, BEACON_TYPE, RSSI_THRESHOLD, FACTIONS, LOCATIONS, DROIDS

# ----------------------------------------------------------------------
# Droid Beacon (Low Level)
# ----------------------------------------------------------------------
class DroidBeacon:
    def __init__(self, bt_controller):
        self.bt = bt_controller
        self.current_active = "None"
        self.debug_payload = ""
        self.thread = None
        self.stop_event = threading.Event()
        self._lock = threading.Lock()

    def _send_payload(self, name, payload):
        """Formats the hex string into raw manufacturer data and triggers the BT broadcast"""
        raw = payload.replace("0x", "").replace(" ", "").replace(",", "")
        mfg_id = f"0x{raw[:4]}"
        mfg_data = " ".join(f"0x{raw[i:i+2]}" for i in range(4, len(raw), 2))

        with self._lock:
            try:
                self.bt.broadcast_mfg(mfg_id, mfg_data)
                self.current_active = name
                self.debug_payload = f"{mfg_id} {mfg_data}"
            except Exception:
                pass

    def activate_location(self, loc_id, name, cooldown_byte):
        """Builds the byte payload for a Location beacon"""
        payload = (
            f"0x{BEACON_PROTOCOL['MFG_ID']:04X} "
            f"0x{BEACON_TYPE['LOCATION']:02X} "
            f"0x{BEACON_PROTOCOL['DATA_LEN']:02X} "
            f"0x{loc_id:02X} "
            f"0x{cooldown_byte:02X} "
            f"0x{RSSI_THRESHOLD['MID']:02X} "
            f"0x{BEACON_PROTOCOL['ACTIVE_FLAG']:02X} "
        )
        self._send_payload(name, payload)

    def activate_droid(self, p_id, p_name, faction_name):
        """Constructs the byte payload to simulate a specific droid's presence"""
        aff_id = FACTIONS.get(faction_name, 0x01)
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
        self._send_payload(p_name, payload)

    def stop(self):
        """Stops the advertisement and resets the beacon's internal status"""
        self.stop_event.set()
        with self._lock:
            try:
                self.bt.stop_advertising()
            except Exception:
                pass
            self.current_active = "None"
            self.debug_payload = ""
        
    def start_loop(self, target_type, target_id, faction=None, **kwargs):
        """Creates a background loop that periodically refreshes the beacon broadcast"""
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=0.2)

        self.stop_event.clear()

        def loop():
            while not self.stop_event.is_set():
                try:
                    wait_time = 1.5
                    
                    if target_type == "location":
                        data = LOCATIONS.get(target_id)
                        if data:
                            self.activate_location(target_id, data[1], data[2])
                            wait_time = max(1.0, data[2] * 5)
                    elif target_type == "droid":
                        f_data = DROIDS.get(faction, {})
                        d_data = f_data.get(target_id)
                        if d_data:
                            self.activate_droid(d_data["id"], d_data["name"], faction)
                            wait_time = 2.0
                    
                    end_sleep = time.time() + wait_time
                    while time.time() < end_sleep and not self.stop_event.is_set():
                        time.sleep(0.1)
                except Exception:
                    time.sleep(1.0)

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

# ----------------------------------------------------------------------
# Beacon Manager (High Level)
# ----------------------------------------------------------------------
class BeaconManager:
    def __init__(self, bt_controller):
        self.bt = bt_controller
        self.droid_beacon = DroidBeacon(self.bt)
        self.thread = None

    def start_location(self, loc_id, name):
        """Interface method to begin broadcasting a specific Location ID"""
        self._run(target_type="location", target_id=loc_id)

    def start_droid(self, faction, droid_id, name):
        """Interface method to begin broadcasting as a specific Droid personality"""
        self._run(target_type="droid", target_id=droid_id, faction=faction)

    def _run(self, **kwargs):
        """Manages the lifecycle of the BeaconLoopThread for non-blocking execution"""
        self.stop()
        self.thread = threading.Thread(
            target=self.droid_beacon.start_loop,
            kwargs=kwargs,
            name="BeaconLoopThread",
            daemon=True
        )
        self.thread.start()

    def stop(self):
        """Calls the low-level stop logic and ensures the management thread is cleared"""
        self.droid_beacon.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.1)

    @property
    def current_active(self):
        """Returns the name of the currently active broadcast for UI display"""
        return self.droid_beacon.current_active