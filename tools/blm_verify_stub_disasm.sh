#!/usr/bin/env bash
# Verify the Round 19 SPMI stub really removed bus calls from the vibrator path.
set -uo pipefail
ROOT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-
BASE=$ROOT/build/vib-20261114160500/vmlinux
FIX=$ROOT/build/vibfix-20261114171500/vmlinux
SMAP=$ROOT/build/vibfix-20261114171500/System.map

echo "=== SYMBOLS ==="
for f in qpnp_vibrator_probe qpnp_vibrator_config qpnp_vib_set qpnp_vib_read_u8 qpnp_vib_write_u8; do
    grep -E " [tT] ${f}$" "$SMAP" || echo "$f INLINE_OR_ABSENT"
done

echo "=== SPMI EXT CALL SITES (whole vmlinux) ==="
for v in "$BASE" "$FIX"; do
    n=$("${TC}objdump" -d "$v" 2>/dev/null | grep -cE 'bl[[:space:]]+[0-9a-f]+ <spmi_ext_register_readl>')
    w=$("${TC}objdump" -d "$v" 2>/dev/null | grep -cE 'bl[[:space:]]+[0-9a-f]+ <spmi_ext_register_writel>')
    echo "$(basename "$(dirname "$v")") read_callsites=$n write_callsites=$w"
done

echo "=== VIBRATOR PROBE / CONFIG / SET DISASM CALLEES (fix) ==="
for f in qpnp_vibrator_probe qpnp_vibrator_config qpnp_vib_set; do
    a=$(grep -E " [tT] ${f}$" "$SMAP" | head -1 | awk '{print $1}')
    echo "-- $f addr=$a"
    if [ -n "$a" ]; then
        end=$((0x$a + 0x700))
        "${TC}objdump" -d --start-address=0x"$a" --stop-address="$end" "$FIX" 2>/dev/null \
            | grep -oE 'bl[[:space:]]+[0-9a-f]+ <[^>]+>' \
            | sed -E 's/.*<(.*)>/\1/' | sort | uniq -c | sort -nr | head -20
    fi
done

echo "=== STUB TRACE TAGS IN VMLINUX ==="
for s in VIB_STUB_READ VIB_STUB_WRITE BLM_SPMI_STUB_ACTIVE; do
    printf '%s count=' "$s"
    grep -a -c "$s" "$FIX" 2>/dev/null || echo 0
done
echo DISASM_VERIFY_DONE
