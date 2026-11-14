#!/usr/bin/env bash
# ===========================================================================
#  PD1610 / vivo Xplay6 -- LineageOS 16.0 UNOFFICIAL -- Linux/macOS flasher
#  Build 2026-11-12 (system = sys13, boot = boot_pddiag5)
#
#  Usage:  ./flash_all.sh [--wipe] [--recovery]
#    --wipe      erase userdata + cache (REQUIRED when coming from stock 8.1)
#    --recovery  also flash recovery.img (unvalidated Lineage recovery)
#
#  Requirements: unlocked bootloader (devinfo +0x10 = 0xFF), phone in fastboot,
#  USB connected. tools/fastboot_linux is bundled; if it cannot run on your
#  distro, install platform-tools and pass FB=/path/to/fastboot.
#
#  Only boot/system[/recovery] are written; aboot, xbl, modem, persist,
#  devinfo and misc are untouched.
#
#  On "AdbWriteEndpointSync failed" / "no link": unplug/replug the USB cable
#  while the phone stays in fastboot, then rerun.
#
#  STATUS -- DEVELOPMENT BUILD, NOT A FINAL RELEASE
#   Verified: first boot ~40 s, setup wizard, WiFi enabled + AP scan, audio,
#   camera provider HAL, fingerprint, bluetooth, sensors, keymaster/keystore,
#   gnss, OMX. Broken/unfinished: camera reports 0 devices;
#   xtwifi-inet-agent lacks libcurl.so; SELinux permissive; diagnostic code
#   (raw-block marker in boot init, kmsg markers, disabled watchdog,
#   temporary crypto-fix action) is still present and must be removed and
#   retested before a public release. Backup first, unlocked bootloader only.
# ===========================================================================
set -euo pipefail
cd "$(dirname "$0")"

FB="${FB:-./tools/fastboot_linux}"
[ -x "$FB" ] || FB="$(command -v fastboot || true)"
[ -n "$FB" ] || { echo "ERROR: no fastboot binary. Install platform-tools or set FB=/path/to/fastboot"; exit 1; }
chmod +x ./tools/fastboot_linux ./tools/adb_linux 2>/dev/null || true

WIPE=0
RECOVERY=0
for a in "$@"; do
  case "$a" in
    --wipe) WIPE=1 ;;
    --recovery) RECOVERY=1 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown option: $a"; exit 1 ;;
  esac
done

[ -f images/boot.img ] && [ -f images/system.img ] || {
  echo "ERROR: extract the whole zip first (images/*.img missing)"; exit 1; }

echo "============================================================"
echo " PD1610 / vivo Xplay6 - LineageOS 16.0 UNOFFICIAL"
echo " Build 2026-11-12 | sys13 system + verified boot"
echo "============================================================"

DEVS="$("$FB" devices 2>&1 | awk '$2=="fastboot"{print $1}')"
[ -n "$DEVS" ] || { echo "ERROR: no device in fastboot mode"; exit 1; }
echo " Device(s): $DEVS"

MD="$("$FB" getvar max-download-size 2>&1 || true)"
echo "$MD" | grep -qi FAILED && {
  echo "ERROR: fastboot cannot talk to the device (stuck USB endpoint).";
  echo "Unplug/replug the USB cable, keep phone in fastboot, retry."; exit 1; }
echo " $MD"

if [ "$WIPE" -eq 0 ]; then
  echo
  echo " IMPORTANT: stock Funtouch 8.1 -> this ROM REQUIRES erasing userdata."
  read -r -p " Erase userdata + cache now? [y/N] " ans
  case "$ans" in y|Y|yes|YES) WIPE=1 ;; esac
fi
[ "$WIPE" -eq 1 ] && echo " Mode: WIPE userdata/cache" || echo " Mode: KEEP userdata/cache"

echo
echo " [1/3] boot.img ..."
"$FB" flash boot images/boot.img
echo " [2/3] system.img (sparse, 4 chunks, ~60 s) ..."
"$FB" flash system images/system.img
if [ "$RECOVERY" -eq 1 ]; then
  echo " [opt] recovery.img ..."
  "$FB" flash recovery images/recovery.img
fi
if [ "$WIPE" -eq 1 ]; then
  echo " [3/3] erasing userdata + cache ..."
  "$FB" erase userdata
  "$FB" erase cache || true
else
  echo " [3/3] wipe skipped."
fi

echo " Rebooting ... first boot takes about 40 seconds."
"$FB" reboot
echo " DONE. Verify:  ./tools/adb_linux shell getprop sys.boot_completed  -> 1"
