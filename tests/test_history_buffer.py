import os
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "gui"))

from widgets.history_buffer import HistoryBuffer


class HistoryBufferTest(unittest.TestCase):
    def test_series_share_the_same_time_slots(self):
        history = HistoryBuffer(("cpu", "gpu"), capacity=3)
        history.push(cpu=50, gpu=60)
        history.push(cpu=51)

        self.assertEqual(history.values("cpu"), (50.0, 51.0))
        self.assertEqual(history.values("gpu"), (60.0, None))

    def test_capacity_discards_oldest_sample(self):
        history = HistoryBuffer(("fan",), capacity=3)
        for value in (1000, 1100, 1200, 1300):
            history.push(fan=value)

        self.assertEqual(history.values("fan"), (1100.0, 1200.0, 1300.0))
        self.assertEqual(history.latest("fan"), 1300.0)

    def test_invalid_measurement_becomes_gap(self):
        history = HistoryBuffer(("temperature",), capacity=3)
        history.push(temperature="unavailable")
        self.assertEqual(history.values("temperature"), (None,))


if __name__ == "__main__":
    unittest.main()

