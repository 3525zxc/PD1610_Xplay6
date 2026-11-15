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
**`PD1610_Xplay6/`**（约 75 GiB / 7073 文件，14 个分类）。

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
They live in the private Baidu Netdisk folder **`PD1610_Xplay6/`** (~75 GiB,
7073 files, 14 categories).

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