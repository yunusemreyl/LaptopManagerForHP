#!/usr/bin/env python3
import sys
import os
import json
import subprocess
from pydbus import SystemBus


def get_os():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=")[1].strip().strip('"')
    except: pass
    return "Unknown OS"

def get_host():
    try:
        with open("/sys/devices/virtual/dmi/id/product_name") as f:
            return f.read().strip()
    except: pass
    return "Unknown Host"

def get_kernel():
    try:
        return subprocess.check_output(["uname", "-r"]).decode().strip()
    except: pass
    return "Unknown Kernel"

def get_cpu():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except: pass
    return "Unknown CPU"

def get_gpu():
    gpus = []
    try:
        out = subprocess.check_output(["lspci"]).decode()
        for line in out.splitlines():
            if "VGA" in line or "3D" in line:
                parts = line.split(": ")
                if len(parts) > 1:
                    name = parts[-1].replace("Advanced Micro Devices, Inc. [AMD/ATI]", "AMD")
                    name = name.replace("NVIDIA Corporation", "NVIDIA")
                    name = name.split("(rev")[0].strip()
                    gpus.append(name)
    except: pass
    return " / ".join(gpus) if gpus else "Unknown GPU"

def print_info(bus=None):
    art = [
        "   ____                        ______ __ ",
        "  / __ \\____ ___  ___  ____   / ____// /_/ /",
        " / / / / __ `__ \\/ _ \\/ __ \\ / /    / __/ / ",
        "/ /_/ / / / / / /  __/ / / // /___ / /_ / / ",
        "\\____/_/ /_/ /_/\\___/_/ /_/ \\____/ \\__//_/  "
    ]
    
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    CYAN = '\033[96m'

    fan_mode = "Unknown"
    power_prof = "Unknown"
    mux_mode = "Unknown"
    if bus:
        try:
            fan_svc = bus.get("com.yyl.hpmanager.fan")
            st = json.loads(fan_svc.GetFanInfo())
            fan_mode = st.get("mode", "Unknown").capitalize()
        except: pass
        try:
            power_svc = bus.get("com.yyl.hpmanager.power")
            st = json.loads(power_svc.GetPowerProfile())
            power_prof = st.get("active", "Unknown").capitalize()
        except: pass
        try:
            mux_svc = bus.get("com.yyl.hpmanager.mux")
            st = json.loads(mux_svc.GetMuxInfo())
            mux_mode = st.get("mode", "Unknown").capitalize()
        except: pass

    lines = [
        f"{RED}{BOLD}{os.environ.get('USER', 'user')}@{get_host()}{RESET}",
        "-----------------------",
        f"{CYAN}OS:{RESET} {get_os()}",
        f"{CYAN}Kernel:{RESET} {get_kernel()}",
        f"{CYAN}CPU:{RESET} {get_cpu()}",
        f"{CYAN}GPU:{RESET} {get_gpu()}",
        "-----------------------",
        f"{CYAN}Fan Mode:{RESET} {fan_mode}",
        f"{CYAN}Power Profile:{RESET} {power_prof}",
        f"{CYAN}MUX Switch:{RESET} {mux_mode}",
    ]

    max_lines = max(len(art), len(lines))
    print("")
    for i in range(max_lines):
        art_line = art[i] if i < len(art) else " " * len(art[0])
        colored_art = f"{RED}{art_line}{RESET}"
        info_line = lines[i] if i < len(lines) else ""
        print(f" {colored_art}   {info_line}")
    print("")

