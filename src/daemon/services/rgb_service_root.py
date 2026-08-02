#!/usr/bin/env python3
"""OMEN Command Center for Linux — RGB Microservice.

Owns RGB LED zone control and all lighting animation modes.
Exposes its functionality over D-Bus as ``com.yyl.hpmanager.rgb``.
"""

import json
import os
import re
import sys
import threading
import time
import math
import random
import typing

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.dbus_helpers import run_service

logger = setup_logging("rgb")

DRIVER_PATH_NEW = "/sys/devices/platform/omen-rgb-keyboard/rgb_zones"
DRIVER_PATH_CUSTOM = "/sys/devices/platform/hp-rgb-lighting"
HEX_COLOR_RE = re.compile(r"^[0-9A-F]{6}$")

VALID_LIGHT_MODES = {"static", "breathing", "wave", "cycle", "rainbow", "pulse", "chase", "sparkle", "candle", "aurora", "disco", "gradient"}
VALID_DIRECTIONS = {"ltr", "rtl"}

class RGBController:
    """Low-level RGB LED zone access via sysfs."""

    def __init__(self):
        self.driver_path = self._find_rgb_path()
        self.available = self.driver_path is not None
        self.is_new_driver = self.available and "omen-rgb-keyboard" in self.driver_path
        self.unsupported = not self.available
        self.zone_count = self._detect_zone_count()
        self._color_cache = {}

    def _detect_zone_count(self):
        if not self.available:
            return 0
        if self.is_new_driver:
            return 8
        zone4 = os.path.join(self.driver_path, "zone4")
        zone4_new = os.path.join(self.driver_path, "zone04")
        if os.path.exists(zone4) or os.path.exists(zone4_new):
            return 8
        return 4

    def _find_rgb_path(self):
        if os.path.exists(DRIVER_PATH_NEW):
            logger.info("RGB: Using new driver path %s", DRIVER_PATH_NEW)
            return DRIVER_PATH_NEW
        if os.path.exists(DRIVER_PATH_CUSTOM):
            logger.info("RGB: Using custom driver path %s", DRIVER_PATH_CUSTOM)
            return DRIVER_PATH_CUSTOM

        for candidate in (
            "/sys/devices/platform/hp-rgb-lighting",
            "/sys/devices/platform/hp_rgb_lighting",
        ):
            if os.path.exists(candidate):
                logger.info("RGB: Found loaded module at %s", candidate)
                return candidate

        self._try_load_rgb_drivers()

        for check in (DRIVER_PATH_NEW, DRIVER_PATH_CUSTOM,
                      "/sys/devices/platform/hp-rgb-lighting",
                      "/sys/devices/platform/hp_rgb_lighting"):
            if os.path.exists(check):
                logger.info("RGB: Driver path available after modprobe: %s", check)
                return check

        logger.info("RGB: No RGB control path found (hp_rgb_lighting / omen-rgb-keyboard not loaded)")
        return None

    @staticmethod
    def _try_load_rgb_drivers():
        import subprocess as _sp
        for mod in ("omen-rgb-keyboard", "hp_rgb_lighting", "hp-rgb-lighting"):
            try:
                result = _sp.run(["modprobe", mod], capture_output=True, timeout=5)
                if result.returncode == 0:
                    logger.info("RGB: Loaded kernel module '%s'", mod)
                    return
            except Exception as e:
                logger.debug("RGB: modprobe %s failed: %s", mod, e)

    def is_available(self):
        return self.available

    def write_zone(self, zone, hex_color):
        if not self.available or not (0 <= zone <= 7):
            return
            
        # Skip redundant sysfs I/O if the zone color hasn't changed.
        if self._color_cache.get(zone) == hex_color:
            return
        self._color_cache[zone] = hex_color
        
        if 0 <= zone <= 3:
            zone = 3 - zone
        
        filename = f"zone{zone:02d}" if self.is_new_driver else f"zone{zone}"
        path = f"{self.driver_path}/{filename}"
        
        try:
            with open(path, "w") as f:
                f.write(hex_color)
        except Exception as e:
            pass

    def write_all(self, hex_color):
        if not self.available:
            return
        if self.is_new_driver:
            try:
                with open(f"{self.driver_path}/all", "w") as f:
                    f.write(hex_color)
            except Exception as e:
                logger.error(f"Failed to write all zones: {e}")
        else:
            for i in range(self.zone_count):
                self.write_zone(i, hex_color)

    def write_brightness(self, value_or_bool):
        if not self.available:
            return
        try:
            with open(f"{self.driver_path}/brightness", "w") as f:
                if self.is_new_driver:
                    if isinstance(value_or_bool, bool):
                        val = "100" if value_or_bool else "0"
                    else:
                        val = str(int(value_or_bool))
                    f.write(val)
                else:
                    val = "1" if value_or_bool else "0"
                    f.write(val)
        except Exception as e:
            logger.error(f"Failed to write brightness: {e}")

    def read_brightness(self):
        if not self.available:
            return None
        try:
            with open(f"{self.driver_path}/brightness", "r") as f:
                val = f.read().strip()
                if self.is_new_driver:
                    return int(val) > 0
                return val == "1"
        except Exception:
            return None

    def write_win_lock(self, locked):
        if not self.available:
            return
        try:
            path = f"{self.driver_path}/win_lock"
            if os.path.exists(path):
                with open(path, "w") as f:
                    f.write("1" if locked else "0")
        except Exception:
            pass
            
    def write_mode(self, mode, speed=50):
        if not self.is_new_driver:
            return
        if mode == "cycle":
            mode = "rainbow"
        try:
            with open(f"{self.driver_path}/animation_mode", "w") as f:
                f.write(mode)
            mapped_speed = max(1, min(10, int(speed / 10)))
            with open(f"{self.driver_path}/animation_speed", "w") as f:
                f.write(str(mapped_speed))
        except Exception as e:
            logger.error(f"Failed to write mode/speed: {e}")


