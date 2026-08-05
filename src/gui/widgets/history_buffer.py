"""Small in-memory, synchronized history buffer for dashboard telemetry."""

from collections import deque


class HistoryBuffer:
    """Keep equally-timed samples for multiple telemetry series in RAM."""

    def __init__(self, series, capacity=120):
        if capacity < 2:
            raise ValueError("capacity must be at least 2")
        self.series = tuple(series)
        self.capacity = int(capacity)
        self._values = {
            name: deque(maxlen=self.capacity) for name in self.series
        }

    def push(self, **sample):
        """Append one time slot to every series, using None for missing data."""
        for name in self.series:
            value = sample.get(name)
            try:
                value = float(value) if value is not None else None
            except (TypeError, ValueError):
                value = None
            self._values[name].append(value)

    def values(self, name):
        return tuple(self._values[name])

    def latest(self, name):
        values = self._values[name]
        return values[-1] if values else None

    def __len__(self):
        return max((len(values) for values in self._values.values()), default=0)

