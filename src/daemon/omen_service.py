#!/usr/bin/env python3
import sys, os, time, threading, logging, json, colorsys, math, shutil, subprocess
from gi.repository import GLib
from pydbus import SystemBus

# --- SÜRÜCÜ AYARLARI ---
DRIVER_PATH = "/sys/devices/platform/hp-omen-rgb"
CONFIG_FILE = os.path.expanduser("~/.config/omen-control.json")
ENVY_CMD = shutil.which("envycontrol")

# --- LOGLAMA ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()

lock = threading.RLock()
state = {
    "mode": "static", 
    "colors": ["FF0000"]*4, 
    "speed": 50, 
    "brightness": 100, 
    "direction": "ltr", 
    "power": True, 
    "perf_mode": "balanced"
}

class AnimationEngine(threading.Thread):
    def __init__(self): 
        super().__init__()
        self.daemon = True
        self.running = True
        self.last_written = [None] * 4

    def run(self):
        logger.info(f"Motor Başlatılıyor... (V3.9 - Smooth Speed)")
        
        while self.running:
            loop_start = time.time()
            
            with lock: 
                pwr = state.get("power", True)
                mode = state.get("mode", "static")
                bri = state.get("brightness", 100) / 100.0
                spd = state.get("speed", 50)
                cols = state.get("colors", ["FF0000"]*4)[:]
                d = state.get("direction", "ltr")
            
            if not pwr:
                self.apply_batch(["000000"]*4)
                time.sleep(0.5)
                continue
            
            t = time.time()
            targets = []

            # --- EFEKT MATEMATİĞİ (YAVAŞLATILMIŞ) ---
            if mode == "static":
                targets = [self.hex_to_rgb(c) for c in cols]
            
            elif mode == "breathing": 
                # Periyot uzatıldı (Daha yavaş nefes)
                period = 8.0 - (spd * 0.06) 
                phase = (math.sin(2 * math.pi * t / period) + 1) / 2
                base = self.hex_to_rgb(cols[0])
                targets = [(int(base[0]*phase), int(base[1]*phase), int(base[2]*phase))] * 4
            
            elif mode == "cycle": 
                # Hız çarpanı 0.01 -> 0.003 (3 kat yavaş)
                hue = (t * (spd * 0.003)) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                targets = [(int(r*255), int(g*255), int(b*255))] * 4
            
            elif mode == "wave": 
                # Hız çarpanı 0.02 -> 0.007 (3 kat yavaş)
                speed_factor = spd * 0.007
                for i in range(4): 
                    offset = (i * 0.15) if d == "ltr" else ((3 - i) * 0.15)
                    hue = (t * speed_factor + offset) % 1.0
                    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                    targets.append((int(r*255), int(g*255), int(b*255)))
            
            # --- PARLAKLIK VE HEX ---
            final_hex_list = []
            for r, g, b in targets:
                r, g, b = int(r*bri), int(g*bri), int(b*bri)
                final_hex_list.append(f"{r:02X}{g:02X}{b:02X}")
            
            self.apply_batch(final_hex_list)
            
            if mode == "static": 
                time.sleep(0.5)
            else:
                elapsed = time.time() - loop_start
                time.sleep(max(0.033 - elapsed, 0.001))

    def hex_to_rgb(self, h):
        h = h.lstrip('#')
        if not h: return (255, 0, 0)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def apply_batch(self, hex_list):
        for i, hex_code in enumerate(hex_list):
            if self.last_written[i] == hex_code: continue
            path = f"{DRIVER_PATH}/zone{i}"
            try: 
                with open(path, "w") as f: 
                    f.write(hex_code)
                    f.flush()
                self.last_written[i] = hex_code
            except: pass

engine = AnimationEngine()

def save_state(): 
    with lock: 
        try: 
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f: json.dump(state, f)
        except Exception as e: logger.error(f"Kayıt Hatası: {e}")

def load_state(): 
    with lock: 
        try: 
            if os.path.exists(CONFIG_FILE): state.update(json.load(open(CONFIG_FILE, "r")))
        except: pass

class HPControlService(object):
    """
    <node>
      <interface name="com.yyl.hpcontrolcenter">
        <method name="SetColor"><arg type="i" name="z" direction="in"/><arg type="s" name="h" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetMode"><arg type="s" name="m" direction="in"/><arg type="i" name="s" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetGlobal"><arg type="b" name="p" direction="in"/><arg type="i" name="b" direction="in"/><arg type="s" name="d" direction="in"/><arg type="s" name="resp" direction="out"/></method>
        <method name="SetGpuMode"><arg type="s" name="mode" direction="in"/><arg type="s" name="result" direction="out"/></method>
        <method name="GetState"><arg type="s" name="j" direction="out"/></method>
      </interface>
    </node>
    """
    def SetColor(self, z, h):
        logger.info(f"Renk: Zone {z} -> {h}")
        with lock: 
            state["mode"] = "static"
            state["power"] = True
            c = h.lstrip("#").upper()
            if z == 4: state["colors"] = [c] * 4
            elif 0 <= z < 4: state["colors"][z] = c
        save_state()
        return "OK"

    def SetMode(self, m, s):
        logger.info(f"Mod: {m} (Hız: {s})")
        with lock: 
            state["mode"] = m
            state["speed"] = int(s)
            state["power"] = True
        save_state()
        return "OK"

    def SetGlobal(self, p, b, d):
        logger.info(f"Global: Güç={p}, Parlaklık={b}")
        with lock: 
            state["power"] = bool(p)
            state["brightness"] = int(b)
            state["direction"] = d
        save_state()
        return "OK"

    def SetGpuMode(self, mode):
        if not ENVY_CMD: return "EnvyControl Yok"
        try:
            subprocess.run([ENVY_CMD, "-s", mode], check=True)
            return "OK"
        except Exception as e: return f"Hata: {e}"

    def GetState(self):
        with lock:
            return json.dumps(state)

def main():
    if os.geteuid() != 0:
        print("Root yetkisi gerekli (sudo).")
        sys.exit(1)
    
    load_state()
    engine.start()
    
    try:
        bus = SystemBus()
        bus.publish("com.yyl.hpcontrolcenter", HPControlService())
        logger.info("Daemon Hazır ve D-Bus'a Bağlandı.")
        GLib.MainLoop().run()
    except Exception as e:
        logger.critical(f"Servis Hatası: {e}")

if __name__ == "__main__":
    main()
