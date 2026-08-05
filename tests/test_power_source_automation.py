import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "daemon"))
sys.modules.setdefault("pydbus", types.SimpleNamespace(SystemBus=lambda: None))

from services import power_service


def make_supply(root, name, supply_type, **attributes):
    path = Path(root, name)
    path.mkdir()
    path.joinpath("type").write_text(supply_type, encoding="utf-8")
    for key, value in attributes.items():
        path.joinpath(key).write_text(str(value), encoding="utf-8")


class FakeConfig:
    def __init__(self, **values):
        self.values = values
        self.save_count = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def update(self, values):
        self.values.update(values)

    def save(self):
        self.save_count += 1


class FakeController:
    def __init__(self, active="balanced"):
        self.active = active
        self.changes = []

    def get_profiles(self):
        return ["power-saver", "balanced", "performance"]

    def get_active(self):
        return self.active

    def set_profile(self, profile):
        self.active = profile
        self.changes.append(profile)
        return True


class PowerSourceDetectionTest(unittest.TestCase):
    def test_online_adapter_wins_over_discharging_battery(self):
        with tempfile.TemporaryDirectory() as root:
            make_supply(root, "AC", "Mains", online=1)
            make_supply(root, "BAT0", "Battery", status="Discharging")
            self.assertEqual(power_service.detect_power_source(root), "ac")

    def test_offline_adapter_with_discharging_battery(self):
        with tempfile.TemporaryDirectory() as root:
            make_supply(root, "AC", "Mains", online=0)
            make_supply(root, "BAT0", "Battery", status="Discharging")
            self.assertEqual(power_service.detect_power_source(root), "battery")

    def test_missing_power_supply_directory(self):
        self.assertEqual(power_service.detect_power_source("/does/not/exist"), "unknown")


class PowerSourceProfileTest(unittest.TestCase):
    def make_service(self):
        service = power_service.PowerService.__new__(power_service.PowerService)
        service._ctrl = FakeController()
        service._config = FakeConfig(
            power_profile="balanced",
            power_source_profiles_enabled=False,
            ac_profile="balanced",
            battery_profile="power-saver",
        )
        service._automation_lock = threading.RLock()
        service._active_app = None
        service._power_source = "ac"
        return service

    def test_enabling_automation_applies_current_source_profile(self):
        service = self.make_service()
        with mock.patch.object(power_service, "detect_power_source", return_value="battery"):
            result = service.SetPowerSourceProfiles(True, "performance", "power-saver")

        self.assertEqual(result, "OK")
        self.assertEqual(service._ctrl.changes, ["power-saver"])
        self.assertEqual(service._config.save_count, 1)

    def test_app_profile_temporarily_has_priority(self):
        service = self.make_service()
        service._config.values["power_source_profiles_enabled"] = True
        service._config.values["ac_profile"] = "performance"
        service._active_app = "game.exe"

        self.assertFalse(service._apply_power_source_profile("ac"))
        self.assertEqual(service._ctrl.changes, [])

    def test_rejects_unknown_profile(self):
        service = self.make_service()
        result = service.SetPowerSourceProfiles(True, "turbo", "power-saver")
        self.assertEqual(result, "FAIL")
        self.assertEqual(service._config.save_count, 0)


if __name__ == "__main__":
    unittest.main()

