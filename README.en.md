# PD1610 / Xplay6 self-compiled kernel + bootloop forensics

> Languages: [简体中文](README.md) (default) | **English**

vivo Xplay6 (MSM8996, LineageOS 16) self-compiled `3.18.120` kernel:
from bootloop to a bootable desktop with working touch, using a custom
RAM-log monitor (BLM) and Qualcomm 9008 Firehose `peek` to observe failures.
The same repository also ships the text results of the older **prebuilt**
route (stock kernel + vendor blobs + borrowed PD1619 device tree -> LOS16 ROM).

> **Two reading tracks, the same facts.** Pick either one; no data, hash or
> criterion is simplified or removed.
> - **Technical track**: the route tree below, changelog, glossary, round
>   lineage, per-file netdisk index, reports and raw evidence - all unchanged.
> - **Plain-language track**: jump to "**Plain-language track**" further down
>   this page, or read `docs/BEGINNER_GUIDE_EN.md` in full. It retells the same
>   files and the same workflow in everyday language, with copy-paste AI prompts.
> - Both tracks point at the same files and conclusions. `AGENTS.md` holds the
>   hard rules for the AI and is shared by both.

**Start here - pick your route first.** This repository holds **two different
lines of work**; decide which one you are continuing before opening any report:

```
Route A - continue the PREBUILT ROM (fix camera / WiFi / sepolicy / packaging)
  prebuilt/evidence/_log_append4.md ...... WiFi fix chain, 4 open TODOs, corrected misjudgements
  prebuilt/release/.../patches/ ......... final sys13 source changes (diff before editing)
  prebuilt/refs/PD1619_PORTING_NOTES.md . 1042-line porting note
  offline/14_prebuilt_upload_checklist.md  upload checklist and continuation notes
  netdisk 03_/sys13_system.img .......... known-good WiFi-fixed baseline
  netdisk 15_/*.zip ..................... flashable LOS16 ROM
  netdisk 02_/images/boot.img ........... rollback baseline

Route B - continue the SELF-COMPILED 3.18.120 kernel (finish Tier-3 gates)
  offline/12_ai_handoff_index.md ........ resource map; paste as-is to an AI
  offline/13_continuation_playbook.md ... single-variable loop, 8-step SOP
  offline/05_experiment_queue.md ........ experiment queue A-D (claims / criteria)
  offline/08_roundA_result.md ........... A-round evidence result
  ROUND10-19*.md + flash_log/ .......... per-round evidence and raw logs
  fixtures/ + tools/ .................... adapted drivers, BLM, preflight/coverage scripts
  netdisk 01_/ .......................... authoritative cold-storage volumes

Shared entry: netdisk 00_必读_恢复说明/ (RESTORE, SHA256SUMS, checklists, indexes).
Beginner on-ramp: docs/BEGINNER_GUIDE_EN.md (plain-language guide with copy-paste AI prompts).
`prebuilt/` and netdisk 02/03/15 use the stock prebuilt kernel; `ROUND*` and
`flash_log/` are the self-compiled line. Their images are not interchangeable.
```


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

## Glossary: A round / experiment queue / completion meter

**Experiment queue** = `offline/05_experiment_queue.md`, a claim-driven TODO
table. Four gates still fail, so each planned experiment fixes a claim, its
precondition, a numeric criterion, the gate it affects and a failure branch;
every round must end with a coverage-tool run.

```
Experiment queue
  A  reproduce the b6d5debb bootloop, read BLM fixed slots over 9008   (original claim, NOT executed)
  B  add IRQF_ONESHOT -> nav keys + cold-boot touch                     (split into single variables first)
  C  restore two tasha jack input devices
  D  verify the BBK private restart flag behind adb reboot bootloader
  long tail (not queued): goodixfp fingerprint - zero symbols, 5-15 days, no guarantee
  exit criteria: 3 clean cold boots / input 9/9 / I2C >=8/9 / 30s touch / full evidence / 17-17 + rollback
```

**A round result** = `offline/08_roundA_result.md`. There are **two "A rounds"**:
the queue's original A (bootloop reproduction, not done) and the A actually
executed on Nov 14 21:45-22:04, which fixed nothing - it flashed the known-good
`#9` baseline, captured full evidence and rolled back to stock, in order to
close the `UNVERIFIED` gap.

