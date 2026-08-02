import os
import sys
import unittest
from unittest import mock


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "daemon"))

from services import mux_service


class MUXControllerTest(unittest.TestCase):
    def test_detect_backend_prefers_envycontrol(self):
        with mock.patch.object(mux_service.shutil, "which", side_effect=lambda cmd: f"/usr/bin/{cmd}"):
            ctrl = mux_service.MUXController()
            ctrl.detect_backend("auto")
        self.assertEqual(ctrl.get_backend(), "envycontrol")

    def test_get_mode_normalizes_envycontrol_query_output(self):
        ctrl = mux_service.MUXController.__new__(mux_service.MUXController)
        ctrl.backend = "envycontrol"
        ctrl.envycontrol = "/usr/bin/envycontrol"
        ctrl.supergfxctl = None
        ctrl.prime_select = None
        ctrl._cached_mode = "unknown"
        ctrl._last_check = 0.0
        with mock.patch.object(mux_service.subprocess, "check_output", return_value=b"Current mode: Hybrid\n"):
            self.assertEqual(ctrl.get_mode(), "hybrid")

    def test_normalize_mode_handles_nvidia_offload_as_hybrid(self):
        self.assertEqual(
            mux_service.MUXController._normalize_mode("nvidia-offload"),
            "hybrid",
        )
if __name__ == "__main__":
    unittest.main()
