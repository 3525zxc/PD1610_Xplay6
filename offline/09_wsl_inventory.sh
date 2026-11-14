#!/bin/bash
# Read-only inventory of the PD1610 WSL build environment.
SRC=/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000
OUT=/home/builder/ksrc/kout-los16-blm-shrink-20261114133000
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9

echo "=== A. patched files present in active source tree ==="
for f in drivers/input/touchscreen/fts.c include/linux/input/fts.h \
         drivers/input/touchscreen/cyttsp_button.c \
         drivers/power/reset/msm-poweroff.c \
         drivers/platform/msm/qpnp-vibrator.c kernel/bootloop_monitor.c; do
  if [ -f "$SRC/$f" ]; then
    echo "  EXIST $(stat -c %s "$SRC/$f") $f"
  else
    echo "  MISSING $f"
  fi
done

echo "=== B. active source tree / out / toolchain size ==="
du -sh "$SRC" "$OUT" "$TC" 2>/dev/null
test -d "$SRC/.git" && echo "SRC_HAS_GIT=yes" || echo "SRC_HAS_GIT=no"

echo "=== C. defconfig candidates ==="
ls "$SRC/arch/arm64/configs/" 2>/dev/null | grep -iE 'msm8996|pd1610|lineage|perf' | head -12
echo "CONFIG_KEYS=$(grep -c '^CONFIG_' "$OUT/.config" 2>/dev/null)"

echo "=== D. build-critical packages (dpkg) ==="
dpkg-query -W -f='${Package} ${Version}\n' 2>/dev/null | grep -iE '^(build-essential|make|bc|bison|flex|libssl-dev|libncurses5-dev|libncurses-dev|device-tree-compiler|u-boot-tools|lzop|liblz4-tool|git|python2|python3|ccache|cpio|rsync|unzip|zip|curl|wget|ca-certificates) ' | sort | head -30

echo "=== E. kernel build script head ==="
sed -n '1,25p' /mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/tools/blm_trace_build.sh

echo "=== F. WSL config files on Windows side (if any) ==="
ls -l /mnt/d/WSL/PD1610/ 2>/dev/null | head -10
cat /etc/wsl.conf 2>/dev/null || echo "(no /etc/wsl.conf)"

echo "=== G. reclaimable summary ==="
printf 'los16/out        : '; du -sh /home/builder/los16/out 2>/dev/null | cut -f1
printf 'los16/.repo      : '; du -sh /home/builder/los16/.repo 2>/dev/null | cut -f1
printf 'historical kout-* : '; du -sch /home/builder/ksrc/kout-* 2>/dev/null | tail -1 | cut -f1
printf 'old src trees     : '; du -sch /home/builder/ksrc/msm8996-* 2>/dev/null | tail -1 | cut -f1
printf 'ksrc tarballs     : '; du -sch /home/builder/ksrc/*.tar.gz 2>/dev/null | tail -1 | cut -f1
printf 'TOTAL builder     : '; du -sh /home/builder 2>/dev/null | cut -f1
