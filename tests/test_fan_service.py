import os
import sys
import tempfile
import types
import unittest
from unittest import mock


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "daemon"))

gi = types.ModuleType("gi")
gi.repository = types.ModuleType("gi.repository")
gi.repository.GLib = types.SimpleNamespace(MainLoop=lambda: None)
sys.modules.setdefault("gi", gi)
sys.modules.setdefault("gi.repository", gi.repository)
sys.modules.setdefault("pydbus", types.SimpleNamespace(SystemBus=lambda: None))

from services import fan_service


class FanControllerSysfsTest(unittest.TestCase):
    def make_controller(self, hwmon_path, fans=(1, 2), max_speed=6000):
        controller = fan_service.FanController.__new__(fan_service.FanController)
        controller.hwmon_path = hwmon_path
        controller.found_fans = list(fans)
        controller.fan_count = len(fans)
        controller.max_speeds = {fan: max_speed for fan in fans}
        controller.mode = "custom"
        controller._fallback_paths = {}
        return controller

    def write_file(self, directory, name, value="0"):
        path = os.path.join(directory, name)
        with open(path, "w") as handle:
            handle.write(str(value))
        return path

    def read_file(self, directory, name):
        with open(os.path.join(directory, name)) as handle:
            return handle.read()

    def test_existing_fan_target_file_wins_over_pwm_fallback(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "0")
            self.write_file(hwmon, "fan1_target", "0")
            controller = self.make_controller(hwmon, fans=(1,))

            self.assertTrue(controller.set_fan_target(1, 3000))

            self.assertEqual(self.read_file(hwmon, "fan1_target"), "3000")
            self.assertEqual(self.read_file(hwmon, "pwm1"), "0")

    def test_pwm_fallback_maps_rpm_to_pwm_when_target_file_missing(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "0")
            self.write_file(hwmon, "pwm1_enable", "1")
            controller = self.make_controller(hwmon, fans=(1,), max_speed=6000)

            self.assertTrue(controller.set_fan_target(1, 6000))

            self.assertEqual(self.read_file(hwmon, "pwm1"), "255")

    def test_pwm_fallback_clamps_nonzero_pwm_to_safe_minimum(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "0")
            self.write_file(hwmon, "pwm1_enable", "1")
            controller = self.make_controller(hwmon, fans=(1,), max_speed=6000)

            self.assertTrue(controller.set_fan_target(1, 1000))

            self.assertEqual(self.read_file(hwmon, "pwm1"), "220")

    def test_pwm_fallback_preserves_zero_pwm(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "255")
            self.write_file(hwmon, "pwm1_enable", "1")
            controller = self.make_controller(hwmon, fans=(1,), max_speed=6000)

            self.assertTrue(controller.set_fan_target(1, 0))

            self.assertEqual(self.read_file(hwmon, "pwm1"), "0")

    def test_read_current_mode_uses_thermal_profile_fallback_for_max(self):
        controller = self.make_controller("/fake/hwmon", fans=(1,))
        def read_side_effect(path, default=0):
            if path.endswith("pwm1_enable"):
                return 2
            return 1

        def exists_side_effect(path):
            return path.endswith("thermal_profile")

        with mock.patch.object(fan_service, "sysfs_read", side_effect=read_side_effect), \
             mock.patch.object(fan_service, "sysfs_exists", side_effect=exists_side_effect), \
             mock.patch.object(fan_service, "sysfs_read_str", return_value="balanced"):
            controller._read_current_mode()
        self.assertEqual(controller.mode, "max")

    def test_read_current_mode_uses_platform_profile_fallback_for_max(self):
        controller = self.make_controller("/fake/hwmon", fans=(1,))
        def read_side_effect(path, default=0):
            if path.endswith("pwm1_enable"):
                return 2
            return 0

        def exists_side_effect(path):
            return path.endswith("platform_profile")

        with mock.patch.object(fan_service, "sysfs_read", side_effect=read_side_effect), \
             mock.patch.object(fan_service, "sysfs_exists", side_effect=exists_side_effect), \
             mock.patch.object(fan_service, "sysfs_read_str", return_value="performance"):
            controller._read_current_mode()
        self.assertEqual(controller.mode, "max")


if __name__ == "__main__":
    unittest.main()
