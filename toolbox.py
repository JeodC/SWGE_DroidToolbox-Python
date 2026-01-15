#!/usr/bin/env python3
"""
toolbox.py - Backend logic manager for navigation and actions
"""

import asyncio
import os
import time
import threading
from typing import List

import sdl2
import sdl2.ext

# ----------------------------------------------------------------------
# Local imports
# ----------------------------------------------------------------------
from bluetoothctl import BluetoothCtl
from input import Input
from scan import ScanManager
from beacon import BeaconManager
from connect import ConnectionManager
from ui import UserInterface

from dicts import (
    FAVORITES,
    LOCATIONS,
    FACTIONS,
    DROIDS,
    AUDIO_GROUPS,
    UI_STRINGS,
    UI_BUTTONS
)

# ----------------------------------------------------------------------
# DroidToolbox class
# ----------------------------------------------------------------------
class DroidToolbox:
    def __init__(self) -> None:
        self.input = Input()
        self.ui = UserInterface()
        self.bt = BluetoothCtl()
        self.favorites_path = os.path.join(os.path.dirname(__file__), ".favorites")
        self.favorites = {}
        self._lock = threading.Lock()
        self._load_favorites()

        # Managers
        self.scan_mgr = ScanManager(
            self.bt, lock=self._lock, favorites=self.favorites, progress_callback=self._show_progress
        )
        self.beacon_mgr = BeaconManager(self.bt)
        self.conn_mgr = ConnectionManager()

        # Menu Map
        self.view_map = {
            "main": (self._render_main, self._update_main),
            "scan": (self._render_scan, self._update_scan),
            "beacon": (self._render_beacon, self._update_beacon),
            "connect": (self._render_connect, self._update_connect),
            "connected": (self._render_connected, self._update_connected),
            "audio": (self._render_audio_menu, self._update_audio_menu),
            "script": (self._render_script_menu, self._update_script_menu),
            "remote": (self._render_remote_menu, self._update_remote_menu)
        }

        # Indexes
        self.idx = 0
        self.main_idx = 0
        self.beacon_idx = 0
        self.connect_idx = 0
        self.connected_idx = 0
        self.audio_group_idx = 0
        self.audio_clip_idx = 0
        self.script_idx = 0
        
        self.beacon_selection = []
        self.audio_group_selected = None
        self.current_view = "main"
        self.submenu = None
        self.running = True

        self.last_progress_msg = None
        self.last_progress_time = 0.0
        self.PROGRESS_STICKY_SECONDS = 2.0

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _set_buttons(self, *btn_keys):
        self.ui.buttons_config = []
        
        color_map = {
            "a": self.ui.c_btn_a,
            "b": self.ui.c_btn_b,
            "x": self.ui.c_btn_x,
            "y": self.ui.c_btn_y,
            "s": self.ui.c_btn_s
        }

        for key in btn_keys:
            cfg = UI_BUTTONS.get(key)
            if cfg:
                self.ui.buttons_config.append({
                    "key": cfg["btn"],
                    "label": cfg["label"],
                    "color": color_map.get(cfg["color_ref"], self.ui.c_text)
                })

    def _load_favorites(self):
        """ Loads favorites from file and populates the FAVORITES dict """
        with self._lock:
            if os.path.exists(self.favorites_path):
                try:
                    with open(self.favorites_path, "r") as f:
                        for line in f:
                            if "|" in line:
                                mac, name = line.strip().split("|", 1)
                                self.favorites[mac.upper()] = name
                except Exception as e:
                    print(f"[FAVORITES] Error: {e}")

    def _write_favorites(self):
        """ Writes to favorites file """
        def _io_task():
            with self._lock:
                try:
                    with open(self.favorites_path, "w") as f:
                        for mac, name in self.favorites.items():
                            f.write(f"{mac}|{name}\n")
                except Exception as e:
                    print(f"[FAVORITES] IO Error: {e}")
        threading.Thread(target=_io_task, daemon=True, name="FavoritesIOThread").start()

    def save_favorite(self, mac, name):
        with self._lock:
            self.favorites[mac.upper()] = name
            self._write_favorites()

    def delete_favorite(self, mac):
        with self._lock:
            self.favorites.pop(mac.upper(), None)
            self._write_favorites()

    def _reset_bluetooth_adapter(self):
        self.scan_mgr.stop_scan()
        self.beacon_mgr.stop()
        time.sleep(0.3)

    def _monitor_input(self) -> None:
        while self.running:
            try:
                for ev in sdl2.ext.get_events():
                    self.input.check_event(ev)
                    if ev.type == sdl2.SDL_QUIT:
                        continue
            except Exception as e:
                print(f"[INPUT THREAD ERROR] {e}")
                self.running = False
            time.sleep(0.001)

    def _change_view(self, target: str):
        self._reset_bluetooth_adapter()
        self.current_view = target
        self.submenu = None
        self.idx = 0
        
        if target == "scan":
            self.scan_mgr.start_scan()
        elif target == "beacon":
            self.beacon_selection = []
            self.beacon_idx = 0

    def _reset_to_main(self, show_msg: str = None):
        self._reset_bluetooth_adapter()
        self.current_view = "main"
        self.submenu = None
        self.idx = 0
        self.main_idx = 0
        self.connect_idx = 0
        self.connected_idx = 0
        self.audio_group_idx = 0
        self.audio_clip_idx = 0
        self.script_idx = 0
        if show_msg:
            self._show_progress(show_msg)

    def _show_progress(self, msg: str):
        self.last_progress_msg = msg
        self.last_progress_time = time.time()

    def _render_menu_list(self, items: list, current_idx: int, start_y: int = 60, scroll_limit: int = 12, show_details: bool = True):
        if not items: return 0
        current_idx = max(0, min(current_idx, len(items) - 1))
        start_view = max(0, current_idx - (scroll_limit - 1))
        
        for i, item in enumerate(items[start_view:start_view + scroll_limit]):
            actual_idx = start_view + i
            sel = (actual_idx == current_idx)
            y_pos = start_y + i * 30
            
            if isinstance(item, dict):
                mac = item.get("mac", "").upper()
                # Prioritize saved nickname, then the parsed identity from get_droid_identity
                display_name = item.get("nickname") or item.get("identity") or "Droid"
                label = f"{display_name} - {mac}" if show_details else display_name
            elif isinstance(item, tuple):
                label = f"{item[1]} - {item[0].upper()}" if show_details else item[1]
            else:
                label = str(item)

            self.ui.row_list(
                label, 
                (20, y_pos), 
                self.ui.screen_width // 2, 
                28, 
                sel, 
                color=self.ui.c_text if sel else self.ui.c_menu_bg
            )
            
        return start_view
        
    def _get_active_status(self, default_msg: str) -> str:
        if self.last_progress_msg:
            elapsed = time.time() - self.last_progress_time
            if elapsed < self.PROGRESS_STICKY_SECONDS:
                if self.conn_mgr.is_connecting:
                    self.ui.spin()
                    return f"{self.last_progress_msg} {self.ui.spinner_frame}"
                return self.last_progress_msg
            else:
                self.last_progress_msg = None

        if self.scan_mgr.scanning:
            self.ui.spin()
            return f"{default_msg} {self.ui.spinner_frame}"

        return default_msg

    # ----------------------------------------------------------------------
    # Main Menu
    # ----------------------------------------------------------------------
    def _render_main(self):
        self.ui.draw_header(UI_STRINGS["MAIN_HEADER"])
        status = self._get_active_status(UI_STRINGS["MAIN_FOOTER"])
        self.ui.draw_status_footer(status)
        menu_items = [UI_STRINGS["MAIN_SCAN"], UI_STRINGS["MAIN_BEACON"], UI_STRINGS["MAIN_CONNECT"]]
        
        self._render_menu_list(menu_items, self.main_idx)

        self._set_buttons("SELECT", "EXIT")
        self.ui.draw_buttons()

    def _update_main(self):
        self.main_idx = self.input.ui_handle_navigation(self.main_idx, 1, 3)

        if self.input.ui_key("A"):
            views = ["scan", "beacon", "connect"]
            self._change_view(views[self.main_idx])
        elif self.input.ui_key("B"):
            self.running = False

    # ----------------------------------------------------------------------
    # Scan Menu
    # ----------------------------------------------------------------------
    def _render_scan(self):
        self.ui.draw_header(UI_STRINGS["SCAN_HEADER"])
        items = self.scan_mgr.get_results()

        if self.scan_mgr.scanning:
            self.ui.spin()
            status_msg = UI_STRINGS['SCAN_MSG']
        else:
            status_msg = UI_STRINGS["SCAN_PROMPT"] if items else UI_STRINGS["SCAN_NONE"]
        
        # Apply the helper here
        status = self._get_active_status(status_msg)
        self.ui.draw_status_footer(status)

        if items:
            self.idx = min(self.idx, len(items) - 1)
            self._render_menu_list(items, self.idx, show_details=True)

        self._set_buttons("CONN", "FAV", "SCAN", "BACK")
        self.ui.draw_buttons()

    def _update_scan(self):
        items = self.scan_mgr.get_results()
        if items:
            self.idx = self.input.ui_handle_navigation(self.idx, 1, len(items))
            selected = items[self.idx]
        else:
            selected = None

        if self.input.ui_key("Y") and selected:
            mac = selected["mac"]
            name = selected.get("identity") or selected.get("nickname") or "Droid"
            
            if mac.upper() in self.favorites:
                self.delete_favorite(mac)
                self._show_progress(UI_STRINGS["FAVORITES_DELCONF"])
            else:
                self.save_favorite(mac, name)
                self._show_progress(UI_STRINGS["FAVORITES_SAVED"])

        elif self.input.ui_key("X"):
            self.scan_mgr.start_scan()
            self._show_progress(UI_STRINGS["SCAN_MSG"])

        elif self.input.ui_key("A") and selected:
            name = selected.get("nickname") or selected.get("identity") or "Droid"
            self.conn_mgr.connect_droid(selected["mac"], name)
            self._show_progress(UI_STRINGS["CONN_CONNECTING"].format(name=name))

        elif self.input.ui_key("B"):
            self._reset_to_main()

    # ----------------------------------------------------------------------
    # Beacon Menu
    # ----------------------------------------------------------------------
    def _render_beacon(self):
        if not self.beacon_selection:
            items = ["Location Beacons"] + list(FACTIONS.keys())
            header = UI_STRINGS["BEACON_HEADER_MAIN"]
        elif self.beacon_selection[0] == "Location Beacons":
            items = [v[1] for v in LOCATIONS.values()]
            header = UI_STRINGS["BEACON_HEADER_LOCATIONS"]
        else:
            faction = self.beacon_selection[0]
            items = [d["name"] for d in DROIDS[faction].values()]
            header = UI_STRINGS["BEACON_HEADER_DROIDS"].format(faction=faction.upper())

        self.ui.draw_header(header)
        
        # Apply the helper here
        status_msg = UI_STRINGS["BEACON_FOOTER"].format(status=self.beacon_mgr.current_active)
        status = self._get_active_status(status_msg)
        self.ui.draw_status_footer(status)
            
        self._render_menu_list(items, self.beacon_idx)
        self._set_buttons("SELECT", "BACK", "STOP")
        self.ui.draw_buttons()
        self._beacon_items_cache = items

    def _update_beacon(self):
        if self.input.ui_key("B"):
            if self.beacon_selection:
                self.beacon_selection.pop()
                self.beacon_idx = 0
            else:
                self._reset_to_main()
            return

        if self.input.ui_key("X"):
            self.beacon_mgr.stop()
            self._show_progress("Beacon Stopped")
            return

        items = getattr(self, "_beacon_items_cache", [])
        self.beacon_idx = self.input.ui_handle_navigation(self.beacon_idx, 1, len(items))

        if self.input.ui_key("A") and items:
            selected = items[self.beacon_idx]
            if not self.beacon_selection:
                self.beacon_selection.append(selected)
                self.beacon_idx = 0
            else:
                self._reset_bluetooth_adapter()
                self._start_beacon(selected)

    def _start_beacon(self, selected_name):
        time.sleep(0.1)

        if self.beacon_selection[0] == "Location Beacons":
            loc_id = next(k for k, v in LOCATIONS.items() if v[1] == selected_name)
            self.beacon_mgr.start_location(loc_id, selected_name)
        else:
            faction = self.beacon_selection[0]
            droid_id = next(i for i, d in DROIDS[faction].items() if d["name"] == selected_name)
            self.beacon_mgr.start_droid(faction, droid_id, selected_name)

    # ----------------------------------------------------------------------
    # Connect Menu (Select a Favorite)
    # ----------------------------------------------------------------------
    def _render_connect(self):
        self.ui.draw_header(UI_STRINGS["MAIN_CONNECT"])
        with self._lock:
            fav_items = list(self.favorites.items())

        if not fav_items:
            status_msg = UI_STRINGS["FAVORITES_EMPTY"]
        else:
            status_msg = UI_STRINGS["FAVORITES_PROMPT"]
            self._render_menu_list(fav_items, self.connect_idx, show_details=False)

        # Apply the priority helper
        status = self._get_active_status(status_msg)
        self.ui.draw_status_footer(status)

        self._set_buttons("CONN", "BACK", "DELETE")
        self.ui.draw_buttons()

    def _update_connect(self):
        if self.input.ui_key("B"):
            self._reset_to_main()
            return

        with self._lock:
            fav_items = list(self.favorites.items())
        
        if not fav_items or self.conn_mgr.is_connecting: 
            return

        self.connect_idx = self.input.ui_handle_navigation(self.connect_idx, 1, len(fav_items))
        
        # Guard against index errors if the list changed
        self.connect_idx = max(0, min(self.connect_idx, len(fav_items) - 1))
        mac, name = fav_items[self.connect_idx]

        if self.input.ui_key("X"):
            self.delete_favorite(mac)
            # Update index immediately so the next render doesn't crash
            if len(fav_items) <= 1:
                self.connect_idx = 0
            else:
                self.connect_idx = max(0, self.connect_idx - 1)
                
            self._show_progress(UI_STRINGS["FAVORITES_DELCONF"])
            
        elif self.input.ui_key("A"):
            self.conn_mgr.connect_droid(mac, name)
            self._show_progress(UI_STRINGS["CONN_CONNECTING"].format(name=name))

    # ----------------------------------------------------------------------
    # Connected Menu (Connected to Droid)
    # ----------------------------------------------------------------------
    def _render_connected(self):
        self.ui.draw_header(UI_STRINGS["CONNECTED_HEADER"].format(name=self.conn_mgr.active_name))
        options = [
            UI_STRINGS["CONNECTED_PLAY_AUDIO"],
            UI_STRINGS["CONNECTED_RUN_SCRIPT"],
            UI_STRINGS["CONNECTED_REMOTE_CONTROL"],
            UI_STRINGS["CONNECTED_DISCONNECT"]
        ]
        self._render_menu_list(options, self.connected_idx)
        
        self._set_buttons("SELECT", "BACK")
        self.ui.draw_buttons()
        self.ui.draw_status_footer(UI_STRINGS["CONNECTED_FOOTER"])

    def _update_connected(self):
        self.connected_idx = self.input.ui_handle_navigation(self.connected_idx, 1, 4)
        
        if self.input.ui_key("B"):
            self._handle_disconnect()

        elif self.input.ui_key("A"):
            choices = ["audio", "script", "remote", "disconnect"]
            choice = choices[self.connected_idx]

            if choice == "disconnect":
                self._handle_disconnect()
            else:
                self.submenu = choice

    def _handle_disconnect(self):
        if self.conn_mgr.is_connected and self.conn_mgr.conn.loop:
            fut = asyncio.run_coroutine_threadsafe(self.conn_mgr.conn.disconnect(), self.conn_mgr.conn.loop)
            
            def _wait_and_reset():
                try:
                    fut.result(timeout=5)
                except Exception:
                    pass
                self.conn_mgr.is_connecting = False
                self.conn_mgr.active_mac = None
                self.conn_mgr.active_name = None
                self._reset_to_main(UI_STRINGS["CONN_DISCONNECTED"])
            
            threading.Thread(target=_wait_and_reset, daemon=True).start()
        else:
            self.conn_mgr.is_connecting = False
            self.conn_mgr.active_mac = None
            self.conn_mgr.active_name = None
            self._reset_to_main(UI_STRINGS["CONN_DISCONNECTED"])

    # ----------------------------------------------------------------------
    # Audio Menu
    # ----------------------------------------------------------------------
    def _render_audio_menu(self):
        self.ui.draw_header(UI_STRINGS["AUDIO_HEADER"])
        
        if self.audio_group_selected is None:
            items = [f"G{k}: {v}" for k, v in AUDIO_GROUPS.items()]
            idx = self.audio_group_idx
            self.ui.draw_status_footer(UI_STRINGS["AUDIO_FOOTER1"])
        else:
            items = [f"Clip {i}" for i in range(8)]
            idx = self.audio_clip_idx
            self.ui.draw_status_footer(UI_STRINGS["AUDIO_FOOTER2"])

        self._render_menu_list(items, idx)
        self._set_buttons("SELECT", "BACK")
        self.ui.draw_buttons()

    def _update_audio_menu(self):
        if self.audio_group_selected is None:
            self.audio_group_idx = self.input.ui_handle_navigation(self.audio_group_idx, 1, len(AUDIO_GROUPS))
            if self.input.ui_key("B"): self.submenu = None
            elif self.input.ui_key("A"): self.audio_group_selected = self.audio_group_idx
        else:
            self.audio_clip_idx = self.input.ui_handle_navigation(self.audio_clip_idx, 1, 8)
            if self.input.ui_key("B"): self.audio_group_selected = None
            elif self.input.ui_key("A"):
                self.conn_mgr.run_action(f"G{self.audio_group_selected}C{self.audio_clip_idx}", "Audio")

    # ----------------------------------------------------------------------
    # Script Menu
    # ----------------------------------------------------------------------
    def _render_script_menu(self):
        self.ui.draw_header(UI_STRINGS["SCRIPTS_HEADER"])
        items = [f"Script {i + 1}" for i in range(18)]
        
        self._render_menu_list(items, self.script_idx)
        self.ui.draw_status_footer(UI_STRINGS["SCRIPTS_FOOTER"])
        self._set_buttons("SELECT", "BACK")
        self.ui.draw_buttons()

    def _update_script_menu(self):
        self.script_idx = self.input.ui_handle_navigation(self.script_idx, 1, 18)
        if self.input.ui_key("B"): self.submenu = None
        elif self.input.ui_key("A"):
            self.conn_mgr.run_action(f"Script {self.script_idx + 1}", "Scripts")

    # ----------------------------------------------------------------------
    # Remote Menu
    # ----------------------------------------------------------------------
    def _render_remote_menu(self):
        self.ui.draw_header(UI_STRINGS["REMOTE_HEADER"])
        self.ui.draw_status_footer(UI_STRINGS["REMOTE_FOOTER"])
        self.ui.draw_buttons()

    def _update_remote_menu(self):
        if self.input.ui_key("B"): self.submenu = None

    def start(self):
        threading.Thread(target=self._monitor_input, name="InputThread", daemon=True).start()

    def update(self):
        # 1. Handle Auto-Transition to Connected View
        if self.conn_mgr.is_connected and self.current_view != "connected" and not self.submenu:
            self.current_view = "connected"
            self.idx = 0

        # 2. Handle Auto-Revert on Connection Loss
        if (self.current_view == "connected" or self.submenu) and not self.conn_mgr.is_connected:
            self._reset_to_main(UI_STRINGS["CONN_LOST"])

        if self.conn_mgr.last_error:
            self._show_progress(self.conn_mgr.last_error)
            self.conn_mgr.last_error = None

        target = self.submenu if self.submenu else self.current_view
        render, update_func = self.view_map.get(target, (None, None))

        if render: render()
        if update_func: update_func()

    def cleanup(self) -> None:
        self.running = False
        self.beacon_mgr.stop()
        try:
            self.conn_mgr.disconnect_droid()
        except RuntimeError:
            print("Event loop already closed, skipping disconnect")