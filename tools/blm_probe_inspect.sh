#!/usr/bin/env bash
# Read-only inspection of usb_bam_probe() in the BLM shrink source tree.
# Kept as a standalone script because wsl.exe argument quoting mangles
# shell variables / regexes passed through bash -lc from the Windows side.
set -u
F=/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000/drivers/platform/msm/usb_bam.c

echo "=== FILE ==="
ls -l "$F"
echo "=== KEY LINES ==="
grep -n -E 'usb_bam_probe|ipa_is_ready|ipa_rm_create_resource|usb_bam_init\(|write_lock_irqsave|write_unlock_irqrestore|of_get_next_child|complete\(|pm_runtime_enable|return ret|return 0' "$F" | head -80
echo "=== PROBE BODY ==="
N=$(grep -n 'static int usb_bam_probe' "$F" | head -1 | cut -d: -f1)
echo PROBE_LINE=$N
if [ -n "$N" ]; then
    sed -n "${N},$((N + 45))p" "$F"
fi
echo "=== 3085-3130 (usb_bam_init caller) ==="
sed -n '3085,3130p' "$F"
echo "=== 3195-3280 (probe tail / ipa_is_ready) ==="
sed -n '3195,3280p' "$F"
