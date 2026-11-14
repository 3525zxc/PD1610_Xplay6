#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor
SRC=/home/builder/ksrc/msm8996-lineage-16.0-blm-20261114011739
BASE=/home/builder/ksrc/kout-los16-blm-20261114011739/.config
TMP=/home/builder/ksrc/kout-los16-shrink-configtest
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-

mkdir -p "$TMP"
python3 -m py_compile "$ROOT/tools/blm_shrink_config.py"
python3 "$ROOT/tools/blm_shrink_config.py" --in "$BASE" --out "$TMP/.config" \
  --report "$ROOT/build/shrink_config_diff.json"

cd "$SRC"
ARCH=arm64 SUBARCH=arm64 CROSS_COMPILE=$TC LC_ALL=C make O="$TMP" olddefconfig \
  > "$TMP/olddefconfig.log" 2>&1
echo OLDDEFCONFIG_RC=0

echo '=== EFFECTIVE VALUES AFTER olddefconfig ==='
grep -E '^(CONFIG_LOG_BUF_SHIFT|CONFIG_LOG_CPU_MAX_BUF_SHIFT|CONFIG_KALLSYMS_ALL|CONFIG_FTRACE|CONFIG_TRACING|CONFIG_DEBUG_INFO|CONFIG_DEBUG_KERNEL|CONFIG_PERF_EVENTS|CONFIG_PROFILING|CONFIG_KPROBES|CONFIG_JUMP_LABEL|CONFIG_TRACEPOINTS|CONFIG_RING_BUFFER|CONFIG_EVENT_TRACING)=' "$TMP/.config" | sort || true
echo '=== DISABLED COUNT ==='
grep -c 'is not set' "$TMP/.config" || true
echo '=== BLM CONFIG SANITY ==='
grep -E '^(CONFIG_BLM|CONFIG_BOOTLOOP|CONFIG_UFS|CONFIG_SCSI_UFSHCD|CONFIG_MSM_SERIAL|CONFIG_SERIAL_MSM)' "$TMP/.config" | head -20 || true
echo CONFIGTEST_OK
