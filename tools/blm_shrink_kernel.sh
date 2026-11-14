#!/usr/bin/env bash
# Build a SHRUNK 3.18.120 BLM kernel so that _end < 0x42000000
# (the physical address where aboot places the selected DTB).
#
# Only debug/trace/symbol-table/log-buffer options are changed. Storage,
# display, power, UFS and the BLM instrumentation stay untouched.
set -euo pipefail

ROOT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor
TS=${1:-$(date +%Y%m%d%H%M%S)}
SRC=/home/builder/ksrc/msm8996-lineage-16.0
BLM_SRC=/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-$TS
OUT=/home/builder/ksrc/kout-los16-blm-shrink-$TS
BASE_OUT=/home/builder/ksrc/kout-los16-blm-20261114011739
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-
NM=${TC}nm
WOUT=$ROOT/build/shrink-$TS

mkdir -p "$WOUT" "$ROOT/images"
echo "$TS" > "$ROOT/build/current_shrink.txt"
exec > "$WOUT/build.log" 2>&1

echo BUILD_START ts=$TS
echo SRC=$SRC
echo BLM_SRC=$BLM_SRC
echo OUT=$OUT
echo BASE_CONFIG=$BASE_OUT/.config

echo COPY_SOURCE_TREE_START
cp -a "$SRC" "$BLM_SRC"
cp -a "$ROOT/tests/patched_tree/." "$BLM_SRC/"
echo COPY_SOURCE_TREE_OK

C6FILES=$(find "$BLM_SRC/fs" -maxdepth 1 -name 'c6_0*.c' 2>/dev/null | wc -l)
C6MK=$(grep -c c6_0 "$BLM_SRC/fs/Makefile" 2>/dev/null || true)
C6HOOK=$(grep -c c6_su_detect "$BLM_SRC/security/selinux/ss/services.c" 2>/dev/null || true)
C6MK=${C6MK:-0}; C6HOOK=${C6HOOK:-0}
echo SRC_PURITY c6_files=$C6FILES makefile=$C6MK hook=$C6HOOK
if [ "$C6FILES" -ne 0 ] || [ "$C6MK" -ne 0 ] || [ "$C6HOOK" -ne 0 ]; then
  echo SRC_CONTAMINATED; exit 1
fi

mkdir -p "$OUT"
cp "$BASE_OUT/.config" "$OUT/.config.base"
python3 "$ROOT/tools/blm_shrink_config.py" \
  --in "$OUT/.config.base" --out "$OUT/.config" --report "$WOUT/config_diff.json"

cd "$BLM_SRC"
export ARCH=arm64 SUBARCH=arm64 CROSS_COMPILE=$TC LC_ALL=C
set +e
make O="$OUT" olddefconfig
ORC=$?
make O="$OUT" -j14 Image.gz-dtb
MRC=$?
set -e
echo MAKE_OLDDEFCONFIG_RC=$ORC
echo MAKE_IMAGE_RC=$MRC
if [ $ORC -ne 0 ] || [ $MRC -ne 0 ]; then
  echo KERNEL_BUILD_FAIL olddefconfig_rc=$ORC image_rc=$MRC
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
SRC=$SRC
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
C6_FILES=$C6FILES
C6_MAKEFILE=$C6MK
C6_HOOK=$C6HOOK
C6_SYMBOLS=$C6SYMS
TOOLCHAIN=$TC
SOURCE_TREE_MODIFIED=false
EOF

echo KERNEL_BUILD_OK ts=$TS image=$WOUT/Image.gz-dtb sha256=$IMAGE_SHA256 size=$IMAGE_SIZE blm_symbols=$NM_SYMS
exit 0
