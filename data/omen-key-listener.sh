#!/bin/bash
# HP Omen Key Listener
# Watches for KEY_PROG2 (Omen Key) events and toggles HP Manager GUI
#
# Dependencies: evtest (or libinput debug-events)

set -euo pipefail

# Find the HP WMI hotkeys input device
find_device() {
    for dir in /sys/class/input/event*/device; do
        if [ -f "$dir/name" ] && grep -q "HP WMI hotkeys" "$dir/name" 2>/dev/null; then
            echo "/dev/input/$(basename "$(dirname "$dir")")"
            return 0
        fi
    done
    return 1
}

DEV=$(find_device) || {
    echo "HP WMI hotkeys input device not found. Exiting."
    exit 1
}

echo "Listening for Omen Key on $DEV ..."

# Use evtest to grab & watch for KEY_PROG2 press events (value 1)
evtest "$DEV" 2>/dev/null | while IFS= read -r line; do
    if echo "$line" | grep -q "KEY_PROG2.*value 1"; then
        echo "Omen Key pressed — toggling HP Manager"

        # HP Manager handles its own single-instance activation via GtkApplication.
        hp-manager &
    fi
done
