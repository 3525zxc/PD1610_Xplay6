#!/usr/bin/env bash
# Incremental resume of the shrunk-kernel build after a config fix.
set -euo pipefail
TS=20261114133000
ROOT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor
BLM_SRC=/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-$TS
OUT=/home/builder/ksrc/kout-los16-blm-shrink-$TS
BASE=/home/builder/ksrc/kout-los16-blm-20261114011739/.config
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-
NM=${TC}nm
WOUT=$ROOT/build/shrink-$TS

exec >> "$WOUT/build.log" 2>&1
echo "=== RESUME $(date +%H:%M:%S) ==="

python3 "$ROOT/tools/blm_shrink_config.py" --in "$BASE" --out "$OUT/.config" \
  --report "$WOUT/config_diff.json"

cd "$BLM_SRC"
export ARCH=arm64 SUBARCH=arm64 CROSS_COMPILE=$TC LC_ALL=C
set +e
make O="$OUT" olddefconfig
ORC=$?
make O="$OUT" -j14 Image.gz-dtb
MRC=$?
set -e
echo RESUME_OLDDEFCONFIG_RC=$ORC
echo RESUME_MAKE_IMAGE_RC=$MRC
if [ $ORC -ne 0 ] || [ $MRC -ne 0 ]; then
  echo RESUME_KERNEL_BUILD_FAIL
  exit 1
fi

IMG=$OUT/arch/arm64/boot/Image.gz-dtb
cp "$IMG" "$WOUT/Image.gz-dtb"
cp "$OUT/vmlinux" "$WOUT/vmlinux"
cp "$OUT/System.map" "$WOUT/System.map"
cp "$OUT/.config" "$WOUT/config_los16_blm_shrink.txt"
"$TC"size "$WOUT/vmlinux" > "$WOUT/vmlinux_size.txt" || true
cat "$WOUT/vmlinux_size.txt"

NM_SYMS=$($NM "$OUT/vmlinux" 2>/dev/null | grep -E ' (blm_early_init|blm_reserve_logmem|blm_mark|blm_write_bytes|blm_write_text|blm_arm_watchdog|blm_disarm_watchdog)$' | wc -l || true)
echo VMLINUX_BLM_SYMBOLS=$NM_SYMS
if [ "$NM_SYMS" -lt 7 ]; then echo BLM_SYMBOLS_MISSING; exit 1; fi
C6SYMS=$($NM "$OUT/vmlinux" 2>/dev/null | grep -cE 'c6_01_isroot|c6_su_detect|vivo_obf_decode|c6_mount_state|c6_vivo_gate_should_check' || true)
C6SYMS=${C6SYMS:-0}
echo VMLINUX_C6_SYMBOLS=$C6SYMS
if [ "$C6SYMS" -ne 0 ]; then echo VMLINUX_C6_CONTAMINATED; exit 1; fi

IMAGE_SHA256=$(sha256sum "$WOUT/Image.gz-dtb" | cut -d' ' -f1)
IMAGE_SIZE=$(stat -c %s "$WOUT/Image.gz-dtb")
cat > "$WOUT/kernel_build.env" <<EOF
BUILD_TS=$TS
BUILD_RC=$MRC
OLDDEFCONFIG_RC=$ORC
BLM_SRC=$BLM_SRC
OUT=$OUT
WOUT=$WOUT
IMAGE=$WOUT/Image.gz-dtb
SYSTEM_MAP=$WOUT/System.map
VMLINUX=$WOUT/vmlinux
CONFIG=$WOUT/config_los16_blm_shrink.txt
IMAGE_SHA256=$IMAGE_SHA256
IMAGE_SIZE=$IMAGE_SIZE
BLM_SYMBOLS=$NM_SYMS
C6_SYMBOLS=$C6SYMS
TOOLCHAIN=$TC
SOURCE_TREE_MODIFIED=false
EOF

echo KERNEL_BUILD_OK ts=$TS image=$WOUT/Image.gz-dtb sha256=$IMAGE_SHA256 size=$IMAGE_SIZE blm_symbols=$NM_SYMS
exit 0
