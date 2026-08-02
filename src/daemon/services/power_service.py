#!/usr/bin/env python3
"""OMEN Command Center for Linux — Power Profile Microservice.

Owns power-profile management (PPD / Tuned / OMEN Direct) and NVIDIA
GPU power-limit synchronisation.  Exposes its functionality over D-Bus
as ``com.yyl.hpmanager.power``.
"""

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.dbus_helpers import run_service
from common.app_launchers import get_running_launcher_ids
from common.sysfs import (
    normalize_profile_name,
    sysfs_exists,
    sysfs_read,
    sysfs_read_str,
    sysfs_write,
)
from common.ec_controller import LinuxEcController

from pydbus import SystemBus

logger = setup_logging("power")
THERMAL_PROFILE_BALANCED = 0

_dbus_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="pwr-dbus")

def is_amd_cpu():
    try:
        with open("/proc/cpuinfo", "r") as f:
            return "AuthenticAMD" in f.read()
    except Exception:
        return False

# Attempt to load native intel_undervolt
try:
    import intel_undervolt
    HAS_INTEL_UV = True
except ImportError:
    HAS_INTEL_UV = False


def _dbus_call(fn, *args, timeout=3.0):
    """Run a D-Bus proxy call with a timeout to avoid indefinite blocking."""
    fut = _dbus_pool.submit(fn, *args)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning("D-Bus call timed out after %ss: %s", timeout, fn)
        return None
    except Exception as e:
        logger.warning("D-Bus call failed: %s", e)
        return None


# ─── Power Profile Controller ────────────────────────────────────────────────


