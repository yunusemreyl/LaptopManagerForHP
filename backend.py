#!/usr/bin/env python3
import sys, os, json, time, math, colorsys, signal, subprocess, shutil
from pathlib import Path

# --- AYARLAR ---
CONFIG_DIR_STR = "/etc/omen-control"
CONFIG_PATH_STR = "/etc/omen-control/config.json"
ZONE_BASE_PATH = "/sys/devices/platform/hp-wmi"

# Komutlar
PPD_CMD = shutil.which("powerprofilesctl")
TUNED_CMD = shutil.which("tuned-adm")

# Varsayılan Ayarlar
config = {"enabled": True, "mode": 0, "zone_colors": ["#FF0000"]*4, "bri": 1.0, "spd": 50, "power": "balanced"}
running = True
last_power_mode = None

def load_config():
    global config
    try:
        if os.path.exists(CONFIG_PATH_STR):
            with open(CONFIG_PATH_STR, "r") as f:
                data = json.load(f)
                config.update(data)
    except Exception as e:
        print(f"Config hatası: {e}")

def apply_power_profile():
    global last_power_mode
    target = config.get("power", "balanced")
    if target == last_power_mode: return
    try:
        if PPD_CMD:
            ppd_map = {"eco": "power-saver", "balanced": "balanced", "perf": "performance"}
            subprocess.run([PPD_CMD, "set", ppd_map.get(target, "balanced")], capture_output=True)
        elif TUNED_CMD:
            tuned_map = {"eco": "powersave", "balanced": "balanced", "perf": "throughput-performance"}
            subprocess.run([TUNED_CMD, "profile", tuned_map.get(target, "balanced")], capture_output=True)
        last_power_mode = target
    except: pass

def driver_write(idx, r, g, b):
    path = f"{ZONE_BASE_PATH}/zone{idx}"
    try:
        if os.path.exists(path):
            with open(path, "w") as f: f.write("{:02X}{:02X}{:02X}".format(r, g, b))
    except: pass

def hex_to_rgb(h):
    try: return tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    except: return (255, 0, 0)

def run_service():
    print("Omen Control Servisi Başlatıldı (v2.1 + Wave).")
    while running:
        try:
            load_config()
            apply_power_profile()

            if not config.get("enabled", True):
                for i in range(4): driver_write(i, 0, 0, 0)
                time.sleep(2)
                continue

            mode = config.get("mode", 0)
            bri = config.get("bri", 1.0)
            spd_val = config.get("spd", 50)

            # Hız çarpanı (Slider 1-100 arası)
            speed_factor = (spd_val / 100.0) * 0.5

            if mode == 0: # Statik
                for i in range(4):
                    r, g, b = hex_to_rgb(config["zone_colors"][i])
                    driver_write(i, int(r*bri), int(g*bri), int(b*bri))
                time.sleep(1.0)

            elif mode == 1: # Nefes
                tick = time.time()
                alpha = 0.1 + (0.9 * ((math.sin(tick * 2) + 1) / 2))
                current_bri = bri * alpha
                for i in range(4):
                    r, g, b = hex_to_rgb(config["zone_colors"][i])
                    driver_write(i, int(r*current_bri), int(g*current_bri), int(b*current_bri))
                time.sleep(0.05)

            elif mode == 2: # Döngü (Tüm klavye aynı anda değişir)
                hue = (time.time() * speed_factor) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                for i in range(4):
                    driver_write(i, int(r*255*bri), int(g*255*bri), int(b*255*bri))
                time.sleep(0.02)

            elif mode == 3: # Dalga (Soldan Sağa)
                base_hue = time.time() * speed_factor
                for i in range(4):
                    # Her bölgeye biraz ofset ekle (i * 0.15)
                    hue = (base_hue + (i * 0.15)) % 1.0
                    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                    driver_write(i, int(r*255*bri), int(g*255*bri), int(b*255*bri))
                time.sleep(0.02)

            elif mode == 4: # Dalga (Sağdan Sola)
                base_hue = time.time() * speed_factor
                for i in range(4):
                    # İndeksi ters çevir (3-i)
                    hue = (base_hue + ((3-i) * 0.15)) % 1.0
                    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                    driver_write(i, int(r*255*bri), int(g*255*bri), int(b*255*bri))
                time.sleep(0.02)

        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(1)

def handle_signal(signum, frame):
    global running
    running = False

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Init Check
    try:
        if not os.path.exists(CONFIG_DIR_STR):
            os.makedirs(CONFIG_DIR_STR, exist_ok=True); os.chmod(CONFIG_DIR_STR, 0o777)
        if not os.path.exists(CONFIG_PATH_STR):
            with open(CONFIG_PATH_STR, "w") as f: json.dump(config, f)
            os.chmod(CONFIG_PATH_STR, 0o666)
    except: pass

    run_service()
