#!/usr/bin/env python3
"""OMEN Command Center for Linux — MUX (GPU Switch) Microservice."""

import json, os, subprocess, threading, typing, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.logging_config import setup_logging
from common.config import ServiceConfig
from common.sysfs import sysfs_read, sysfs_write, sysfs_exists
from common.dbus_helpers import run_service

logger = setup_logging("mux")

VALID_GPU_MODES = {"hybrid", "discrete"}

# Native WMI MUX sysfs path provided by our custom hp-rgb-lighting module
HP_WMI_GRAPHICS_MODE_PATH = "/sys/devices/platform/hp-rgb-lighting/omen_mux"


class NativeWmiMuxController:
    """
    WMI Orchestrator for MUX switching.
    Uses the native Linux hp-rgb-lighting driver, which interacts with the exact same
    ACPI/WMI methods (CommandType 0x52, command 0x00002) as OmenFlow on Windows.
    
    Modes:
      - 0: Hybrid (Optimus)
      - 1: Discrete
    """
    def __init__(self):
        self.backend = "wmi-native"
        self._cached_mode = "unknown"

    def is_available(self) -> bool:
        return sysfs_exists(HP_WMI_GRAPHICS_MODE_PATH)

    def get_available_backends(self) -> typing.List[str]:
        if self.is_available():
            return [self.backend]
        return []

    def get_backend(self) -> str:
        return self.backend if self.is_available() else "none"

    def set_backend(self, backend: str) -> bool:
        if backend == self.backend and self.is_available():
            return True
        return False

    def get_mode(self) -> str:
        if not self.is_available():
            return "unknown"
            
        if self._cached_mode != "unknown":
            return self._cached_mode
            
        try:
            # First, check DRM display outputs to see if internal display is connected to NVIDIA
            # This is much more reliable on modern laptops where both GPUs remain on the PCIe bus
            import glob, os
            edp_on_nvidia = False
            for card in glob.glob("/sys/class/drm/card[0-9]*"):
                basename = os.path.basename(card).upper()
                if "EDP" in basename:
                    try:
                        with open(os.path.join(card, "status")) as f:
                            if f.read().strip() == "connected":
                                parent = os.path.realpath(os.path.join(card, "device", "device"))
                                vendor_file = os.path.join(parent, "vendor")
                                if os.path.exists(vendor_file):
                                    with open(vendor_file) as vf:
                                        if vf.read().strip().lower() == "0x10de":
                                            edp_on_nvidia = True
                    except Exception:
                        pass
                        
            if edp_on_nvidia:
                self._cached_mode = "discrete"
                return self._cached_mode
                
            # Fallback to lspci detection
            lspci_out = subprocess.check_output(["lspci", "-D"], text=True).strip().lower()
            
            has_nvidia = False
            has_igpu = False
            
            for line in lspci_out.split('\n'):
                if "vga compatible controller" in line or "3d controller" in line or "display controller" in line:
                    if "nvidia" in line:
                        has_nvidia = True
                    elif "intel" in line or "amd" in line or "advanced micro devices" in line:
                        has_igpu = True
            
            if has_nvidia and not has_igpu:
                self._cached_mode = "discrete"
            elif has_nvidia and has_igpu:
                self._cached_mode = "hybrid"
            else:
                self._cached_mode = "unknown"
        except Exception as e:
            logger.debug("MUX get_mode error: %s", e)
            
        return self._cached_mode

    def set_mode(self, mode: str) -> str:
        if not self.is_available():
            return "Error: WMI MUX interface not found"
            
        if mode not in VALID_GPU_MODES:
            return f"Error: Invalid mode '{mode}'"
            
        try:
            val = "0" if mode == "hybrid" else "1"
            success = sysfs_write(HP_WMI_GRAPHICS_MODE_PATH, val)
            if success:
                self._cached_mode = mode
                # WMI hardware MUX switch always requires a reboot to take effect
                return "OK_REBOOT_REQUIRED"
            else:
                return "Error: Failed to write to WMI sysfs"
        except Exception as e:
            logger.error("WMI MUX set_mode error: %s", e)
            return f"Error: {e}"


class MUXService:
    """
    <node>
      <interface name="com.yyl.hpmanager.mux">
        <method name="SetGpuMode"><arg type="s" name="mode" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="GetGpuInfo"><arg type="s" name="j" direction="out"/></method>
        <method name="SetMuxBackend"><arg type="s" name="backend" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="Ping"><arg type="s" name="resp" direction="out"/></method>
      </interface>
    </node>
    """
    def __init__(self):
        self._mux = NativeWmiMuxController()
        self._config = ServiceConfig("mux", {"mux_backend": "auto"})
        self._config.load()
        self._cache_lock = threading.Lock()
        self._displays_cache = None
        
    def _get_displays(self):
        if self._displays_cache is not None:
            return self._displays_cache
        import glob, os
        conns = []
        vendors = {"0x10de": "NVIDIA", "0x8086": "Intel", "0x1002": "AMD"}
        for card in glob.glob("/sys/class/drm/card[0-9]*"):
            if "-" in os.path.basename(card):
                try:
                    with open(os.path.join(card, "status")) as f:
                        if f.read().strip() == "connected":
                            parent = os.path.realpath(os.path.join(card, "device", "device"))
                            vendor_file = os.path.join(parent, "vendor")
                            vendor_name = "Unknown"
                            if os.path.exists(vendor_file):
                                with open(vendor_file) as vf:
                                    v_id = vf.read().strip()
                                    vendor_name = vendors.get(v_id, "Unknown GPU")
                            
                            disp_name = os.path.basename(card).split("-", 1)[1]
                            conns.append({"display": disp_name, "gpu": vendor_name})
                except Exception:
                    pass
        self._displays_cache = conns
        return conns

    def _get_current_info(self):
        return {
            "available": self._mux.is_available(),
            "backend": self._mux.get_backend(),
            "available_backends": self._mux.get_available_backends(),
            "forced_backend": self._config.get("mux_backend", "auto"),
            "mode": self._mux.get_mode(),
            "displays": self._get_displays(),
        }

    def SetGpuMode(self, mode):
        if mode not in VALID_GPU_MODES: 
            return "FAIL"
        result = self._mux.set_mode(mode)
        return result

    def GetGpuInfo(self):
        with self._cache_lock:
            data = self._get_current_info()
        return json.dumps(data)

    def SetMuxBackend(self, backend):
        logger.info("SetMuxBackend: %s", backend)
        # We only support wmi-native now
        if backend in ("auto", "wmi-native"):
            self._config.set("mux_backend", backend)
            self._config.save()
            return "OK"
        return "FAIL"

    def Ping(self):
        return "OK"


def main():
    svc = MUXService()
    if svc._mux.is_available():
        logger.info("MUX backend: %s", svc._mux.get_backend())
    else:
        logger.warning("MUX interface (%s) not available on this system.", HP_WMI_GRAPHICS_MODE_PATH)
        
    run_service("com.yyl.hpmanager.mux", svc, service_name="mux")

if __name__ == "__main__":
    main()
