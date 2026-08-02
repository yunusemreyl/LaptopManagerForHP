"""
OMEN Command Center for Linux — Application Launchers Utility.
Contributed by CodesRahul96
"""
import re
import os

LAUNCHERS = {
    "steam": {
        "env_keys": ["STEAM_COMPAT_APP_ID", "SteamAppId"],
        "exec_patterns": [r"steam://rungameid/(\d+)"]
    },
    "flatpak": {
        "env_keys": ["FLATPAK_ID"],
        "exec_patterns": [r"(?:^|\/)flatpak\s+run\s+([\w\.-]+)"]
    },
    "snap": {
        "env_keys": ["SNAP_NAME"],
        "exec_patterns": [r"(?:^|\/)snap\s+run\s+([\w\.-]+)"]
    },
    "lutris": {
        "env_keys": ["LUTRIS_GAME_UUID", "LUTRIS_GAME_SLUG"],
        "exec_patterns": [r"lutris:rungame/([\w\.-]+)", r"lutris:rungameid/(\d+)"]
    },
    "heroic": {
        "env_keys": ["LEGENDARY_GAME_ID", "LEGENDARY_APP_NAME"],
        "exec_patterns": [r"heroic://launch/[\w-]+/([\w\.-]+)"]
    }
}

def parse_exec_command(exec_raw):
    """
    Parses a raw Exec command line from a desktop entry.
    If it uses a known launcher, extracts the unique target and returns '{launcher}_{target}'.
    Otherwise, returns the base executable name.
    """
    if not exec_raw:
        return None
    
    # Try launcher patterns first
    for launcher, cfg in LAUNCHERS.items():
        for pattern in cfg["exec_patterns"]:
            match = re.search(pattern, exec_raw)
            if match:
                return f"{launcher}_{match.group(1)}"

    # Fallback to default parsing
    try:
        first_part = exec_raw.split()[0]
        first_part = first_part.strip('"\'')
        return os.path.basename(first_part)
    except Exception:
        return None

def get_running_launcher_ids(pid, proc_dir="/proc"):
    """
    Reads {proc_dir}/{pid}/environ and returns a set of launcher-specific IDs (e.g. steam_12345).
    """
    ids = set()
    try:
        environ_path = os.path.join(proc_dir, str(pid), "environ")
        with open(environ_path, "r", errors="ignore") as f:
            env = f.read()
            # Fast check first
            has_launcher = False
            for launcher, cfg in LAUNCHERS.items():
                for env_key in cfg["env_keys"]:
                    if f"{env_key}=" in env:
                        has_launcher = True
                        break
                if has_launcher:
                    break
            
            if has_launcher:
                for item in env.split("\x00"):
                    for launcher, cfg in LAUNCHERS.items():
                        for env_key in cfg["env_keys"]:
                            if item.startswith(f"{env_key}="):
                                parts = item.split("=", 1)
                                if len(parts) == 2 and parts[1]:
                                    ids.add(f"{launcher}_{parts[1]}")
    except Exception:
        pass
    return ids