def print_usage():
    print("OmenCtl CLI (Command Line Interface)")
    print("Usage: omenctl <command> [args]")
    print("  info                          - Shows OMEN system info (Default)")
    print("\nCommands:")
    print("  fan <max|auto|performance>    - Sets fan mode")
    print("  performans <profile>          - Sets power profile (performance, balanced, quiet)")
    print("  power <profile>               - Alias for performans")
    print("  klavye <mode>                 - Sets RGB mode (static, breathing, wave, rainbow, etc.)")
    print("  rgb <mode>                    - Alias for klavye")
    print("  mux <hybrid|discrete>         - Sets GPU mode")
    print("  dump                          - Generates auto-calibration & hardware report")
    print("  uninstall                     - Uninstalls OmenCtl from the system")
    print("  help                          - Shows this help menu")
    print("\nExamples:")
    print("  omenctl fan max")
    print("  omenctl power performance")
    print("  omenctl klavye wave")
    print("  omenctl mux discrete")

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("help", "--help", "-h"):
        print_usage()
        sys.exit(0)

    try:
        bus = SystemBus()
    except Exception:
        bus = None

    if len(sys.argv) < 2 or sys.argv[1].lower() == "info":
        print_info(bus)
        sys.exit(0)
        
    cmd = sys.argv[1].lower()

    try:
        if cmd == "fan":
            if len(sys.argv) < 3:
                print("Error: fan command requires a mode (max, auto, performance)")
                sys.exit(1)
            
            sub = sys.argv[2].lower()
            if sub not in ("max", "auto", "performance"):
                print(f"Error: invalid fan mode '{sub}'")
                sys.exit(1)
            
            fan_svc = bus.get("com.yyl.hpmanager.fan")
            res = fan_svc.SetFanMode(sub)
            print(f"Fan mode set to '{sub}': {res}")

        elif cmd in ("performans", "power", "mode"):
            if len(sys.argv) < 3:
                print("Error: power command requires a profile (performance, balanced, quiet)")
                sys.exit(1)
            
            profile = sys.argv[2].lower()
            mapping = {
                "performance": "performance",
                "balanced": "balanced",
                "quiet": "power-saver",
                "eco": "power-saver",
                "powersaver": "power-saver"
            }
            target = mapping.get(profile)
            if not target:
                print(f"Error: invalid power profile '{profile}'. Valid profiles: performance, balanced, quiet")
                sys.exit(1)
            
            power_svc = bus.get("com.yyl.hpmanager.power")
            res = power_svc.SetPowerProfile(target)
            print(f"Power profile set to '{profile}': {res}")

        elif cmd in ("klavye", "rgb"):
            if len(sys.argv) < 3:
                print("Error: rgb command requires a mode (static, breathing, wave, rainbow, pulse, etc.)")
                sys.exit(1)
            
            mode = sys.argv[2].lower()
            rgb_svc = bus.get("com.yyl.hpmanager.rgb")
            # Speed is defaulted to 50 for CLI
            res = rgb_svc.SetMode(mode, 50)
            if res == "FAIL":
                print(f"Error: Invalid or unsupported RGB mode '{mode}'.")
            else:
                print(f"RGB mode set to '{mode}': {res}")

        elif cmd == "mux":
            if len(sys.argv) < 3:
                print("Error: mux command requires a mode (hybrid, discrete)")
                sys.exit(1)
            
            mode = sys.argv[2].lower()
            if mode not in ("hybrid", "discrete"):
                print(f"Error: invalid mux mode '{mode}'")
                sys.exit(1)
            
            mux_svc = bus.get("com.yyl.hpmanager.mux")
            res = mux_svc.SetGpuMode(mode)
            print(f"GPU mode set to '{mode}': {res}")
            if "REBOOT_REQUIRED" in res:
                print("Warning: A system reboot or session restart is required for changes to take effect.")

        elif cmd == "dump":
            plat_svc = bus.get("com.yyl.hpmanager.platform")
            res = plat_svc.GenerateHardwareDump()
            print(res)
            
        elif cmd == "uninstall":
            print("Starting uninstallation process...")
            import subprocess
            subprocess.run(["sudo", "hp-manager-uninstall"])

        else:
            print(f"Error: unknown command '{cmd}'")
            print_usage()
            sys.exit(1)

    except Exception as e:
        print(f"Error (Could not connect to service): {e}")
        print("Ensure that the background services (hpm-fan, hpm-power, etc.) are running.")
        sys.exit(1)

if __name__ == "__main__":
    main()
