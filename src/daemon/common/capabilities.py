#!/usr/bin/env python3
"""OMEN Command Center for Linux — Model Capability Database.

Derived from OmenCore Hardware capabilities database. Maps HP OMEN and Victus
Board IDs and product names to their specific hardware support profiles, WMI versions,
fan zones, EC safety requirements, and MUX capabilities.
"""

import os
import glob
import logging

logger = logging.getLogger("capabilities")

class ModelCapabilities:
    def __init__(self, product_id, model_name, **kwargs):
        self.product_id = product_id.upper()
        self.model_name = model_name
        self.model_year = kwargs.get("model_year", 2023)
        self.family = kwargs.get("family", "OMEN")
        
        # Fan Control Capabilities
        self.supports_fan_control_wmi = kwargs.get("supports_fan_control_wmi", True)
        self.supports_fan_control_ec = kwargs.get("supports_fan_control_ec", True)
        self.supports_fan_curves = kwargs.get("supports_fan_curves", True)
        self.supports_independent_fan_curves = kwargs.get("supports_independent_fan_curves", True)
        self.supports_rpm_readback = kwargs.get("supports_rpm_readback", True)
        self.fan_zone_count = kwargs.get("fan_zone_count", 2)
        self.max_fan_speed_percent = kwargs.get("max_fan_speed_percent", 100)
        self.min_fan_speed_percent = kwargs.get("min_fan_speed_percent", 0)
        
        # Performance Mode Capabilities
        self.supports_performance_modes = kwargs.get("supports_performance_modes", True)
        self.performance_modes = kwargs.get("performance_modes", ["Default", "Performance", "Cool"])
        self.allow_decoupled_wmi_thermal_policy_fallback = kwargs.get("allow_decoupled_wmi_thermal_policy_fallback", False)
        
        # GPU Capabilities
        self.has_mux_switch = kwargs.get("has_mux_switch", False)
        self.supports_gpu_power_boost = kwargs.get("supports_gpu_power_boost", True)
        self.supports_advanced_optimus = kwargs.get("supports_advanced_optimus", False)
        
        # Lighting Capabilities
        self.has_keyboard_backlight = kwargs.get("has_keyboard_backlight", True)
        self.has_four_zone_rgb = kwargs.get("has_four_zone_rgb", True)
        self.has_per_key_rgb = kwargs.get("has_per_key_rgb", False)
        self.has_light_bar = kwargs.get("has_light_bar", False)
        
        # Power / Undervolt Capabilities
        self.supports_undervolt = kwargs.get("supports_undervolt", True)
        self.supports_tcc_offset = kwargs.get("supports_tcc_offset", True)
        self.supports_power_limits = kwargs.get("supports_power_limits", True)
        self.supports_battery_care = kwargs.get("supports_battery_care", True)

        self.notes = kwargs.get("notes", "")

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "model_name": self.model_name,
            "model_year": self.model_year,
            "family": self.family,
            "supports_fan_control_wmi": self.supports_fan_control_wmi,
            "supports_fan_control_ec": self.supports_fan_control_ec,
            "supports_fan_curves": self.supports_fan_curves,
            "fan_zone_count": self.fan_zone_count,
            "has_mux_switch": self.has_mux_switch,
            "supports_gpu_power_boost": self.supports_gpu_power_boost,
            "supports_battery_care": self.supports_battery_care,
            "supports_undervolt": self.supports_undervolt,
            "supports_tcc_offset": self.supports_tcc_offset,
            "supports_power_limits": self.supports_power_limits,
            "notes": self.notes,
        }


