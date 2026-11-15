# PD1610 / Xplay6 self-compiled kernel + bootloop forensics

> Languages: [简体中文](README.md) (default) | **English**

vivo Xplay6 (MSM8996, LineageOS 16) self-compiled `3.18.120` kernel:
from bootloop to a bootable desktop with working touch, using a custom
RAM-log monitor (BLM) and Qualcomm 9008 Firehose `peek` to observe failures.
The same repository also ships the text results of the older **prebuilt**
route (stock kernel + vendor blobs + borrowed PD1619 device tree -> LOS16 ROM).

**Start here:** [`offline/12_ai_handoff_index.md`](offline/12_ai_handoff_index.md)
is a standalone index written for a resuming AI: what is stored where, which
files to fetch from cold storage, how to rebuild the WSL toolchain, and which
experiment round to pick up. Workflow manual:
[`offline/13_continuation_playbook.md`](offline/13_continuation_playbook.md);
prebuilt upload/continuation checklist:
[`offline/14_prebuilt_upload_checklist.md`](offline/14_prebuilt_upload_checklist.md).

## Verified status (2026-11-14)

- Tier-3 completion meter: **50/50 strict**, `UNVERIFIED = 0`
  (report: `flash_log/tier3_coverage_roundA_final_strict.json`).
- Still FAIL: `touch_cold`, `nav_keys`, `input_parity` (5/9), `i2c_parity` (4/9).
- A round: `3/3` clean cold boots (36.8 / 58.1 / 58.2 s); after a
  suspend/resume cycle the touch panel produced 1266 `getevent` lines.
- Device rolled back to stock `3.18.71-perf-g8a8c60dd`, `sys.boot_completed=1`.
- A round result: `offline/08_roundA_result.md`. Queue: `offline/05_experiment_queue.md`.

## Honest limitations

- Touch works only after a suspend/resume cycle; the cold-boot 30 s window has
  no events. `nav_keys` has no `vivo_virtual_key` input device.
- `adb reboot bootloader` still reboots normally on the candidate kernel.
- The last navigation-key candidate `b6d5debb...` was reported as bootloop
  and rolled back; the cause was never isolated.
- Round 14/15 blamed `usb_bam`; **Round 16 fixed-slot evidence overturned
  that**. The real stall was `qpnp_vibrator_init` -> first SPMI read.
  Do not continue from the old conclusion.
- The prebuilt route **did ship a flashable ROM** `PD1610_LOS16_20261112_UNOFFICIAL.zip`
  (935,087,013 B, sha256 `97c3137e...`, in netdisk `15_LOS16_ROM刷机包/`).
  4 issues remain open (camera, libcurl, diagnostic-code cleanup before release,
  sepolicy/configstore); see `prebuilt/evidence/_log_append4.md`.
  Phase-1 signature/unlock/device-tree research is in `prebuilt_c/`.

## What this repository does not contain

Boot images, DTB binaries, firmware blobs, RAM dumps and the WSL build
environment are in a separate private cold-storage archive (about 973 MiB,
2 volumes, zstd tar). This repo is the text-only documentation layer;
see `offline/12_ai_handoff_index.md` section 2 for the restore procedure.

## Baidu Netdisk cold storage (2026-11-15)

Binary assets, original project trees and flashable images are not on GitHub.
They live in the private Baidu Netdisk folder **`PD1610_Xplay6/`** (~76 GiB,
~7160 files, 16 categories).

- Share link: <https://pan.baidu.com/s/5OL1VH3h9Pn_uOQllg29MSQ>
  (an extraction code may be required; ask the maintainer. Links can expire.)
- Layout and per-file manifest: `00_必读_恢复说明/上传清单.md` and `UPLOAD_CHECKLIST.csv`
- Restore entry points: `00_必读_恢复说明/RESTORE.md`, `12_ai_handoff_index.md`

| Groups | Contents |
|---|---|
| `00`–`06` (required, 6.7 GiB) | restore notes/checksums, `01` two cold-storage volumes (973 MiB, zstd tar, authoritative copy), stock release package, sys13 baseline, 9008 tools, firmware, minimal WSL rebuild set |
| `07`–`09` (optional) | redundant GitHub text tree, 48 partition dumps, official OTA packages |
| `10` / `11` | full `D:\16\PD1610_81` 40 GiB (22 volumes) and `kernel_re` 11 GiB (6 volumes), 1.9 GiB tar volumes |
| `12` / `13` | raw self-compiled project tree, misc resources and tools |
| `14` / `15` | full phase-1 C-drive workspace (4.9 MiB), flashable LOS16 ROM zip (935 MB) + checksum |

**Verify after download**: put `SHA256SUMS`, `manifest.json` and the two `01`
volumes in one directory, run `sha256sum -c SHA256SUMS` (3/3 OK required), then
follow `RESTORE.md`. `10_`/`11_` carry their own `SHA256SUMS` + `RESTORE.txt`.

> `10_prebuilt工程_全量分卷/` contains device key material (`imei.der`,
> `donuts_key`) from the stock OTA. Do not share that subfolder publicly.
> `03_.../sys13_system.img` is the known-good WiFi-fixed baseline and is NOT
> the same image as `02_.../images/system.img`.

## Licensing

Self-written tools: MIT. Documentation: CC-BY-4.0. Kernel patches follow
the upstream LineageOS msm8996 3.18 GPL-2.0 with copyright headers intact.

> This is a handoff snapshot (B0'), not a finished Tier-3 port.
