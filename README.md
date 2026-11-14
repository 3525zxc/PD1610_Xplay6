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
- prebuilt 路线尚留 5 项 TODO（相机 0 设备、缺 `libcurl.so`、清诊断代码须重编、
  sepolicy/configstore、无 ROM zip），见 `prebuilt/evidence/_log_append4.md`。

## 本仓库不包含的内容

19 个 `boot.img`、DTB 二进制、332 个固件 blob、RAM dump、原厂 `vmlinux`、
WSL 重建集与 sys13 `system.img` 都在**百度网盘冷备分卷**（约 973 MiB / 2 卷，zstd tar）。
本仓库是纯文本文档层，恢复步骤见 `offline/12_ai_handoff_index.md` §2 与
`archive/RESTORE.md`（后者在分卷内）。

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
- The prebuilt route has 5 open TODOs (camera, libcurl, diagnostic-code
  cleanup, sepolicy/configstore, no ROM zip); see `prebuilt/evidence/_log_append4.md`.

### What this repository does not contain

Boot images, DTB binaries, firmware blobs, RAM dumps and the WSL build
environment are in a separate private cold-storage archive (about 973 MiB,
2 volumes, zstd tar). This repo is the text-only documentation layer;
see `offline/12_ai_handoff_index.md` section 2 for the restore procedure.

### Licensing

Self-written tools: MIT. Documentation: CC-BY-4.0. Kernel patches follow
the upstream LineageOS msm8996 3.18 GPL-2.0 with copyright headers intact.

> This is a handoff snapshot (B0'), not a finished Tier-3 port.