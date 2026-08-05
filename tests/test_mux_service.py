import glob
import os
import sys
import unittest
from unittest import mock


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "daemon"))

from services import mux_service


class NativeWmiMuxControllerTest(unittest.TestCase):
    def test_native_backend_is_available_when_wmi_path_exists(self):
        controller = mux_service.NativeWmiMuxController()
        with mock.patch.object(mux_service, "sysfs_exists", return_value=True):
            self.assertTrue(controller.is_available())
            self.assertEqual(controller.get_backend(), "wmi-native")

    def test_get_mode_detects_hybrid_from_pci_devices(self):
        controller = mux_service.NativeWmiMuxController()
        lspci_output = (
            "0000:01:00.0 VGA compatible controller: NVIDIA Corporation Device\n"
            "0000:05:00.0 VGA compatible controller: AMD Radeon Graphics\n"
        )
        with mock.patch.object(mux_service, "sysfs_exists", return_value=True), \
             mock.patch.object(glob, "glob", return_value=[]), \
             mock.patch.object(
                 mux_service.subprocess,
                 "check_output",
                 return_value=lspci_output,
             ):
            self.assertEqual(controller.get_mode(), "hybrid")

    def test_set_mode_writes_native_discrete_value(self):
        controller = mux_service.NativeWmiMuxController()
        with mock.patch.object(mux_service, "sysfs_exists", return_value=True), \
             mock.patch.object(mux_service, "sysfs_write", return_value=True) as write:
            self.assertEqual(controller.set_mode("discrete"), "OK_REBOOT_REQUIRED")

        write.assert_called_once_with(mux_service.HP_WMI_GRAPHICS_MODE_PATH, "1")


if __name__ == "__main__":
    unittest.main()
