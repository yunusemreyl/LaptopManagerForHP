import re

with open("src/omen-space-daemon/src/capabilities.rs", "r") as f:
    content = f.read()

new_models = """
        // Advanced Optimus Models
        model!("8D41", "OMEN MAX Gaming Laptop 16-ah0xxx", 2025, "OMEN16", { supports_fan_control_wmi: true, supports_fan_control_ec: false, has_mux_switch: true, supports_gpu_power_boost: true, supports_advanced_optimus: true, has_four_zone_rgb: true, has_per_key_rgb: true, supports_undervolt: true }),
        model!("8D42", "OMEN MAX 16t-ah000", 2025, "OMEN16", { supports_fan_control_wmi: true, supports_fan_control_ec: false, has_mux_switch: true, supports_advanced_optimus: true, has_four_zone_rgb: true, supports_undervolt: true }),
        model!("AK0003NR", "OMEN MAX 16 ak0003nr AMD", 2025, "OMEN2024Plus", { supports_fan_control_wmi: true, supports_fan_control_ec: false, has_mux_switch: true, supports_advanced_optimus: true, has_per_key_rgb: true, has_light_bar: true, supports_undervolt: false }),
"""

if "8D41" not in content:
    content = content.replace("    ])\n}", new_models + "    ])\n}")

with open("src/omen-space-daemon/src/capabilities.rs", "w") as f:
    f.write(content)
