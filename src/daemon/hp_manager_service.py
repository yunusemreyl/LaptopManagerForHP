#!/usr/bin/env python3
"""
HP Laptop Manager - D-Bus Daemon Service
Root olarak çalışır, donanım erişimi sağlar.
"""
import sys, os, time, threading, logging, json, copy, colorsys, math, shutil, subprocess, re, typing, glob, platform
from gi.repository import GLib
from pydbus import SystemBus

# --- PATHS ---
DRIVER_PATH_CUSTOM = "/sys/devices/platform/hp-rgb-lighting"
CONFIG_FILE = "/etc/hp-manager/state.json"

# --- LOGLAMA ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hp-manager")

lock = threading.RLock()
state_changed = threading.Event()  # Animasyon motorunu uyutmak/uyandırmak için eklendi
HEX_COLOR_RE = re.compile(r"^[0-9A-F]{6}$")
VALID_LIGHT_MODES = {"static", "breathing", "cycle", "wave"}
VALID_DIRECTIONS = {"ltr", "rtl"}
VALID_GPU_MODES = {"hybrid", "discrete", "integrated"}


# ============================================================
# FAN CONTROLLER
# ============================================================
class FanController:
    """
    hp-wmi driver hwmon interface:
      - fan{1,2}_input  : current RPM (read-only)
      - fan{1,2}_max    : max RPM (read-only)
      - fan{1,2}_target : target RPM (read-write, for manual mode)
      - pwm1_enable     : global fan mode (0=max, 1=manual, 2=auto)
    """
    def __init__(self):
        self.hwmon_path = self._find_hwmon()
        self.fan_count = 0
        self.found_fans = []
        self.max_speeds = {}
        self.mode = "auto"
        if self.hwmon_path:
            self._detect_fans()
            self._read_max_speeds()
            self._read_current_mode()

    def _find_hwmon(self):
        """Find the 'hp' hwmon device."""
        for path in glob.glob("/sys/class/hwmon/hwmon*/name"):
            try:
                with open(path, 'r') as f:
                    if f.read().strip() == "hp":
                        logger.info(f"Found HP hwmon at {os.path.dirname(path)}")
                        return os.path.dirname(path)
            except Exception:
                pass

        for platform_name in ("hp-wmi", "hp_wmi"):
            platform_hwmon = f"/sys/devices/platform/{platform_name}/hwmon"
            if os.path.exists(platform_hwmon):
                try:
                    entries = sorted(os.listdir(platform_hwmon))
                    if entries:
                        path = os.path.join(platform_hwmon, entries[0])
                        logger.info(f"Found HP hwmon via platform device at {path}")
                        return path
                except Exception:
                    pass

        logger.warning("No HP hwmon device found")
        return None

    def _detect_fans(self):
        if not self.hwmon_path:
            return
        for f in os.listdir(self.hwmon_path):
            if f.startswith("fan") and f.endswith("_input"):
                try:
                    self.found_fans.append(int(f[3:-6]))
                except ValueError:
                    continue
        self.found_fans.sort()
        self.fan_count = len(self.found_fans)

    def _read_max_speeds(self):
        """Read actual max RPMs from driver."""
        if not self.hwmon_path:
            return
        for i in self.found_fans:
            max_path = os.path.join(self.hwmon_path, f"fan{i}_max")
            try:
                with open(max_path) as f:
                    self.max_speeds[i] = int(f.read().strip())
            except Exception:
                self.max_speeds[i] = 6000

    def _read_current_mode(self):
        """Read pwm1_enable to determine current mode."""
        if not self.hwmon_path:
            return
        pwm_path = os.path.join(self.hwmon_path, "pwm1_enable")
        try:
            with open(pwm_path) as f:
                val = int(f.read().strip())
            self.mode = {0: "max", 1: "custom"}.get(val, "auto")
        except Exception:
            self.mode = "auto"

    def _sysfs_read(self, filename):
        if not self.hwmon_path:
            return 0
        try:
            with open(os.path.join(self.hwmon_path, filename)) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def _sysfs_write(self, filename, value):
        if not self.hwmon_path:
            return False
        try:
            with open(os.path.join(self.hwmon_path, filename), "w") as f:
                f.write(str(value))
            return True
        except Exception as e:
            logger.error(f"sysfs write {filename}={value} error: {e}")
            return False

    def get_fan_count(self):
        return self.fan_count

    def get_max_speed(self, fan_num):
        return self.max_speeds.get(fan_num, 6000)

    def get_current_speed(self, fan_num):
        return self._sysfs_read(f"fan{fan_num}_input")

    def get_target_speed(self, fan_num):
        return self._sysfs_read(f"fan{fan_num}_target")

    def set_mode(self, mode):
        """Set fan mode: 'auto' (pwm1_enable=2), 'max' (pwm1_enable=0), 'custom' (pwm1_enable=1)."""
        if not self.hwmon_path:
            return False
        val = {"auto": 2, "max": 0, "custom": 1}.get(mode)
        if val is None:
            return False
        ok = self._sysfs_write("pwm1_enable", val)
        if ok:
            self.mode = mode
            logger.info(f"Fan mode set to {mode} (pwm1_enable={val})")
        return ok

    def set_fan_target(self, fan_num, rpm):
        """Set target RPM for a specific fan (only effective in custom mode)."""
        if not self.hwmon_path or fan_num not in self.found_fans:
            return False
        rpm = max(0, min(rpm, self.get_max_speed(fan_num)))
        ok = self._sysfs_write(f"fan{fan_num}_target", rpm)
        if ok:
            logger.info(f"Fan {fan_num} target set to {rpm} RPM")
        return ok

    def is_available(self):
        return self.hwmon_path is not None and self.fan_count > 0

    def get_mode(self):
        if self.hwmon_path:
            self._read_current_mode()
        return self.mode


