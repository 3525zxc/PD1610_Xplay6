#!/usr/bin/env bash
# Incremental rebuild of the SHRUNK 3.18.120 BLM kernel with:
#   - CON_ENABLED|CON_ANYTIME console fix (printk.c:2536 gate)
#   - per-initcall "IC <ptr>" trace + milestone text markers
# The config and source tree are reused from shrink-20261114133000, so this
# changes ONLY instrumentation code (no new config / no new layout).
set -euo pipefail

TAG=${1:-trace-$(date +%Y%m%d%H%M%S)}
ROOT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor
PATCHED=${2:-$ROOT/tests/patched_tree}
SRC=/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000
OUT=/home/builder/ksrc/kout-los16-blm-shrink-20261114133000
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-
NM=${TC}nm
WOUT=$ROOT/build/$TAG

mkdir -p "$WOUT" "$ROOT/images"
echo "$TAG" > "$ROOT/build/current_trace.txt"
exec > "$WOUT/build.log" 2>&1

echo BUILD_START tag=$TAG
echo SRC=$SRC
echo OUT=$OUT
echo WOUT=$WOUT

test -d "$SRC" || { echo SRC_TREE_MISSING; exit 2; }
test -f "$OUT/.config" || { echo CONFIG_MISSING; exit 2; }

test -d "$PATCHED" || { echo PATCHED_TREE_MISSING "$PATCHED"; exit 2; }
echo PATCHED_TREE=$PATCHED
cp "$PATCHED/init/main.c" "$SRC/init/main.c"
cp "$PATCHED/kernel/bootloop_monitor.c" "$SRC/kernel/bootloop_monitor.c"
cp "$PATCHED/include/linux/bootloop_monitor.h" "$SRC/include/linux/bootloop_monitor.h"
cp "$PATCHED/drivers/platform/msm/usb_bam.c" "$SRC/drivers/platform/msm/usb_bam.c"
cp "$PATCHED/drivers/platform/msm/qpnp-vibrator.c" "$SRC/drivers/platform/msm/qpnp-vibrator.c"
echo PATCH_FILES_COPIED

printf 'INSTRUMENTATION_CHECK main.c blm_note_initcall=%s console_CON_ENABLED=%s usb_bam_traces=%s vibrator_traces=%s\n' \
  "$(grep -c 'blm_note_initcall((unsigned long)fn)' "$SRC/init/main.c")" \
  "$(grep -c 'CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER' "$SRC/kernel/bootloop_monitor.c")" \
  "$(grep -c 'blm_trace_note(' "$SRC/drivers/platform/msm/usb_bam.c")" \
  "$(grep -c 'blm_trace_note(' "$SRC/drivers/platform/msm/qpnp-vibrator.c")"

C6FILES=$(find "$SRC/fs" -maxdepth 1 -name 'c6_0*.c' 2>/dev/null | wc -l)
C6MK=$(grep -c c6_0 "$SRC/fs/Makefile" 2>/dev/null || true)
C6HOOK=$(grep -c c6_su_detect "$SRC/security/selinux/ss/services.c" 2>/dev/null || true)
C6MK=${C6MK:-0}; C6HOOK=${C6HOOK:-0}
echo SRC_PURITY c6_files=$C6FILES makefile=$C6MK hook=$C6HOOK
if [ "$C6FILES" -ne 0 ] || [ "$C6MK" -ne 0 ] || [ "$C6HOOK" -ne 0 ]; then
  echo SRC_CONTAMINATED; exit 1
fi

cd "$SRC"
export ARCH=arm64 SUBARCH=arm64 CROSS_COMPILE=$TC LC_ALL=C
set +e
make O="$OUT" -j14 Image.gz-dtb
MRC=$?
set -e
echo MAKE_IMAGE_RC=$MRC
if [ $MRC -ne 0 ]; then echo KERNEL_BUILD_FAIL make_rc=$MRC; exit 1; fi

IMG=$OUT/arch/arm64/boot/Image.gz-dtb
cp "$IMG" "$WOUT/Image.gz-dtb"
cp "$OUT/vmlinux" "$WOUT/vmlinux"
cp "$OUT/System.map" "$WOUT/System.map"
cp "$OUT/.config" "$WOUT/config_los16_blm_trace.txt"
"$TC"size "$WOUT/vmlinux" > "$WOUT/vmlinux_size.txt" || true
cat "$WOUT/vmlinux_size.txt"

NM_SYMS=$($NM "$OUT/vmlinux" 2>/dev/null | grep -E ' (blm_early_init|blm_reserve_logmem|blm_mark|blm_write_bytes|blm_write_text|blm_note_initcall|blm_trace_note|blm_arm_watchdog|blm_disarm_watchdog)$' | wc -l || true)
echo VMLINUX_BLM_SYMBOLS=$NM_SYMS
if [ "$NM_SYMS" -lt 9 ]; then echo BLM_SYMBOLS_MISSING; exit 1; fi
C6SYMS=$($NM "$OUT/vmlinux" 2>/dev/null | grep -cE 'c6_01_isroot|c6_su_detect|vivo_obf_decode|c6_mount_state|c6_vivo_gate_should_check' || true)
C6SYMS=${C6SYMS:-0}
echo VMLINUX_C6_SYMBOLS=$C6SYMS
if [ "$C6SYMS" -ne 0 ]; then echo VMLINUX_C6_CONTAMINATED; exit 1; fi

IMAGE_SHA256=$(sha256sum "$WOUT/Image.gz-dtb" | cut -d' ' -f1)
IMAGE_SIZE=$(stat -c %s "$WOUT/Image.gz-dtb")
cat > "$WOUT/kernel_build.env" <<EOF
BUILD_TS=$TAG
BUILD_RC=0
OLDDEFCONFIG_RC=0
BLM_SRC=$SRC
OUT=$OUT
WOUT=$WOUT
IMAGE=$WOUT/Image.gz-dtb
SYSTEM_MAP=$WOUT/System.map
VMLINUX=$WOUT/vmlinux
CONFIG=$WOUT/config_los16_blm_trace.txt
IMAGE_SHA256=$IMAGE_SHA256
IMAGE_SIZE=$IMAGE_SIZE
BLM_SYMBOLS=$NM_SYMS
C6_FILES=$C6FILES
C6_MAKEFILE=$C6MK
C6_HOOK=$C6HOOK
C6_SYMBOLS=$C6SYMS
TOOLCHAIN=$TC
SOURCE_TREE_MODIFIED=false
EOF

echo KERNEL_BUILD_OK tag=$TAG image=$WOUT/Image.gz-dtb sha256=$IMAGE_SHA256 size=$IMAGE_SIZE blm_symbols=$NM_SYMS
exit 0
