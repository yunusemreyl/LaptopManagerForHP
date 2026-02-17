#!/usr/bin/env python3
"""
HP Laptop Manager - D-Bus Daemon Service
Root olarak çalışır, donanım erişimi sağlar.
"""
import sys, os, time, threading, logging, json, colorsys, math, shutil, subprocess, re
from gi.repository import GLib
from pydbus import SystemBus

# --- PATHS ---
DRIVER_PATH = "/sys/devices/platform/hp-omen-rgb"
CONFIG_FILE = "/etc/hp-manager/state.json"

# --- LOGLAMA ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hp-manager")

lock = threading.RLock()
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
      - pwm1_enable     : global fan mode (0=max, 1=manual, 2=auto) — SINGLE control for ALL fans
    """
    def __init__(self):
        self.hwmon_path = self._find_hwmon()
        self.fan_count = 0
        self.max_speeds = {}
        self.mode = "auto"  # "auto", "max", "custom"
        if self.hwmon_path:
            self._detect_fans()
            self._read_max_speeds()
            self._read_current_mode()

    def _find_hwmon(self):
        """Find the 'hp' hwmon device."""
        if os.path.exists("/sys/class/hwmon"):
            for d in sorted(os.listdir("/sys/class/hwmon")):
                path = os.path.join("/sys/class/hwmon", d)
                name_file = os.path.join(path, "name")
                if os.path.exists(name_file):
                    try:
                        with open(name_file) as f:
                            name = f.read().strip().lower()
                        if name == "hp":
                            return path
                    except:
                        pass
        return None

    def _detect_fans(self):
        if not self.hwmon_path:
            return
        for i in range(1, 5):
            if os.path.exists(os.path.join(self.hwmon_path, f"fan{i}_input")):
                self.fan_count = i

    def _read_max_speeds(self):
        """Read actual max RPMs from driver."""
        for i in range(1, self.fan_count + 1):
            max_path = os.path.join(self.hwmon_path, f"fan{i}_max")
            try:
                with open(max_path) as f:
                    self.max_speeds[i] = int(f.read().strip())
            except:
                self.max_speeds[i] = 6000

    def _read_current_mode(self):
        """Read pwm1_enable to determine current mode."""
        pwm_path = os.path.join(self.hwmon_path, "pwm1_enable")
        try:
            with open(pwm_path) as f:
                val = int(f.read().strip())
            if val == 0:
                self.mode = "max"
            elif val == 1:
                self.mode = "custom"
            else:
                self.mode = "auto"
        except:
            self.mode = "auto"

    def _sysfs_read(self, filename):
        path = os.path.join(self.hwmon_path, filename)
        try:
            with open(path) as f:
                return int(f.read().strip())
        except:
            return 0

    def _sysfs_write(self, filename, value):
        path = os.path.join(self.hwmon_path, filename)
        try:
            with open(path, "w") as f:
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
        if not self.hwmon_path:
            return 0
        return self._sysfs_read(f"fan{fan_num}_input")

    def get_target_speed(self, fan_num):
        if not self.hwmon_path:
            return -1
        return self._sysfs_read(f"fan{fan_num}_target")

    def set_mode(self, mode):
        """Set fan mode: 'auto' (pwm1_enable=2), 'max' (pwm1_enable=0), 'custom' (pwm1_enable=1)."""
        if not self.hwmon_path:
            return False
        mode_map = {"auto": 2, "max": 0, "custom": 1}
        val = mode_map.get(mode)
        if val is None:
            return False

        # Workaround: Reset targets when switching to auto to Ensure EC takes over
        if mode == "auto":
            for i in range(1, self.fan_count + 1):
                # Bazı BIOS/EC versiyonlarında target 0 yapılmazsa manuel modda takılı kalabiliyor
                self._sysfs_write(f"fan{i}_target", 0)

        ok = self._sysfs_write("pwm1_enable", val)
        if ok:
            self.mode = mode
            logger.info(f"Fan mode set to {mode} (pwm1_enable={val})")
        return ok

    def set_fan_target(self, fan_num, rpm):
        """Set target RPM for a specific fan (only effective in manual/custom mode)."""
        if not self.hwmon_path or fan_num < 1 or fan_num > self.fan_count:
            return False
        # Clamp to max
        max_rpm = self.get_max_speed(fan_num)
        rpm = max(0, min(rpm, max_rpm))
        ok = self._sysfs_write(f"fan{fan_num}_target", rpm)
        if ok:
            logger.info(f"Fan {fan_num} target set to {rpm} RPM")
        return ok

    def is_available(self):
        return self.hwmon_path is not None and self.fan_count > 0

    def get_mode(self):
        """Return current mode string."""
        if self.hwmon_path:
            self._read_current_mode()
        return self.mode


# ============================================================
# RGB CONTROLLER
# ============================================================
class RGBController:
    def __init__(self):
        self.available = os.path.exists(DRIVER_PATH)
        self.last_written = [None] * 4

    def is_available(self):
        return self.available

    def write_zone(self, zone, hex_color):
        if not self.available or zone < 0 or zone > 3:
            return
        if self.last_written[zone] == hex_color:
            return
        path = f"{DRIVER_PATH}/zone{zone}"
        try:
            with open(path, "w") as f:
                f.write(hex_color)
                f.flush()
            self.last_written[zone] = hex_color
        except:
            pass

    def write_all(self, hex_list):
        for i, hc in enumerate(hex_list[:4]):
            self.write_zone(i, hc)


# ============================================================
# POWER PROFILE CONTROLLER (power-profiles-daemon)
# ============================================================
class PowerProfileController:
    PPD_BUS = "net.hadess.PowerProfiles"
    PPD_PATH = "/net/hadess/PowerProfiles"

    def __init__(self):
        try:
            bus = SystemBus()
            self.ppd = bus.get(self.PPD_BUS, self.PPD_PATH)
            self.available = True
        except:
            self.ppd = None
            self.available = False

    def get_profiles(self):
        if not self.available:
            return []
        try:
            return [p["Profile"] for p in self.ppd.Profiles]
        except:
            return ["power-saver", "balanced", "performance"]

    def get_active(self):
        if not self.available:
            return "balanced"
        try:
            return self.ppd.ActiveProfile
        except:
            return "balanced"

    def set_profile(self, profile):
        if not self.available:
            return False
        try:
            self.ppd.ActiveProfile = profile
            return True
        except Exception as e:
            logger.error(f"Power profile set error: {e}")
            return False


# ============================================================
# MUX CONTROLLER
# ============================================================
class MUXController:
    def __init__(self):
        self.envycontrol = shutil.which("envycontrol")
        self.supergfxctl = shutil.which("supergfxctl")
        self.prime_select = shutil.which("prime-select")
        self._detect_backend()

    def _detect_backend(self):
        if self.envycontrol:
            self.backend = "envycontrol"
        elif self.supergfxctl:
            self.backend = "supergfxctl"
        elif self.prime_select:
            self.backend = "prime-select"
        else:
            self.backend = None

    def is_available(self):
        return self.backend is not None

    def get_backend(self):
        return self.backend or "none"

    def get_mode(self):
        try:
            if self.backend == "envycontrol":
                r = subprocess.check_output([self.envycontrol, "--query"], stderr=subprocess.STDOUT).decode().strip()
                return r.lower()
            elif self.backend == "supergfxctl":
                r = subprocess.check_output([self.supergfxctl, "-g"], stderr=subprocess.STDOUT).decode().strip()
                return r.lower()
            elif self.backend == "prime-select":
                r = subprocess.check_output([self.prime_select, "query"], stderr=subprocess.STDOUT).decode().strip()
                return r.lower()
        except:
            pass
        return "unknown"

    def set_mode(self, mode):
        try:
            if self.backend == "envycontrol":
                subprocess.run([self.envycontrol, "-s", mode], check=True)
                return "OK"
            elif self.backend == "supergfxctl":
                mode_map = {"hybrid": "Hybrid", "discrete": "Dedicated", "integrated": "Integrated"}
                subprocess.run([self.supergfxctl, "-m", mode_map.get(mode, mode)], check=True)
                return "OK"
            elif self.backend == "prime-select":
                mode_map = {"hybrid": "on-demand", "discrete": "nvidia", "integrated": "intel"}
                subprocess.run([self.prime_select, mode_map.get(mode, mode)], check=True)
                return "OK"
        except Exception as e:
            return f"Error: {e}"
        return "No backend"


# ============================================================
# ANIMATION ENGINE
# ============================================================
class AnimationEngine(threading.Thread):
    def __init__(self, rgb_ctrl):
        super().__init__(daemon=True)
        self.rgb = rgb_ctrl
        self.running = True

    def run(self):
        logger.info("Animation engine started")
        while self.running:
            loop_start = time.time()
            with lock:
                pwr = state.get("power", True)
                mode = state.get("mode", "static")
                bri = state.get("brightness", 100) / 100.0
                spd = state.get("speed", 50)
                cols = state.get("colors", ["FF0000"] * 4)[:]
                d = state.get("direction", "ltr")

            if not pwr:
                self.rgb.write_all(["000000"] * 4)
                time.sleep(0.5)
                continue

            t = time.time()
            targets = []

            if mode == "static":
                targets = [self._hex_to_rgb(c) for c in cols]
            elif mode == "breathing":
                period = 8.0 - (spd * 0.06)
                phase = (math.sin(2 * math.pi * t / period) + 1) / 2
                base = self._hex_to_rgb(cols[0])
                targets = [(int(base[0] * phase), int(base[1] * phase), int(base[2] * phase))] * 4
            elif mode == "cycle":
                hue = (t * (spd * 0.003)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                targets = [(int(r * 255), int(g * 255), int(b * 255))] * 4
            elif mode == "wave":
                speed_factor = spd * 0.007
                for i in range(4):
                    offset = (i * 0.15) if d == "ltr" else ((3 - i) * 0.15)
                    hue = (t * speed_factor + offset) % 1.0
                    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                    targets.append((int(r * 255), int(g * 255), int(b * 255)))

            final = []
            for r, g, b in targets:
                final.append(f"{int(r * bri):02X}{int(g * bri):02X}{int(b * bri):02X}")
            self.rgb.write_all(final)

            if mode == "static":
                time.sleep(0.5)
            else:
                elapsed = time.time() - loop_start
                time.sleep(max(0.033 - elapsed, 0.001))

    def _hex_to_rgb(self, h):
        h = h.lstrip("#")
        if not h or len(h) < 6:
            return (255, 0, 0)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ============================================================
# STATE
# ============================================================
state = {
    "mode": "static",
    "colors": ["FF0000"] * 4,
    "speed": 50,
    "brightness": 100,
    "direction": "ltr",
    "power": True,
}

ALLOWED_PACKAGES = {
    "steam": "com.valvesoftware.Steam",
    "lutris": "net.lutris.Lutris",
    "protonup-qt": "net.davidotek.pupgui2",
    "heroic": "com.heroicgameslauncher.hgl",
    "mangohud": "org.freedesktop.Platform.VulkanLayer.MangoHud",
}

fan_ctrl = FanController()
rgb_ctrl = RGBController()
power_ctrl = PowerProfileController()
mux_ctrl = MUXController()
engine = AnimationEngine(rgb_ctrl)


def save_state():
    with lock:
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"State save error: {e}")


def load_state():
    with lock:
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE) as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    if loaded.get("mode") in VALID_LIGHT_MODES:
                        state["mode"] = loaded["mode"]
                    colors = loaded.get("colors")
                    if isinstance(colors, list):
                        cleaned = []
                        for c in colors[:4]:
                            c = str(c).lstrip("#").upper()
                            if HEX_COLOR_RE.match(c):
                                cleaned.append(c)
                        if cleaned:
                            state["colors"] = (cleaned + [state["colors"][0]] * 4)[:4]
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
        except:
            pass


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
        <method name="InstallPackage"><arg type="s" name="pkg" direction="in"/><arg type="s" name="result" direction="out"/></method>
      </interface>
    </node>
    """

    def SetColor(self, z, h):
        c = str(h).lstrip("#").upper()
        if not HEX_COLOR_RE.match(c):
            return "FAIL"
        with lock:
            state["mode"] = "static"
            state["power"] = True
            if z == 4:
                state["colors"] = [c] * 4
            elif 0 <= z < 4:
                state["colors"][z] = c
            else:
                return "FAIL"
        save_state()
        return "OK"

    def SetMode(self, m, s):
        if m not in VALID_LIGHT_MODES:
            return "FAIL"
        with lock:
            state["mode"] = m
            state["speed"] = max(1, min(int(s), 100))
            state["power"] = True
        save_state()
        return "OK"

    def SetGlobal(self, p, b, d):
        if d not in VALID_DIRECTIONS:
            return "FAIL"
        with lock:
            state["power"] = bool(p)
            state["brightness"] = max(0, min(int(b), 100))
            state["direction"] = d
        save_state()
        return "OK"

    def GetState(self):
        with lock:
            return json.dumps(state)

    def SetFanMode(self, mode):
        """Set fan mode: 'auto', 'max', or 'custom'."""
        logger.info(f"SetFanMode: {mode}")
        ok = fan_ctrl.set_mode(mode)
        return "OK" if ok else "FAIL"

    def SetFanTarget(self, fan, rpm):
        """Set target RPM for a specific fan (in custom mode)."""
        logger.info(f"SetFanTarget: fan={fan}, rpm={rpm}")
        ok = fan_ctrl.set_fan_target(fan, rpm)
        return "OK" if ok else "FAIL"

    def GetFanInfo(self):
        info = {
            "available": fan_ctrl.is_available(),
            "fan_count": fan_ctrl.get_fan_count(),
            "mode": fan_ctrl.get_mode(),
            "fans": {}
        }
        for i in range(1, fan_ctrl.get_fan_count() + 1):
            info["fans"][str(i)] = {
                "current": fan_ctrl.get_current_speed(i),
                "max": fan_ctrl.get_max_speed(i),
                "target": fan_ctrl.get_target_speed(i),
            }
        return json.dumps(info)

    def SetPowerProfile(self, profile):
        if profile not in power_ctrl.get_profiles():
            return "FAIL"
        ok = power_ctrl.set_profile(profile)
        return "OK" if ok else "FAIL"

    def GetPowerProfile(self):
        return json.dumps({
            "available": power_ctrl.available,
            "active": power_ctrl.get_active(),
            "profiles": power_ctrl.get_profiles()
        })

    def SetGpuMode(self, mode):
        if mode not in VALID_GPU_MODES:
            return "FAIL"
        return mux_ctrl.set_mode(mode)

    def GetGpuInfo(self):
        return json.dumps({
            "available": mux_ctrl.is_available(),
            "backend": mux_ctrl.get_backend(),
            "mode": mux_ctrl.get_mode()
        })

    def GetSystemInfo(self):
        """Return basic system info for the GUI."""
        import platform, glob
        info = {
            "hostname": platform.node(),
            "kernel": platform.release(),
            "cpu_temp": 0,
            "gpu_temp": 0,
        }
        # CPU temp
        for p in sorted(glob.glob("/sys/class/hwmon/hwmon*/temp*_input")):
            try:
                with open(p) as f:
                    info["cpu_temp"] = int(f.read().strip()) / 1000
                    break
            except:
                pass
        # GPU temp
        if shutil.which("nvidia-smi"):
            try:
                info["gpu_temp"] = float(
                    subprocess.check_output(
                        ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL
                    ).decode().strip()
                )
            except:
                pass
        return json.dumps(info)

    def InstallPackage(self, pkg):
        """Install only known gaming packages with a fixed mapping."""
        pkg = str(pkg).strip().lower()
        flatpak_id = ALLOWED_PACKAGES.get(pkg)
        if not flatpak_id:
            return "Error: package_not_allowed"

        if shutil.which("flatpak"):
            try:
                subprocess.run(
                    ["flatpak", "install", "-y", "--noninteractive", "flathub", flatpak_id],
                    check=True, capture_output=True
                )
                return "OK"
            except:
                return "Error: flatpak_install_failed"

        return "No supported package manager found"


def main():
    if os.geteuid() != 0:
        print("Root yetkisi gerekli (sudo).")
        sys.exit(1)

    load_state()
    if rgb_ctrl.is_available():
        engine.start()
        logger.info("RGB engine started")

    try:
        bus = SystemBus()
        bus.publish("com.yyl.hpmanager", HPManagerService())
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