# ============================================================
# RGB CONTROLLER
# ============================================================
class RGBController:
    def __init__(self):
        self.driver_path = self._find_rgb_path()
        self.available = self.driver_path is not None
        self.last_written = [None] * 8

    def _find_rgb_path(self):
        """Find the RGB control sysfs path."""
        if os.path.exists(DRIVER_PATH_CUSTOM):
            logger.info(f"RGB: Using custom driver path {DRIVER_PATH_CUSTOM}")
            return DRIVER_PATH_CUSTOM
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
            if "hp_rgb_lighting" in result.stdout:
                for candidate in ("/sys/devices/platform/hp-rgb-lighting",
                                  "/sys/devices/platform/hp_rgb_lighting"):
                    if os.path.exists(candidate):
                        logger.info(f"RGB: Found loaded module at {candidate}")
                        return candidate
        except Exception:
            pass
        logger.info("RGB: No RGB control path found (hp-rgb-lighting not loaded)")
        return None

    def is_available(self):
        return self.available

    def write_zone(self, zone, hex_color):
        if not self.available or not (0 <= zone <= 7):
            return
        if self.last_written[zone] == hex_color:
            return
        try:
            with open(f"{self.driver_path}/zone{zone}", "w") as f:
                f.write(hex_color)
                f.flush()
            self.last_written[zone] = hex_color
        except Exception:
            pass

    def write_all(self, hex_list):
        for i, hc in enumerate(hex_list[:8]):
            self.write_zone(i, hc)

    def write_brightness(self, on):
        if not self.available:
            return
        try:
            with open(f"{self.driver_path}/brightness", "w") as f:
                f.write("1" if on else "0")
                f.flush()
        except Exception:
            pass

    def write_win_lock(self, locked):
        if not self.available:
            return
        try:
            with open(f"{self.driver_path}/win_lock", "w") as f:
                f.write("1" if locked else "0")
                f.flush()
        except Exception:
            pass


