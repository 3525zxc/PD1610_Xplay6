#!/bin/bash
# Pull proprietary blobs from a running vivo Xplay6 (PD1610) over adb.
# Run on the Linux build host, from the LineageOS source root:
#   cd device/vivo/pd1610 && ./extract-files.sh
# Requirements: device booted into Android, USB debugging authorised,
#               adb in PATH, ANDROID_ROOT set (source build/envsetup.sh first).

set -euo pipefail

VENDOR_DIR="${ANDROID_ROOT:-.}/vendor/vivo/pd1610/proprietary"
LIST="$(dirname "$0")/proprietary-files.txt"
ADB="${ADB:-adb}"

if [ -z "${ANDROID_ROOT:-}" ]; then
    echo "ERROR: run 'source build/envsetup.sh' first so ANDROID_ROOT is set" >&2
    exit 1
fi
if ! "$ADB" get-state 2>/dev/null | grep -qx device; then
    echo "ERROR: no adb device (authorise USB debugging on the phone)" >&2
    exit 1
fi

mkdir -p "$VENDOR_DIR"
count=0
while IFS= read -r line; do
    rel="${line%%#*}"
    rel="$(echo "$rel" | xargs)"
    [ -z "$rel" ] && continue
    src="/system${rel}"
    dst="${VENDOR_DIR}${rel}"
    mkdir -p "$(dirname "$dst")"
    if "$ADB" pull "$src" "$dst" >/dev/null 2>&1; then
        count=$((count + 1))
    else
        echo "WARN: missing $src" >&2
    fi
done < "$LIST"

echo "Pulled $count blobs into $VENDOR_DIR"
echo "Now run ./setup-makefiles.sh to regenerate the vendor makefiles."
