import os
import glob
import logging

logger = logging.getLogger("hid_per_key")

class HidPerKeyBackend:
    HP_VID = 0x03F0
    KNOWN_PIDS = {
        0x0538: "OMEN 16 (2023)",
        0x053A: "OMEN Sequoia",
        0x0547: "OMEN 16 (2024)",
        0x0549: "OMEN 17 (2024)",
        0x054E: "OMEN MAX 16 (2025)",
        0x054F: "OMEN MAX 16 (2025)",
    }

    PACKET_SIZE = 65
    REPORT_ID = 0x00
    CMD_BYTE = 0x0F
    SUB_ENTER_EFFECT = 0x42
    SUB_SET_COLORS = 0x52
    SUB_COMMIT = 0x50
    STATIC_MODE_ID = 0x03
    KEYS_PER_SEGMENT = 20
    TOTAL_KEY_COUNT = 104

    def __init__(self):
        self.hidraw_path, self.device_pid = self._find_device()
        if self.hidraw_path:
            logger.info(f"Initialized HidPerKeyBackend on {self.hidraw_path}")
            self.send_enter_per_key_mode()

    def _find_device(self):
        try:
            for path in glob.glob("/sys/class/hidraw/hidraw*"):
                uevent_path = os.path.join(path, "device", "uevent")
                if not os.path.exists(uevent_path):
                    continue
                with open(uevent_path, "r") as f:
                    uevent = f.read()
                    for line in uevent.splitlines():
                        if line.startswith("HID_ID="):
                            _, vals = line.split("=")
                            bus, vid, pid = vals.split(":")
                            vid = int(vid, 16)
                            pid = int(pid, 16)
                            if vid == self.HP_VID and pid in self.KNOWN_PIDS:
                                logger.info(f"Found HP Per-Key RGB device at {path} with PID {hex(pid)} ({self.KNOWN_PIDS[pid]})")
                                return f"/dev/{os.path.basename(path)}", pid
        except Exception as e:
            logger.error(f"Error scanning for hidraw devices: {e}")
        return None, None

    def is_available(self):
        return self.hidraw_path is not None

    def _build_packet(self, sub_command):
        packet = bytearray(self.PACKET_SIZE)
        packet[0] = self.REPORT_ID
        packet[1] = self.CMD_BYTE
        packet[2] = sub_command
        return packet

    def _write_packet(self, packet):
        if not self.is_available():
            return False
        try:
            with open(self.hidraw_path, "wb") as f:
                f.write(packet)
            return True
        except Exception as e:
            logger.error(f"Failed to write to {self.hidraw_path}: {e}")
            return False

    def send_enter_per_key_mode(self, brightness=100):
        packet = self._build_packet(self.SUB_ENTER_EFFECT)
        packet[3] = self.STATIC_MODE_ID
        packet[4] = max(0, min(100, int(brightness)))
        return self._write_packet(packet)

    def send_commit(self):
        return self._write_packet(self._build_packet(self.SUB_COMMIT))

    def write_per_key_colors(self, key_colors):
        segment_count = (len(key_colors) + self.KEYS_PER_SEGMENT - 1) // self.KEYS_PER_SEGMENT
        for seg in range(segment_count):
            packet = self._build_packet(self.SUB_SET_COLORS)
            packet[3] = seg
            start_key = seg * self.KEYS_PER_SEGMENT
            end_key = min(start_key + self.KEYS_PER_SEGMENT, len(key_colors))

            for k in range(start_key, end_key):
                offset = 4 + (k - start_key) * 3
                if offset + 2 >= self.PACKET_SIZE:
                    break
                r, g, b = key_colors[k]
                packet[offset] = r
                packet[offset+1] = g
                packet[offset+2] = b

            if not self._write_packet(packet):
                return False

        return self.send_commit()
        
    def set_zone_colors(self, colors_hex):
        # Map 4 zones to 104 keys linearly
        # colors_hex is a list of hex strings e.g., ["FF0000", "00FF00", "0000FF", "FFFFFF"]
        colors = []
        for c in colors_hex:
            try:
                c = c.lstrip('#')
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                colors.append((r,g,b))
            except Exception:
                colors.append((0,0,0))
        
        while len(colors) < 4:
            colors.append((0,0,0))
            
        key_colors = []
        keys_per_zone = self.TOTAL_KEY_COUNT // 4
        for i in range(self.TOTAL_KEY_COUNT):
            zone_idx = min(i // keys_per_zone, 3)
            key_colors.append(colors[zone_idx])
            
        return self.write_per_key_colors(key_colors)

    def test_single_key(self, key_index, r=255, g=0, b=0):
        if not self.is_available():
            return False
        
        self.send_enter_per_key_mode(100)
        key_colors = [(0, 0, 0)] * self.TOTAL_KEY_COUNT
        if 0 <= key_index < self.TOTAL_KEY_COUNT:
            key_colors[key_index] = (int(r), int(g), int(b))
            
        return self.write_per_key_colors(key_colors)