# Global database of known OMEN / Victus boards
KNOWN_MODELS = {
    # OMEN 15 Series (2020-2021)
    "8A14": ModelCapabilities("8A14", "OMEN 15 (2020) Intel", model_year=2020, family="OMEN", has_mux_switch=False, supports_fan_control_ec=True),
    "878C": ModelCapabilities("878C", "OMEN Laptop 15-ek0xxx", model_year=2020, family="OMEN", has_mux_switch=False, supports_fan_control_ec=True, notes="Direct EC fan control highly recommended when hp-wmi fails"),
    "878A": ModelCapabilities("878A", "OMEN 15 (2020) AMD", model_year=2020, family="OMEN", has_mux_switch=False, supports_fan_control_ec=True),
    
    # OMEN 16 Series
    "8A43": ModelCapabilities("8A43", "OMEN by HP Gaming Laptop 16-n0xxx", model_year=2022, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8BAB": ModelCapabilities("8BAB", "OMEN by HP Gaming Laptop 16-wf0xxx", model_year=2023, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, supports_fan_control_ec=False, notes="Uses hp-wmi / hwmon routes; direct legacy EC writes are unsafe"),
    "8BAD": ModelCapabilities("8BAD", "OMEN 16 (2023) Intel", model_year=2023, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8CD1": ModelCapabilities("8CD1", "OMEN 16 (2023) AMD", model_year=2023, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8C58": ModelCapabilities("8C58", "OMEN 16 Transcend", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8D24": ModelCapabilities("8D24", "OMEN 16 (2024)", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8D26": ModelCapabilities("8D26", "OMEN 16 (2024) AMD", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8BCD": ModelCapabilities("8BCD", "OMEN by HP Gaming Laptop 16-xd0xxx", model_year=2023, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8E35": ModelCapabilities("8E35", "OMEN MAX 16t-ah000", model_year=2025, family="OMEN", has_mux_switch=True, supports_fan_control_ec=True, has_per_key_rgb=True),
    "8E41": ModelCapabilities("8E41", "OMEN MAX 16-ah0xxx", model_year=2025, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False, has_per_key_rgb=True),
    "8D88": ModelCapabilities("8D88", "OMEN MAX Gaming Laptop 16-ak0xxx", model_year=2025, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False, supports_fan_control_wmi=True, has_per_key_rgb=True, notes="Ryzen AI 7 350 / RTX 5070 Ti. Requires Omen HPC WMI GUID support in hp-wmi."),
    "8C77": ModelCapabilities("8C77", "OMEN by HP Gaming Laptop 16-wf1xxx", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),
    "8C78": ModelCapabilities("8C78", "OMEN by HP Gaming Laptop 16-wf1xxx", model_year=2024, family="OMEN", has_mux_switch=True, supports_fan_control_ec=False),

    # OMEN 17 Series
    "8BB1": ModelCapabilities("8BB1", "OMEN 17 / Victus 15", model_year=2023, family="OMEN/Victus", has_mux_switch=True, supports_fan_control_ec=False),

    # Victus Series
    "88EC": ModelCapabilities("88EC", "Victus by HP 16-e0xxx", model_year=2021, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8934": ModelCapabilities("8934", "Victus by HP 16-e0xxx", model_year=2021, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8A25": ModelCapabilities("8A25", "Victus by HP 15-fb0xxx", model_year=2022, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8A97": ModelCapabilities("8A97", "Victus by HP 16-d1xxx", model_year=2022, family="Victus", has_mux_switch=False, supports_fan_control_ec=True),
    "8B19": ModelCapabilities("8B19", "Victus by HP 16-r0xxx", model_year=2023, family="Victus", has_mux_switch=True, supports_fan_control_ec=False),
    "8B1A": ModelCapabilities("8B1A", "Victus by HP 16-s0xxx", model_year=2023, family="Victus", has_mux_switch=True, supports_fan_control_ec=False),
    "8BBE": ModelCapabilities("8BBE", "Victus by HP 16-r0xxx", model_year=2023, family="Victus", has_mux_switch=True, supports_fan_control_ec=True),
    "88F8": ModelCapabilities("88F8", "Victus by HP Laptop 16-d0xxx", model_year=2023, family="Victus", has_mux_switch=False, supports_fan_control_ec=True, notes="s2idle only — S3 sleep not available; display may not resume after suspend (NVIDIA/hybrid graphics issue)"),
    "8C9C": ModelCapabilities("8C9C", "Victus by HP Gaming Laptop 16-s1xxx", model_year=2024, family="Victus", has_mux_switch=True, supports_fan_control_ec=False),

    # Models migrated from OmenCore (community database)
    "8A15": ModelCapabilities("8A15", "OMEN 15 (2020) AMD", model_year=2020, family="Legacy", has_mux_switch=False, supports_fan_control_ec=True, supports_undervolt=False),
    "8574": ModelCapabilities("8574", "OMEN 15-dc1xxx (2019) Intel", model_year=2019, family="Legacy", has_mux_switch=False, supports_fan_control_wmi=False, supports_fan_control_ec=True, supports_gpu_power_boost=True, has_four_zone_rgb=False, notes="Discord field report - OMEN 15-dc1077tx (ProductId 8574): WMI BIOS command path not functional, EC fan control and PawnIO undervolt runtime available; RGB kept conservative until exact keyboard protocol is verified."),
    "8600": ModelCapabilities("8600", "OMEN 15-dh0xxx (2019) Intel", model_year=2019, family="Legacy", has_mux_switch=False, supports_gpu_power_boost=True, has_four_zone_rgb=False, notes="Discord wafflist 2026-06-15 - OMEN by HP Laptop 15-dh0xxx / ProductId 8600. Exact conservative legacy profile added after FAMILY_LEGACY fallback, barely-effective fan modes except Max, missing PawnIO, CPU temp stuck near 28C, CPU power 0W, and fan RPM 0. Direct EC writes and RPM readback remain disabled until PawnIO/readback validation confirms the board path; WMI thermal-policy fallback enabled for Quick Profiles."),
    "8787": ModelCapabilities("8787", "OMEN 15-en0038ur (2020) AMD", model_year=2020, family="Legacy", has_mux_switch=True, supports_gpu_power_boost=True, supports_undervolt=False, notes="GitHub #120 - HP OMEN Laptop 15-en0038ur, ProductId 8787. Initial support from diagnostics; fan RPM readback remains pending verification."),
    "88D2": ModelCapabilities("88D2", "OMEN by HP Laptop 15z-en100 (2021) AMD", model_year=2021, family="Legacy", has_mux_switch=False, supports_undervolt=False, notes="GitHub #132 - ProductId 88D2 / 15z-en100. Conservative legacy WMI V1 profile; direct EC writes disabled and independent curves held off pending field verification."),
    "8BAF": ModelCapabilities("8BAF", "OMEN 16 (2021) Intel", model_year=2021, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True),
    "8BB0": ModelCapabilities("8BB0", "OMEN 16 (2021) AMD", model_year=2021, family="OMEN", has_mux_switch=True, supports_undervolt=False),
    "8CD0": ModelCapabilities("8CD0", "OMEN 16 (2022) Intel", model_year=2022, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True),
    "8A43": ModelCapabilities("8A43", "OMEN 16 (2022) n0xxx AMD", model_year=2022, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, supports_undervolt=False, notes="GitHub #121 — OMEN 16-n0xxx AMD. Exact same profile as 8A44."),
    "8A44": ModelCapabilities("8A44", "OMEN 16 (2022) n0xxx AMD", model_year=2022, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, supports_undervolt=False, notes="GitHub #112 — OMEN 16-n0xxx. Capabilities inferred from adjacent OMEN 16 generations; needs user verification."),
    "8BCA": ModelCapabilities("8BCA", "OMEN 16 (2023) wf0xxx Intel", model_year=2023, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True),
    "8C76": ModelCapabilities("8C76", "OMEN 16 (2024) wf1xxx Intel", model_year=2024, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, notes="Discord HUrON / HP OMEN 16-WF1015ns 9U8J3EA — ProductId 8C76, i9-14900HX + RTX 4080, BIOS F.19, WMI V1/classic 55-level fan control. Exact entry replaces low-confidence inferred sibling match."),
    "8B2J": ModelCapabilities("8B2J", "OMEN 16 (2024) xf0xxx Intel", model_year=2024, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, notes="2024 model - may have WMI quirks on older BIOS versions"),
    "8D2F": ModelCapabilities("8D2F", "OMEN 16-am0xxx (8D2F)", model_year=2025, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, supports_undervolt=False, notes="GitHub #111 / Discord 2026-05-20 and 2026-05-21; Discord 2026-06-02 follow-up - OMEN Gaming Laptop 16-am0xxx, ProductId 8D2F. Exact board identity confirmed; product ID has appeared across AMD and Intel Core Ultra variants, so direct EC fan writes and independent curves remain disabled. WMI V1 fan/profile control is retained, WMI thermal-policy fallback is enabled for performance modes when EC/MSR power-limit writes are unavailable, and V1 auto-mode floor clear is enabled to let fans ramp down after load."),
    "am0xxx_intel_2025_unverified": ModelCapabilities("am0xxx_intel_2025_unverified", "OMEN 16 (2025) am0xxx Intel Core Ultra", model_year=2025, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, supports_undervolt=False, notes="GitHub #124 - OMEN Gaming Laptop 16-am0168ng / 16-am0xxx (Intel Core Ultra 7-255H + RTX 5070). ProductId pending; direct EC writes disabled until real hardware confirms register layout. WMI thermal-policy fallback is enabled for performance modes when direct EC/MSR power-limit writes are unavailable."),
    "am1xxx_unverified": ModelCapabilities("am1xxx_unverified", "OMEN 16 (2025) am1xxx Intel", model_year=2025, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, notes="Roadmap #26 — OMEN Gaming Laptop 16-am1xxx (2025 Intel, i9-14900HX + RTX 5070 Ti). "),
    "8D40": ModelCapabilities("8D40", "OMEN Slim 16 (2025) an0xxx", model_year=2025, family="OMEN", has_mux_switch=False, supports_gpu_power_boost=True, has_four_zone_rgb=False, supports_undervolt=False, notes="GitHub #145 - OMEN Slim Gaming Laptop 16-an0xxx, ProductId 8D40, SKU 1H85302L6K. Exact conservative profile: WMI V1 fan/profile control retained (matches working family-fallback behavior), direct EC writes and independent curves disabled pending register-layout evidence, MUX/RGB/undervolt left unclaimed until this new thin-chassis line's hardware surface is confirmed. Reported Battery Care (Charge Limit) WMI failure and Performance-mode persistence are tracked separately — see 3.8.1-BUG-REPORTS.md."),
    "8A18": ModelCapabilities("8A18", "OMEN 17-ck1xxx (2022)", model_year=2022, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True, notes="GitHub #134/#144 — WMI V1 control with worker-backed CPU temperature; fan-level fallback is estimated telemetry, not physical RPM. Direct EC remains unverified."),
    "8C3F": ModelCapabilities("8C3F", "HP Victus 15-fa1xxx (2022)", model_year=2022, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, supports_undervolt=False, notes="GitHub #125 — HP Victus 15-fa1xxx (i5-12450H / RTX 2050), ProductId 8C3F. Direct entry to avoid 8BB1 ambiguous-ID path that caused fan control delays. Same conservative Victus profile as 8BB1-VICTUS15."),
    "8BB1-VICTUS15": ModelCapabilities("8BB1-VICTUS15", "HP Victus 15-fa1xxx (2022)", model_year=2022, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, supports_undervolt=False, notes="Victus 15-fa1xxx — single-color backlight; shares 8BB1 product ID with OMEN 17 (2021)"),
    "8B9D": ModelCapabilities("8B9D", "OMEN 17 (2023) Intel", model_year=2023, family="OMEN", has_mux_switch=True, supports_gpu_power_boost=True),
    "17CK2": ModelCapabilities("17CK2", "OMEN 17-ck2xxx (2023)", model_year=2023, family="OMEN", has_mux_switch=True, supports_fan_control_wmi=False, supports_fan_control_ec=True, supports_gpu_power_boost=True, notes="OMEN 17-ck2 series (2023) � WMI ineffective, use OGH proxy or EC access"),
    "8B9E": ModelCapabilities("8B9E", "OMEN 17 (2023) AMD", model_year=2023, family="OMEN", has_mux_switch=True, supports_undervolt=False),
    "8C3A": ModelCapabilities("8C3A", "OMEN Transcend 14 (2023)", model_year=2023, family="Transcend", has_mux_switch=True, supports_fan_control_wmi=False, supports_fan_control_ec=True, supports_gpu_power_boost=True, has_four_zone_rgb=False, notes="Transcend uses different WMI interface - may require OGH proxy for fan control"),
    "8C3B": ModelCapabilities("8C3B", "OMEN Transcend 16 (2023)", model_year=2023, family="Transcend", has_mux_switch=True, supports_fan_control_wmi=False, supports_fan_control_ec=True, has_four_zone_rgb=False, notes="Transcend uses different WMI interface - may require OGH proxy for fan control"),
    "88D9": ModelCapabilities("88D9", "HP Victus 15 (2022) Intel", model_year=2022, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, notes="Victus has limited features compared to OMEN"),
    "88DA": ModelCapabilities("88DA", "HP Victus 15 (2022) AMD", model_year=2022, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, supports_undervolt=False, notes="Victus has limited features compared to OMEN"),
    "8A3E": ModelCapabilities("8A3E", "HP Victus 15 (2022) fb0xxx AMD", model_year=2022, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, supports_undervolt=False, notes="GitHub #105 — Victus 15-fb0xxx. Conservative Victus profile (single-zone backlight)."),
    "8DCD": ModelCapabilities("8DCD", "HP Victus 15 (8DCD)", model_year=2024, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, supports_undervolt=False, notes="GitHub #138 - Victus 15 ProductId 8DCD reports Performance mode remains EC-limited around 40W. Conservative exact profile disables direct EC writes and enables WMI thermal-policy fallback pending diagnostics/readback validation."),
    "8A26": ModelCapabilities("8A26", "HP Victus 16 (2023/2024) d1xxx", model_year=2023, family="Victus", has_mux_switch=False, supports_undervolt=False, notes="GitHub #66 — Victus 16-d1xxx (8A26). Capabilities inferred from nearby Victus 16 entries; awaiting user confirmation."),
    "8BD4": ModelCapabilities("8BD4", "HP Victus 16-s0xxx AMD", model_year=2023, family="Victus", has_mux_switch=False, supports_undervolt=False, notes="RC1 field log - Victus 16-s0xxx (8BD4), Ryzen 7 7840HS + RTX 4060. Conservative WMI V1 fan profile; GPU boost disabled pending verification. Discord 2026-06-08 / 7Z5Z2EA reports basic keyboard RGB should be controllable through WMI ColorTable; EC keyboard writes remain disabled. Discord 2026-06-03 reported fans stuck at max after long gaming session; v3.7.1 Discord 2026-06-07 logs showed non-reactive/0 RPM fan behavior after SetFanLevel(0,0), so V1 manual-zero floor clear is disabled pending a safer handoff sequence."),
    "8C2F": ModelCapabilities("8C2F", "HP Victus 15/16 (2024+) Ryzen (shared board)", model_year=2024, family="Victus", has_mux_switch=False, supports_undervolt=False, notes="GitHub #110 (16-r0xxx) + #155 (15-fb2082wm) — ProductId 8C2F is shared across the 15 inch and 16 inch Victus Ryzen 2024+ chassis. Capabilities were inferred from the 16 inch report and are not yet confirmed on the 15 inch chassis. Keyboard entry 8C2F already present in KeyboardModelDatabase."),
    "88DB": ModelCapabilities("88DB", "HP Victus 16 (2022)", model_year=2022, family="Victus", has_mux_switch=False, supports_undervolt=False),
    "88EE": ModelCapabilities("88EE", "HP Victus 16-e0194nw", model_year=2022, family="Victus", has_mux_switch=False, has_four_zone_rgb=False, supports_undervolt=False, notes="GitHub #140 - HP Victus 16-e0194nw / ProductId 88EE. Exact conservative sibling of 88EC added so model identity resolves by ProductId instead of low-confidence 16-e0 model-name pattern; feature flags remain conservative pending field verification."),
    "DESKTOP-25L": ModelCapabilities("DESKTOP-25L", "OMEN 25L Desktop", model_year=2021, family="Desktop", has_mux_switch=False, supports_fan_control_wmi=False, has_four_zone_rgb=False, notes="OMEN 25L Desktop - fan writes disabled by v3.6.3 safety gate; RPM telemetry/performance modes only pending hardware validation."),
    "DESKTOP-30L": ModelCapabilities("DESKTOP-30L", "OMEN 30L Desktop", model_year=2022, family="Desktop", has_mux_switch=False, supports_fan_control_wmi=False, has_four_zone_rgb=False, notes="OMEN 30L Desktop - fan writes disabled by v3.6.3 safety gate; RPM telemetry/performance modes only pending hardware validation."),
    "DESKTOP-35L": ModelCapabilities("DESKTOP-35L", "OMEN 35L Desktop", model_year=2023, family="Desktop", has_mux_switch=False, supports_fan_control_wmi=False, has_four_zone_rgb=False, notes="OMEN 35L Desktop - fan writes disabled by v3.6.3 safety gate; RPM telemetry/performance modes only pending hardware validation."),
    "DESKTOP-40L": ModelCapabilities("DESKTOP-40L", "OMEN 40L Desktop", model_year=2023, family="Desktop", has_mux_switch=False, supports_fan_control_wmi=False, has_four_zone_rgb=False, notes="OMEN 40L Desktop - fan writes disabled by v3.6.3 safety gate; RPM telemetry/performance modes only pending hardware validation."),
    "DESKTOP-45L": ModelCapabilities("DESKTOP-45L", "OMEN 45L Desktop", model_year=2023, family="Desktop", has_mux_switch=False, supports_fan_control_wmi=False, has_four_zone_rgb=False, notes="OMEN 45L Desktop - fan writes disabled by v3.6.3 safety gate; RPM telemetry/performance modes only pending hardware validation."),
}

DEFAULT_CAPS = ModelCapabilities("DEFAULT", "Unknown HP System", model_year=2023, family="HP", has_mux_switch=False, supports_fan_control_ec=False, notes="Default capability profile")

def get_board_id():
    """Detect HP Board ID from DMI table."""
    for dmi in ("/sys/class/dmi/id/board_name", "/sys/devices/virtual/dmi/id/board_name"):
        if os.path.exists(dmi):
            try:
                with open(dmi) as f:
                    val = f.read().strip()
                    # Some boards have leading 0x or letters, take the core 4 hex chars if possible
                    val = val.replace("0x", "").upper()
                    return val
            except Exception:
                pass
    return "UNKNOWN"

def get_product_name():
    """Detect HP Product Name from DMI table."""
    for dmi in ("/sys/class/dmi/id/product_name", "/sys/devices/virtual/dmi/id/product_name"):
        if os.path.exists(dmi):
            try:
                with open(dmi) as f:
                    return f.read().strip()
            except Exception:
                pass
    return "HP Laptop"

def get_cpu_model():
    """Detect CPU model from /proc/cpuinfo."""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "Unknown CPU"

def detect_capabilities():
    """Discover capabilities based on current board ID and product name."""
    board_id = get_board_id()
    cap = None
    if board_id in KNOWN_MODELS:
        logger.info("Matched board ID %s in capabilities database", board_id)
        cap = KNOWN_MODELS[board_id]
    else:
        # Try matching product name as fallback
        prod = get_product_name().lower()
        for known_cap in KNOWN_MODELS.values():
            if known_cap.model_name.lower() in prod:
                logger.info("Matched product name %s in capabilities database", known_cap.model_name)
                cap = known_cap
                break

    if not cap:
        logger.warning("Board ID %s not found in database, using default capabilities", board_id)
        cap = DEFAULT_CAPS
        
    # Dynamic capability overrides based on hardware specifics
    cpu_model = get_cpu_model().upper()
    is_hx = "HX" in cpu_model
    is_amd = "AMD" in cpu_model or "RYZEN" in cpu_model

    # Disable power tuning on Victus models that do not have an HX processor (Intel only limitation)
    if "VICTUS" in cap.family.upper():
        if not is_hx and not is_amd:
            logger.info("Detected non-HX Intel Victus processor (%s). Disabling Power Tuning features.", cpu_model)
            cap.supports_undervolt = False
            cap.supports_tcc_offset = False
            cap.supports_power_limits = False

    return cap
