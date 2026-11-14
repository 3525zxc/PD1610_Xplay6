#!/bin/bash
# Export the MINIMAL reproducible build set from WSL PD1610.
# Read-only with respect to the source tree: only copies files to /mnt/d.
# This is NOT a full VHDX backup (176 GiB); it is the ~1.7 GiB needed to
# rebuild the 3.18.120 BLM kernel from scratch.
set -euo pipefail

DEST=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/wsl_rebuild
mkdir -p "$DEST"/{src,toolchain,config,scripts,env}

KSRC=/home/builder/ksrc
SRC=$KSRC/msm8996-lineage-16.0-blm-shrink-20261114133000
OUT=$KSRC/kout-los16-blm-shrink-20261114133000
TC=/home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9
ROOT=/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor

echo "EXPORT_START $(date -Is)"

echo "--- 1/6 patched kernel source tree (790M, no .git) ---"
tar -C "$KSRC" -cf "$DEST/src/kernel-src.tar" "$(basename "$SRC")"
echo "    src tar bytes: $(stat -c %s "$DEST/src/kernel-src.tar")"

echo "--- 2/6 active build output incl. .config / System.map (755M) ---"
tar -C "$KSRC" -cf "$DEST/config/kout-shrink.tar" "$(basename "$OUT")"
cp "$OUT/.config" "$DEST/config/.config"
cp "$OUT/System.map" "$DEST/config/System.map"
echo "    kout tar bytes: $(stat -c %s "$DEST/config/kout-shrink.tar")"

echo "--- 3/6 cross toolchain (101M) ---"
tar -C "$(dirname "$TC")" -cf "$DEST/toolchain/aarch64-linux-android-4.9.tar" "$(basename "$TC")"

echo "--- 4/6 build scripts, fixtures, patch set ---"
cp "$ROOT/tools/blm_trace_build.sh" "$DEST/scripts/"
cp "$ROOT/tools/blm_build_bootimg.py" "$DEST/scripts/"
cp "$ROOT/tools/blm_preflight.py" "$DEST/scripts/"
cp "$ROOT/tools/blm_apply_kernel_patch.py" "$DEST/scripts/"
cp -r "$ROOT/fixtures" "$DEST/scripts/fixtures"
cp -r "$ROOT/kernel" "$DEST/scripts/blm_kernel_module"
cp "$ROOT/offline/09_wsl_inventory.sh" "$DEST/scripts/"

echo "--- 5/6 environment manifest ---"
{
  echo "# PD1610 WSL build environment snapshot"
  echo "captured: $(date -Is)"
  echo "distro: $(. /etc/os-release; echo "$PRETTY_NAME")"
  echo "kernel: $(uname -r)"
  echo "wsl: WSL2"
  echo
  echo "## apt packages (build-critical)"
  dpkg-query -W -f='${Package}=${Version}\n' 2>/dev/null | sort
  echo
  echo "## /etc/wsl.conf"
  cat /etc/wsl.conf 2>/dev/null || echo "(none)"
  echo
  echo "## build command"
  grep -nE '^(export ARCH|make O=)' "$ROOT/tools/blm_trace_build.sh" | head -5
  echo
  echo "## paths"
  echo "SRC=$SRC"
  echo "OUT=$OUT"
  echo "TC=$TC/bin/aarch64-linux-androidkernel-"
  echo "ROOT=$ROOT"
} > "$DEST/env/environment.txt"

echo "--- 6/6 sha256 manifest ---"
cd "$DEST"
find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
echo "EXPORT_DONE files=$(find . -type f | wc -l) total=$(du -sh . | cut -f1)"
