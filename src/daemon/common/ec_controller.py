#!/usr/bin/env python3
"""OMEN Command Center for Linux — Embedded Controller (EC) Driver.

Accesses Linux EC via /sys/kernel/debug/ec/ec0/io using the ec_sys module.
Includes strict safety guards to prevent EC panic on 2025+ OMEN Max models
and fallback handling for legacy models like OMEN 15-ek0xxx (Board 878C).
"""

import os
import subprocess
import threading
import logging

from common.capabilities import detect_capabilities, get_board_id, get_product_name

logger = logging.getLogger("ec_controller")

# EC Register Addresses (Valid ONLY for pre-2025 legacy models like OMEN 15 2020)
REG_FAN1_SPEED_SET = 0x34  # Fan 1 speed set in units of 100 RPM
REG_FAN2_SPEED_SET = 0x35  # Fan 2 speed set in units of 100 RPM
REG_FAN1_SPEED_PCT = 0x2E  # Fan 1 speed 0-100%
REG_FAN2_SPEED_PCT = 0x2F  # Fan 2 speed 0-100%
REG_FAN_BOOST      = 0xEC  # Fan boost: 0x00=OFF, 0x0C=ON
REG_FAN_STATE      = 0xF4  # Fan state: 0x00=Enable, 0x02=Disable
REG_CPU_TEMP       = 0x57  # CPU temperature
REG_GPU_TEMP       = 0xB7  # GPU temperature
REG_PERF_MODE      = 0x95  # Performance mode (0x30=Default, 0x31=Perf, 0x50=Cool)
REG_THERMAL_POWER  = 0xBA  # Thermal power limit (0-5)

EC_PATH = "/sys/kernel/debug/ec/ec0/io"

