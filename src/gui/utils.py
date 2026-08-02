import os

def detect_model_type() -> str:
    """Detects if the system is an OMEN or Victus based on DMI info."""
    for dmi_file in ("/sys/class/dmi/id/product_name",
                     "/sys/class/dmi/id/product_family",
                     "/sys/devices/virtual/dmi/id/product_name",
                     "/sys/devices/virtual/dmi/id/product_family"):
        try:
            if os.path.exists(dmi_file):
                with open(dmi_file) as f:
                    name = f.read().strip().lower()
                    if "victus" in name: return "victus"
                    if "omen" in name: return "omen"
        except Exception: pass
    return "omen"
