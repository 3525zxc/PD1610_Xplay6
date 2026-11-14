# Prebuilt-route workspace: extracted results

Source: `D:\16\PD1610_81` (39.8 GiB)
Extracted text: **828 files / 13.6 MiB**
Generated: 2026-11-14T23:31:43

## What this project was

The **prebuilt route** (2026-11-10 → 11-12): vivo never released kernel
source for PD1610/PD1619, so this line of work rebuilt a LOS16 ROM using
the stock prebuilt kernel + vendor blobs + a borrowed LeEco s2 / PD1619
device tree. It is the predecessor of the BLM self-compiled-kernel work.
Key results are in `evidence/GPL_AND_PORTING_ROADMAP.md` and
`refs/PD1619_PORTING_NOTES.md`.

## Two publish trees

- `prebuilt_verbatim/` — full detail, no redaction (matches the user's
  decision to publish everything on GitHub).
- `prebuilt_sanitized/` — same files with device identifiers redacted.

Pick one as the repository root. Both contain a copy of this README.

## Binary assets (private cold storage only)

The binaries are **not copied here**. Upload them to the private netdisk
from the original paths listed in `manifest.json` -> `binary_assets`.
Priority 1: the `boot.img` rollback baseline, `refs/device_PD1619.tar.gz`,
`blobs/_vendor.tar`, `blobs/modules/`, and the `backup/` partition dumps.

## Why the small text layer is the valuable part

40 GiB of the source is ROM zips, system.img, 48 partition dumps and
duplicate upload snapshots. Those are reproducible or re-dumpable from
the device. The text layer is the irreplaceable part: reverse
engineering conclusions, the 1042-line porting note, blob dependency
inventories, and 87 custom tools.

## If the goal is to FIX the remaining bugs (read this first)

`release/PD1610_LOS16_20261112/patches/` contains the **final sys13 patched
sources** (the WiFi fix) and is NOT the same as the `device_tree/` baseline.
Both are extracted; diff them before editing anything. The 7 files that
produced the working WiFi are listed in `manifest.json` -> `wifi_fix_files`.

Known-good baseline for comparison: `out/system.img` = **sys13**,
sha256 `686de5de21ad6c8837530836ba9483bd63e69ce660d2de289c4c0a2eecb88e9a`,
`Wi-Fi is enabled` / `wpa_supplicant=running` / 9 APs visible. Keep this
image in private cold storage; without it a regression cannot be told apart
from a pre-existing broken state.

Open TODOs (full text in `evidence/_log_append4.md`):

1. Camera: `Number of camera devices: 0` despite 116 chromatix + 136
   mmcamera libs present. Check `mm-qcamera-daemon` logs / SELinux perms.
2. `xtwifi-inet-agent` missing `libcurl.so` (non-fatal XTRA download).
3. Remove diagnostic code before release: `init.cpp` PD1610 DIAG,
   `init.qcom.rc` kmsg markers, `PD_WD_SECONDS 100000`,
   `init.rc` `pd1610-crypto-fix`, `printk 7 7 7 7`. Rebuild BOTH boot and
   system afterwards and re-test first boot.
4. sepolicy still permissive; `configstore-hal-1-0` killed by seccomp
   `getdents64` every 5 s (log noise).
5. No flashable ROM zip / TWRP package produced yet.

Also do NOT repeat these corrected misdiagnoses (all in
`evidence/_log_append3.md` / `_log_append4.md`):

- "device hung / kernel panic" was wrong - `logcat -v time -b all` plus
  2 s dmesg sampling proved the device stayed alive; only USB/adbd dropped.
- `WifiScanningService: wifi driver unloaded` is the normal
  `CMD_DRIVER_UNLOADED` message when WiFi is off, not missing-driver evidence.
- The "AOSP9 wifi HAL vs 8.1 libwifi-hal ABI mismatch" theory was wrong:
  the real cause was the 8.1 `libwifi-hal.so` blob **overwriting** the
  freshly built AOSP9 one. Removing that copy rule fixed the SIGSEGV.

Build command (from `build/build_pd1610.sh`, bypasses lunch because
`lunch lineage_pd1610-userdebug` hangs on this tree):

    bash ~/build_pd1610.sh systemimage     # ~75 s