class LinuxEcController:
    def __init__(self):
        self._lock = threading.Lock()
        self.capabilities = detect_capabilities()
        self.board_id = get_board_id() or "UNKNOWN"
        self.product_name = get_product_name()
        
        # Check if direct EC access is safe on this board
        self.is_unsafe_ec_model = not self.capabilities.supports_fan_control_ec
        self.has_ec_access = False
        
        # We need EC access for fan control OR for thermal fallback on specific boards
        self.needs_ec_fallback = self.board_id in ("8E35", "8A43")
        
        if not self.is_unsafe_ec_model or self.needs_ec_fallback:
            self._ensure_ec_sys()
            self.has_ec_access = os.path.exists(EC_PATH)
        else:
            logger.info("Board ID %s (%s) flagged as Unsafe for legacy EC writes. Direct EC access disabled.", self.board_id, self.product_name)

    def _ensure_ec_sys(self):
        """Ensure ec_sys module is loaded with write_support=1."""
        if os.path.exists(EC_PATH):
            return  # Already available

        # ec0/io lives under debugfs — make sure it is mounted first.
        debugfs_base = "/sys/kernel/debug"
        if not os.path.ismount(debugfs_base):
            try:
                subprocess.run(["mount", "-t", "debugfs", "none", debugfs_base],
                               capture_output=True, timeout=5)
                logger.info("Mounted debugfs at %s", debugfs_base)
            except Exception as e:
                logger.debug("Could not mount debugfs: %s", e)

        try:
            logger.info("Trying to load ec_sys kernel module with write_support=1...")
            subprocess.run(["modprobe", "ec_sys", "write_support=1"], capture_output=True, timeout=5)
        except Exception as e:
            logger.debug("modprobe ec_sys failed: %s", e)

        if not os.path.exists(EC_PATH):
            if os.path.exists("/sys/kernel/security/lockdown"):
                try:
                    with open("/sys/kernel/security/lockdown") as f:
                        ld = f.read().strip()
                        if "[integrity]" in ld or "[confidentiality]" in ld:
                            logger.warning(
                                "EC fallback unavailable: Kernel lockdown is active, "
                                "likely due to Secure Boot. ec_sys write_support is blocked."
                            )
                except Exception:
                    pass

    def try_lazy_ec_load(self) -> bool:
        """Attempt a fresh ec_sys load at runtime and refresh has_ec_access.

        Called by fan_service when EC is needed but was not available at boot
        (e.g. ec_sys not installed yet, but user added it later).
        Returns True if EC access is now available.
        """
        if self.has_ec_access:
            return True
        if self.is_unsafe_ec_model and not self.needs_ec_fallback:
            return False
        self._ensure_ec_sys()
        self.has_ec_access = os.path.exists(EC_PATH)
        if self.has_ec_access:
            logger.info("Lazy EC load succeeded for board %s", self.board_id)
        return self.has_ec_access

    def read_byte(self, reg: int) -> int:
        """Read a single byte from the EC register."""
        if not self.has_ec_access:
            return 0
        # If unsafe, only allow safe thermal registers for fallback
        if self.is_unsafe_ec_model and reg not in (0x59, REG_PERF_MODE):
            return 0
        with self._lock:
            try:
                with open(EC_PATH, "rb") as f:
                    f.seek(reg)
                    data = f.read(1)
                    if data:
                        return data[0]
            except Exception as e:
                logger.debug("EC read_byte failed at 0x%02X: %s", reg, e)
                if isinstance(e, PermissionError):
                    logger.info("Kernel lockdown detected (PermissionError). Disabling EC access.")
                    self.has_ec_access = False
        return 0

    def write_byte(self, reg: int, val: int) -> bool:
        """Write a single byte to the EC register."""
        if not self.has_ec_access:
            return False
        # If unsafe, only allow safe thermal registers for fallback
        if self.is_unsafe_ec_model and reg not in (0x59, REG_PERF_MODE):
            return False
        with self._lock:
            try:
                with open(EC_PATH, "r+b") as f:
                    f.seek(reg)
                    f.write(bytes([val]))
                    f.flush()
                logger.debug("EC write_byte success at 0x%02X = 0x%02X", reg, val)
                return True
            except Exception as e:
                logger.debug("EC write_byte failed at 0x%02X: %s", reg, e)
                if isinstance(e, PermissionError):
                    logger.info("Kernel lockdown detected (PermissionError). Disabling EC access.")
                    self.has_ec_access = False
        return False

    def get_cpu_temp(self) -> float:
        val = self.read_byte(REG_CPU_TEMP)
        return float(val) if val > 0 else 0.0

    def get_gpu_temp(self) -> float:
        val = self.read_byte(REG_GPU_TEMP)
        return float(val) if val > 0 else 0.0

    def set_fan_speed_pct(self, fan_idx: int, pct: int) -> bool:
        """Set fan speed percentage (0-100) directly via EC for legacy models."""
        if self.is_unsafe_ec_model or not self.has_ec_access:
            return False
        pct = max(0, min(100, pct))
        reg = REG_FAN1_SPEED_PCT if fan_idx == 1 else REG_FAN2_SPEED_PCT
        return self.write_byte(reg, pct)

    def set_fan_boost(self, enable: bool) -> bool:
        """Enable or disable fan boost via EC."""
        if self.is_unsafe_ec_model or not self.has_ec_access:
            return False
        val = 0x0C if enable else 0x00
        return self.write_byte(REG_FAN_BOOST, val)

    def set_perf_mode(self, mode: str) -> bool:
        """Set performance mode directly via EC."""
        if not self.has_ec_access:
            return False
            
        # EC Fallback for 8E35 and 8A43 (broken WMI methods _SB.WMID.WQBZ)
        if self.board_id in ("8E35", "8A43"):
            fallback_map = {
                "performance": 0x31,
                "max": 0x31,
                "default": 0x30,
                "auto": 0x30,
                "balanced": 0x30,
                "cool": 0x50,
                "eco": 0x50,
            }
            val = fallback_map.get(mode.lower(), 0x30)
            logger.info("Using EC Fallback for %s to set thermal profile: 0x%02X at 0x59", self.board_id, val)
            return self.write_byte(0x59, val)

        if self.is_unsafe_ec_model:
            return False

        mode_map = {
            "default": 0x30,
            "auto": 0x30,
            "balanced": 0x30,
            "performance": 0x31,
            "max": 0x31,
            "cool": 0x50,
            "eco": 0x50,
        }
        val = mode_map.get(mode.lower(), 0x30)
        return self.write_byte(REG_PERF_MODE, val)
