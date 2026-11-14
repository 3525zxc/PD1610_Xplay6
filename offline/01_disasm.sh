#!/usr/bin/env bash
set -u
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-objdump
IMG=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/offline/stock_Image.bin
OUT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/offline/01_do_msm_restart.asm
"$TC" -D -b binary -m aarch64 --adjust-vma=0xffffffc000080000 \
  --start-address=0xffffffc0008a2d4c --stop-address=0xffffffc0008a3320 \
  "$IMG" > "$OUT" 2>&1
echo "OBJDUMP_RC=$?"
wc -l "$OUT"
head -24 "$OUT"
