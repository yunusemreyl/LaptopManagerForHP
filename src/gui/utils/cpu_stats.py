"""Dependency-free helpers for delta-based aggregate and per-core CPU usage."""


def parse_cpu_counters(lines):
    """Return ``{cpu_name: (total, idle)}`` counters from ``/proc/stat`` lines."""
    counters = {}
    for line in lines:
        fields = line.split()
        if not fields or not fields[0].startswith("cpu"):
            if counters:
                break
            continue
        if fields[0] != "cpu" and not fields[0][3:].isdigit():
            continue
        try:
            values = [int(value) for value in fields[1:]]
        except ValueError:
            continue
        if len(values) < 4:
            continue
        # guest and guest_nice are already included in user/nice by Linux,
        # therefore only the first eight counters belong in the total.
        total = sum(values[:8])
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        counters[fields[0]] = (total, idle)
    return counters


def read_cpu_counters(path="/proc/stat"):
    with open(path, encoding="utf-8") as handle:
        return parse_cpu_counters(handle)


def usage_between(previous, current):
    """Calculate busy percentage between two ``(total, idle)`` counters."""
    if previous is None or current is None:
        return None
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))
