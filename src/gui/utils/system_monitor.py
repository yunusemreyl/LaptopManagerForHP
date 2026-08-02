import threading
import time
import subprocess
import os
import shutil
import json
import glob
from gi.repository import GLib
from i18n import T
import concurrent.futures

_DBUS_TIMEOUT = 5
_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sysmon-dbus")

def _dbus_call(fn, *args, timeout=_DBUS_TIMEOUT):
    fut = _dbus_pool.submit(fn, *args)
    try:
        return fut.result(timeout=timeout)
    except Exception as e:
        print(f"⚠ SysMon D-Bus call failed/timeout: {e}")
        return None

class SystemMonitor(threading.Thread):
    def __init__(self, services_provider):
        super().__init__(daemon=True)
        self.services_provider = services_provider
        self.running = True
        self._active_event = threading.Event()
        self._active_event.set()
        self.lock = threading.Lock()
        self.data = {
            "cpu_temp": 0.0,
            "gpu_temp": 0.0,
            "cpu_pct": 0.0,
            "gpu_pct": 0.0,
            "cpu_freq": "0.00GHz",
            "gpu_freq": "0.00GHz",
            "ram_pct": 0.0,
            "ram_text": "RAM 0% 0.0GB",
            "disk_pct": 0.0,
            "disk_text": "DISK 0% 0.0GB",
            "bat_pct": 0.0,
            "bat_text": "BAT 0%",
            "fan_info": {},
            "power_profile": {},
            "rgb_state": {},
            "power_conflict": None,
            "gamemode": "Inactive",
            "all_sensors": [],
            "gpu_tgp_state": False,
            "gpu_ppab_state": False,
        }
        self._conflict_cache = None
        self._conflict_counter = 0
        self._nvidia_smi = shutil.which("nvidia-smi") or ""

    def set_active(self, active):
        if active:
            self._active_event.set()
        else:
            self._active_event.clear()

    def run(self):
        while self.running:
            if not self._active_event.is_set():
                time.sleep(4.0)
                continue

            c, g = 0.0, 0.0
            fi, pp, si, rg = {}, {}, {}, {}
            services = self.services_provider()

            # D-Bus reads
            if services:
                platform_svc = services.get("platform")
                fan_svc = services.get("fan")
                power_svc = services.get("power")
                rgb_svc = services.get("rgb")

                if platform_svc:
                    try:
                        raw = _dbus_call(platform_svc.GetSystemInfo)
                        if raw is not None:
                            si = json.loads(raw)
                            c = si.get("cpu_temp", 0.0)
                            g = si.get("gpu_temp", 0.0)
                    except Exception: pass

                if fan_svc:
                    try:
                        raw = _dbus_call(fan_svc.GetFanInfo)
                        if raw is not None:
                            fi = json.loads(raw)
                    except Exception: pass

                if power_svc:
                    try:
                        raw = _dbus_call(power_svc.GetPowerProfile)
                        if raw is not None:
                            pp = json.loads(raw)
                    except Exception: pass

                if rgb_svc:
                    try:
                        raw = _dbus_call(rgb_svc.GetState)
                        if raw is not None:
                            rg = json.loads(raw)
                    except Exception: pass

            # CPU / GPU Utilization and speeds
            cpu_pct = 0.0
            try:
                with open("/proc/stat") as f:
                    cpu = f.readline().strip().split()
                vals = [int(x) for x in cpu[1:9]]
                idle_all = vals[3] + vals[4]
                total = sum(vals)
                cpu_pct = max(0.0, min(100.0, (1.0 - (idle_all / total)) * 100.0))
            except Exception: pass

            cpu_freq = "3.20GHz"
            try:
                with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
                    val = int(f.read().strip())
                    cpu_freq = f"{val / 1000000:.2f}GHz"
            except Exception:
                try:
                    with open("/proc/cpuinfo") as f:
                        for line in f:
                            if line.startswith("cpu MHz"):
                                cpu_freq = f"{float(line.split(':')[1].strip()) / 1000:.2f}GHz"
                                break
                except Exception: pass

            gpu_pct = 0.0
            gpu_freq = "0.00GHz"
            if self._nvidia_smi:
                try:
                    out_pct = subprocess.check_output(
                        [self._nvidia_smi, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL, timeout=1.5
                    ).decode().strip()
                    if out_pct:
                        gpu_pct = float(out_pct.splitlines()[0])

                    out_freq = subprocess.check_output(
                        [self._nvidia_smi, "--query-gpu=clocks.gr", "--format=csv,noheader,nounits"],
                        stderr=subprocess.DEVNULL, timeout=1.5
                    ).decode().strip()
                    if out_freq:
                        gpu_freq = f"{float(out_freq.splitlines()[0]) / 1000:.2f}GHz"
                except Exception: pass

            # RAM percentage and text
            ram_pct = 0.0
            ram_text = "RAM 0% 0.0GB"
            try:
                mem = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        k, v = line.split(":", 1)
                        mem[k.strip()] = int(v.split()[0])
                mt = mem.get("MemTotal", 1)
                ma = mem.get("MemAvailable", mt)
                used = mt - ma
                ram_pct = (used / mt) * 100
                used_gb = used / (1024 * 1024)
                total_gb = mt / (1024 * 1024)
                ram_text = f"RAM {int(ram_pct)}% {used_gb:.1f}GB / {total_gb:.0f}GB"
            except Exception: pass

            # Disk percentage and text
            disk_pct = 0.0
            disk_text = "DISK 0% 0.0GB"
            try:
                total, used, free = shutil.disk_usage("/")
                if total > 0:
                    disk_pct = (used / total) * 100
                used_gb = used / (1024 ** 3)
                total_gb = total / (1024 ** 3)
                disk_text = f"DISK {int(disk_pct)}% {used_gb:.1f}GB / {total_gb:.0f}GB"
            except Exception: pass

            # Battery percentage and text
            bat_pct = 0.0
            bat_text = "BAT N/A"
            try:
                lang_is_tr = T("fan") == "Performans" or "tr" in os.getenv("LANG", "").lower()
                bat_paths = glob.glob("/sys/class/power_supply/BAT*")
                if bat_paths:
                    bp = bat_paths[0]
                    cap_p = f"{bp}/capacity"
                    status_p = f"{bp}/status"
                    
                    pct = 100
                    if os.path.exists(cap_p):
                        with open(cap_p) as f:
                            pct = int(f.read().strip())
                    
                    status = "Unknown"
                    if os.path.exists(status_p):
                        with open(status_p) as f:
                            status = f.read().strip()
                    
                    bat_pct = float(pct)
                    
                    status_tr = {
                        "Charging": "Şarj Oluyor" if lang_is_tr else "Charging",
                        "Discharging": "Deşarj Oluyor" if lang_is_tr else "Discharging",
                        "Full": "Dolu" if lang_is_tr else "Full",
                        "Not charging": "Şarj Olmuyor" if lang_is_tr else "Not Charging",
                    }
                    stat_lbl = status_tr.get(status, status)
                    bat_text = f"BAT {int(pct)}% ({stat_lbl})"
                else:
                    bat_pct = 100.0
                    bat_text = "BAT 100% (AC)"
            except Exception: pass

            # Feral GameMode Query
            gamemode = "Inactive"
            if shutil.which("gamemoded"):
                try:
                    res = subprocess.run(["gamemoded", "-s"], capture_output=True, text=True, timeout=1.0)
                    out = res.stdout.lower()
                    if "active" in out:
                        gamemode = "Active"
                except Exception: pass

            # Query all real-time sensor diagnostics
            sensors = self._get_all_sensors()

            # Query physical hp-wmi cTGP & PPAB states
            gpu_tgp_state = False
            gpu_ppab_state = False
            try:
                for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
                    tgp_p = f"{base}/gpu_tgp"
                    ppab_p = f"{base}/gpu_ppab"
                    if os.path.exists(tgp_p):
                        with open(tgp_p) as f:
                            gpu_tgp_state = f.read().strip() == "1"
                    if os.path.exists(ppab_p):
                        with open(ppab_p) as f:
                            gpu_ppab_state = f.read().strip() == "1"
            except Exception: pass

            # Fallbacks for temperatures
            if not c:
                try:
                    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
                        with open(path) as f:
                            c = int(f.read().strip()) / 1000
                            break
                except Exception: c = 42.0
            if not g: g = 0.0

            # Conflict checking
            self._conflict_counter += 1
            if self._conflict_counter >= 8:
                self._conflict_counter = 0
                self._conflict_cache = None
                for tool in ("tlp", "auto-cpufreq"):
                    try:
                        res = subprocess.run(["systemctl", "is-active", f"{tool}.service"],
                                             capture_output=True, text=True, timeout=1.5)
                        if res.stdout.strip() == "active":
                            self._conflict_cache = tool
                            break
                    except Exception: pass

            with self.lock:
                self.data["cpu_temp"] = c
                self.data["gpu_temp"] = g
                self.data["cpu_pct"] = cpu_pct
                self.data["gpu_pct"] = gpu_pct
                self.data["cpu_freq"] = cpu_freq
                self.data["gpu_freq"] = gpu_freq
                self.data["ram_pct"] = ram_pct
                self.data["ram_text"] = ram_text
                self.data["disk_pct"] = disk_pct
                self.data["disk_text"] = disk_text
                self.data["bat_pct"] = bat_pct
                self.data["bat_text"] = bat_text
                self.data["fan_info"] = fi
                self.data["power_profile"] = pp
                self.data["rgb_state"] = rg
                self.data["power_conflict"] = self._conflict_cache
                self.data["gamemode"] = gamemode
                self.data["all_sensors"] = sensors
                self.data["gpu_tgp_state"] = gpu_tgp_state
                self.data["gpu_ppab_state"] = gpu_ppab_state

            time.sleep(2.0)

    def _get_all_sensors(self):
        sensors = []
        try:
            for d in sorted(os.listdir("/sys/class/hwmon")):
                path = os.path.join("/sys/class/hwmon", d)
                name = "unknown"
                try:
                    with open(os.path.join(path, "name")) as f:
                        name = f.read().strip()
                except Exception: continue

                for tf in sorted(glob.glob(os.path.join(path, "temp*_input"))):
                    try:
                        with open(tf) as f:
                            temp = int(f.read().strip()) / 1000
                        label_file = tf.replace("_input", "_label")
                        try:
                            with open(label_file) as f:
                                label = f.read().strip()
                        except Exception:
                            label = os.path.basename(tf).replace("_input", "")
                        
                        if label.lower() == "package id 0":
                            label = "CPU Package"
                        elif label.lower().startswith("core "):
                            try:
                                core_num = int(label.split()[1])
                                label = f"Core {core_num + 1}"
                            except ValueError: pass
                        elif label.lower() == "tctl":
                            label = "CPU (tctl)"
                        elif label.lower() == "tdie":
                            label = "CPU (tdie)"
                            
                        sensors.append({"driver": name, "label": label, "temp": temp})
                    except Exception: pass
        except Exception: pass
        return sensors

    def get_data(self):
        with self.lock:
            return self.data.copy()

    def stop(self):
        self.running = False
        self._active_event.set()

# ═════════════════════════════════════════════════════════════════════════════
#  PERFORMANCE & FAN PAGE MAIN COMPONENT
# ═════════════════════════════════════════════════════════════════════════════

