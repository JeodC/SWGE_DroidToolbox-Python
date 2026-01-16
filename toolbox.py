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
from options import OptionsManager
from ui import UserInterface

from dicts import (
    FAVORITES,
    LOCATIONS,
    FACTIONS,
    DROIDS,
    AUDIO_GROUPS,
    UI_STRINGS,
    UI_BUTTONS,
    UI_THEMES
)

# ----------------------------------------------------------------------
# DroidToolbox class
# ----------------------------------------------------------------------
class DroidToolbox:
    def __init__(self) -> None:
        self.input = Input()
        self.ui = UserInterface()
        self.bt = BluetoothCtl()
        self._lock = threading.Lock()

        # Managers
        self.options_mgr = OptionsManager(self.ui)
        self.scan_mgr = ScanManager(
            self.bt, lock=self._lock, favorites=self.options_mgr.get_favorites_dict(), progress_callback=self._show_progress
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
            "options": (self._render_options, self._update_options),
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
        self.options_idx = 0
        self.audio_group_idx = 0
        self.audio_clip_idx = 0
        self.script_idx = 0
        
        self.beacon_selection = []
        self.options_selection = []
        self.audio_group_selected = None
        self.current_view = "main"
        self.submenu = None
        self.running = True

        self.last_progress_msg = None
        self.last_progress_time = 0.0
        self.PROGRESS_STICKY_SECONDS = 2.0

        # Apply theme
        current_theme = self.options_mgr.get_theme()
        self.ui.apply_theme(current_theme)

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
        elif target == "exit":
            self.running = False

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

    def _render_menu_list(self, items: list, current_idx: int, start_y: int = 60, scroll_limit: int = 12):
        """
        Render a vertical list of menu items.

        Supports:
          - Plain strings
          - Tuples (mac, data) for favorites
          - Automatically highlights the selected index
        """
        if not items:
            return 0

        # Clamp the current index
        current_idx = max(0, min(current_idx, len(items) - 1))

        # Determine scroll window
        start_view = max(0, current_idx - (scroll_limit - 1))

        for i, item in enumerate(items[start_view:start_view + scroll_limit]):
            actual_idx = start_view + i
            sel = (actual_idx == current_idx)
            y_pos = start_y + i * 30

            if isinstance(item, tuple):
                # Favorite: (mac, data)
                mac, data = item
                display_name = data.get("nickname") or data.get("personality") or "Droid"
                # Controller profile name (from options)
                profile_name = data.get("controller_profile", "R_Tank")
                label = f"{display_name} - Controller Profile: {profile_name}"
            else:
                # Plain string
                label = str(item)

            # Draw the row
            self.ui.row_list(
                label,
                (20, y_pos),
                self.ui.screen_width // 2,
                28,
                sel,
                color=self.ui.c_text if sel else self.ui.c_header_bg
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
        menu_items = [UI_STRINGS["MAIN_SCAN"], UI_STRINGS["MAIN_BEACON"], UI_STRINGS["MAIN_CONNECT"], UI_STRINGS["MAIN_OPTIONS"], UI_STRINGS["MAIN_EXIT"]]
        
        self._render_menu_list(menu_items, self.main_idx)

        self._set_buttons("SELECT", "EXIT")
        self.ui.draw_buttons()

    def _update_main(self):
        menu_items = [UI_STRINGS["MAIN_SCAN"], UI_STRINGS["MAIN_BEACON"], 
                          UI_STRINGS["MAIN_CONNECT"], UI_STRINGS["MAIN_OPTIONS"], UI_STRINGS["MAIN_EXIT"]]
            
        self.main_idx = self.input.ui_handle_navigation(self.main_idx, 1, len(menu_items))

        if self.input.ui_key("A"):
            views = ["scan", "beacon", "connect", "options", "exit"]
            self._change_view(views[self.main_idx])
        elif self.input.ui_key("B"):
            self.running = False

    # ----------------------------------------------------------------------
    # Options Menu
    # ----------------------------------------------------------------------
    def _render_options(self):
        if not self.options_selection:
            header = UI_STRINGS["OPTIONS_HEADER"]
            items = [UI_STRINGS["OPTIONS_THEME"], UI_STRINGS["OPTIONS_FAVORITES"], UI_STRINGS["OPTIONS_MAPPINGS"]]
            category = None  # define it so the rest of the code can check safely
        else:
            category = self.options_selection[0]
            header = f"--- {category.upper()} ---"
            if category == UI_STRINGS["OPTIONS_THEME"]:
                items = list(UI_THEMES.keys())
            else:
                items = self.options_mgr.get_favorites_list() or []

        self.ui.draw_header(header)
        status = self._get_active_status(UI_STRINGS["MAIN_FOOTER"])
        self.ui.draw_status_footer(status)
        
        self._render_menu_list(items, self.options_idx)

        # Set buttons depending on the category
        if category == UI_STRINGS["OPTIONS_FAVORITES"]:
            # Favorites management: Select = edit, X = delete, B = back
            self._set_buttons("SELECT", "BACK", "DELETE")
        else:
            self._set_buttons("SELECT", "BACK")
        
        self.ui.draw_buttons()
        self._options_items_cache = items

    def _update_options(self):
        items = getattr(self, "_options_items_cache", [])
        if not items:
            return

        # Navigation
        self.options_idx = self.input.ui_handle_navigation(self.options_idx, 1, len(items))

        # Selection / actions
        if self.input.ui_key("A"):
            selected = items[self.options_idx]
            if not self.options_selection:
                # Enter submenu
                self.options_selection.append(selected)
                self.options_idx = 0
            else:
                category = self.options_selection[0]

                if category == UI_STRINGS["OPTIONS_THEME"]:
                    # Switch the current UI theme
                    self.options_mgr.set_theme(selected)
                    self.ui.apply_theme(selected)

                elif category == UI_STRINGS["OPTIONS_FAVORITES"]:
                    # Edit nickname
                    pass

                elif category == UI_STRINGS["OPTIONS_MAPPINGS"]:
                    # Edit controller profile
                    pass

        # Delete favorite
        elif self.input.ui_key("X"):
            if self.options_selection and self.options_selection[0] == UI_STRINGS["OPTIONS_FAVORITES"]:
                selected = items[self.options_idx]
                if isinstance(selected, tuple):
                    mac, data = selected
                    self.options_mgr.delete_favorite(mac)
                    self._show_progress(UI_STRINGS["FAVORITES_DELCONF"])
                    # Update items and clamp index
                    items = self.options_mgr.get_favorites_list() or []
                    self._options_items_cache = items
                    self.options_idx = max(0, min(self.options_idx, len(items) - 1))

        # Back
        elif self.input.ui_key("B"):
            if self.options_selection:
                self.options_selection.pop()
                self.options_idx = 0
            else:
                self._reset_to_main()

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
            self._render_menu_list(items, self.idx)

        self._set_buttons("CONN", "FAV", "SCAN", "BACK")
        self.ui.draw_buttons()

    def _update_scan(self):
        items = self.scan_mgr.get_results()
        selected = items[self.idx] if items else None

        if selected:
            self.idx = self.input.ui_handle_navigation(self.idx, 1, len(items))
            mac = selected["mac"]
            nickname = selected.get("nickname") or selected.get("identity") or "Droid"
            personality = selected.get("personality", "Default")
            controller_profile = selected.get("controller_profile")

            if self.input.ui_key("Y"):
                if self.options_mgr.has_favorite(mac):
                    self.options_mgr.delete_favorite(mac)
                    self._show_progress(UI_STRINGS["FAVORITES_DELCONF"])
                else:
                    self.options_mgr.save_favorite(mac, nickname, personality, controller_profile)
                    self._show_progress(UI_STRINGS["FAVORITES_SAVED"])

            elif self.input.ui_key("A"):
                self.conn_mgr.connect_droid(mac, nickname)
                self._show_progress(UI_STRINGS["CONN_CONNECTING"].format(name=nickname))

        if self.input.ui_key("X"):
            self.scan_mgr.start_scan()
            self._show_progress(UI_STRINGS["SCAN_MSG"])

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
    def _render_connect(self, on_select=None):
        """
        Renders the favorites list. 
        on_select: callable(mac:str, data:dict) -> None
                   Called when user presses A on a favorite.
                   Defaults to connecting to droid.
        """
        self.ui.draw_header(UI_STRINGS["MAIN_CONNECT"])

        fav_items = self.options_mgr.get_favorites_list()

        if not fav_items:
            status_msg = UI_STRINGS["FAVORITES_EMPTY"]
        else:
            status_msg = UI_STRINGS["FAVORITES_PROMPT"]
            self._render_menu_list(
                fav_items, 
                self.connect_idx
            )

        status = self._get_active_status(status_msg)
        self.ui.draw_status_footer(status)

        # Buttons
        self._set_buttons("SELECT", "BACK", "DELETE")
        self.ui.draw_buttons()
        self._connect_items_cache = fav_items
        self._connect_select_callback = on_select

    def _update_connect(self):
        fav_items = getattr(self, "_connect_items_cache", [])

        if not fav_items or self.conn_mgr.is_connecting:
            return

        self.connect_idx = min(self.connect_idx, len(fav_items)-1)
        mac, data = fav_items[self.connect_idx]

        # Delete favorite
        if self.input.ui_key("X"):
            self.options_mgr.delete_favorite(mac)
            self.connect_idx = max(0, self.connect_idx - 1)
            self._show_progress(UI_STRINGS["FAVORITES_DELCONF"])
            return

        # Select favorite
        elif self.input.ui_key("A"):
            callback = getattr(self, "_connect_select_callback", None)
            if callback:
                callback(mac, data)
            else:
                # Default behavior: connect
                self.conn_mgr.connect_droid(mac, data.get("nickname", "Droid"))
                self._show_progress(UI_STRINGS["CONN_CONNECTING"].format(name=data.get("nickname", "Droid")))
            return

        # Back
        elif self.input.ui_key("B"):
            self._reset_to_main()

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
        self._draw_controller_telemetry()
        self.ui.draw_status_footer(UI_STRINGS["REMOTE_FOOTER"])
        
        self._set_buttons("BACK")
        self.ui.draw_buttons()

    def _update_remote_menu(self):
        if self.input.ui_key("B"): self.submenu = None

    def start(self):
        threading.Thread(target=self._monitor_input, name="InputThread", daemon=True).start()

    def _draw_controller_telemetry(self):
        self.input.update_smoothing()

        lx = self.input.get_axis_float("DX")
        ly = self.input.get_axis_float("DY")
        rx = self.input.get_axis_float("RX")
        ry = self.input.get_axis_float("RY")
        l2 = self.input.get_axis_float("L2")
        r2 = self.input.get_axis_float("R2")

        rad = 50
        spacing = 120
        trigger_w, trigger_h = 25, 100
        trigger_gap = 40
        
        total_width = (spacing) + (trigger_w * 2) + trigger_gap
        
        start_x = (self.ui.screen_width - total_width) // 2
        base_y = self.ui.screen_height // 2

        self.ui.draw_joystick_monitor((start_x, base_y), rad, lx, ly, "L")
        
        self.ui.draw_joystick_monitor((start_x + spacing, base_y), rad, rx, ry, "R")

        trigger_base_x = start_x + spacing + 80
        self.ui.draw_trigger_gauge(
            (trigger_base_x, base_y - (trigger_h // 2)), 
            (trigger_w, trigger_h), 
            l2, "L2"
        )
        self.ui.draw_trigger_gauge(
            (trigger_base_x + trigger_gap, base_y - (trigger_h // 2)), 
            (trigger_w, trigger_h), 
            r2, "R2"
        )

    def update(self):
        # Handle Auto-Transition to Connected View
        if self.conn_mgr.is_connected and self.current_view != "connected" and not self.submenu:
            self.current_view = "connected"
            self.idx = 0

        # Handle Auto-Revert on Connection Loss
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
