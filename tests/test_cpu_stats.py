import os
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "gui"))

from utils.cpu_stats import parse_cpu_counters, usage_between


class CPUStatsTest(unittest.TestCase):
    def test_parses_aggregate_and_logical_core_counters(self):
        counters = parse_cpu_counters([
            "cpu  100 0 50 800 20 0 0 0 0 0\n",
            "cpu0 40 0 20 400 10 0 0 0 0 0\n",
            "cpu1 60 0 30 400 10 0 0 0 0 0\n",
            "intr 12\n",
        ])
        self.assertEqual(counters["cpu"], (970, 820))
        self.assertEqual(counters["cpu0"], (470, 410))
        self.assertEqual(counters["cpu1"], (500, 410))

    def test_usage_uses_counter_delta_not_boot_average(self):
        self.assertEqual(usage_between((100, 80), (200, 130)), 50.0)

    def test_guest_time_is_not_counted_twice(self):
        counters = parse_cpu_counters([
            "cpu  100 20 30 400 10 5 3 2 40 10\n",
        ])
        self.assertEqual(counters["cpu"], (570, 410))

    def test_missing_or_invalid_delta_is_unavailable(self):
        self.assertIsNone(usage_between(None, (200, 130)))
        self.assertIsNone(usage_between((200, 130), (200, 130)))


if __name__ == "__main__":
    unittest.main()
