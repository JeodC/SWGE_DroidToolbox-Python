#!/usr/bin/env python3
"""
scan.py - Performs the logic in scan actions
"""

import os
import re
import subprocess
import time
import threading
from itertools import cycle

from dicts import FACTIONS, DROIDS

# ----------------------------------------------------------------------
# DroidScanner (Low Level)
# ----------------------------------------------------------------------
class DroidScanner:
    def __init__(self, bt_controller):
        self.bt = bt_controller
        self.base_dir = os.path.dirname(os.path.realpath(__file__))

    def _get_raw_devices(self):
        """Directly queries the OS for visible Bluetooth devices"""
        return subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True).stdout

    def _parse_personality(self, info_text):
        """Parses hex code to determine the personality and faction of a droid"""
        if not info_text or "ManufacturerData.Value" not in info_text:
            return None
        try:
            parts = info_text.split("ManufacturerData.Value:")[1]
            
            if "AdvertisingFlags" in parts:
                parts = parts.split("AdvertisingFlags:")[0]
            elif "RSSI" in parts:
                parts = parts.split("RSSI:")[0]

            clean_hex = "".join(re.findall(r'[0-9a-fA-F]+', parts)).lower()

            if "0304" in clean_hex:
                start = clean_hex.find("0304")
                payload = clean_hex[start:start+12]

                if len(payload) == 12:
                    raw_aff_byte = int(payload[8:10], 16)
                    raw_pers_val = int(payload[10:12], 16)
                    derived_aff_id = (raw_aff_byte - 0x80) // 2

                    chip_name = "Droid"
                    faction_label = ""

                    for f_label, droids_dict in DROIDS.items():
                        if FACTIONS.get(f_label) == derived_aff_id:
                            faction_label = f_label.capitalize()
                            for d_info in droids_dict.values():
                                if d_info["id"] == raw_pers_val:
                                    chip_name = d_info["name"]
                                    break
                            break
                    
                    if faction_label:
                        return f"{chip_name} ({faction_label})"
                    return chip_name
        except Exception as e:
            print(f"DEBUG: Parse Error -> {e}")
            return None
        return None

    def scan_for_droids(self):
        """Returns a list of MAC addresses identified as 'DROID'"""
        raw_output = self._get_raw_devices()
        return [l.split()[1] for l in raw_output.splitlines() if "DROID" in l.upper()]

    def get_droid_identity(self, mac):
        """Returns the Faction and Personality name for a given MAC"""
        info_text = self.bt.get_info(mac)
        return self._parse_personality(info_text)


# ----------------------------------------------------------------------
# Scan Manager (High Level)
# ----------------------------------------------------------------------
class ScanManager:
    def __init__(self, bt_controller, lock=None, favorites=None, progress_callback=None):
        self.bt = bt_controller
        self.scanner = DroidScanner(bt_controller)
        self._lock = lock or threading.Lock()
        self.favorites = favorites or {}
        self.scanning = False
        self.scan_results = []
        self.last_error = None
        self.progress_callback = progress_callback

    def _update_progress(self, msg):
        """Triggers the UI callback to update the user on scan status"""
        if self.progress_callback:
            self.progress_callback(msg)

    def start_scan(self, duration=2.0):
        """Initiates the background thread to perform a non-blocking device scan"""
        if self.scanning:
            return
        
        self.scanning = True
        self.last_error = None
        threading.Thread(target=self._scan_thread, args=(duration,), daemon=True, name="ScanningThread").start()
        
    def stop_scan(self):
        """Signals the Bluetooth controller to cease discovery and updates state"""
        if self.scanning:
            try:
                self.bt.stop_scanning()
            except Exception:
                pass
            self.scanning = False

    def _scan_thread(self, duration):
        try:
            with self._lock:
                self.scan_results = []
            
            self.bt.power_on()  
            self.bt.start_scanning()
            time.sleep(duration)
            self.bt.stop_scanning()
            
            # Increase this to allow the OS to process the final scan results
            time.sleep(0.5) 

            found_macs = self.scanner.scan_for_droids()
            
            for mac in found_macs:
                mac = mac.upper()
                
                # Give the info command two chances to find the ManufacturerData
                identity = self.scanner.get_droid_identity(mac)
                if not identity:
                    time.sleep(0.2)
                    identity = self.scanner.get_droid_identity(mac)
                
                nickname = self.favorites.get(mac)
                
                new_droid = {
                    "mac": mac, 
                    "nickname": nickname, 
                    "identity": identity if identity else "Droid Found"
                }

                with self._lock:
                    self.scan_results.append(new_droid)
        finally:
            self.scanning = False

    def get_results(self):
        """Provides a thread-safe copy of the currently discovered droid list"""
        with self._lock:
            return self.scan_results.copy()
            
    def clear_results(self):
        """Resets the result list and error tracking for a new scan session"""
        with self._lock:
            self.scan_results = []
            self.last_error = None