class PowerProfileController:
    PPD_BUS = "net.hadess.PowerProfiles"
    PPD_PATH = "/net/hadess/PowerProfiles"
    TUNED_BUS = "com.redhat.tuned"
    TUNED_PATH = "/Tuned"

    def __init__(self, ec_controller=None):
        self.ec = ec_controller
        self.mode = "ppd"
        self.available = False
        self.bus = SystemBus()
        self.proxy = None

        self.has_auto_cpufreq = False
        self.has_tlp = False

        try:
            has_external_manager = False
            for tool in ("tlp", "auto-cpufreq"):
                res = subprocess.run(["systemctl", "is-active", f"{tool}.service"], capture_output=True, text=True, timeout=1.0)
                if res.stdout.strip() == "active":
                    has_external_manager = True
                    logger.info("PowerProfileController: Detected external manager '%s'", tool)
                    if tool == "auto-cpufreq":
                        self.has_auto_cpufreq = True
                    elif tool == "tlp":
                        self.has_tlp = True
        except Exception:
            has_external_manager = False

        if not has_external_manager:
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
                    if shutil.which("system76-power"):
                        self.mode = "system76"
                        self.available = True
                        logger.info("PowerProfileController: Using system76-power backend")
                    else:
                        pass

        if not self.available:
            if sysfs_exists("/sys/devices/platform/hp-wmi/thermal_profile") or \
               sysfs_exists("/sys/devices/platform/hp-omen/thermal_profile"):
                self.mode = "omen_direct"
                self.available = True
                logger.info("PowerProfileController: Using OMEN Direct sysfs backend")
            else:
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
            # First, check direct WMI/ACPI platform profile as it is the absolute source of truth!
            wmi_active = self._get_omen_direct_active()
            if wmi_active is not None:
                return wmi_active

            # Fallback to ppd / tuned
            if self.mode == "ppd":
                return self.proxy.ActiveProfile
            if self.mode == "tuned":
                tp = self.proxy.active_profile()
                if "powersave" in tp:
                    return "power-saver"
                if "performance" in tp:
                    return "performance"
                return "balanced"
            if self.mode == "system76":
                try:
                    res = subprocess.run(["system76-power", "profile"], capture_output=True, text=True, timeout=1.0)
                    out = res.stdout.strip().lower()
                    if "battery" in out:
                        return "power-saver"
                    if "performance" in out:
                        return "performance"
                    return "balanced"
                except Exception:
                    return "balanced"
            return "balanced"
        except Exception:
            return "balanced"

    def _get_omen_direct_active(self):
        found = False
        for path in (
            "/sys/firmware/acpi/platform_profile",
            "/sys/devices/platform/hp-wmi/platform_profile",
        ):
            if not sysfs_exists(path):
                continue
            found = True
            normalized = normalize_profile_name(sysfs_read_str(path, "balanced"))
            if "performance" in normalized:
                return "performance"
            if normalized in ("low-power", "quiet", "cool", "power-saver"):
                return "power-saver"
            return "balanced"

        for path in (
            "/sys/devices/platform/hp-wmi/thermal_profile",
            "/sys/devices/platform/hp-omen/thermal_profile",
        ):
            if not sysfs_exists(path):
                continue
            found = True
            val = sysfs_read(path, THERMAL_PROFILE_BALANCED)
            if val == 1:
                return "performance"
            return "balanced"

        return None if not found else "balanced"

    def _sync_omen_profile(self, profile):
        ok = False
        target_candidates = {
            "performance": ("performance",),
            "balanced": ("balanced",),
            "power-saver": ("low-power", "quiet", "cool", "power-saver", "balanced"),
        }.get(profile, ("balanced",))

        # Write generic kernel platform_profile (PPD / power profile daemon interface)
        for path in (
            "/sys/firmware/acpi/platform_profile",
            "/sys/devices/platform/hp-wmi/platform_profile",
        ):
            if not sysfs_exists(path):
                continue
            choices_raw = sysfs_read_str(f"{path}_choices", "")
            choices = {
                normalize_profile_name(token.strip("[]"))
                for token in choices_raw.split()
                if token.strip("[]")
            }
            if choices:
                candidates = [candidate for candidate in target_candidates if candidate in choices]
                if not candidates and "balanced" in choices:
                    candidates = ["balanced"]
            else:
                candidates = list(target_candidates)

            for target in candidates:
                if sysfs_write(path, target):
                    ok = True
                    break

        # ALSO write HP-specific thermal_profile — this is what BIOS reads to
        # select its built-in fan curve (0=balanced, 1=performance).
        # Must be written independently of platform_profile; previously this block
        # was skipped because _sync_omen_profile returned early above.
        thermal_val = {"power-saver": "0", "balanced": "0", "performance": "1"}.get(
            profile, "0"
        )
        for path in (
            "/sys/devices/platform/hp-wmi/thermal_profile",
            "/sys/devices/platform/hp-omen/thermal_profile",
        ):
            if not sysfs_exists(path):
                continue
            if sysfs_write(path, thermal_val):
                ok = True
                break

        return ok

    def set_profile(self, profile):
        if not self.available:
            return False

        if self.has_auto_cpufreq:
            try:
                if profile == "performance":
                    ac_target = "performance"
                elif profile in ("eco", "power-saver", "quiet"):
                    ac_target = "powersave"
                else:
                    ac_target = "reset"
                subprocess.run(["auto-cpufreq", "--force", ac_target], capture_output=True, timeout=2.0)
                logger.info("auto-cpufreq synced to '%s'", ac_target)
            except Exception as e:
                logger.warning("Failed to sync auto-cpufreq: %s", e)

        if self.has_tlp:
            try:
                tlp_d = "/etc/tlp.d"
                conf_path = f"{tlp_d}/99-omenctl-profile.conf"
                if os.path.exists(tlp_d):
                    # Map OmenCtl profile to TLP profile
                    tlp_target = {"performance": "PRF", "eco": "SAV", "power-saver": "SAV", "quiet": "SAV"}.get(profile, "BAL")
                    with open(conf_path, "w") as f:
                        f.write(f"TLP_AUTO_SWITCH=0\nTLP_PROFILE_DEFAULT={tlp_target}\n")
                    
                    # Remove the old platform-only conflict drop-in if it exists
                    old_conf = f"{tlp_d}/99-omenctl-platform.conf"
                    if os.path.exists(old_conf):
                        os.remove(old_conf)
                        
                    subprocess.run(["tlp", "start"], capture_output=True, timeout=2.0)
                    logger.info("TLP synced to '%s'", tlp_target)
            except Exception as e:
                logger.warning("Failed to sync TLP: %s", e)

        try:
            ok = False
            if self.mode == "ppd":
                if shutil.which("powerprofilesctl"):
                    try:
                        res = subprocess.run(["powerprofilesctl", "set", profile], capture_output=True, text=True, timeout=2.0)
                        if res.returncode == 0:
                            logger.info("Successfully set ppd profile via powerprofilesctl: %s", profile)
                            ok = True
                        else:
                            logger.warning("powerprofilesctl set returned non-zero: %s (stderr: %s), falling back to direct dbus", res.returncode, res.stderr)
                            try:
                                self.proxy.ActiveProfile = profile
                                ok = True
                            except Exception as dbus_err:
                                logger.warning("Direct D-Bus set also failed: %s", dbus_err)
                    except Exception as e:
                        logger.warning("Failed to run powerprofilesctl set: %s, falling back to direct dbus", e)
                        try:
                            self.proxy.ActiveProfile = profile
                            ok = True
                        except Exception as dbus_err:
                            logger.warning("Direct D-Bus set also failed: %s", dbus_err)
                else:
                    try:
                        self.proxy.ActiveProfile = profile
                        ok = True
                    except Exception as e:
                        logger.warning("PPD D-Bus set failed: %s", e)

                # If PPD failed (e.g. AMD pstate boost error), fall back to
                # direct sysfs / OMEN WMI so the platform profile is still set.
                if not ok:
                    logger.info("PPD backend failed for '%s', attempting omen_direct sysfs fallback", profile)
                    if self._sync_omen_profile(profile):
                        ok = True
                        logger.info("omen_direct sysfs fallback succeeded for '%s'", profile)

            elif self.mode == "tuned":
                mapping = {
                    "power-saver": "powersave",
                    "balanced": "balanced",
                    "performance": "throughput-performance",
                }
                self.proxy.switch_profile(mapping.get(profile, "balanced"))
                ok = True
            elif self.mode == "system76":
                mapping = {
                    "power-saver": "battery",
                    "balanced": "balanced",
                    "performance": "performance",
                }
                target = mapping.get(profile, "balanced")
                try:
                    res = subprocess.run(["system76-power", "profile", target], capture_output=True, text=True, timeout=2.0)
                    if res.returncode == 0:
                        logger.info("Successfully set system76-power profile: %s", profile)
                        ok = True
                    else:
                        logger.warning("system76-power set returned non-zero: %s (stderr: %s)", res.returncode, res.stderr)
                except Exception as e:
                    logger.warning("Failed to run system76-power set: %s", e)
                
                if not ok:
                    logger.info("system76-power backend failed for '%s', attempting omen_direct sysfs fallback", profile)
                    if self._sync_omen_profile(profile):
                        ok = True
                        logger.info("omen_direct sysfs fallback succeeded for '%s'", profile)
            elif self.mode == "omen_direct":
                if not self._sync_omen_profile(profile):
                    return False
                threading.Thread(
                    target=self._sync_runtime_power, args=(profile,), daemon=True
                ).start()
                return True

            if ok:
                threading.Thread(
                    target=self._sync_hardware_power, args=(profile,), daemon=True
                ).start()
            return ok
        except Exception as e:
            logger.error("Power profile set error (%s): %s", self.mode, e)
            return False

    def _sync_nvidia_power(self, profile):
        try:
            if not shutil.which("nvidia-smi"):
                return

            if profile == "performance":
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=power.max_limit",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=2.0,
                ).decode().strip()
                if out:
                    limit = int(float(out))
                    subprocess.run(
                        ["nvidia-smi", "-pl", str(limit)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                    )
                    logger.info("NVIDIA GPU locked to MAX Performance: %dW", limit)
            else:
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=power.default_limit",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=2.0,
                ).decode().strip()
                if out:
                    limit = int(float(out))
                    subprocess.run(
                        ["nvidia-smi", "-pl", str(limit)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                    )
                    logger.info("NVIDIA GPU restored to DEFAULT Base: %dW", limit)
        except Exception as e:
            logger.warning("Failed to sync NVIDIA power curve: %s", e)

    def _sync_runtime_power(self, profile):
        self._sync_nvidia_power(profile)
        self._sync_kernel_gpu_power(profile)

    def _sync_hardware_power(self, profile):
        """Orchestrate platform profile sync and GPU power limits.
        
        Order matters: the platform profile MUST be committed before
        triggering GPU cTGP / PPAB, otherwise the BIOS may reject the
        power-limit change (observed on 8D41 boards).
        """
        self._sync_omen_profile(profile)
        
        # Fallback mechanism: Attempt direct EC write.
        # For boards with broken WMI (like 8E35), this bypasses WMI entirely.
        # For boards where WMI works but is insufficient, this serves as a helper.
        if self.ec:
            self.ec.set_perf_mode(profile)

        # Give BIOS/EC time to acknowledge the profile change before
        # touching GPU power registers — without this delay the cTGP
        # trigger is silently rejected on some boards (e.g. 8D41).
        time.sleep(0.5)
        self._sync_runtime_power(profile)

    def _sync_kernel_gpu_power(self, profile):
        """Trigger TGP and PPAB via the patched hp-wmi driver."""
        base = "/sys/devices/platform/hp-wmi"
        if not sysfs_exists(base):
            base = "/sys/devices/platform/hp-omen"
        
        tgp_path = f"{base}/gpu_tgp"
        ppab_path = f"{base}/gpu_ppab"

        if not sysfs_exists(tgp_path):
            logger.debug("gpu_tgp sysfs path not found at %s — skipping GPU power sync", tgp_path)
            return

        try:
            if profile == "performance":
                ok_tgp = sysfs_write(tgp_path, "1")
                ok_ppab = sysfs_write(ppab_path, "1")
                logger.info("Kernel GPU Power: TGP=Enabled(%s), PPAB=Enabled(%s)", ok_tgp, ok_ppab)
                if not ok_tgp:
                    logger.warning("sysfs_write to gpu_tgp FAILED — GPU may be capped at base TGP")
            elif profile == "balanced":
                ok_tgp = sysfs_write(tgp_path, "0")
                ok_ppab = sysfs_write(ppab_path, "1")
                logger.info("Kernel GPU Power: TGP=Disabled(%s), PPAB=Enabled(%s)", ok_tgp, ok_ppab)
            else: # power-saver / quiet / eco
                ok_tgp = sysfs_write(tgp_path, "0")
                ok_ppab = sysfs_write(ppab_path, "0")
                logger.info("Kernel GPU Power: TGP=Disabled(%s), PPAB=Disabled(%s)", ok_tgp, ok_ppab)
        except Exception as e:
            logger.warning("Failed to sync Kernel GPU power: %s", e)


# ─── D-Bus Service ────────────────────────────────────────────────────────────


class PowerService:
    """
    <node>
      <interface name="com.yyl.hpmanager.power">
        <method name="SetPowerProfile"><arg type="s" name="profile" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="GetPowerProfile"><arg type="s" name="j" direction="out"/></method>
        <method name="SetAppProfilesEnabled"><arg type="b" name="enabled" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetAppProfiles"><arg type="s" name="profiles_json" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetUndervolt"><arg type="i" name="mv" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetTccOffset"><arg type="i" name="val" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetPowerLimits"><arg type="b" name="enabled" direction="in"/><arg type="i" name="pl1" direction="in"/><arg type="i" name="pl2" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """

    def __init__(self):
        self.ec = LinuxEcController()
        self._ctrl = PowerProfileController(ec_controller=self.ec)
        self._config = ServiceConfig(
            "power",
            {
                "power_profile": "balanced",
                "app_profiles_enabled": False,
                "app_profiles": {},
                "undervolt_mv": 0,
                "tcc_offset": 0,
                "pl1_w": 45,
                "pl2_w": 80,
                "pl_enabled": False,
            },
        )
        self._config.load()
        self._apply_power_tuning()

    def _apply_power_tuning(self):
        if self._config.get("pl_enabled"):
            self.SetPowerLimits(True, self._config.get("pl1_w"), self._config.get("pl2_w"))

        self._active_app = None
        self._pre_app_state = None  # (power_profile, fan_mode)

        # Restore saved profile after a short delay so that PPD / tuned /
        # ACPI subsystems are fully initialised.  Without this delay the
        # profile write can be silently rejected or overridden by PPD's own
        # startup logic, causing "custom" to appear instead of the saved value.
        if self._ctrl.available:
            threading.Timer(3.0, self._delayed_profile_restore).start()

        # Background app monitor thread
        threading.Thread(target=self._app_monitor_loop, daemon=True).start()

    def _delayed_profile_restore(self, _retry=0):
        """Restore saved power profile with retry.

        Called 3 seconds after daemon start so PPD/tuned has time to
        initialise.  Retries once after 5 more seconds on failure.

        Guard against the "performance revert loop": when PPD has trouble
        writing profiles (e.g. AMD pstate boost error), the platform_profile
        sysfs node may still read \"performance\" from the previous boot even
        after the user selected \"balanced\".  We trust OUR saved config as
        the source of truth, and only skip the write if the hardware already
        agrees AND PPD also agrees.
        """
        saved = self._config.get("power_profile", "balanced")
        if saved not in self._ctrl.get_profiles():
            logger.warning("Saved profile '%s' not in available profiles, skipping restore", saved)
            return

        current = self._ctrl.get_active()
        if current == saved:
            logger.info("Power profile already '%s' after boot, no restore needed", saved)
            # Still sync hardware power (GPU TGP/PPAB) to ensure consistency
            self._ctrl._sync_hardware_power(saved)
            return

        logger.info(
            "Restoring power profile '%s' (hardware reports '%s', attempt=%d)",
            saved, current, _retry + 1
        )
        ok = self._ctrl.set_profile(saved)

        # Verify the write actually stuck by re-reading after a short settle
        if ok:
            time.sleep(0.5)
            after = self._ctrl.get_active()
            if after != saved:
                logger.warning(
                    "Profile restore wrote '%s' but hardware reads '%s' — "
                    "possible PPD conflict. Will retry.", saved, after
                )
                ok = False

        logger.info("Delayed restore of power profile '%s' (success=%s)", saved, ok)

        if not ok and _retry < 1:
            logger.info("Profile restore failed, scheduling retry in 5 seconds...")
            threading.Timer(5.0, self._delayed_profile_restore, kwargs={"_retry": _retry + 1}).start()

    def _app_monitor_loop(self):
        from pydbus import SystemBus
        bus = SystemBus()
        fan_proxy = None
        
        while True:
            time.sleep(3.0)
            if not self._config.get("app_profiles_enabled", False):
                if self._active_app is not None:
                    self._restore_pre_app_state(fan_proxy)
                continue

            app_profiles = self._config.get("app_profiles", {})
            if not app_profiles:
                if self._active_app is not None:
                    self._restore_pre_app_state(fan_proxy)
                continue

            if fan_proxy is None:
                try:
                    fan_proxy = _dbus_call(bus.get, "com.yyl.hpmanager.fan", "/com/yyl/hpmanager/fan")
                except Exception:
                    pass

            # Scan running processes and launchers
            found_app = None
            try:
                for pid_str in os.listdir("/proc"):
                    if not pid_str.isdigit():
                        continue
                    try:
                        cmdline_path = os.path.join("/proc", pid_str, "cmdline")
                        if os.stat(cmdline_path).st_uid < 1000:
                            continue
                        with open(cmdline_path, "r", errors="ignore") as f:
                            cmdline = f.read().replace("\x00", " ").strip()
                        if not cmdline:
                            continue
                        
                        # Check direct matches
                        for app_key in app_profiles.keys():
                            if app_key in cmdline.lower():
                                found_app = app_key
                                break
                                
                        # Check launcher IDs
                        if not found_app:
                            l_ids = get_running_launcher_ids(pid_str)
                            for app_key in app_profiles.keys():
                                if app_key in l_ids:
                                    found_app = app_key
                                    break
                    except Exception:
                        pass
                    if found_app:
                        break
            except Exception:
                pass

            if found_app != self._active_app:
                if found_app is not None:
                    # New app launched
                    val = app_profiles.get(found_app)
                    target_profile = val.get("profile", "balanced") if isinstance(val, dict) else val
                    target_fan = val.get("fan_mode", "default") if isinstance(val, dict) else "default"
                    
                    # Store previous state
                    curr_power = self._ctrl.get_active()
                    curr_fan = "auto"
                    if fan_proxy:
                        try:
                            f_info_raw = _dbus_call(fan_proxy.GetFanInfo)
                            if f_info_raw:
                                f_info = json.loads(f_info_raw)
                                curr_fan = f_info.get("mode", "auto")
                            else:
                                # D-Bus call returned None → proxy is stale, reset it
                                fan_proxy = None
                        except Exception:
                            fan_proxy = None
                    
                    if self._active_app is None:
                        self._pre_app_state = (curr_power, curr_fan)

                    logger.info("App Monitor: Detected '%s', switching power=%s, fan=%s", found_app, target_profile, target_fan)
                    self._ctrl.set_profile(target_profile)
                    if fan_proxy and target_fan in ("auto", "max"):
                        result = _dbus_call(fan_proxy.SetFanMode, target_fan)
                        if result is None:
                            fan_proxy = None
                else:
                    # App closed, restore previous state
                    self._restore_pre_app_state(fan_proxy)
                
                self._active_app = found_app

    def _restore_pre_app_state(self, fan_proxy):
        if self._pre_app_state:
            old_power, old_fan = self._pre_app_state
            logger.info("App Monitor: App closed, restoring power=%s, fan=%s", old_power, old_fan)
            self._ctrl.set_profile(old_power)
            if fan_proxy and old_fan in ("auto", "max"):
                _dbus_call(fan_proxy.SetFanMode, old_fan)
            self._pre_app_state = None
        self._active_app = None

    def SetPowerProfile(self, profile):
        if profile not in self._ctrl.get_profiles():
            return "FAIL"
        ok = self._ctrl.set_profile(profile)
        if ok:
            self._config.set("power_profile", profile)
            self._config.save()
            if self._active_app is not None and self._pre_app_state is not None:
                # Update base state if user forces profile change while app is active
                _, old_fan = self._pre_app_state
                self._pre_app_state = (profile, old_fan)
        return "OK" if ok else "FAIL"

    def GetPowerProfile(self):
        return json.dumps(
            {
                "available": self._ctrl.available,
                "active": self._ctrl.get_active(),
                "profiles": self._ctrl.get_profiles(),
                "app_profiles_enabled": self._config.get("app_profiles_enabled", False),
                "app_profiles": self._config.get("app_profiles", {}),
                "active_app": self._active_app,
                "capabilities": self.ec.capabilities.to_dict(),
                "undervolt_mv": self._config.get("undervolt_mv", 0),
                "tcc_offset": self._config.get("tcc_offset", 0),
                "pl1_w": self._config.get("pl1_w", 45),
                "pl2_w": self._config.get("pl2_w", 80),
                "pl_enabled": self._config.get("pl_enabled", False),
            }
        )

    def SetUndervolt(self, mv):
        try:
            mv = int(mv)
            mv = max(-250, min(250, mv))
        except (ValueError, TypeError):
            return "FAIL"
        logger.info("SetUndervolt: %d mV", mv)
        self._config.set("undervolt_mv", mv)
        self._config.save()
        try:
            if is_amd_cpu():
                # AMD Curve Optimizer (Negative = Undervolt)
                ryzen_bin = "/usr/libexec/hp-manager/ryzenadj"
                if os.path.exists(ryzen_bin):
                    subprocess.run([ryzen_bin, f"--curve-opt={mv}"], capture_output=True, timeout=2.0)
                elif shutil.which("ryzenadj"):
                    subprocess.run(["ryzenadj", f"--curve-opt={mv}"], capture_output=True, timeout=2.0)
            else:
                # Intel Core & Cache Undervolt
                if HAS_INTEL_UV:
                    if not os.path.exists("/dev/cpu/0/msr"):
                        subprocess.run(["modprobe", "msr"], capture_output=True)
                    # Apply offset to Core (0) and Cache (2)
                    off_val = intel_undervolt.convert_offset(mv)
                    intel_undervolt.write_msr(intel_undervolt.pack_offset(0, off_val), intel_undervolt.ADDRESSES.addr_voltage_offsets)
                    intel_undervolt.write_msr(intel_undervolt.pack_offset(2, off_val), intel_undervolt.ADDRESSES.addr_voltage_offsets)
                elif shutil.which("intel-undervolt"):
                    subprocess.run(["intel-undervolt", "apply"], capture_output=True, timeout=2.0)
        except Exception as e:
            logger.debug("Failed to apply undervolt: %s", e)
        return "OK"

    def SetTccOffset(self, val):
        try:
            val = int(val)
            val = max(0, min(15, val))
        except (ValueError, TypeError):
            return "FAIL"
        logger.info("SetTccOffset: %d", val)
        self._config.set("tcc_offset", val)
        self._config.save()
        try:
            if is_amd_cpu():
                # AMD Max Temp Limit
                ryzen_bin = "/usr/libexec/hp-manager/ryzenadj"
                if os.path.exists(ryzen_bin):
                    subprocess.run([ryzen_bin, f"--tctl-temp={100 - val}"], capture_output=True, timeout=2.0)
                elif shutil.which("ryzenadj"):
                    subprocess.run(["ryzenadj", f"--tctl-temp={100 - val}"], capture_output=True, timeout=2.0)
            else:
                # Intel TCC Offset (MSR 0x1a2)
                if HAS_INTEL_UV:
                    if not os.path.exists("/dev/cpu/0/msr"):
                        subprocess.run(["modprobe", "msr"], capture_output=True)
                    intel_undervolt.set_temperature(100 - val, intel_undervolt.ADDRESSES)
                elif shutil.which("wrmsr"):
                    subprocess.run(["modprobe", "msr"], capture_output=True)
                    subprocess.run(["wrmsr", "-a", "0x1a2", f"{val:x}000000"], capture_output=True, timeout=2.0)
        except Exception as e:
            logger.debug("Failed to apply TCC offset: %s", e)
        return "OK"

    def SetPowerLimits(self, enabled, pl1, pl2):
        # Validate and clamp power limits to safe hardware ranges.
        # pl1 = sustained / STAPM (1–200 W), pl2 = peak / fast (1–250 W).
        # Rejecting out-of-range values prevents accidental or malicious
        # destruction of hardware via the D-Bus interface.
        try:
            pl1 = int(pl1)
            pl2 = int(pl2)
        except (ValueError, TypeError):
            logger.warning("SetPowerLimits: non-integer values pl1=%s pl2=%s", pl1, pl2)
            return "FAIL"

        PL1_MIN, PL1_MAX = 1, 200   # sustained TDP range (Watts)
        PL2_MIN, PL2_MAX = 1, 250   # peak / fast TDP range (Watts)

        if not (PL1_MIN <= pl1 <= PL1_MAX):
            logger.warning("SetPowerLimits: pl1=%d out of safe range [%d, %d]", pl1, PL1_MIN, PL1_MAX)
            return "FAIL"
        if not (PL2_MIN <= pl2 <= PL2_MAX):
            logger.warning("SetPowerLimits: pl2=%d out of safe range [%d, %d]", pl2, PL2_MIN, PL2_MAX)
            return "FAIL"
        if pl2 < pl1:
            logger.warning("SetPowerLimits: pl2 (%d) < pl1 (%d), clamping pl2 to pl1", pl2, pl1)
            pl2 = pl1

        logger.info("SetPowerLimits: enabled=%s, pl1=%dW, pl2=%dW", enabled, pl1, pl2)
        self._config.set("pl_enabled", bool(enabled))
        self._config.set("pl1_w", pl1)
        self._config.set("pl2_w", pl2)
        self._config.save()
        if not enabled:
            return "OK"
        try:
            if is_amd_cpu():
                ryzen_bin = "/usr/libexec/hp-manager/ryzenadj"
                if os.path.exists(ryzen_bin):
                    subprocess.run([ryzen_bin, f"--stapm-limit={pl1*1000}", f"--fast-limit={pl2*1000}", f"--slow-limit={pl1*1000}"], capture_output=True, timeout=2.0)
                elif shutil.which("ryzenadj"):
                    subprocess.run(["ryzenadj", f"--stapm-limit={pl1*1000}", f"--fast-limit={pl2*1000}", f"--slow-limit={pl1*1000}"], capture_output=True, timeout=2.0)
            else:
                rapl1 = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw"
                rapl2 = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw"
                if sysfs_exists(rapl1):
                    sysfs_write(rapl1, pl1 * 1_000_000)
                if sysfs_exists(rapl2):
                    sysfs_write(rapl2, pl2 * 1_000_000)
        except Exception as e:
            logger.debug("Failed to apply power limits: %s", e)
        return "OK"


    def SetAppProfilesEnabled(self, enabled):
        logger.info("SetAppProfilesEnabled: %s", enabled)
        self._config.set("app_profiles_enabled", bool(enabled))
        self._config.save()
        return "OK"

    def SetAppProfiles(self, profiles_json):
        logger.info("SetAppProfiles: %s", profiles_json)
        try:
            data = json.loads(profiles_json)
            self._config.set("app_profiles", data)
            self._config.save()
            return "OK"
        except Exception as e:
            logger.error("Failed to parse app profiles json: %s", e)
            return "FAIL"

    def Ping(self):
        return "OK"


# ─── Entry point ──────────────────────────────────────────────────────────────


def main():
    service = PowerService()
    if service._ctrl.available:
        logger.info("Power profiles: %s", service._ctrl.get_profiles())
    run_service("com.yyl.hpmanager.power", service, service_name="power")


if __name__ == "__main__":
    main()
