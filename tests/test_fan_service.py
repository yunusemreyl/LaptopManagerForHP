import os
import sys
import tempfile
import types
import unittest
from unittest import mock


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "daemon"))

gi = types.ModuleType("gi")
gi.repository = types.ModuleType("gi.repository")
gi.repository.GLib = types.SimpleNamespace(MainLoop=lambda: None)
sys.modules.setdefault("gi", gi)
sys.modules.setdefault("gi.repository", gi.repository)
sys.modules.setdefault("pydbus", types.SimpleNamespace(SystemBus=lambda: None))

from services import fan_service
from common import sysfs as sysfs_helpers


class FanControllerSysfsTest(unittest.TestCase):
    def make_controller(self, hwmon_path, fans=(1, 2), max_speed=6000):
        controller = fan_service.FanController.__new__(fan_service.FanController)
        controller.hwmon_path = hwmon_path
        controller.found_fans = list(fans)
        controller.fan_count = len(fans)
        controller.max_speeds = {fan: max_speed for fan in fans}
        controller.mode = "custom"
        controller._fallback_paths = {}
        controller._last_targets = {}
        return controller

    def write_file(self, directory, name, value="0"):
        path = os.path.join(directory, name)
        with open(path, "w") as handle:
            handle.write(str(value))
        return path

    def read_file(self, directory, name):
        with open(os.path.join(directory, name)) as handle:
            return handle.read()

    def allow_test_sysfs(self, directory):
        return mock.patch.object(
            sysfs_helpers,
            "_ALLOWED_PREFIXES",
            (os.path.realpath(directory) + os.sep,),
        )

    def test_existing_fan_target_file_wins_over_pwm_fallback(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "0")
            self.write_file(hwmon, "fan1_target", "0")
            controller = self.make_controller(hwmon, fans=(1,))

            with self.allow_test_sysfs(hwmon):
                self.assertTrue(controller.set_fan_target(1, 3000))

            self.assertEqual(self.read_file(hwmon, "fan1_target"), "3000")
            self.assertEqual(self.read_file(hwmon, "pwm1"), "0")

    def test_pwm_fallback_maps_rpm_to_pwm_when_target_file_missing(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "0")
            self.write_file(hwmon, "pwm1_enable", "1")
            controller = self.make_controller(hwmon, fans=(1,), max_speed=6000)

            with self.allow_test_sysfs(hwmon):
                self.assertTrue(controller.set_fan_target(1, 6000))

            self.assertEqual(self.read_file(hwmon, "pwm1"), "255")

    def test_pwm_fallback_clamps_nonzero_pwm_to_safe_minimum(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "0")
            self.write_file(hwmon, "pwm1_enable", "1")
            controller = self.make_controller(hwmon, fans=(1,), max_speed=6000)

            with self.allow_test_sysfs(hwmon):
                self.assertTrue(controller.set_fan_target(1, 1000))

            self.assertEqual(
                self.read_file(hwmon, "pwm1"),
                str(fan_service.PWM_FALLBACK_MIN),
            )

    def test_pwm_fallback_preserves_zero_pwm(self):
        with tempfile.TemporaryDirectory() as hwmon:
            self.write_file(hwmon, "pwm1", "255")
            self.write_file(hwmon, "pwm1_enable", "1")
            controller = self.make_controller(hwmon, fans=(1,), max_speed=6000)

            with self.allow_test_sysfs(hwmon):
                self.assertTrue(controller.set_fan_target(1, 0))

            self.assertEqual(self.read_file(hwmon, "pwm1"), "0")

    def test_auto_pwm_mode_is_not_overridden_by_thermal_profile(self):
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
        self.assertEqual(controller.mode, "auto")

    def test_auto_pwm_mode_is_not_overridden_by_platform_profile(self):
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
        self.assertEqual(controller.mode, "auto")


class ThermalProtectionTest(unittest.TestCase):
    def test_releases_after_temperature_drops_below_hysteresis_threshold(self):
        self.assertTrue(
            fan_service.FanService._should_exit_thermal_protection(84.9, 10.0)
        )

    def test_stays_active_between_release_and_trigger_thresholds(self):
        self.assertFalse(
            fan_service.FanService._should_exit_thermal_protection(89.0, 10.0)
        )

    def test_timeout_releases_a_slow_cooling_sensor(self):
        self.assertTrue(
            fan_service.FanService._should_exit_thermal_protection(89.0, 301.0)
        )


if __name__ == "__main__":
    unittest.main()
