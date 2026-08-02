#!/usr/bin/env bash

set -euo pipefail

OUT_DIR=$(mktemp -d /tmp/hp-wmi-raw-XXXXXXX)

{
    echo "timestamp=$(date -Is)"
    echo "kernel=$(uname -r)"
    echo "board_name=$(cat /sys/devices/virtual/dmi/id/board_name 2>/dev/null || echo unknown)"
    echo "product_name=$(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null || echo unknown)"
} > "$OUT_DIR/system.txt"

lsmod | grep -E '^(hp_wmi|hp_wmi_sensors|hp_bioscfg|wmi|hp_rgb_lighting)' > "$OUT_DIR/lsmod.txt" || true

if dmesg -T >/dev/null 2>&1; then
    dmesg -T 2>/dev/null | grep -E 'hp-wmi|hp_wmi|hp_bioscfg|AE_AML_OPERAND_VALUE|WQBD|WQBC' > "$OUT_DIR/dmesg_hp_wmi.txt" || true
else
    dmesg 2>/dev/null | grep -E 'hp-wmi|hp_wmi|hp_bioscfg|AE_AML_OPERAND_VALUE|WQBD|WQBC' > "$OUT_DIR/dmesg_hp_wmi.txt" || true
    if [ ! -s "$OUT_DIR/dmesg_hp_wmi.txt" ]; then
        echo "dmesg output unavailable (insufficient permissions)." > "$OUT_DIR/dmesg_hp_wmi.txt"
    fi
fi

{
    echo "=== /sys/bus/wmi/devices ==="
    ls -la /sys/bus/wmi/devices 2>/dev/null || true
    echo
    echo "=== HP GUID filtered entries ==="
    ls -1 /sys/bus/wmi/devices 2>/dev/null | grep -Ei '95f24279|5fb7f034' || true
} > "$OUT_DIR/wmi_devices.txt"

for guid in /sys/bus/wmi/devices/*; do
    [ -d "$guid" ] || continue
    base="$(basename "$guid")"
    if ! echo "$base" | grep -Eiq '95f24279|5fb7f034'; then
        continue
    fi

    guid_dir="$OUT_DIR/wmi_${base}"
    mkdir -p "$guid_dir"

    {
        echo "device=$base"
        cat "$guid/guid" 2>/dev/null || true
        readlink -f "$guid/driver" 2>/dev/null || true
    } > "$guid_dir/info.txt"

    for f in modalias instance_count notify_id object_id setable; do
        if [ -f "$guid/$f" ]; then
            cat "$guid/$f" > "$guid_dir/$f.txt" 2>/dev/null || true
        fi
    done
done

echo "HP WMI raw diagnostic output written to: $OUT_DIR"
echo "Please share the files in this directory with the maintainer."
