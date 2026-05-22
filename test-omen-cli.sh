#!/usr/bin/env bash
# Test script for OMEN Command Center CLI
# Usage: ./test-omen-cli.sh

set -euo pipefail

PASS=0
FAIL=0

run_test() {
    local label=$1
    shift
    if "$@" > /dev/null 2>&1; then
        printf "  [PASS] %s\n" "$label"
        ((PASS++)) || true
    else
        printf "  [FAIL] %s\n" "$label"
        ((FAIL++)) || true
    fi
}

echo "=== OMEN CLI Service Tests ==="
echo ""

# --- Fan tests ---
echo "Fan tests:"
run_test "fan max"  omen fan max
run_test "fan auto" omen fan auto

# --- Power mode tests ---
echo ""
echo "Power mode tests:"
run_test "mode performance" omen mode performance
run_test "mode balanced"    omen mode balanced
run_test "mode quiet"       omen mode quiet
run_test "mode eco"         omen mode eco

# --- MUX tests ---
echo ""
echo "MUX tests:"
run_test "mux hybrid"   omen mux hybrid
run_test "mux discrete" omen mux discrete

# --- Service health ---
echo ""
echo "D-Bus service health:"
run_test "dbus fan service"    /usr/bin/python3 -c "from pydbus import SystemBus; SystemBus().get('com.yyl.hpmanager.fan')"
run_test "dbus power service"  /usr/bin/python3 -c "from pydbus import SystemBus; SystemBus().get('com.yyl.hpmanager.power')"
run_test "dbus rgb service"    /usr/bin/python3 -c "from pydbus import SystemBus; SystemBus().get('com.yyl.hpmanager.rgb')"
run_test "dbus mux service"    /usr/bin/python3 -c "from pydbus import SystemBus; SystemBus().get('com.yyl.hpmanager.mux')"
run_test "dbus platform svc"   /usr/bin/python3 -c "from pydbus import SystemBus; SystemBus().get('com.yyl.hpmanager.platform')"

# --- Summary ---
echo ""
echo "=== Results ==="
printf "  Passed: %d\n" "$PASS"
printf "  Failed: %d\n" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
    echo "  All tests passed."
    exit 0
else
    echo "  Some tests failed — check individual service logs with:"
    echo "    journalctl -u hpm-fan.service -u hpm-power.service --since '5 minutes ago'"
    exit 1
fi