# ============================================================
# POWER PROFILE CONTROLLER
# ============================================================
class PowerProfileController:
    PPD_BUS   = "net.hadess.PowerProfiles"
    PPD_PATH  = "/net/hadess/PowerProfiles"
    TUNED_BUS = "com.redhat.tuned"
    TUNED_PATH = "/Tuned"

    def __init__(self):
        self.mode = "ppd"
        self.available = False
        self.bus = SystemBus()
        self.proxy = None

        # Try Tuned first (Fedora default)
        try:
            self.proxy = self.bus.get(self.TUNED_BUS, self.TUNED_PATH)
            self.proxy.active_profile()
            self.mode = "tuned"
            self.available = True
            logger.info("PowerProfileController: Using Tuned backend")
        except Exception:
            try:
                self.proxy = self.bus.get(self.PPD_BUS, self.PPD_PATH)
                self.mode = "ppd"
                self.available = True
                logger.info("PowerProfileController: Using Power-Profiles-Daemon backend")
            except Exception:
                self.proxy = None
                self.available = False
                logger.warning("PowerProfileController: No power profile backend found")

    def get_profiles(self):
        if not self.available:
            return []
        if self.mode == "ppd":
            try:
                return [p["Profile"] for p in self.proxy.Profiles]
            except Exception:
                return ["power-saver", "balanced", "performance"]
        return ["power-saver", "balanced", "performance"]

    def get_active(self):
        if not self.available:
            return "balanced"
        try:
            if self.mode == "ppd":
                return self.proxy.ActiveProfile
            tp = self.proxy.active_profile()
            if "powersave" in tp:   return "power-saver"
            if "performance" in tp: return "performance"
            return "balanced"
        except Exception:
            return "balanced"

    def set_profile(self, profile):
        if not self.available:
            return False
        try:
            if self.mode == "ppd":
                self.proxy.ActiveProfile = profile
            else:
                mapping = {
                    "power-saver": "powersave",
                    "balanced":    "balanced",
                    "performance": "throughput-performance",
                }
                self.proxy.switch_profile(mapping.get(profile, "balanced"))
            return True
        except Exception as e:
            logger.error(f"Power profile set error ({self.mode}): {e}")
            return False


# ============================================================
# MUX CONTROLLER
# ============================================================
class MUXController:
    def __init__(self):
        self.envycontrol  = shutil.which("envycontrol")
        self.supergfxctl  = shutil.which("supergfxctl")
        self.prime_select = shutil.which("prime-select")
        self.backend: typing.Optional[str] = None
        self._detect_backend()

    def _detect_backend(self):
        if self.envycontrol:
            self.backend = "envycontrol"
        elif self.supergfxctl:
            self.backend = "supergfxctl"
        elif self.prime_select:
            self.backend = "prime-select"

    def is_available(self):
        return self.backend is not None

    def get_backend(self):
        return self.backend or "none"

    def get_mode(self):
        try:
            if self.backend == "envycontrol" and self.envycontrol:
                return subprocess.check_output([self.envycontrol, "--query"],
                                               stderr=subprocess.STDOUT, timeout=5).decode().strip().lower()
            elif self.backend == "supergfxctl" and self.supergfxctl:
                return subprocess.check_output([self.supergfxctl, "-g"],
                                               stderr=subprocess.STDOUT, timeout=5).decode().strip().lower()
            elif self.backend == "prime-select" and self.prime_select:
                return subprocess.check_output([self.prime_select, "query"],
                                               stderr=subprocess.STDOUT, timeout=5).decode().strip().lower()
        except Exception:
            pass
        return "unknown"

    def set_mode(self, mode):
        try:
            if self.backend == "envycontrol" and self.envycontrol:
                subprocess.run([self.envycontrol, "-s", mode], check=True, timeout=10)
                return "OK"
            elif self.backend == "supergfxctl" and self.supergfxctl:
                m = {"hybrid": "Hybrid", "discrete": "Dedicated", "integrated": "Integrated"}.get(mode, mode)
                subprocess.run([self.supergfxctl, "-m", m], check=True, timeout=10)
                return "OK"
            elif self.backend == "prime-select" and self.prime_select:
                m = {"hybrid": "on-demand", "discrete": "nvidia", "integrated": "intel"}.get(mode, mode)
                subprocess.run([self.prime_select, m], check=True, timeout=10)
                return "OK"
        except Exception as e:
            return f"Error: {e}"
        return "No backend"


