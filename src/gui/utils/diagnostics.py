import platform
import subprocess
import os
import glob
import re

def _read_dmi(name, default="N/A"):
    for prefix in ("/sys/class/dmi/id/", "/sys/devices/virtual/dmi/id/"):
        path = prefix + name
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return f.read().strip()
        except Exception:
            pass
    return default

def _read_sysfs(path, default="N/A"):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    except Exception:
        pass
    return default

def _run_cmd(cmd, timeout=3):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout).decode(errors='ignore').strip()
    except Exception:
        return ""

def generate_diagnostic_report(app_version, distro_name):
    out = [f"{'='*60}", f"  OmenCtl System Diagnostic Report (v{app_version})", f"{'='*60}", ""]

    # ── 1. System Information ────────────────────────────────────
    board_id = _read_dmi("board_name", "Unknown")
    product_name = _read_dmi("product_name", "Unknown")
    bios_version = _read_dmi("bios_version", "Unknown")
    bios_date = _read_dmi("bios_date", "Unknown")
    board_vendor = _read_dmi("board_vendor", "Unknown")

    out.append("── SYSTEM INFORMATION ──")
    out.append(f"  Board ID       : {board_id}")
    out.append(f"  Product Name   : {product_name}")
    out.append(f"  Board Vendor   : {board_vendor}")
    out.append(f"  BIOS Version   : {bios_version}")
    out.append(f"  BIOS Date      : {bios_date}")
    out.append(f"  Kernel         : {platform.release()}")
    out.append(f"  OS             : {distro_name}")
    out.append(f"  Architecture   : {platform.machine()}")

    # Secure Boot
    secure_boot = "Unknown"
    try:
        for sb_path in glob.glob("/sys/firmware/efi/efivars/SecureBoot-*"):
            with open(sb_path, "rb") as f:
                data = f.read()
                secure_boot = "Enabled" if data[-1] == 1 else "Disabled"
                break
    except Exception:
        pass
    out.append(f"  Secure Boot    : {secure_boot}")
    out.append("")

    # ── 2. Capabilities Database Match ───────────────────────────
    out.append("── CAPABILITIES DATABASE ──")
    try:
        import sys as _sys
        _daemon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "daemon"))
        if _daemon_path not in _sys.path:
            _sys.path.insert(0, _daemon_path)
        from common.capabilities import KNOWN_MODELS, DEFAULT_CAPS
        caps = KNOWN_MODELS.get(board_id.upper(), None)
        if caps:
            out.append(f"  DB Match       : ✓ {caps.model_name} ({caps.product_id})")
            out.append(f"  Model Year     : {caps.model_year}")
            out.append(f"  Family         : {caps.family}")
            out.append(f"  Fan Control WMI: {caps.supports_fan_control_wmi}")
            out.append(f"  Fan Control EC : {caps.supports_fan_control_ec}")
            out.append(f"  Fan Curves     : {caps.supports_fan_curves}")
            out.append(f"  MUX Switch     : {caps.has_mux_switch}")
            out.append(f"  GPU Power Boost: {caps.supports_gpu_power_boost}")
            if caps.notes:
                out.append(f"  Notes          : {caps.notes}")
        else:
            out.append(f"  DB Match       : ✗ Board ID '{board_id}' not in database")
            out.append(f"  Using defaults : supports_fan_control_ec=False")
    except Exception as e:
        out.append(f"  DB Match       : Error loading capabilities ({e})")
    out.append("")

    # ── 3. ACPI / DSDT / SSDT Analysis ───────────────────────────
    out.append("── ACPI TABLE ANALYSIS ──")

    # List available ACPI tables
    acpi_tables_path = "/sys/firmware/acpi/tables"
    if os.path.exists(acpi_tables_path):
        try:
            tables = sorted(os.listdir(acpi_tables_path))
            dsdt_found = "DSDT" in tables
            ssdt_list = [t for t in tables if t.startswith("SSDT")]
            out.append(f"  DSDT           : {'Present' if dsdt_found else 'Not Found'}")
            out.append(f"  SSDT Tables    : {len(ssdt_list)} ({', '.join(ssdt_list[:8])}{'...' if len(ssdt_list) > 8 else ''})")
            other_tables = [t for t in tables if t not in ("DSDT",) and not t.startswith("SSDT") and not t.startswith("dynamic")]
            if other_tables:
                out.append(f"  Other Tables   : {', '.join(other_tables[:12])}")
        except Exception as e:
            out.append(f"  Table listing  : Error ({e})")
    else:
        out.append(f"  ACPI Tables    : {acpi_tables_path} not accessible")

    # ACPI errors from dmesg
    out.append("")
    out.append("  ACPI Errors (dmesg):")
    acpi_errors = []
    try:
        acpi_pattern = re.compile(
            r'ACPI\s*(Error|Warning|Exception)|AE_AML_|WQBZ|WQBE|WMID|_SB\.WMID|'
            r'AE_NOT_FOUND|AE_BAD_PARAMETER|AE_ALREADY_EXISTS|'
            r'hp.wmi.*error|hp.wmi.*fail|thermal.*profile.*fail',
            re.IGNORECASE
        )
        dmesg_out = ""
        try:
            dmesg_out = subprocess.check_output(['dmesg'], stderr=subprocess.DEVNULL, timeout=5).decode(errors='ignore')
        except Exception:
            try:
                dmesg_out = subprocess.check_output(
                    ['journalctl', '-k', '--no-pager', '-b'],
                    stderr=subprocess.DEVNULL, timeout=5
                ).decode(errors='ignore')
            except Exception:
                pass

        if dmesg_out:
            for line in dmesg_out.splitlines():
                if acpi_pattern.search(line):
                    acpi_errors.append(line.strip())

        if acpi_errors:
            seen = set()
            unique_errors = []
            for err in acpi_errors:
                normalized = re.sub(r'^\[[\s\d.]+\]\s*', '', err)
                if normalized not in seen:
                    seen.add(normalized)
                    unique_errors.append(err)
            for err in unique_errors[:20]:
                out.append(f"    {err}")
            if len(unique_errors) > 20:
                out.append(f"    ... ({len(unique_errors) - 20} more)")
            out.append(f"  Total ACPI Errors: {len(unique_errors)}")
        else:
            out.append("    None detected ✓")
    except Exception as e:
        out.append(f"    Could not read dmesg/journal: {e}")
    out.append("")

    # ── 4. WMI Subsystem ─────────────────────────────────────────
    out.append("── WMI SUBSYSTEM ──")
    guids = {
        "95F24279-4D7B-4334-9387-ACCDC67EF61C": "HP WMI Event",
        "5FB7F034-2C63-45E9-BE91-3D44E2C707E4": "HP WMI BIOS",
        "2B814318-4BE8-4707-9D84-A190A859B5D0": "HP OMEN WMI",
    }
    wmi_devices_path = "/sys/bus/wmi/devices/"
    for guid, name in guids.items():
        found = False
        if os.path.exists(wmi_devices_path):
            try:
                for d in os.listdir(wmi_devices_path):
                    if guid.lower() in d.lower():
                        found = True
                        break
            except Exception:
                pass
        out.append(f"  {name:20s}: {'✓ Found' if found else '✗ Not Found'}")
    out.append("")

    # ── 5. Fan / Thermal Sysfs Deep Scan ─────────────────────────
    out.append("── FAN & THERMAL SYSFS ──")
    hwmon_found = False
    for hdir in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            name_val = _read_sysfs(os.path.join(hdir, "name"), "")
            if name_val in ("hp", "hp-omen"):
                hwmon_found = True
                out.append(f"  Hwmon Path     : {hdir} (driver: {name_val})")

                for fan_path in sorted(glob.glob(os.path.join(hdir, "fan*_input"))):
                    fname = os.path.basename(fan_path)
                    fnum = fname.replace("fan", "").replace("_input", "")
                    rpm = _read_sysfs(fan_path, "?")
                    fan_max = _read_sysfs(os.path.join(hdir, f"fan{fnum}_max"), "N/A")
                    fan_target = _read_sysfs(os.path.join(hdir, f"fan{fnum}_target"), "N/A")
                    out.append(f"  Fan {fnum}         : {rpm} RPM (max={fan_max}, target={fan_target})")

                for pwm_file in ("pwm1", "pwm1_enable", "pwm1_min", "pwm1_max"):
                    pwm_path = os.path.join(hdir, pwm_file)
                    if os.path.exists(pwm_path):
                        val = _read_sysfs(pwm_path, "?")
                        writable = os.access(pwm_path, os.W_OK)
                        out.append(f"  {pwm_file:16s}: {val} {'(writable)' if writable else '(read-only)'}")
                    else:
                        out.append(f"  {pwm_file:16s}: NOT PRESENT")

                break
        except Exception:
            continue
    if not hwmon_found:
        out.append("  HP Hwmon       : ✗ Not Found")

    out.append("")
    out.append("  Thermal Profile Paths:")
    profile_paths = [
        "/sys/firmware/acpi/platform_profile",
        "/sys/devices/platform/hp-wmi/platform_profile",
        "/sys/devices/platform/hp-wmi/thermal_profile",
        "/sys/devices/platform/hp-omen/thermal_profile",
    ]
    for pp in profile_paths:
        if os.path.exists(pp):
            val = _read_sysfs(pp, "?")
            choices_path = pp + "_choices" if "platform_profile" in pp else ""
            choices = ""
            if choices_path:
                choices_path_alt = pp.replace("platform_profile", "platform_profile_choices")
                choices = _read_sysfs(choices_path_alt, "")
                if choices == "N/A":
                    choices = ""
            extra = f" (choices: {choices})" if choices else ""
            out.append(f"    ✓ {pp} = {val}{extra}")
        else:
            out.append(f"    ✗ {pp}")

    out.append("")
    out.append("  GPU Power Paths:")
    for base in ("/sys/devices/platform/hp-wmi", "/sys/devices/platform/hp-omen"):
        for attr in ("gpu_tgp", "gpu_ppab"):
            p = f"{base}/{attr}"
            if os.path.exists(p):
                out.append(f"    ✓ {p} = {_read_sysfs(p, '?')}")
    out.append("")

    # ── 6. EC Access State ───────────────────────────────────────
    out.append("── EC ACCESS ──")
    ec_path = "/sys/kernel/debug/ec/ec0/io"
    ec_exists = os.path.exists(ec_path)
    out.append(f"  EC sysfs path  : {ec_path}")
    out.append(f"  EC accessible  : {'✓ Yes' if ec_exists else '✗ No'}")
    ec_sys_loaded = False
    try:
        with open("/proc/modules") as f:
            ec_sys_loaded = "ec_sys" in f.read()
    except Exception:
        pass
    out.append(f"  ec_sys module   : {'Loaded' if ec_sys_loaded else 'Not Loaded'}")
    out.append("")

    # ── 7. Kernel Modules ────────────────────────────────────────
    out.append("── KERNEL MODULES ──")
    modules_to_check = [
        "hp_wmi", "hp_rgb_lighting", "ec_sys", "wmi", "wmi_bmof",
        "hp_omen", "hp_laptop", "platform_profile",
    ]
    try:
        lsmod_out = _run_cmd(["lsmod"], timeout=2)
        for mod in modules_to_check:
            loaded = mod in lsmod_out.split() or any(
                line.split()[0] == mod for line in lsmod_out.splitlines() if line.strip()
            )
            out.append(f"  {mod:24s}: {'✓ Loaded' if loaded else '✗ Not Loaded'}")
    except Exception:
        out.append("  Could not check modules")
    out.append("")

    # ── 8. Service Status ────────────────────────────────────────
    out.append("── OMENCTL SERVICES ──")
    for svc_name in ("hpm-fan", "hpm-rgb", "hpm-power", "hpm-mux", "hpm-platform"):
        try:
            status = subprocess.check_output(
                ["systemctl", "is-active", f"{svc_name}.service"],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode(errors='ignore').strip()
            emoji = "✓" if status == "active" else "✗"
            out.append(f"  {emoji} {svc_name:18s}: {status}")
        except subprocess.CalledProcessError as e:
            status = e.output.decode(errors='ignore').strip() if e.output else "inactive"
            out.append(f"  ✗ {svc_name:18s}: {status}")
        except Exception as e:
            out.append(f"  ? {svc_name:18s}: Error ({e})")

    out.append("")
    out.append("  Saved Configs (/etc/hp-manager/):")
    config_dir = "/etc/hp-manager"
    if os.path.exists(config_dir):
        for cfg_file in sorted(glob.glob(os.path.join(config_dir, "*.json"))):
            fname = os.path.basename(cfg_file)
            try:
                import json as _json
                with open(cfg_file) as f:
                    data = _json.load(f)
                items = []
                for k, v in data.items():
                    sv = str(v)
                    if len(sv) > 40:
                        sv = sv[:37] + "..."
                    items.append(f"{k}={sv}")
                out.append(f"    {fname}: {', '.join(items)}")
            except Exception:
                out.append(f"    {fname}: (unreadable)")
    else:
        out.append(f"    {config_dir} does not exist")
    out.append("")

    # ── 9. Relevant Kernel Logs ──────────────────────────────────
    out.append("── KERNEL LOGS (hp_wmi / ACPI / thermal) ──")
    try:
        log_pattern = re.compile(
            r'hp.wmi|hp.omen|hp.rgb|wmi.*hp|thermal.*profile|omen|ACPI.*Error|AE_AML',
            re.IGNORECASE
        )
        dmesg_text = ""
        try:
            dmesg_text = subprocess.check_output(['dmesg'], stderr=subprocess.DEVNULL, timeout=5).decode(errors='ignore')
        except Exception:
            try:
                dmesg_text = subprocess.check_output(
                    ['journalctl', '-k', '--no-pager', '-b'],
                    stderr=subprocess.DEVNULL, timeout=5
                ).decode(errors='ignore')
            except Exception:
                pass

        if dmesg_text:
            log_lines = [l for l in dmesg_text.splitlines() if log_pattern.search(l)]
            seen = set()
            unique_lines = []
            for l in log_lines:
                normalized = re.sub(r'^\[[\s\d.]+\]\s*', '', l.strip())
                if normalized not in seen:
                    seen.add(normalized)
                    unique_lines.append(l.strip())
            for line in unique_lines[-25:]:
                out.append(f"  {line}")
            if not unique_lines:
                out.append("  No relevant kernel logs found.")
        else:
            out.append("  Could not access dmesg/journal.")
    except Exception:
        out.append("  Could not access dmesg/journal (insufficient permissions).")

    out.append("")
    out.append(f"{'='*60}")
    out.append(f"  End of Diagnostic Report")
    out.append(f"{'='*60}")
    return "\n".join(out)


def generate_github_issue_body(app_version, distro_name):
    """Build a Markdown-formatted GitHub issue body with diagnostics."""
    board_id = _read_dmi("board_name", "Unknown")
    product_name = _read_dmi("product_name", "Unknown")
    bios_version = _read_dmi("bios_version", "Unknown")
    bios_date = _read_dmi("bios_date", "Unknown")
    kernel = platform.release()

    body_parts = []
    body_parts.append("## System Information\n")
    body_parts.append("| Property | Value |")
    body_parts.append("|----------|-------|")
    body_parts.append(f"| **Board ID** | `{board_id}` |")
    body_parts.append(f"| **Model** | {product_name} |")
    body_parts.append(f"| **BIOS** | {bios_version} ({bios_date}) |")
    body_parts.append(f"| **Kernel** | `{kernel}` |")
    body_parts.append(f"| **OS** | {distro_name} |")
    body_parts.append(f"| **OmenCtl** | v{app_version} |")

    secure_boot = "Unknown"
    try:
        for sb_path in glob.glob("/sys/firmware/efi/efivars/SecureBoot-*"):
            with open(sb_path, "rb") as f:
                data = f.read()
                secure_boot = "Enabled" if data[-1] == 1 else "Disabled"
                break
    except Exception:
        pass
    body_parts.append(f"| **Secure Boot** | {secure_boot} |\n")

    try:
        import sys as _sys
        _daemon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "daemon"))
        if _daemon_path not in _sys.path:
            _sys.path.insert(0, _daemon_path)
        from common.capabilities import KNOWN_MODELS
        caps = KNOWN_MODELS.get(board_id.upper(), None)
        if caps:
            body_parts.append(f"**Capabilities DB**: Matched `{caps.model_name}` — EC={caps.supports_fan_control_ec}, WMI={caps.supports_fan_control_wmi}, MUX={caps.has_mux_switch}\n")
        else:
            body_parts.append(f"**Capabilities DB**: Board `{board_id}` not in database\n")
    except Exception:
        pass

    acpi_errors = []
    try:
        acpi_pattern = re.compile(
            r'ACPI\s*(Error|Warning|Exception)|AE_AML_|WQBZ|WQBE|WMID|'
            r'AE_NOT_FOUND|AE_BAD_PARAMETER|hp.wmi.*error|hp.wmi.*fail',
            re.IGNORECASE
        )
        dmesg_out = ""
        try:
            dmesg_out = subprocess.check_output(['dmesg'], stderr=subprocess.DEVNULL, timeout=5).decode(errors='ignore')
        except Exception:
            pass

        if dmesg_out:
            seen = set()
            for line in dmesg_out.splitlines():
                if acpi_pattern.search(line):
                    normalized = re.sub(r'^\[[\s\d.]+\]\s*', '', line.strip())
                    if normalized not in seen:
                        seen.add(normalized)
                        acpi_errors.append(normalized)
    except Exception:
        pass

    if acpi_errors:
        body_parts.append("## ACPI Errors\n```")
        for err in acpi_errors[:15]:
            body_parts.append(err)
        if len(acpi_errors) > 15:
            body_parts.append(f"... ({len(acpi_errors) - 15} more)")
        body_parts.append("```\n")

    body_parts.append("## Fan & Thermal Control\n")
    sysfs_lines = []
    for hdir in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            name_val = _read_sysfs(os.path.join(hdir, "name"), "")
            if name_val in ("hp", "hp-omen"):
                sysfs_lines.append(f"Hwmon: {hdir} (driver: {name_val})")
                for fan_path in sorted(glob.glob(os.path.join(hdir, "fan*_input"))):
                    fnum = os.path.basename(fan_path).replace("fan", "").replace("_input", "")
                    rpm = _read_sysfs(fan_path, "?")
                    sysfs_lines.append(f"  fan{fnum}_input = {rpm} RPM")
                break
        except Exception:
            continue

    if sysfs_lines:
        body_parts.append("```\n" + "\n".join(sysfs_lines) + "\n```\n")

    body_parts.append("## Issue Description\n<!-- Describe your issue here -->\n")
    body_parts.append("## Steps to Reproduce\n1. \n2. \n3. \n")
    body_parts.append("## Expected Behavior\n<!-- What did you expect to happen? -->\n")
    body_parts.append("## Actual Behavior\n<!-- What actually happened? -->\n")

    full_body = "\n".join(body_parts)
    title = f"[{board_id}] Bug Report — {product_name}"

    return {"title": title, "body": full_body}
