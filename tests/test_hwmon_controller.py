import os
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "daemon"))

from common import hwmon_controller


class HwMonSensorSelectionTest(unittest.TestCase):
    def write_sensor(self, root, index, name, temperatures):
        directory = os.path.join(root, f"hwmon{index}")
        os.makedirs(directory)
        with open(os.path.join(directory, "name"), "w") as handle:
            handle.write(name)
        for sensor_index, temperature in enumerate(temperatures, start=1):
            with open(
                os.path.join(directory, f"temp{sensor_index}_input"), "w"
            ) as handle:
                handle.write(str(temperature))

    def test_nvme_sensor_does_not_drive_cpu_or_gpu_temperature(self):
        with tempfile.TemporaryDirectory() as directory:
            hwmon_root = os.path.join(directory, "hwmon")
            thermal_root = os.path.join(directory, "thermal")
            os.makedirs(hwmon_root)
            os.makedirs(thermal_root)

            self.write_sensor(hwmon_root, 0, "k10temp", [42000])
            self.write_sensor(hwmon_root, 1, "nvme", [35000, 99000])
            self.write_sensor(hwmon_root, 2, "amdgpu", [45000])

            with mock.patch.object(hwmon_controller, "HWMON_PATH", hwmon_root), \
                 mock.patch.object(hwmon_controller, "THERMAL_ZONE_PATH", thermal_root):
                controller = hwmon_controller.LinuxHwMonController()

            self.assertEqual(controller.get_cpu_temperature(), 42.0)
            self.assertEqual(controller.get_gpu_temperature(), 45.0)
            self.assertEqual(controller.available_sensor_count, 2)

    def test_invalid_absolute_zero_sensor_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            sensor = os.path.join(directory, "temp1_input")
            with open(sensor, "w") as handle:
                handle.write("-273000")

            controller = hwmon_controller.LinuxHwMonController.__new__(
                hwmon_controller.LinuxHwMonController
            )
            self.assertIsNone(controller._read_temperature_file(sensor))


if __name__ == "__main__":
    unittest.main()
