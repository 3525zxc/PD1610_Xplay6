#!/usr/bin/env bash
set -u
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-objdump
VML=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/build/ftsirq-20261114192500/vmlinux
OUT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/offline/01_do_msm_restart_custom.asm
"$TC" -d --start-address=0xffffffc0009d44dc --stop-address=0xffffffc0009d47c0 "$VML" > "$OUT" 2>&1
echo "OBJDUMP_RC=$?"
wc -l "$OUT"
grep -cE '\bbl\b' "$OUT"
