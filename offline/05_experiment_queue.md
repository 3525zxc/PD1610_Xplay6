# ⑤ 第 3 档收敛实验队列（claim-driven）

目标：把 `blm_tier3_coverage.py` 的 `[15%, 88%]` 区间收窄。每轮写死 claim、判据、采集清单、失败分支；**每轮结束必须跑一次覆盖率工具**，否则不算完成。

## 每轮统一采集清单（写入 `flash_log/roundNN_*`）

`/proc/bus/input/devices`、**完整 I²C 绑定表**（`for d in /sys/bus/i2c/devices/*; do readlink $d/driver; done`）、`getprop`（含 `init.svc.*`）、`getevent` 触摸与虚拟键各 30 s、`dmesg`（2 MiB log_buf）、镜像 sha256、`.preflight.json`。这些正好填满当前 6 个 `UNVERIFIED` gate 的证据缺口。

| 轮 | Claim | 前置 | 量化判据 | 影响 gate | 失败分支 |
|---|---|---|---|---|---|
| **A** | `b6d5debb…` 的 bootloop 是 pinctrl 之后新代码路径卡死同步 initcall，而非误判 | 需一次手动进 fastboot | 刷候选 → 复现后进 9008 读 BLM 固定槽；`last_stage=12 KERNEL_INIT` 且最后 initcall 落在 `cyttsp_button_init` 附近 ⇒ 真卡死；若设备正常进桌面 ⇒ 误判 | `boot`(20) | 真卡死：回退 pinctrl 改动，只保留 `hw-version` 容错 + 补 ONESHOT |
| **B** | 补 `irqflags \|= IRQF_ONESHOT` 后 `3-0028` probe 完成、虚拟键三键可用 | A 结论 | `3-0028` 有 driver 绑定、`vivo_virtual_key` 出现在 input 列表、`getevent` 收到 172/158/139 三键；冷启动 30 s 内触摸 `getevent` 有事件 | `nav_keys`(8) `input_parity`(12) `touch_cold`(15) | 仍失败：看 `request_threaded_irq` 返回值与 pinctrl，按日志再定点修 |
| **C** | 两个 tasha jack input 设备可恢复 | B 通过 | input 列表出现 `msm8996-tasha-cdp-snd-card Headset/Button Jack`；对比两边 `ASoC` 注册日志定位差异 | `input_parity`(12) `hal`(10) | 若是 machine driver 私有实现差异，转 ① 式二进制差分 |
| **D** | `adb reboot bootloader` 走 BBK 私有写入标志（① 的 H1） | ① 的 `set_dload_mode_bbk` 反汇编结论 | 在自编译 `do_msm_restart` 补对应 `__raw_writel` 后，`adb reboot bootloader` 60 s 内 `fastboot devices` 出现 | `boot`(20) `reproducible`(15) | H1 不成立则改查 H2（复位路径）或反汇编原厂 aboot |

**不进队列的长尾**：`goodixfp` 指纹（需 vivo 私有 SPI 驱动源码化，见 `02_input_parity_gap.md`）。它是 `input_parity` 满分的最后一块，但工作量远大于 A–D，建议单独立里程碑，不要混进这 4 轮拖慢收敛。

## 收尾判据（第 3 档宣布完成前必须全过）

1. 连续 3 次冷启动 `sys.boot_completed=1`、无 bootloop；
2. input 设备 9/9（或明确标注指纹为「保留 vendor blob」并写进清单）；
3. I²C 有 driver 节点绑定 ≥ 8/9；
4. 冷启动 30 s 内触摸事件可抓；
5. 每轮采集清单齐全、覆盖率报告区间收窄到 ≤10 个百分点；
6. `blm_preflight.py` 17/17 + 回滚验证。

## 当前基线

设备已在原厂 `3.18.71-perf-g8a8c60dd` / `sys.boot_completed=1`，**不在 fastboot**。按约定，开始 A 轮前我会明确说「请进 fastboot」。
