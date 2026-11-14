#!/usr/bin/env bash
# Read-only inspection of qpnp_vibrator_probe() in the BLM shrink source tree.
# Standalone script: wsl.exe argument quoting mangles shell variables and
# regexes when passed through bash -lc from the Windows side.
set -u
TREE=/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000

echo "=== CANDIDATE FILES ==="
find "$TREE/drivers" -iname "*qpnp*vib*" -o -iname "*vibrator*" 2>/dev/null | head -10

F=$(find "$TREE/drivers" -iname "*qpnp*vib*" 2>/dev/null | head -1)
if [ -z "$F" ]; then
    F=$(grep -rln 'qpnp_vibrator_probe' "$TREE/drivers" --include=*.c 2>/dev/null | head -1)
fi
echo "FILE=$F"
if [ -z "$F" ] || [ ! -f "$F" ]; then
    echo "SOURCE_NOT_FOUND"
    exit 1
fi

echo "=== KEY LINES ==="
grep -n -E 'qpnp_vibrator_probe|spmi_ext_register_readl|qpnp_vib_write_u8|pwm_request|timed_output_dev_register|hrtimer_init|of_property_read_u32_array|of_property_read_string|spmi_get_resource|devm_kzalloc|devm_kmalloc|return ret|return 0|return -' "$F" | head -80

echo "=== PROBE BODY ==="
N=$(grep -n 'static int qpnp_vibrator_probe' "$F" | head -1 | cut -d: -f1)
echo PROBE_LINE=$N
if [ -n "$N" ]; then
    sed -n "${N},$((N + 95))p" "$F"
fi

echo "=== 60-180 (read / config helpers) ==="
sed -n '60,180p' "$F"
