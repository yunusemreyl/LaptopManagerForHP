import math
import os
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GUI_ROOT = os.path.join(REPO_ROOT, "src", "gui")
if GUI_ROOT not in sys.path:
    sys.path.insert(0, GUI_ROOT)

from utils.system_monitor import (  # noqa: E402
    friendly_sensor_label,
    is_plausible_temperature,
    select_sensor_candidates,
)


class SensorFilteringTest(unittest.TestCase):
    def test_rejects_disconnected_and_corrupt_values(self):
        for value in (-273.2, 0, 116, math.inf, math.nan, None):
            with self.subTest(value=value):
                self.assertFalse(is_plausible_temperature(value))
        self.assertTrue(is_plausible_temperature(43.75))

    def test_nvme_prefers_composite_temperature(self):
        sensors = [
            {"raw_label": "Composite", "temp": 31.85},
            {"raw_label": "Sensor 2", "temp": 82.85},
        ]
        self.assertEqual(
            select_sensor_candidates("nvme", sensors), [sensors[0]])

    def test_friendly_labels_distinguish_common_devices(self):
        self.assertEqual(friendly_sensor_label("k10temp", "Tctl"), "CPU")
        self.assertEqual(friendly_sensor_label("amdgpu", "edge"), "GPU")
        self.assertEqual(friendly_sensor_label("spd5118", "temp1", 2), "RAM 2")
        self.assertEqual(friendly_sensor_label("acpitz_1", "temp1"), "ACPI 2")


if __name__ == "__main__":
    unittest.main()
