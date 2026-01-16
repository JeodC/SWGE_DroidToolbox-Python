#!/usr/bin/env python3
"""
options.py - Handles application options and settings.json
"""

import os
import threading
import json
from dicts import CONTROLLER_PROFILES

class OptionsManager:
    def __init__(self, ui, settings_path=None):
        self.ui = ui
        self._lock = threading.Lock()
        self.settings_path = settings_path or os.path.join(os.path.dirname(__file__), "settings.json")

        # Default structure
        self.favorites = {}
        self.options_data = {
            "selected_theme": "DEFAULT",
            "controller_profiles": {}
        }

        self._load_settings()

    # ----------------------------
    # Load / Write Settings
    # ----------------------------
    def _load_settings(self):
        with self._lock:
            if not os.path.exists(self.settings_path) or os.path.getsize(self.settings_path) == 0:
                self._write_settings()
                return
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    self.favorites = data.get("favorites", {})
                    self.options_data = data.get("options", self.options_data)
            except Exception as e:
                print(f"[OPTIONS] Error loading JSON: {e}")
                self.favorites = {}
                self.options_data = {"selected_theme": "DEFAULT", "controller_profiles": {}}

    def _write_settings(self):
        def _io_task():
            with self._lock:
                try:
                    with open(self.settings_path, "w") as f:
                        json.dump({"favorites": self.favorites, "options": self.options_data}, f, indent=2)
                except Exception as e:
                    print(f"[OPTIONS] IO Error: {e}")

        threading.Thread(target=_io_task, daemon=True, name="OptionsIOThread").start()

    # ----------------------------
    # Favorites Management
    # ----------------------------
    def save_favorite(self, mac, nickname, personality, controller_profile_name="R_Racing"):
        mac = mac.upper()
        with self._lock:
            self.favorites[mac] = {
                "nickname": nickname,
                "personality": personality,
                "controller_profile": controller_profile_name
            }
            self._write_settings()

    def delete_favorite(self, mac):
        mac = mac.upper()
        with self._lock:
            self.favorites.pop(mac, None)
            self.options_data["controller_profiles"].pop(mac, None)
            self._write_settings()

    def get_favorites_dict(self):
        """Return the favorites as a dict (MAC → data)."""
        with self._lock:
            return self.favorites.copy()

    def get_favorites_list(self):
        """Return favorites as a list of (mac, data) tuples for menus."""
        with self._lock:
            return list(self.favorites.items())

    # ----------------------------
    # Controller Profiles
    # ----------------------------
    def get_controller_profile(self, mac):
        mac = mac.upper()
        with self._lock:
            profile_name = self.favorites.get(mac, {}).get("controller_profile", "R_Tank")
            return CONTROLLER_PROFILES.get(profile_name, CONTROLLER_PROFILES["R_Tank"])

    def set_controller_profile(self, mac, profile_name):
        mac = mac.upper()
        if profile_name not in CONTROLLER_PROFILES:
            print(f"[OPTIONS] Unknown controller profile: {profile_name}")
            return

        with self._lock:
            if mac in self.favorites:
                self.favorites[mac]["controller_profile"] = profile_name
                self.options_data["controller_profiles"][mac] = profile_name
                self._write_settings()

    # ----------------------------
    # Theme Management
    # ----------------------------
    def get_theme(self):
        with self._lock:
            return self.options_data.get("selected_theme", "DEFAULT")

    def set_theme(self, theme_name):
        with self._lock:
            self.options_data["selected_theme"] = theme_name
            self._write_settings()
        self.ui.apply_theme(theme_name)
