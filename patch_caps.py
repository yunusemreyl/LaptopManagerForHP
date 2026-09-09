import re

with open("src/omen-space-daemon/src/capabilities.rs", "r") as f:
    content = f.read()

# Models that need max_fan_speed_percent: 55
fan55_models = ["8600", "8787", "878C", "88D2", "8C76", "8C77", "8D24", "8E35", "8D26", "8D2F", "8D40", "8A18"]

for model in fan55_models:
    # Find the line like: model!("8600", "OMEN...", 2019, "Legacy", { ... }),
    pattern = r'(model!\("' + model + r'".*?\{)(.*?)\}\),'
    
    def repl(m):
        prefix = m.group(1)
        inner = m.group(2)
        if "max_fan_speed_percent" not in inner:
            if not inner.strip():
                inner = " max_fan_speed_percent: 55 "
            else:
                inner = inner + ", max_fan_speed_percent: 55 "
        return prefix + inner + "}),"
        
    content = re.sub(pattern, repl, content)

# Add missing models
missing_models = """
        // Missing models imported from OmenCore
        model!("8BA9", "OMEN 16 (2024)", 2024, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true, max_fan_speed_percent: 55 }),
        model!("8C30", "HP Victus 15 (2023) fb1xxx", 2023, "Victus", { has_mux_switch: false, supports_undervolt: false, has_four_zone_rgb: false }),
        model!("8D42", "OMEN MAX Gaming Laptop 16-ah0xxx", 2025, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false, has_per_key_rgb: true }),
        model!("8DD5", "HP Victus 15 (2024)", 2024, "Victus", { has_mux_switch: false, supports_undervolt: false }),
        model!("8DD6", "HP Victus 15 (2024)", 2024, "Victus", { has_mux_switch: false, supports_undervolt: false }),
        model!("8E10", "OMEN Gaming Laptop 17-db1xxx", 2025, "OMEN", { has_mux_switch: false, supports_gpu_power_boost: false, max_fan_speed_percent: 45 }),
        model!("8E5E", "HP Victus 15-fa2303TX (2024)", 2024, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
"""

if "Missing models imported from OmenCore" not in content:
    content = content.replace("    ])\n}", missing_models + "    ])\n}")

with open("src/omen-space-daemon/src/capabilities.rs", "w") as f:
    f.write(content)
