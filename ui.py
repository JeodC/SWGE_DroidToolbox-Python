#!/usr/bin/env python3
"""
ui.py - The User Interface
"""

import collections
import ctypes
import os
import time
from itertools import cycle
from typing import List, Optional, Tuple, Any

import sdl2
import sdl2.sdlttf as ttf
import sdl2.sdlimage as img

from dicts import UI_THEMES

FONT_PATH = os.path.join(os.getcwd(), "fonts", "romm.ttf")
FONT_SIZE = 12
HEADER_HEIGHT = 25
FOOTER_HEIGHT = 20
BUTTON_AREA_HEIGHT = 50
MAX_TEXTURE_CACHE = 48

# ----------------------------------------------------------------------
# UserInterface
# ----------------------------------------------------------------------
class UserInterface:
    screen_width = 640
    screen_height = 480

    def __init__(self, theme_name="ARTOO"):
        self.apply_theme(theme_name)

        # Track what this instance initialized so cleanup is safe
        self._inited_sdl_video = False
        self._inited_ttf = False
        self._inited_img_flags = 0

        # --- SDL video init: only if not already initialized ---
        was = sdl2.SDL_WasInit(0)
        if not (was & sdl2.SDL_INIT_VIDEO):
            if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) < 0:
                raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError().decode()}")
            self._inited_sdl_video = True

        # --- SDL_image init: ensure PNG/JPG available ---
        desired_img_flags = img.IMG_INIT_PNG | img.IMG_INIT_JPG
        current_img = img.IMG_Init(0)
        if (current_img & desired_img_flags) != desired_img_flags:
            got = img.IMG_Init(desired_img_flags)
            if (got & desired_img_flags) != desired_img_flags:
                # only fail if we couldn't init necessary formats
                raise RuntimeError("Failed to init SDL_image for PNG/JPG")
            self._inited_img_flags = got & desired_img_flags

        # --- SDL_ttf init ---
        try:
            if ttf.TTF_WasInit() == 0:
                if ttf.TTF_Init() != 0:
                    raise RuntimeError("TTF_Init failed")
                self._inited_ttf = True
        except Exception:
            # Some SDL2 wrappers expose TTF_WasInit differently; attempt init anyway
            try:
                ttf.TTF_Init()
                self._inited_ttf = True
            except Exception:
                # Non-fatal: we can continue without fonts (text drawing will be skipped)
                self._inited_ttf = False

        # --- Create window, renderer, and render target texture ---
        self.window = self._create_window()
        self.renderer = self._create_renderer()

        # Create a target texture used as main drawing surface
        self.screen_texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.screen_width,
            self.screen_height
        )
        if not self.screen_texture:
            raise RuntimeError("Failed to create render target texture")

        # instance font
        self.font = None
        if self._inited_ttf:
            try:
                self.font = ttf.TTF_OpenFont(FONT_PATH.encode(), FONT_SIZE)
                if not self.font:
                    print("[UI] Warning: failed to load font.")
            except Exception:
                self.font = None
                print("[UI] Warning: exception opening font.")

        self._scroll_speed = 1
        self._row_scroll_state = {}
        self._desc_scroll_state = {}
        self._scroll_start_delay = 60
        self._scroll_end_delay = 60

        # LRU texture cache: path -> texture
        self.texture_cache = collections.OrderedDict()
        
        # Animated spinner
        self.spinner = cycle(["|", "/", "-", "\\"])
        self.spinner_speed = 0.12
        self.last_spinner = 0.0
        self.spinner_frame = "|"
        
        # Finalize init
        self.draw_clear()
        self._initialized = True

    # ------------------------------------------------------------------
    # SDL2 setup helpers
    # ------------------------------------------------------------------
    def _create_window(self):
        window = sdl2.SDL_CreateWindow(
            b"Pharos",
            sdl2.SDL_WINDOWPOS_UNDEFINED,
            sdl2.SDL_WINDOWPOS_UNDEFINED,
            0, 0,
            sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_SHOWN,
        )
        if not window:
            raise RuntimeError(f"SDL_CreateWindow failed: {sdl2.SDL_GetError().decode()}")
        return window

    def _create_renderer(self):
        renderer = sdl2.SDL_CreateRenderer(
            self.window, -1, sdl2.SDL_RENDERER_ACCELERATED
        )
        if not renderer:
            raise RuntimeError(f"SDL_CreateRenderer failed: {sdl2.SDL_GetError().decode()}")
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"0")
        return renderer

    # ------------------------------------------------------------------
    # Frame management
    # ------------------------------------------------------------------
    def draw_start(self):
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)
        sdl2.SDL_SetRenderTarget(self.renderer, self.screen_texture)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

    def draw_clear(self):
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

    def render_to_screen(self):
        sdl2.SDL_SetRenderTarget(self.renderer, None)
        w = ctypes.c_int()
        h = ctypes.c_int()
        sdl2.SDL_GetWindowSize(self.window, ctypes.byref(w), ctypes.byref(h))
        dst_rect = sdl2.SDL_Rect(0, 0, w.value, h.value)
        sdl2.SDL_RenderCopy(self.renderer, self.screen_texture, None, dst_rect)
        sdl2.SDL_RenderPresent(self.renderer)

    # ------------------------------------------------------------------
    # Cleanup Does NOT call SDL_Quit().
    # Top-level code should call SDL_Quit() once for the process.
    # ------------------------------------------------------------------
    def cleanup(self):
        # Destroy cached textures
        for tex in list(self.texture_cache.values()):
            try:
                sdl2.SDL_DestroyTexture(tex)
            except Exception:
                pass
        self.texture_cache.clear()

        # Destroy render target texture
        try:
            if getattr(self, "screen_texture", None):
                sdl2.SDL_DestroyTexture(self.screen_texture)
                self.screen_texture = None
        except Exception:
            pass

        # Destroy renderer and window
        try:
            if getattr(self, "renderer", None):
                sdl2.SDL_DestroyRenderer(self.renderer)
                self.renderer = None
        except Exception:
            pass

        try:
            if getattr(self, "window", None):
                sdl2.SDL_DestroyWindow(self.window)
                self.window = None
        except Exception:
            pass

        # Close font
        try:
            if getattr(self, "font", None):
                ttf.TTF_CloseFont(self.font)
                self.font = None
        except Exception:
            pass

        # Quit TTF/IMG only if this instance initialized them.
        # If other parts of program rely on these subsystems, they should manage lifetime.
        try:
            if self._inited_img_flags:
                img.IMG_Quit()
                self._inited_img_flags = 0
        except Exception:
            pass

        try:
            if self._inited_ttf:
                ttf.TTF_Quit()
                self._inited_ttf = False
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Text rendering helpers
    # ------------------------------------------------------------------
    def _render_text(self, text: str, color: sdl2.SDL_Color):
        # if font unavailable return None
        if not getattr(self, "font", None):
            return None
        try:
            return ttf.TTF_RenderUTF8_Blended(self.font, text.encode("utf-8"), color)
        except Exception:
            return None

    def _blit_text(self, surface: Any, x: int, y: int):
            if surface is None:
                return
                
            texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surface)
            if not texture:
                sdl2.SDL_FreeSurface(surface)
                return

            w, h = ctypes.c_int(), ctypes.c_int()
            sdl2.SDL_QueryTexture(texture, None, None, ctypes.byref(w), ctypes.byref(h))
            dst = sdl2.SDL_Rect(x, y, w.value, h.value)
            
            sdl2.SDL_RenderCopy(self.renderer, texture, None, dst)
            
            sdl2.SDL_DestroyTexture(texture)
            sdl2.SDL_FreeSurface(surface)

    def draw_text(self, pos: Tuple[int, int], text: str, color: Optional[sdl2.SDL_Color] = None):
        if not text:
            return
        
        if color is None:
            color = self.c_text
            
        surface = self._render_text(text, color)
        if surface:
            self._blit_text(surface, int(pos[0]), int(pos[1]))

    # ------------------------------------------------------------------
    # Shapes
    # ------------------------------------------------------------------
    def draw_rectangle(self, rect: Tuple[int, int, int, int], fill: Optional[sdl2.SDL_Color] = None):
        if fill:
            sdl2.SDL_SetRenderDrawColor(self.renderer, fill.r, fill.g, fill.b, fill.a)
            sdl2.SDL_RenderFillRect(self.renderer, sdl2.SDL_Rect(*rect))

    def draw_rectangle_outline(self, rect: Tuple[int, int, int, int], color: sdl2.SDL_Color, width: int = 1):
        sdl2.SDL_SetRenderDrawColor(self.renderer, color.r, color.g, color.b, color.a)
        for i in range(width):
            outer = sdl2.SDL_Rect(rect[0] - i, rect[1] - i, rect[2] + 2 * i, rect[3] + 2 * i)
            sdl2.SDL_RenderDrawRect(self.renderer, outer)

    def draw_circle(self, center: Tuple[int, int], radius: int, fill: Optional[sdl2.SDL_Color] = None):
        if not fill:
            return
            
        sdl2.SDL_SetRenderDrawColor(self.renderer, fill.r, fill.g, fill.b, fill.a)
        
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            dx = int((r2 - dy * dy)**0.5)
            sdl2.SDL_RenderDrawLine(
                self.renderer,
                int(center[0] - dx), int(center[1] + dy),
                int(center[0] + dx), int(center[1] + dy)
            )

    # ------------------------------------------------------------------
    # UI Components
    # ------------------------------------------------------------------
    def spin(self):
        """ Animates the spinner in draw_status_footer """
        now = time.time()
        if now - self.last_spinner >= self.spinner_speed:
            self.last_spinner = now
            self.spinner_frame = next(self.spinner)

    def row_list(self, text: str, pos: Tuple[float, float], width: int, height: int,
        selected: bool = False, fill: Optional[sdl2.SDL_Color] = None,
        color: Optional[sdl2.SDL_Color] = None, highlight: bool = False):
            
            ix, iy = int(pos[0]), int(pos[1])
            
            # Resolve defaults from instance colors
            if color is None: color = self.c_text
            if fill is None: fill = self.c_row_bg

            if highlight and not selected:
                # Hardcoded gold for highlight
                bg = sdl2.SDL_Color(211, 185, 72, 255) 
            else:
                bg = self.c_row_sel if selected else fill

            self.draw_rectangle((ix, iy, width, height), fill=bg)
            
            clip_rect = sdl2.SDL_Rect(ix, iy, width, height)
            sdl2.SDL_RenderSetClipRect(self.renderer, clip_rect)
            
            text_w = self.get_text_width(text)
            padding_left = 12
            render_y = iy + 8

            if text_w <= width - 20:
                self.draw_text((ix + padding_left, render_y), text, color)
            else:
                state = self._row_scroll_state.get(text, {
                    "offset": 0, 
                    "direction": 1, 
                    "timer": self._scroll_start_delay
                })
                
                if state["timer"] > 0:
                    state["timer"] -= 1
                else:
                    state["offset"] += state["direction"] * self._scroll_speed
                    max_offset = text_w - (width - 20)
                    
                    if state["offset"] >= max_offset:
                        state["offset"] = max_offset
                        state["direction"] = -1
                        state["timer"] = self._scroll_end_delay
                    elif state["offset"] <= 0:
                        state["offset"] = 0
                        state["direction"] = 1
                        state["timer"] = self._scroll_start_delay
                
                self._row_scroll_state[text] = state
                self.draw_text((ix + padding_left - int(state["offset"]), render_y), text, color)
            
            sdl2.SDL_RenderSetClipRect(self.renderer, None)

    def button_circle(self, pos: Tuple[float, float], button: str, label: str,
                  color: Optional[sdl2.SDL_Color] = None):
        
        circle_color = color if color is not None else self.c_btn_a
        
        radius = 8
        padding = 8
        
        self.draw_circle((int(pos[0]), int(pos[1])), radius, fill=circle_color)
        
        text_y = int(pos[1] - FONT_SIZE // 2)
        text_x = int(pos[0] - (self.get_text_width(button) // 2))
        
        self.draw_text((text_x, text_y), button, self.c_text)
        
        label_x = int(pos[0] + radius + padding)
        self.draw_text((label_x, text_y), label, self.c_text)

    def get_text_width(self, text: str) -> int:
        if not getattr(self, "font", None):
            return 0
        w = ctypes.c_int()
        h = ctypes.c_int()
        try:
            ttf.TTF_SizeUTF8(self.font, text.encode("utf-8"), ctypes.byref(w), ctypes.byref(h))
            return w.value
        except Exception:
            return 0

    def draw_buttons(self):
        pos_y = self.screen_height - FOOTER_HEIGHT - BUTTON_AREA_HEIGHT//2
        pos_x = 20
        radius = 8
        padding = 10
        for config in getattr(self, "buttons_config", []):
            self.button_circle((pos_x, pos_y), config["key"], config["label"], color=config.get("color"))
            text_width = self.get_text_width(config["label"])
            total_width = radius*2 + padding + text_width
            pos_x += total_width + padding

    def draw_status_footer(self, text_line_1: str = "", text_line_2: str = "",
                           color: Optional[sdl2.SDL_Color] = None, **kwargs):
        if color is None:
            color = self.c_text
            
        y = self.screen_height - FOOTER_HEIGHT
        self.draw_rectangle((0, y, self.screen_width, FOOTER_HEIGHT), fill=self.c_footer_bg)
        self.draw_text((10, y + 3), text_line_1, color)
        if text_line_2:
            self.draw_text((10, y + 3 + FONT_SIZE), text_line_2, color)

    def draw_header(self, title: str, color: Optional[sdl2.SDL_Color] = None):
        if color is None:
            color = self.c_text
            
        self.draw_rectangle((0, 0, self.screen_width, HEADER_HEIGHT), fill=self.c_header_bg)
        self.draw_text((self.screen_width // 2 - self.get_text_width(title)//2, 8), title, color)

    def apply_theme(self, theme_name):
        theme = UI_THEMES.get(theme_name, UI_THEMES["ARTOO"])
        for key, rgba in theme.items():
            setattr(self, f"c_{key}", sdl2.SDL_Color(*rgba))
        
        self.c_row_sel = self.c_btn_a
    # ------------------------------------------------------------------
    # Image loading with LRU cache
    # ------------------------------------------------------------------
    def _cache_texture(self, path: str, texture: Any):
        # Evict oldest if full
        if path in self.texture_cache:
            # move to end (most recently used)
            self.texture_cache.move_to_end(path)
            return
        while len(self.texture_cache) >= MAX_TEXTURE_CACHE:
            old_path, old_tex = self.texture_cache.popitem(last=False)
            try:
                sdl2.SDL_DestroyTexture(old_tex)
            except Exception:
                pass
        self.texture_cache[path] = texture

    def draw_image(self, port: Any, max_w: int = 380, max_h: int = 280) -> None:
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"2")

        path = getattr(port, "image_path", None)
        if not path or not os.path.exists(path):
            return

        texture = self.texture_cache.get(path)
        if texture is None:
            surface = None
            texture = None
            try:
                surface = img.IMG_Load(path.encode())
                if not surface:
                    return
                texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surface)
                if not texture:
                    return
                self._cache_texture(path, texture)
            except Exception:
                try:
                    if texture:
                        sdl2.SDL_DestroyTexture(texture)
                except Exception:
                    pass
                return
            finally:
                try:
                    if surface:
                        sdl2.SDL_FreeSurface(surface)
                except Exception:
                    pass

        # Query original size
        w = ctypes.c_int()
        h = ctypes.c_int()
        sdl2.SDL_QueryTexture(texture, None, None, ctypes.byref(w), ctypes.byref(h))
        tex_w, tex_h = w.value, h.value
        if tex_w == 0 or tex_h == 0:
            return

        # Compute scale while preserving aspect ratio
        scale = min(max_w / tex_w, max_h / tex_h, 1.0)
        dw, dh = int(tex_w * scale), int(tex_h * scale)

        # Center in the allocated area
        desc_center_x = self.screen_width * 3 // 4 - 40
        desc_max_width = self.screen_width // 2
        desc_left_x = desc_center_x - desc_max_width // 2
        x = desc_left_x + (max_w - dw) // 2
        y = 40 + (max_h - dh) // 2

        dst_rect = sdl2.SDL_Rect(x, y, dw, dh)
        sdl2.SDL_RenderCopyEx(self.renderer, texture, None, dst_rect, 0, None, sdl2.SDL_FLIP_NONE)
        
    def draw_joystick_monitor(self, pos: Tuple[int, int], radius: int, x_val: float, y_val: float, label: str):
        self.draw_rectangle_outline(
            (pos[0] - radius, pos[1] - radius, radius * 2, radius * 2), 
            self.c_row_bg
        )
        
        self.draw_circle(pos, radius, fill=sdl2.SDL_Color(30, 30, 30, 255))
        knob_x = pos[0] + int(x_val * (radius - 5))
        knob_y = pos[1] + int(y_val * (radius - 5))
        knob_radius = radius // 3
        self.draw_circle((knob_x, knob_y), knob_radius, fill=self.c_btn_x)
        label_x = pos[0] - (self.get_text_width(label) // 2)
        self.draw_text((label_x, pos[1] + radius + 5), label)
        
    def draw_trigger_gauge(self, pos: Tuple[int, int], size: Tuple[int, int], value: float, label: str):
        x, y = pos
        w, h = size
        
        self.draw_rectangle((x, y, w, h), fill=sdl2.SDL_Color(30, 30, 30, 255))
        self.draw_rectangle_outline((x, y, w, h), self.c_row_bg)
        
        fill_h = int(h * value)
        if fill_h > 0:
            self.draw_rectangle((x + 1, y + h - fill_h + 1, w - 2, fill_h - 2), fill=self.c_btn_a)
            
        tw = self.get_text_width(label)
        self.draw_text((x + (w // 2) - (tw // 2), y + h + 4), label)