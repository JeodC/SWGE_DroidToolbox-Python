#!/usr/bin/env python3
"""
input.py - Input manager for sdl gamepad
"""

import os
import time
from threading import Lock
from typing import Any, Dict, Optional

import sdl2

# ----------------------------------------------------------------------
# Input class
# ----------------------------------------------------------------------
class Input:
    _instance: Optional["Input"] = None

    _key_mapping = {
        sdl2.SDL_CONTROLLER_BUTTON_A: "A",
        sdl2.SDL_CONTROLLER_BUTTON_B: "B",
        sdl2.SDL_CONTROLLER_BUTTON_X: "X",
        sdl2.SDL_CONTROLLER_BUTTON_Y: "Y",
        sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER: "L1",
        sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: "R1",
        sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK: "L3",
        sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK: "R3",
        sdl2.SDL_CONTROLLER_BUTTON_BACK: "SELECT",
        sdl2.SDL_CONTROLLER_BUTTON_START: "START",
        sdl2.SDL_CONTROLLER_BUTTON_GUIDE: "MENUF",
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP: "DY-",
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN: "DY+",
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT: "DX-",
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT: "DX+",
    }

    _axis_mapping = {
        sdl2.SDL_CONTROLLER_AXIS_LEFTX: "DX",
        sdl2.SDL_CONTROLLER_AXIS_LEFTY: "DY",
        sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT: "L2",
        sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT: "R2",
    }

    def __new__(cls):
        """Implements the Singleton pattern to ensure only one input manager exists."""
        if not cls._instance:
            cls._instance = super(Input, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initializes SDL subsystems, thread locks, and internal state containers."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._input_lock = Lock()

        # Input states
        self._keys_pressed: set[str] = set()
        self._keys_held: set[str] = set()
        self._keys_held_start_time: Dict[str, float] = {}
        self._axis_values: Dict[str, int] = {}

        # UI Settings
        self._initial_delay = 0.35

        # Initialize SDL Controller Subsystem
        sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER | sdl2.SDL_INIT_JOYSTICK)
        self._load_controller_mappings()
        sdl2.SDL_GameControllerEventState(sdl2.SDL_ENABLE)
        sdl2.SDL_JoystickEventState(sdl2.SDL_ENABLE)

        self.controllers: list[Any] = []
        self._open_available_controllers()

    def _open_available_controllers(self) -> None:
        """Scans for and opens all connected game controllers compatible with SDL."""
        num_controllers = sdl2.SDL_NumJoysticks()
        for i in range(num_controllers):
            if sdl2.SDL_IsGameController(i):
                controller = sdl2.SDL_GameControllerOpen(i)
                if controller:
                    name = sdl2.SDL_GameControllerName(controller).decode("utf-8")
                    self.controllers.append(controller)
                    print(f"Controller Connected: {name}")

    def _load_controller_mappings(self) -> None:
        """Loads community-standard controller layout strings from environment or file."""
        config_path = sdl2.SDL_getenv(b"SDL_GAMECONTROLLERCONFIG")
        if config_path:
            config_str = config_path.decode("utf-8")
            if "," in config_str and not config_str.endswith((".txt", ".cfg")):
                sdl2.SDL_GameControllerAddMapping(config_str.encode("utf-8"))
            elif os.path.exists(config_str):
                sdl2.SDL_GameControllerAddMappingsFromFile(config_str.encode("utf-8"))

    def _add_input_event(self, key_name: str) -> None:
        """Updates internal sets to mark a key as pressed and held, recording the start time."""
        with self._input_lock:
            if key_name not in self._keys_held:
                self._keys_held_start_time[key_name] = time.time()
            self._keys_pressed.add(key_name)
            self._keys_held.add(key_name)

    def _remove_input_event(self, key_name: str) -> None:
        """Cleans up internal state when a key is released."""
        with self._input_lock:
            self._keys_held.discard(key_name)
            self._keys_held_start_time.pop(key_name, None)

    def ui_key(self, key_name: str) -> bool:
        """Used for menu navigation. Supports auto-repeat and consumes press state."""
        with self._input_lock:
            is_pressed = key_name in self._keys_pressed
            self._keys_pressed.discard(key_name)

            if key_name in self._keys_held and key_name in self._keys_held_start_time:
                held_time = time.time() - self._keys_held_start_time[key_name]
                if held_time >= self._initial_delay:
                    is_pressed = True
            return is_pressed

    def ui_handle_navigation(self, selected_position: int, items_per_page: int, total_items: int) -> int:
        """Helper to process standard list navigation."""
        if self.ui_key("DY+"):  # DOWN
            selected_position = (selected_position + 1) % total_items
        elif self.ui_key("DY-"):  # UP
            selected_position = (selected_position - 1) % total_items
        elif self.ui_key("R1") or self.ui_key("DX+"):  # PAGE DOWN
            selected_position = min(selected_position + items_per_page, total_items - 1)
        elif self.ui_key("L1") or self.ui_key("DX-"):  # PAGE UP
            selected_position = max(selected_position - items_per_page, 0)
        return selected_position

    def drive_is_held(self, key_name: str) -> bool:
        """Used for motor control. Returns True as long as button is held down."""
        with self._input_lock:
            return key_name in self._keys_held

    def drive_get_axis(self, axis_name: str) -> int:
        """Returns raw analog value (-32768 to 32767) for precise steering."""
        with self._input_lock:
            return self._axis_values.get(axis_name, 0)

    # --- SYSTEM METHODS ---

    def check_event(self, event) -> bool:
        """Process an SDL event and update internal state."""
        if not event:
            return False

        if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
            if event.cbutton.button in self._key_mapping:
                self._add_input_event(self._key_mapping[event.cbutton.button])
                return True

        elif event.type == sdl2.SDL_CONTROLLERBUTTONUP:
            if event.cbutton.button in self._key_mapping:
                self._remove_input_event(self._key_mapping[event.cbutton.button])

        elif event.type == sdl2.SDL_CONTROLLERAXISMOTION:
            axis, value = event.caxis.axis, event.caxis.value
            if axis in self._axis_mapping:
                key_name = self._axis_mapping[axis]
                with self._input_lock:
                    self._axis_values[key_name] = value

                # Map axis to digital triggers for UI/Driving toggles
                if abs(value) > 10000:
                    dir_str = "+" if value > 0 else "-"
                    self._add_input_event(f"{key_name}{dir_str}")
                elif abs(value) < 5000:
                    self._remove_input_event(f"{key_name}+")
                    self._remove_input_event(f"{key_name}-")
        return False

    def clear_ui_states(self) -> None:
        """Flushes the 'pressed' state buffer to prevent accidental double-inputs on menu changes."""
        with self._input_lock:
            self._keys_pressed.clear()

    def cleanup(self) -> None:
        """Safely closes all controller handles and shuts down the SDL joystick subsystem."""
        with self._input_lock:
            for c in self.controllers:
                sdl2.SDL_GameControllerClose(c)
            self.controllers.clear()
        sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_GAMECONTROLLER)