# ============================================================
# ANIMATION ENGINE
# ============================================================
class AnimationEngine(threading.Thread):
    FRAME_TIME = 0.05  # 20 fps

    def __init__(self, rgb_ctrl):
        super().__init__(daemon=True)
        self.rgb = rgb_ctrl
        self.running = True

    def run(self):
        logger.info("Animation engine started")
        while self.running:
            loop_start = time.time()
            with lock:
                pwr  = bool(state.get("power", True))
                mode = str(state.get("mode", "static"))
                bri  = float(state.get("brightness", 100)) / 100.0
                spd  = float(state.get("speed", 50))
                cols = [str(c) for c in state.get("colors", ["FF0000"] * 8)]
                d    = str(state.get("direction", "ltr"))

            if not pwr:
                self.rgb.write_brightness(False)
                self.rgb.write_all(["000000"] * 8)
                state_changed.clear()
                state_changed.wait() # Kapalıyken sonsuza kadar uyur
                continue

            self.rgb.write_brightness(True)
            t = time.time()
            targets = []

            if mode == "static":
                targets = [self._hex_to_rgb(c) for c in cols]
                self.rgb.write_all([
                    f"{int(r * bri):02X}{int(g * bri):02X}{int(b * bri):02X}"
                    for r, g, b in targets
                ])
                state_changed.clear()
                state_changed.wait() # Statik renkteyken işlem biter bitmez uyur
                continue
                
            elif mode == "breathing":
                period = 8.0 - (spd * 0.06)
                phase  = 0.1 + 0.9 * ((math.sin(2 * math.pi * t / period) + 1) / 2)
                base   = self._hex_to_rgb(cols[0])
                targets = [(int(base[0] * phase), int(base[1] * phase), int(base[2] * phase))] * 8
            elif mode == "cycle":
                hue = (t * (spd * 0.003)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                targets = [(int(r * 255), int(g * 255), int(b * 255))] * 8
            elif mode == "wave":
                for i in range(8):
                    offset = (i * 0.15) if d == "ltr" else ((7 - i) * 0.15)
                    r, g, b = colorsys.hsv_to_rgb((t * spd * 0.007 + offset) % 1.0, 1.0, 1.0)
                    targets.append((int(r * 255), int(g * 255), int(b * 255)))

            self.rgb.write_all([
                f"{int(r * bri):02X}{int(g * bri):02X}{int(b * bri):02X}"
                for r, g, b in targets
            ])

            sleep_time = max(self.FRAME_TIME - (time.time() - loop_start), 0.001)
            # Eğer bekleme sırasında bir event tetiklenirse, bekleme kırılır ve anında tepki verir
            if state_changed.wait(timeout=sleep_time):
                state_changed.clear()

    def _hex_to_rgb(self, h):
        h = str(h).lstrip("#")
        if not h or len(h) < 6:
            logger.warning(f"Invalid hex color: '{h}', falling back to red")
            return (255, 0, 0)
        try:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError as e:
            logger.error(f"Hex conversion error for '{h}': {e}")
            return (255, 0, 0)


# ============================================================
# STATE
# ============================================================
state: typing.Dict[str, typing.Any] = {
    "mode":          "static",
    "colors":        ["FF0000"] * 8,
    "speed":         50,
    "brightness":    100,
    "direction":     "ltr",
    "power":         True,
    "fan_mode":      "auto",
    "power_profile": "balanced",
    "win_lock":      False,
    "prtsc_fix":     False,
    "f1_fix":        False,
}

ALLOWED_PACKAGES = {
    "steam":       "com.valvesoftware.Steam",
    "lutris":      "net.lutris.Lutris",
    "protonup-qt": "net.davidotek.pupgui2",
    "heroic":      "com.heroicgameslauncher.hgl",
    "mangohud":    "org.freedesktop.Platform.VulkanLayer.MangoHud",
}

fan_ctrl   = FanController()
rgb_ctrl   = RGBController()
power_ctrl = PowerProfileController()
mux_ctrl   = MUXController()
engine     = AnimationEngine(rgb_ctrl)


def save_state():
    with lock:
        try:
            snapshot = copy.deepcopy(state)
        except Exception as e:
            logger.error(f"State snapshot error: {e}")
            return
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(snapshot, f)
    except Exception as e:
        logger.error(f"State save error: {e}")
    finally:
        state_changed.set()  # Durum kaydedildiğinde animasyon motorunu uyandır


def load_state():
    with lock:
        try:
            if not os.path.exists(CONFIG_FILE):
                return
            with open(CONFIG_FILE) as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                return

            if loaded.get("mode") in VALID_LIGHT_MODES:
                state["mode"] = loaded["mode"]

            colors = loaded.get("colors")
            if isinstance(colors, list):
                cleaned: typing.List[str] = []
                for i, c in enumerate(colors):
                    if i >= 8:
                        break
                    c_str = str(c).lstrip("#").upper()
                    if HEX_COLOR_RE.match(c_str):
                        cleaned.append(c_str)
                if cleaned:
                    c0 = cleaned[0]
                    state["colors"] = (cleaned + [c0] * 8)[:8]

            speed = loaded.get("speed")
            if isinstance(speed, int):
                state["speed"] = max(1, min(speed, 100))

            brightness = loaded.get("brightness")
            if isinstance(brightness, int):
                state["brightness"] = max(0, min(brightness, 100))

            if loaded.get("direction") in VALID_DIRECTIONS:
                state["direction"] = loaded["direction"]

            if isinstance(loaded.get("power"), bool):
                state["power"] = loaded["power"]

            fm = loaded.get("fan_mode")
            if fm in ("auto", "max", "custom"):
                state["fan_mode"] = fm

            pp = loaded.get("power_profile")
            if isinstance(pp, str) and pp in ("power-saver", "balanced", "performance"):
                state["power_profile"] = pp

            # --- Keyboard fixes ---
            if isinstance(loaded.get("prtsc_fix"), bool):
                state["prtsc_fix"] = loaded["prtsc_fix"]
            if isinstance(loaded.get("f1_fix"), bool):
                state["f1_fix"] = loaded["f1_fix"]

            # --- Win lock ---
            if isinstance(loaded.get("win_lock"), bool):
                state["win_lock"] = loaded["win_lock"]

        except Exception as e:
            logger.error(f"State load error: {e}")


# ============================================================
# D-BUS SERVICE
# ============================================================
class HPManagerService(object):
    """
    <node>
      <interface name="com.yyl.hpmanager">
        <method name="SetColor"><arg type="i" name="z" direction="in"/><arg type="s" name="h" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetMode"><arg type="s" name="m" direction="in"/><arg type="i" name="s" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetGlobal"><arg type="b" name="p" direction="in"/><arg type="i" name="b" direction="in"/><arg type="s" name="d" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetState"><arg type="s" name="j" direction="out"/></method>
        <method name="SetFanMode"><arg type="s" name="mode" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetFanTarget"><arg type="i" name="fan" direction="in"/><arg type="i" name="rpm" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetFanInfo"><arg type="s" name="j" direction="out"/></method>
        <method name="SetPowerProfile"><arg type="s" name="profile" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetPowerProfile"><arg type="s" name="j" direction="out"/></method>
        <method name="SetGpuMode"><arg type="s" name="mode" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="GetGpuInfo"><arg type="s" name="j" direction="out"/></method>
        <method name="GetSystemInfo"><arg type="s" name="j" direction="out"/></method>
        <method name="CleanMemory"><arg type="s" name="result" direction="out"/></method>
        <method name="InstallPackage"><arg type="s" name="pkg" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="SetWinLock"><arg type="b" name="locked" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="SetKeyboardFixes"><arg type="b" name="prtsc" direction="in"/><arg type="b" name="f1" direction="in"/><arg type="s" name="result" direction="out"/></method>
      </interface>
    </node>
    """

    def SetColor(self, z, h):
        c = str(h).lstrip("#").upper()
        if not HEX_COLOR_RE.match(c):
            return "FAIL"
        with lock:
            state["mode"]  = "static"
            state["power"] = True
            if z == 8:
                state["colors"] = [c] * 8
            elif 0 <= z < 8:
                state["colors"][z] = c
            else:
                return "FAIL"
        save_state()
        return "OK"

    def SetMode(self, m, s):
        if m not in VALID_LIGHT_MODES:
            return "FAIL"
        with lock:
            state["mode"]  = m
            state["speed"] = max(1, min(int(s), 100))
            state["power"] = True
        save_state()
        return "OK"

    def SetGlobal(self, p, b, d):
        if d not in VALID_DIRECTIONS:
            return "FAIL"
        with lock:
            state["power"]      = bool(p)
            state["brightness"] = max(0, min(int(b), 100))
            state["direction"]  = d
        save_state()
        return "OK"

    def GetState(self):
        with lock:
            return json.dumps(state)

    def SetFanMode(self, mode):
        """Set fan mode: 'auto', 'max', or 'custom'."""
        logger.info(f"SetFanMode: {mode}")
        ok = fan_ctrl.set_mode(mode)
        if ok:
            with lock:
                state["fan_mode"] = mode
            save_state()
        return "OK" if ok else "FAIL"

    def SetFanTarget(self, fan, rpm):
        """Set target RPM for a specific fan (in custom mode)."""
        logger.info(f"SetFanTarget: fan={fan}, rpm={rpm}")
        return "OK" if fan_ctrl.set_fan_target(fan, rpm) else "FAIL"

    def GetFanInfo(self):
        fans_data = {
            str(i): {
                "current": fan_ctrl.get_current_speed(i),
                "max":     fan_ctrl.get_max_speed(i),
                "target":  fan_ctrl.get_target_speed(i),
            }
            for i in fan_ctrl.found_fans
        }
        return json.dumps({
            "available":  fan_ctrl.is_available(),
            "fan_count":  fan_ctrl.get_fan_count(),
            "mode":       fan_ctrl.get_mode(),
            "fans":       fans_data,
        })

    def SetPowerProfile(self, profile):
        if profile not in power_ctrl.get_profiles():
            return "FAIL"
        ok = power_ctrl.set_profile(profile)
        if ok:
            with lock:
                state["power_profile"] = profile
            save_state()
        return "OK" if ok else "FAIL"

    def GetPowerProfile(self):
        return json.dumps({
            "available": power_ctrl.available,
            "active":    power_ctrl.get_active(),
            "profiles":  power_ctrl.get_profiles(),
        })

    def SetGpuMode(self, mode):
        if mode not in VALID_GPU_MODES:
            return "FAIL"
        return mux_ctrl.set_mode(mode)

    def GetGpuInfo(self):
        return json.dumps({
            "available": mux_ctrl.is_available(),
            "backend":   mux_ctrl.get_backend(),
            "mode":      mux_ctrl.get_mode(),
        })

    def GetSystemInfo(self):
        now = time.time()
        si  = state.get("_system_info_cache")
        
        # Süre (2 saniye) dolmadıysa hiçbir donanım sorgusu yapma, doğrudan cache'i dön.
        if si and (now - state.get("_system_info_last", 0) < 2.0):
            return json.dumps(si)

        info = {
            "hostname":     platform.node(),
            "kernel":       platform.release(),
            "os_name":      "Linux",
            "cpu_temp":     self._get_cached_cpu_temp(),
            "gpu_temp":     self._get_cached_gpu_temp(),
            "product_name": "HP Laptop",
        }
        for dmi_file in ("/sys/devices/virtual/dmi/id/product_name",
                         "/sys/devices/virtual/dmi/id/product_family"):
            if os.path.exists(dmi_file):
                try:
                    with open(dmi_file) as f:
                        info["product_name"] = f.read().strip()
                    break
                except Exception:
                    pass

        state["_system_info_cache"] = info
        state["_system_info_last"]  = now
        return json.dumps(info)

    def _get_cached_cpu_temp(self):
        best_t, best_score = 0.0, -1000
        RANK_DRV = {"zenpower": 100, "coretemp": 90, "k10temp": 90,
                    "cpu_thermal": 80, "hp_wmi": 60, "acpitz": 30}
        RANK_LBL = {"tdie": 100, "package id 0": 95, "tctl": 90, "core": 80, "composite": 50}
        try:
            for d in os.listdir("/sys/class/hwmon"):
                path = os.path.join("/sys/class/hwmon", d)
                try:
                    with open(os.path.join(path, "name")) as f:
                        drv = f.read().strip().lower()
                except Exception:
                    continue
                d_score = RANK_DRV.get(drv, 10)
                for tf in glob.glob(os.path.join(path, "temp*_input")):
                    try:
                        with open(tf) as f:
                            t = int(f.read().strip()) / 1000.0
                        if not (0 < t <= 125):
                            continue
                        label = ""
                        lp = tf.replace("_input", "_label")
                        if os.path.exists(lp):
                            with open(lp) as f:
                                label = f.read().strip().lower()
                        l_score = max((v for k, v in RANK_LBL.items() if k in label), default=0)
                        score   = d_score + l_score - (500 if t in (75.0, 0.0) else 0)
                        if score > best_score:
                            best_score, best_t = score, t
                    except Exception:
                        pass
        except Exception:
            pass
        return best_t

    def _get_cached_gpu_temp(self):
        # 1. Önce Sysfs üzerinden oku (Sıfıra yakın CPU tüketimi)
        try:
            for d in os.listdir("/sys/class/hwmon"):
                path = os.path.join("/sys/class/hwmon", d)
                try:
                    with open(os.path.join(path, "name")) as f:
                        name = f.read().strip().lower()
                    if name in ("amdgpu", "i915", "nouveau"):
                        with open(os.path.join(path, "temp1_input")) as f:
                            return int(f.read().strip()) / 1000.0
                except Exception:
                    continue
        except Exception:
            pass

        # 2. Eğer hwmon üzerinden gpu bulunamazsa nvidia-smi kullan (Ağır işlem)
        if shutil.which("nvidia-smi"):
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                    stderr=subprocess.DEVNULL, timeout=2
                ).decode().strip()
                return float(out)
            except Exception:
                pass
                
        return "NOT_REACHABLE"

    def CleanMemory(self):
        """Clear pagecache, dentries, and inodes as root."""
        try:
            subprocess.run(["sync"], check=True, timeout=5)
            with open("/proc/sys/vm/drop_caches", "w") as f:
                f.write("3\n")
            return "OK"
        except Exception as e:
            return f"Error: {e}"

    def InstallPackage(self, pkg):
        """Install only whitelisted gaming packages via Flatpak."""
        flatpak_id = ALLOWED_PACKAGES.get(str(pkg).strip().lower())
        if not flatpak_id:
            return "Error: package_not_allowed"
        if shutil.which("flatpak"):
            try:
                subprocess.run(
                    ["flatpak", "install", "-y", "--noninteractive", "flathub", flatpak_id],
                    check=True, capture_output=True, timeout=120
                )
                return "OK"
            except Exception:
                return "Error: flatpak_install_failed"
        return "No supported package manager found"

    def SetWinLock(self, locked):
        logger.info(f"SetWinLock: {'LOCKED' if locked else 'UNLOCKED'}")
        with lock:
            state["win_lock"] = bool(locked)
        rgb_ctrl.write_win_lock(bool(locked))
        save_state()
        return "OK"

    def SetKeyboardFixes(self, prtsc, f1):
        """Apply/update persistent hwdb rules for keyboard scancodes."""
        logger.info(f"SetKeyboardFixes: prtsc={prtsc}, f1={f1}")
        with lock:
            state["prtsc_fix"] = bool(prtsc)
            state["f1_fix"]    = bool(f1)
        self._write_hwdb_rules(prtsc, f1)
        save_state()
        return "OK"

    def _write_hwdb_rules(self, prtsc, f1):
        hwdb_path = "/etc/udev/hwdb.d/90-hp-keyboard-fixes.hwdb"

        if not prtsc and not f1:
            if os.path.exists(hwdb_path):
                try:
                    os.remove(hwdb_path)
                    subprocess.run(["systemd-hwdb", "update"], capture_output=True)
                    subprocess.run(["udevadm", "trigger", "-s", "input"], capture_output=True)
                except Exception:
                    pass
            return

        content = [
            "# HP Keyboard Fixes - Generated by HP Laptop Manager",
            "evdev:atkbd:dmi:bvn*:bvr*:bd*:svnHP*:pn*:*",
        ]
        if prtsc:
            content.append(" KEYBOARD_KEY_b7=sysrq")   # PrtSc -> SysRq
        if f1:
            content.append(" KEYBOARD_KEY_ab=f1")        # Presentation key -> F1

        new_content = "\n".join(content) + "\n"

        # OPTİMİZASYON: Dosya içeriği aynıysa ağır hwdb derlemesini tamamen atla!
        if os.path.exists(hwdb_path):
            try:
                with open(hwdb_path, "r") as f:
                    if f.read() == new_content:
                        return
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(hwdb_path), exist_ok=True)
            with open(hwdb_path, "w") as f:
                f.write(new_content)

            def _apply():
                try:
                    subprocess.run(["systemd-hwdb", "update"], check=True)
                    subprocess.run(["udevadm", "trigger", "-s", "input"], check=True)
                    logger.info("Keyboard fixes applied via hwdb successfully")
                except Exception as e:
                    logger.error(f"Failed to apply hwdb: {e}")

            threading.Thread(target=_apply, daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to write hwdb rules: {e}")


# ============================================================
# MAIN
# ============================================================
def main():
    if os.geteuid() != 0:
        print("Root yetkisi gerekli (sudo).")
        sys.exit(1)

    load_state()

    # Restore fan mode
    if fan_ctrl.is_available():
        saved_fan = state.get("fan_mode", "auto")
        if saved_fan == "custom":
            saved_fan = "auto"
            state["fan_mode"] = "auto"
            logger.warning("Custom fan mode not restorable (no saved targets), falling back to auto")
        if saved_fan in ("auto", "max"):
            ok = fan_ctrl.set_mode(saved_fan)
            logger.info(f"Restored fan mode '{saved_fan}' (success={ok})")

    # Restore power profile
    if power_ctrl.available:
        saved_pp = state.get("power_profile", "balanced")
        if saved_pp in power_ctrl.get_profiles():
            ok = power_ctrl.set_profile(saved_pp)
            logger.info(f"Restored power profile '{saved_pp}' (success={ok})")

    service = HPManagerService()

    # Restore keyboard fixes
    if state.get("prtsc_fix") or state.get("f1_fix"):
        service.SetKeyboardFixes(state.get("prtsc_fix"), state.get("f1_fix"))

    # Restore RGB / win-lock
    if rgb_ctrl.is_available():
        rgb_ctrl.write_win_lock(state.get("win_lock", False))
        engine.start()
        logger.info("RGB engine started")

    try:
        bus = SystemBus()
        bus.publish("com.yyl.hpmanager", service)
        logger.info("HP Manager Daemon ready on D-Bus")
        if fan_ctrl.is_available():
            logger.info(f"Fan control active: {fan_ctrl.get_fan_count()} fans")
        if power_ctrl.available:
            logger.info(f"Power profiles: {power_ctrl.get_profiles()}")
        if mux_ctrl.is_available():
            logger.info(f"MUX backend: {mux_ctrl.get_backend()}")
        GLib.MainLoop().run()
    except Exception as e:
        logger.critical(f"Service error: {e}")


if __name__ == "__main__":
    main()