```
Executed A round
  flash 5f164490 (#9) -> 3.18.120-perf #9 reaches the desktop
  blm_round_capture.py -> 12 snapshots (199 KB dmesg, sha256 manifest)
  blm_coldboot_verify.py -> 3/3 cold boots PASS (36.8 / 58.1 / 58.2 s)
  touch: 35s cold window 0 events; after resume 1266 events, IRQ 87 -> 474
  nav keys: no vivo_virtual_key, 0 key events -> FAIL
  score 20/88 -> static 40/63 -> strict 50/50 (UNVERIFIED=0); 65/65 control only
  fixed a HAL gate false positive; added two capture tools
  rolled back to stock 929fda99... and verified
```

**Completion meter** = `tools/blm_tier3_coverage.py`: 8 weighted gates -
boot(20), touch_cold(15), nav_keys(8), input_parity(12), i2c_parity(15),
hal(10), firmware_inventory(5), reproducible(15). The denominator is the
device list enumerated on the stock system, and each item needs three proofs
(device node + driver binding + real events). `UNVERIFIED` means "evidence not
captured", not "work not done": the early 68-point interval was an evidence gap.

## Plain-language track: continuing if you only know how to flash

> This section runs **in parallel with the technical sections above**, which
> stay unchanged. It restates the same facts in everyday language. No coding or
> kernel knowledge is required: all 26 earlier rounds were run as "human
> handles the phone, AI handles code and evidence".

**Technical track ↔ plain-language track** (same files, two wordings)

| Technical (above) | Plain-language version |
|---|---|
| Start here: two-route tree | this section + `docs/BEGINNER_GUIDE_EN.md` §0.2 |
| Glossary: A round / queue / meter | "Three-step start" below + guide §5 jargon table |
| Round lineage ROUND1-9 / 10-26 | guide §0.3 current state + §10 reading order |
| Verified status 50/50, 4 FAILs | guide §0.3 / §9 FAQ |
| Baidu Netdisk index (file-by-file tree) | guide §2 "what to download" + §5 |
| `offline/13` 8-step SOP | guide §4 round script (AI says / you do / you reply) |
| `offline/05` experiment queue A-D | guide §8 zero-risk first round |
| `fixtures/` `tools/` source and scripts | guide §1 "the AI does the rest" |
| `AGENTS.md` hard rules for the AI | guide §3 opening prompt makes it read that file |


```
You (flashing is enough)            AI (Codex / WorkBuddy)
├─ restore repo + netdisk files     ├─ read logs, diff source, edit code
├─ enter fastboot when asked ──────> ├─ compile, build boot.img, preflight
├─ tap screen / press nav keys ────> ├─ flash, capture evidence, PASS/FAIL
├─ report "works / does not work"   └─ roll back to stock and verify
└─ decide continue / pause / rollback
```

**Three-step start (round one should be zero-risk)**

1. Download netdisk `00` `01` `02` `04`; have the AI run
   `sha256sum -c SHA256SUMS` and require **3/3 OK**.
2. Open the repo root with Codex or WorkBuddy (`AGENTS.md` is read
   automatically), then paste the opening prompt from
   `docs/BEGINNER_GUIDE_EN.md` section 3 verbatim.
3. Explicitly require **no compile, no flash, no partition writes** in round
   one: status check, baseline capture, one plain-language state report.
   Only then follow `offline/05_experiment_queue.md` into real rounds.

| What you need | Where |
|---|---|
| First message to the AI (copy-paste) | `docs/BEGINNER_GUIDE_EN.md` §3 |
| Round script: AI says / you do / you reply | §4 |
| Jargon translator (fastboot, dmesg, preflight, single variable) | §5 |
| When to stop, how to roll back, 8 things never to do | §6 |
| How to tell if the AI is fabricating results | §7 |
| Zero-risk first round | §8 |
| Hard rules the AI must follow | `AGENTS.md` (repo root) |
| Full methodology | `offline/13_continuation_playbook.md` |

> Chinese version: `docs/BEGINNER_GUIDE_CN.md`. Never mix the two routes'
> images: `03_/sys13_system.img` (WiFi-fixed) is not `02_/images/system.img`.

## Round lineage: ROUND1-9 vs ROUND10-26

Three independent ROUND numbering schemes appear in this project:

