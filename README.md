<a id="zh-cn" name="zh-cn"></a>
# PD1610 / Xplay6 自编译内核与 bootloop 取证

> 语言 / Language：**简体中文（默认）** · [English ↓](#english) · [英文独立文件](README.en.md)

vivo Xplay6（MSM8996 / LineageOS 16）自编译 `3.18.120` 内核的完整取证记录：
从 bootloop 一路定位到能进桌面、触摸可用。手段是自写的 RAM 日志监测模块
（BLM）+ 高通 9008 Firehose `peek` 读取物理内存，把黑盒启动失败变成可复现的证据链。
本仓库同时收录较早的 **prebuilt 路线** 文本成果（原厂内核 + vendor blobs +
借用 PD1619 设备树编译 LOS16 ROM），两条路线一并交接。

## 从这里开始

| 文档 | 回答什么 |
|---|---|
| [`offline/12_ai_handoff_index.md`](offline/12_ai_handoff_index.md) | **资源在哪**：三处存放分工、网盘分卷清单、WSL 最小重建集、给接手 AI 的开场白。整份贴给 AI 即可恢复上下文 |
| [`offline/13_continuation_playbook.md`](offline/13_continuation_playbook.md) | **活怎么干**：单变量 6 铁律、人机分工、8 步 SOP、7 层定位法、提示词模板、坑速查 |
| [`offline/14_prebuilt_upload_checklist.md`](offline/14_prebuilt_upload_checklist.md) | **prebuilt 续修**：上传必要清单、5 项未解 TODO、sys13 已知良好基线 |

A 轮结果见 [`offline/08_roundA_result.md`](offline/08_roundA_result.md)，
实验队列见 [`offline/05_experiment_queue.md`](offline/05_experiment_queue.md)。

## 仓库内容

| 目录 | 内容 |
|---|---|
| `ROUND*.md`、`offline/` | Round10–19 报告、6 份离线分析、B0′ 交接基准与 A 轮结果 |
| `flash_log/` | 每轮实机 dmesg / input / I2C 绑定 / 冷启动台账 / 覆盖率 JSON |
| `fixtures/`、`tools/`、`tests/` | 驱动源码适配副本、BLM 与归档/度量脚本、门禁自测 |
| `prebuilt/` | prebuilt 路线 829 份文本：1042 行移植笔记、WiFi 修复全程、sys13 最终版 `patches/` |
| `prebuilt_c/` | 第一阶段（C 盘 `寒霜刷机`）验签 / 解锁 / 原厂 DTS / ROM 设备树 / `20261112` 日志包，约 80 份文本 |

## 项目进展与更新记录

> 本节是主页摘要。逐轮证据见 `ROUND*.md`、`offline/`、`flash_log/`；
> 资源地图见 `offline/12_ai_handoff_index.md` §9，工作手册见 `offline/13_continuation_playbook.md`。

### 三条工作线（别混成一条）

| 线 | 时间 | 原始目录 | 产物 |
|---|---|---|---|
| 第一阶段：验签 / 解锁 | 11-08 → 11-12 | `C:/Users/Tse/WorkBuddy/寒霜刷机` | aboot 验签与启动状态机、boot hash 数据流、跨机型对照、原厂 DTS 反编译、临时 root / 解锁工具链；文本层 → `prebuilt_c/` |
| prebuilt 路线 | 11-10 → 11-12 | `D:/16/PD1610_81` | 原厂 prebuilt 内核 + vendor blobs + 借 PD1619 设备树编译 LOS16；WiFi 修通；可刷 ROM zip |
| 自编译内核取证 | 11-14 → 11-15 | 本仓库 | `3.18.120-perf` + BLM / 9008 观察通道、bootloop 根因、触摸驱动源码重建、完成度 50/50 |

vivo 从未发布 PD1610/PD1619 的 3.18 内核源码，所以 prebuilt 路线**不编译内核**；
自编译路线用的是上游 LineageOS msm8996 3.18 开源树，两条线的镜像不能混用。

### 时间线

| 日期 | 阶段 | 关键结果 |
|---|---|---|
| 11-08 → 11-12 | 第一阶段研究 | 验签 / 解锁 / 设备树取证，30+ 份报告；`20261112.zip` 整理包 |
| 11-10 → 11-12 | prebuilt 路线 | LOS16 ROM 编译，WiFi 4 条因果链修复（sys13 `system.img` sha `686de5de…`），产出 `PD1610_LOS16_20261112_UNOFFICIAL.zip`（935,087,013 B） |
| 11-14 上午 | Round10–13 | BLM / 9008 `peek` 观察通道；查到 FDT 全零根因 = 自编译内核 BSS 清零区覆盖 `0x42000000` 的 DTB；裁剪调试配置后恢复 `d00dfeed` |
| 11-14 下午 | Round14–19 | 固定槽推翻 `usb_bam` 误判 → 定位 `qpnp_vibrator_init` 第一次 SPMI 读 → `FDT_NOP` 绕过 → SPMI stub + 恢复节点，`#5` 首次 `sys.boot_completed=1` |
| 11-14 傍晚 | Round20–26 | 触摸从「无驱动」推进到「事件链打通」：`CONFIG_TOUCHSCREEN_ST_FTS`、DT 属性、pinctrl、`IRQF_ONESHOT`、`vdd_ana`/`vcc_i2c`；导航键绑定成功但 probe 未完；最后一版报 bootloop 已回滚 |
| 11-14 夜 | 离线 6 项 + A 轮 | 8 门完成度定义、332 固件清单、原厂/自编译 `do_msm_restart` 反汇编差分；A 轮 3/3 冷启动、唤醒后 1266 行触摸事件，`UNVERIFIED` 全消 → 严格 50/50 |
| 11-15 | 归档与交接 | 双版 README、16 类 / 76 GiB 网盘冷备、WSL 最小重建集、第一阶段记录与 ROM 包补全、AI 索引 §9 |

### 归因演进（最容易走错的地方）

- **Round14/15 判 `usb_bam` 是错的**，Round16 固定槽证据推翻；真正卡点是
  `qpnp_vibrator_init` → 第一次 `spmi_ext_register_readl()` 未返回。
- Round18 用 DTB `FDT_NOP` 绕过 vibrator 只进到用户态（HAL 缺项卡二屏）；
  Round19 换成 SPMI stub 并恢复节点才完整进桌面。
- 触摸不是 probe 延迟，是**驱动根本没编进内核**（`System.map` 里无 `fts_driver_init`）。
- `adb reboot bootloader` 失效不是缺配置开关：原厂 `do_msm_restart` 1492 B vs
  自编译 740 B，原厂独有 `set_dload_mode_bbk` / `set_aee_system_restarting` /
  `deassert_ps_hold` 等 BBK 私有调用。[H1] aboot 读私有标志，未实机验证。

### 完成度口径演进

`20/88`（6 项 UNVERIFIED）→ 静态 `40/63` → A 轮**严格 `50/50`**、唤醒后对照 `65/65`（仅说明触摸能通，不算 `touch_cold` 通过）。正式采用 **50**。
区间从 68 点收窄到 0，靠的是补齐证据，不是补写代码 —— 早期 68% 是「没留证据」，不是「68% 代码没写」。
`hal` 门必须带 `--hal-ignore init.svc.vivo-fingerprint-sh`（该服务 `disabled`+`oneshot`，`stopped` 是正常态）。

### 2026-11-15 文档与资源更新

- README 改为**简体中文首选** + 页内 `English ↓` 切换 + 独立 `README.en.md`；新增百度网盘冷备索引。
- 补 `prebuilt_c/`（97 份第一阶段研究文本），网盘新增 `14_寒霜刷机_C盘工作目录/`（84 文件，含会话日志，仅私有）与 `15_LOS16_ROM刷机包/`（ROM zip + `SHA256SUMS`）。
- **更正过期结论**：「无 ROM zip / 未解 TODO 5 项」→「ROM 已产出 / 4 项 TODO」。
- `offline/12_ai_handoff_index.md` 新增 §9 当前准确状态，13/14 号文档同步；网盘扩为 16 类 / 76 GiB。
- 归档 `01` 两卷保持 01:34 版本（避免改动已上传的 973 MiB 分卷），其内的索引是旧版，以本仓库 / 网盘 `00` 目录为准。

### 当前状态与剩余工作

- 设备：原厂 `3.18.71-perf-g8a8c60dd` / LOS16 / `sys.boot_completed=1` / 不在 fastboot。
- 仍 FAIL 四门：`touch_cold`、`nav_keys`、`input_parity` 5/9、`i2c_parity` 4/9。
- 最大长尾：`goodixfp` 指纹（自编译内核里相关符号 0 个，需反汇编重建，5–15 工作日且不保证成功）。
- 这是**可交接快照 B0′，不是完成的第 3 档移植**。接续实验从 `offline/05_experiment_queue.md` 的 B 轮开始，先按 `13_continuation_playbook.md` 的单变量循环走。

## 已验证状态（2026-11-14）

- 第 3 档完成度 **严格口径 50/50，`UNVERIFIED = 0`**
  （`flash_log/tier3_coverage_roundA_final_strict.json`）；起点为 `20/88`。
- 仍 FAIL 四门：`touch_cold`、`nav_keys`、`input_parity` 5/9、`i2c_parity` 4/9。
- A 轮：**3/3 连续冷启动**通过（36.8 / 58.1 / 58.2 s）；锁屏唤醒后 25 秒窗口抓到
  **1266 行触摸事件**，IRQ 87→474。冷启动 30 秒窗口 0 事件。
- 设备已回滚原厂 `3.18.71-perf-g8a8c60dd`，`sys.boot_completed=1`，不在 fastboot。

## 已知缺口与诚实限制

- 触摸需一次锁屏 / 唤醒才生效（怀疑与 `st_fts.bin` 缺失、自动固件更新失败有关，未验证）；
  导航键无 `vivo_virtual_key` 输入设备。
- 自编译内核里 `adb reboot bootloader` 仍退化成普通重启，misc BCB 通道已排除。
- 最后一版导航键候选 `b6d5debb…` 报 bootloop 并已回滚，**卡点未隔离**。
- **归因演进必须注意**：Round14/15 判 `usb_bam`，被 Round16 固定槽证据推翻；
  真正卡点是 `qpnp_vibrator_init` → 第一次 SPMI 读。别从旧结论接着做。
- prebuilt 路线**已产出可刷 ROM** `PD1610_LOS16_20261112_UNOFFICIAL.zip`
  （935,087,013 B，sha256 `97c3137e…`，在百度网盘 `15_LOS16_ROM刷机包/`）；
  仍留 4 项 TODO（相机 0 设备、缺 `libcurl.so`、发布前清诊断代码须重编、
  sepolicy/configstore），见 `prebuilt/evidence/_log_append4.md`。
  第一阶段验签 / 解锁 / 设备树研究见 `prebuilt_c/`。

## 本仓库不包含的内容

19 个 `boot.img`、DTB 二进制、332 个固件 blob、RAM dump、原厂 `vmlinux`、
WSL 重建集与 sys13 `system.img` 都在**百度网盘冷备分卷**（约 973 MiB / 2 卷，zstd tar）。
本仓库是纯文本文档层，恢复步骤见 `offline/12_ai_handoff_index.md` §2 与
`archive/RESTORE.md`（后者在分卷内）。

## 百度网盘冷备索引（2026-11-15）

二进制、原始工程与可刷镜像不上 GitHub，放在百度网盘私有目录
**`PD1610_Xplay6/`**（约 76 GiB / 约 7160 文件，16 个分类）。

- 分享链接：<https://pan.baidu.com/s/5OL1VH3h9Pn_uOQllg29MSQ>
  （若页面要求提取码，请向维护者索取；分享链接可能随设置失效）
- 目录结构与逐文件清单：云端 `00_必读_恢复说明/上传清单.md` 与 `UPLOAD_CHECKLIST.csv`
- 恢复入口：云端 `00_必读_恢复说明/RESTORE.md`、`12_ai_handoff_index.md`

| 分类 | 内容 |
|---|---|
| `00`–`06` 必传 6.7 GiB | 恢复说明与校验文件、`01` 两卷冷备（973 MiB，zstd tar，权威副本）、原厂发布包、sys13 基线、9008 工具、固件、WSL 最小重建集 |
| `07`–`09` 可选 | GitHub 文本层冗余、48 分区 dump、官方 OTA |
| `10` / `11` 全量分卷 | `D:\16\PD1610_81` 40 GiB（22 卷）、`kernel_re` 11 GiB（6 卷），1.9 GiB tar 分卷 |
| `12` / `13` 原貌 | 自编译工程原始全量、其它资料与工具 |
| `14` / `15` 追加 | C 盘 `寒霜刷机` 工作目录全量（4.9 MiB）、LOS16 可刷 ROM zip（935 MB）与校验 |

**校验**：把 `00` 的 `SHA256SUMS`、`manifest.json` 与 `01` 两个分卷下载到同一目录，
跑 `sha256sum -c SHA256SUMS`（必须 3/3 OK），再按 `RESTORE.md` 重组解压。
`10_`/`11_` 各自目录内也有 `SHA256SUMS` 与 `RESTORE.txt`（`cat *.part* > xxx.tar`）。

> ⚠️ `10_prebuilt工程_全量分卷/` 内含原厂 OTA 解包出的 `imei.der` / `donuts_key`
> 设备密钥材料，**该子目录不应公开分享**。若分享链接覆盖整个 `PD1610_Xplay6/`，
> 请改为只分享 `00`–`09`，或在云端把 `10_` 移出分享范围。
> 另：`03_prebuilt_续修基线/sys13_system.img` 是已修通 WiFi 的已知良好基线，
> 与 `02_原厂回滚与发布包/images/system.img` 不是同一版本，别混用。

## 许可证

自研工具 MIT；文档 CC-BY-4.0；内核补丁沿用上游 LineageOS msm8996 3.18 的
GPL-2.0 并保留版权头。

> 这是可交接快照（B0′），**不是**已完成的第 3 档移植。

---

## English

> [↑ 返回中文](#zh-cn) · [README.en.md](README.en.md) · **English (default in this file: Chinese above)**

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

### Project status & changelog

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

### Verified status (2026-11-14)

- Tier-3 completion meter: **50/50 strict**, `UNVERIFIED = 0`
  (report: `flash_log/tier3_coverage_roundA_final_strict.json`).
- Still FAIL: `touch_cold`, `nav_keys`, `input_parity` (5/9), `i2c_parity` (4/9).
- A round: `3/3` clean cold boots (36.8 / 58.1 / 58.2 s); after a
  suspend/resume cycle the touch panel produced 1266 `getevent` lines.
- Device rolled back to stock `3.18.71-perf-g8a8c60dd`, `sys.boot_completed=1`.
- A round result: `offline/08_roundA_result.md`. Queue: `offline/05_experiment_queue.md`.

### Honest limitations

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

### What this repository does not contain

Boot images, DTB binaries, firmware blobs, RAM dumps and the WSL build
environment are in a separate private cold-storage archive (about 973 MiB,
2 volumes, zstd tar). This repo is the text-only documentation layer;
see `offline/12_ai_handoff_index.md` section 2 for the restore procedure.

### Baidu Netdisk cold storage (2026-11-15)

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

### Licensing

Self-written tools: MIT. Documentation: CC-BY-4.0. Kernel patches follow
the upstream LineageOS msm8996 3.18 GPL-2.0 with copyright headers intact.

> This is a handoff snapshot (B0'), not a finished Tier-3 port.