class RGBService:
    """
    <node>
      <interface name="com.yyl.hpmanager.rgb">
        <method name="SetColor"><arg type="i" name="z" direction="in"/><arg type="s" name="h" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetMode"><arg type="s" name="m" direction="in"/><arg type="i" name="s" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetGlobal"><arg type="b" name="p" direction="in"/><arg type="i" name="b" direction="in"/><arg type="s" name="d" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetState"><arg type="s" name="j" direction="out"/></method>
        <method name="SetWinLock"><arg type="b" name="locked" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self._rgb = RGBController()
        self._config = ServiceConfig(
            "rgb",
            {
                "mode": "static",
                "colors": ["FF0000"] * 8,
                "speed": 50,
                "brightness": 100,
                "direction": "ltr",
                "power": True,
                "win_lock": False,
            },
        )
        self._config.load()

        colors = self._config.get("colors", [])
        if isinstance(colors, list):
            cleaned = []
            for c in colors[:8]:
                cs = str(c).lstrip("#").upper()
                if HEX_COLOR_RE.match(cs):
                    cleaned.append(cs)
            if cleaned:
                c0 = cleaned[0]
                self._config.set("colors", (cleaned + [c0] * 8)[:8])

        if self._config.get("mode") not in VALID_LIGHT_MODES:
            self._config.set("mode", "static")

        # User-space animation driver configuration properties
        self._anim_step = 0.0
        self._lock = threading.Lock()

        self._apply_current_state()
        
        if self._rgb.is_available():
            self._rgb.write_win_lock(self._config.get("win_lock", False))

        # Start the background software engine animation thread loop
        threading.Thread(target=self._software_animation_loop, daemon=True).start()
            
    def _apply_current_state(self):
        if not self._rgb.is_available():
            return

        with self._lock:
            power = self._config.get("power", True)
            brightness = self._config.get("brightness", 100)

            if not power or brightness == 0:
                self._rgb.write_brightness(0)
                return

            mode = self._config.get("mode", "static")
            speed = self._config.get("speed", 50)
            colors = self._config.get("colors", ["FF0000"] * 8)

            if self._rgb.is_new_driver:
                self._rgb.write_brightness(brightness)
                self._rgb.write_mode(mode, speed)
                if mode == "static":
                    for i in range(self._rgb.zone_count):
                        color = colors[i] if i < len(colors) else colors[0]
                        self._rgb.write_zone(i, color)
            else:
                self._rgb.write_brightness(1)
                if mode == "static":
                    scaler = max(0.0, min(1.0, float(brightness) / 100.0))
                    for i in range(self._rgb.zone_count):
                        raw_hex = colors[i] if i < len(colors) else colors[0]
                        self._write_scaled_zone_color(i, raw_hex, scaler)

    def _write_scaled_zone_color(self, zone_idx, raw_hex, scaler):
        try:
            r = int(raw_hex[0:2], 16)
            g = int(raw_hex[2:4], 16)
            b = int(raw_hex[4:6], 16)
        except (ValueError, IndexError):
            r, g, b = 255, 0, 0

        scaled_hex = f"{int(r * scaler):02X}{int(g * scaler):02X}{int(b * scaler):02X}"
        self._rgb.write_zone(zone_idx, scaled_hex)

    def _software_animation_loop(self):
        """Background loop executing software animations on the legacy driver framework."""
        while True:
            if not self._rgb.is_available() or self._rgb.is_new_driver:
                time.sleep(2.0)
                continue

            with self._lock:
                power = self._config.get("power", True)
                mode = self._config.get("mode", "static")

            if not power or mode == "static":
                time.sleep(0.5)
                continue

            time.sleep(0.05) # ~20Hz update rate framing ticks

            with self._lock:
                power = self._config.get("power", True)
                mode = self._config.get("mode", "static")
                if not power or mode == "static":
                    continue

                brightness = self._config.get("brightness", 100)
                scaler = max(0.0, min(1.0, float(brightness) / 100.0))
                speed = self._config.get("speed", 50)
                direction = self._config.get("direction", "ltr")
                colors = self._config.get("colors", ["FF0000"] * 8)
                zone_count = self._rgb.zone_count

                # Ramping animation frequency based on user selection
                step_increment = (speed / 100.0) * 0.25
                self._anim_step += step_increment

                try:
                    r1, g1 = int(colors[0][0:2], 16), int(colors[0][2:4], 16)
                    b1 = int(colors[0][4:6], 16)
                except Exception:
                    r1, g1, b1 = 255, 0, 0

                for i in range(zone_count):
                    # Direction inversion multiplier calculation
                    eff_idx = i if direction == "ltr" else (zone_count - 1 - i)
                    
                    if mode in ("wave", "rainbow", "cycle"):
                        # Calculate color phase shifting dynamically using a sine loop
                        hue_shift = self._anim_step + (eff_idx * (2.0 * math.pi / zone_count))
                        r = int((math.sin(hue_shift) * 127) + 128)
                        g = int((math.sin(hue_shift + 2.0 * math.pi / 3.0) * 127) + 128)
                        b = int((math.sin(hue_shift + 4.0 * math.pi / 3.0) * 127) + 128)
                        
                    elif mode in ("breathing", "pulse"):
                        # Global factor brightness modulation
                        factor = (math.sin(self._anim_step) * 0.5) + 0.5
                        r, g, b = int(r1 * factor), int(g1 * factor), int(b1 * factor)
                        
                    elif mode == "chase":
                        # Sequentially steps a lit frame block down the zone count index
                        pos = int(self._anim_step * 2) % zone_count
                        factor = 1.0 if eff_idx == pos else 0.15
                        r, g, b = int(r1 * factor), int(g1 * factor), int(b1 * factor)

                    elif mode == "sparkle":
                        # Simulated randomness per individual matrix zone
                        factor = random.uniform(0.1, 1.0) if random.random() > 0.75 else 0.2
                        r, g, b = int(r1 * factor), int(g1 * factor), int(b1 * factor)

                    elif mode == "candle":
                        # Low frequency organic noise flicker simulation
                        noise = (math.sin(self._anim_step) * 0.3) + (math.sin(self._anim_step * 2.3) * 0.15)
                        factor = max(0.3, min(1.0, 0.6 + noise))
                        # Tinting green channel down slightly to maintain a warm fire amber glow
                        r, g, b = int(r1 * factor), int(g1 * 0.6 * factor), int(b1 * 0.2 * factor)

                    elif mode == "aurora":
                        # Slow moving deep cyan, green, and purple fluid phase shift
                        hue_shift = (self._anim_step * 0.3) + (eff_idx * 0.5)
                        r = int((math.sin(hue_shift) * 40) + 40)
                        g = int((math.cos(hue_shift + 1.0) * 100) + 120)
                        b = int((math.sin(hue_shift + 2.0) * 90) + 140)

                    elif mode == "disco":
                        # Sharp random palette jumps synched directly to speed changes
                        beat = int(self._anim_step * 1.5)
                        random.seed(beat + eff_idx)
                        r = random.randint(0, 255)
                        g = random.randint(0, 255)
                        b = random.randint(0, 255)

                    elif mode == "gradient":
                        # Smooth cross-fading sweep between the first two custom color matrix elements
                        try:
                            r2, g2 = int(colors[1][0:2], 16), int(colors[1][2:4], 16)
                            b2 = int(colors[1][4:6], 16)
                        except Exception:
                            r2, g2, b2 = 0, 0, 255 # Default fallback gradient profile secondary anchor color
                        
                        blend_factor = (math.sin(self._anim_step + (eff_idx * 0.7)) * 0.5) + 0.5
                        r = int(r1 * (1.0 - blend_factor) + r2 * blend_factor)
                        g = int(g1 * (1.0 - blend_factor) + g2 * blend_factor)
                        b = int(b1 * (1.0 - blend_factor) + b2 * blend_factor)
                    else:
                        continue

                    scaled_hex = f"{int(r * scaler):02X}{int(g * scaler):02X}{int(b * scaler):02X}"
                    self._rgb.write_zone(i, scaled_hex)

    # ── D-Bus methods ─────────────────────────────────────────────────

    def SetColor(self, z, h):
        c = str(h).lstrip("#").upper()
        if not HEX_COLOR_RE.match(c):
            return "FAIL"

        self._config.set("mode", "static")
        self._config.set("power", True)
        if z == 8:
            self._config.set("colors", [c] * 8)
        elif 0 <= z < 8:
            colors = self._config.get("colors", ["FF0000"] * 8)
            colors[z] = c
            self._config.set("colors", colors)
        else:
            return "FAIL"
            
        self._config.save()
        self._apply_current_state()
        return "OK"

    def SetMode(self, m, s):
        if m not in VALID_LIGHT_MODES:
            return "FAIL"
        self._config.set("mode", m)
        self._config.set("speed", max(1, min(int(s), 100)))
        self._config.set("power", True)
        self._config.save()
        self._apply_current_state()
        return "OK"

    def SetGlobal(self, p, b, d):
        if d not in VALID_DIRECTIONS:
            return "FAIL"
        self._config.set("power", bool(p))
        self._config.set("brightness", max(0, min(int(b), 100)))
        self._config.set("direction", d)
        self._config.save()
        self._apply_current_state()
        return "OK"

    def GetState(self):
        snap = self._config.snapshot()
        snap["unsupported"] = getattr(self._rgb, "unsupported", False)
        snap["driver_active"] = self._rgb.available
        snap["driver_path"] = self._rgb.driver_path or ""
        snap["is_new_driver"] = getattr(self._rgb, "is_new_driver", False)
        if not self._rgb.available:
            snap["unavailable_reason"] = (
                "RGB kernel module not loaded. Install 'hp_rgb_lighting' or "
                "'omen-rgb-keyboard' and ensure it loads at boot "
                "(e.g. add to /etc/modules-load.d/)."
            )
        return json.dumps(snap)

    def SetWinLock(self, locked):
        logger.info("SetWinLock: %s", "LOCKED" if locked else "UNLOCKED")
        self._config.set("win_lock", bool(locked))
        self._rgb.write_win_lock(bool(locked))
        self._config.save()
        return "OK"

    def Ping(self):
        return "OK"

def main():
    service = RGBService()
    run_service("com.yyl.hpmanager.rgb", service, service_name="rgb")

if __name__ == "__main__":
    main()