```
(1) Signature / unlock state machine, Nov 8-12 (C-drive + prebuilt/evidence)
      ROUND3_LOOP_LIFECYCLE.txt, ROUND4_FLAG_BEQ_DATAFLOW.txt,
      ROUND5_RETVAL_CLASSIFICATION_AND_STATE_PATH.txt,
      aboot_verification_analysis.md, boot_state_machine_analysis.md,
      original DTS, xplay6_unlock/ tooling

(2) Offline RE + multi-model review ROUND1-9, Nov 12-13 (kernel_re/out/)
      these numbers count review briefings sent to GPT/Claude, NOT flashes
      round3/  aboot decompress trace, ARM64 Image memory audit, address overlap,
               config diff attribution, DTB selector disassembly
      round4/  aboot handoff, early MMU evidence, FDT chain, BOOT_ONLY feasibility,
               Unicorn replay, memory_lifecycle_and_observability.md
      ROUND3_REVIEW_LANDING.md, ROUND4..9_FOLLOWUP_FOR_GPT.md, BRIEF_*_BATTLE.md,
      multimodel_capture/ (18 files), STAGE1..30*.md (yet another numbering),
      MASTER_FINDINGS.md, MASTER_HANDOFF_20261113.md, COMPILABLE_SOURCE_PROGRESS.md,
      h6/ROUND5_BOOT_ONLY_DELIVERY.md

(3) BLM on-device forensics ROUND10-26, Nov 14 (this tree)
      ROUND10-13  BLM / 9008 chain, all-zero FDT root cause, config shrink
      ROUND14-17  usb_bam claim overturned -> qpnp_vibrator_init -> first SPMI read
      ROUND18-19  FDT_NOP bypass -> SPMI stub + restored node -> sys.boot_completed=1
      ROUND20-26  touch driver rebuilt from source, nav keys, reboot path, rollback
      A round     not a ROUND: it is queue letter A (evidence narrowing)
```

The first report here is called ROUND10 because it continued the numbering of
(2); it is not "the tenth flash". ROUND1-9 material lives in `prebuilt_c/`,
netdisk `11_逆向证据_全量分卷/`, `14_寒霜刷机_C盘工作目录/` and `prebuilt/evidence/`.

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

### File-by-file tree (what each item is for)

The full 7260-row manifest is `00_必读_恢复说明/UPLOAD_CHECKLIST.csv`.
The trees below explain the files you will actually open.

```
PD1610_Xplay6/                         16 categories / 76 GiB
  00_必读_恢复说明/                    restore entry (17 files)
     RESTORE.md ..................... reassemble -> zstd -> tar extraction
     SHA256SUMS / manifest.json ..... 3-line checksum + 2121 file hashes
     上传清单.md / UPLOAD_CHECKLIST.csv ... summary and per-file manifest
     12_ai_handoff_index.md ......... AI resource map (section 9 = current state)
     13_continuation_playbook.md .... single-variable loop and SOP
     14_prebuilt_upload_checklist.md  prebuilt TODOs and must-keep files
     11_wsl_rebuild_guide.md ........ minimal WSL rebuild
     百度网盘索引_草稿.md / 增量补传清单 / 操作卡 ... indexes and upload steps
  01_全量冷备分卷/                    part01 900 MiB + part02 72.5 MiB (both required)
  02_原厂回滚与发布包/                images/boot.img rollback, recovery, system,
                                     patches/ (7 final source changes), tools/, flash_all.*
  03_prebuilt_续修基线/               sys13_system.img (WiFi fixed), prebuilt_kernel,
                                     vendor_blobs/_vendor.tar, modules/, compat_libs/
  04_9008与刷机工具/                  qfil/ (QFIL, QSaharaServer, fh_loader, firehose .elf),
                                     platform-tools/, firehose_scripts/
  05_固件blob/                        332-file inventory CSV, 76 pulled blobs zip,
                                     FAT16 /firmware image, extraction notes
  06_WSL重建集/                       src/kernel-src.tar, config/kout-shrink.tar,
                                     .config + System.map, toolchain tar, scripts/, env/
  07_GitHub发布树_冗余/               offline copy of the public text tree
  08_分区dump_可选/                    48 raw partition dumps (8.4 GiB)
  09_原厂OTA_可选/                     official OTA zips and signed firmware
  10_prebuilt工程_全量分卷/            22 x 1.9 GiB tar volumes of D:/16/PD1610_81
  11_逆向证据_全量分卷/                6 tar volumes of kernel_re (ROUND1-9 evidence)
  12_自编译工程原始全量/               raw bootloop_monitor tree
  13_其它资料与工具/                   misc D:/16 material, dist, local git repo
  14_寒霜刷机_C盘工作目录/              phase-1 workspace: signature/aboot studies,
                                     original DTS/DTB, pd1610_rom/ device tree,
                                     xplay6_unlock/ tooling, H1 test pack,
                                     20261112.zip log bundle, .workbuddy/memory/ (private)
  15_LOS16_ROM刷机包/                 flashable ROM zip + SHA256SUMS + flashing notes
```

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
