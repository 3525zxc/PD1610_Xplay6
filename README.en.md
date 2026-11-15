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

## Project status & changelog

> Summary for the front page. Per-round evidence: `ROUND*.md`, `offline/`,
> `flash_log/`. Resource map: `offline/12_ai_handoff_index.md` section 9;
> working manual: `offline/13_continuation_playbook.md`.

**Three separate lines of work (do not merge them)**

| Line | When | Original tree | Output |
|---|---|---|---|
| Phase 1: signature / unlock | Nov 8-12 | `C:/Users/Tse/WorkBuddy/寒霜刷机` | aboot verification & boot state machine, boot hash datapath, cross-device comparison, stock DTS decompilation, temp-root / unlock tooling; text layer -> `prebuilt_c/` |
| Prebuilt route | Nov 10-12 | `D:/16/PD1610_81` | LOS16 built from stock prebuilt kernel + vendor blobs + borrowed PD1619 device tree; WiFi fixed; flashable ROM zip |
| Self-compiled kernel forensics | Nov 14-15 | this repo | `3.18.120-perf` + BLM / 9008 observation chain, bootloop root cause, touch driver rebuilt from source, completion meter 50/50 |

vivo never released 3.18 kernel sources for PD1610/PD1619, so the prebuilt route
does not compile a kernel; the self-compiled route uses the upstream LineageOS
msm8996 3.18 tree. Images from the two routes are not interchangeable.

**Timeline**

| Date | Stage | Result |
|---|---|---|
| Nov 8-12 | Phase 1 research | signature / unlock / device-tree forensics, 30+ reports, `20261112.zip` bundle |
| Nov 10-12 | Prebuilt route | LOS16 built, WiFi fixed after four causal fixes (sys13 `system.img` sha `686de5de...`), `PD1610_LOS16_20261112_UNOFFICIAL.zip` produced (935,087,013 B) |
| Nov 14 AM | Round 10-13 | BLM / 9008 `peek` chain; root cause = BSS clear range overwrote the DTB at `0x42000000`; shrinking debug config restored `d00dfeed` |
| Nov 14 PM | Round 14-19 | fixed-slot evidence overturned the `usb_bam` claim -> `qpnp_vibrator_init` first SPMI read -> `FDT_NOP` bypass -> SPMI stub + restored node, `#5` reached `sys.boot_completed=1` |
| Nov 14 evening | Round 20-26 | touch went from "no driver" to a working event chain (`CONFIG_TOUCHSCREEN_ST_FTS`, DT props, pinctrl, `IRQF_ONESHOT`, regulators); nav-key bind succeeded but probe incomplete; last candidate bootlooped and was rolled back |
| Nov 14 night | 6 offline studies + A round | 8-gate completion meter, 332-firmware inventory, stock/custom `do_msm_restart` disassembly diff; A round 3/3 cold boots, 1266 touch events after resume, all `UNVERIFIED` removed -> strict 50/50 |
| Nov 15 | Archive & handoff | bilingual README, 16-category / 76 GiB netdisk cold storage, minimal WSL rebuild set, phase-1 records and ROM package added, AI index section 9 |

**Attribution changes (the easiest way to go wrong)**

- Round 14/15 blamed `usb_bam`; **Round 16 fixed-slot evidence overturned it**.
  The real stall was `qpnp_vibrator_init` -> the first `spmi_ext_register_readl()`.
- Round 18 (`FDT_NOP` bypass) only reached userspace; Round 19's SPMI stub plus
  restoring the node produced a full desktop.
- Touch was not a probe deferral: the driver was **not compiled in at all**
  (no `fts_driver_init` in `System.map`).
- `adb reboot bootloader` is not a missing config switch: stock `do_msm_restart`
  is 1492 B vs 740 B in our build, with BBK-private calls such as
  `set_dload_mode_bbk` / `set_aee_system_restarting` / `deassert_ps_hold`.
  [H1] aboot reads a private flag; not verified on hardware.

**Completion-meter evolution**

`20/88` (6 UNVERIFIED) -> static `40/63` -> A round **strict `50/50`**, with a
`65/65` post-resume control that only proves touch can work (not `touch_cold`).
The official number is **50**. The 68-point interval was an evidence gap, not
68% of the code being unwritten. The `hal` gate needs
`--hal-ignore init.svc.vivo-fingerprint-sh` (that service is `disabled`+`oneshot`,
so `stopped` is normal).

**Nov 15, 2026 documentation & resource updates**

- README is now Chinese-first with an in-page English switch plus standalone
  `README.en.md`; added a Baidu Netdisk cold-storage index.
- Added `prebuilt_c/` (97 phase-1 texts); netdisk gained
  `14_寒霜刷机_C盘工作目录/` (84 files, private only) and
  `15_LOS16_ROM刷机包/` (ROM zip + `SHA256SUMS`).
- **Corrected a stale claim**: "no ROM zip / 5 open TODOs" -> "ROM shipped /
  4 open TODOs".
- `offline/12_ai_handoff_index.md` gained section 9; docs 13/14 synced; netdisk
  is now 16 categories / 76 GiB.
- Archive volumes `01` stay at the 01:34 build (repacking would change 973 MiB
  already uploading); their bundled index is older - use this repo / netdisk `00`.

**Current state & remaining work**

- Device: stock `3.18.71-perf-g8a8c60dd` / LOS16 / `sys.boot_completed=1` / not in fastboot.
- Four gates still FAIL: `touch_cold`, `nav_keys`, `input_parity` 5/9, `i2c_parity` 4/9.
- Longest tail: `goodixfp` fingerprint (zero related symbols in our build; needs
  disassembly-based reconstruction, 5-15 workdays, no guarantee).
- This is a **handoff snapshot (B0'), not a finished Tier-3 port**. Resume from
  round B in `offline/05_experiment_queue.md`, following the single-variable loop
  in `offline/13_continuation_playbook.md`.

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
