# ⑧ A 轮实机结果（2026-11-14 21:45–）

目标：不改任何代码、只刷一次候选，把 `blm_tier3_coverage.py` 的 `UNVERIFIED` 证据缺口填满并收窄分数区间。设备回到可回滚的原厂状态。

## [O] 执行事实

| 步骤 | 结果 |
|---|---|
| 刷入镜像 | `images/boot_los16_blm_ftsirq_20261114192500.img`，sha `5f164490032dd866ae673734d0913dfdc6e629700ab3f331f6c8ef3db3ce638d`，预检 17/17 `SAFE_TO_FLASH`；`Sending OKAY [1.542s]` / `Writing OKAY [0.393s]`，一次通过 |
| 启动 | `3.18.120-perf #9`、`sys.boot_completed=1`、`init.svc.bootanim=stopped` |
| 静态采集 | `tools/blm_round_capture.py --tag roundA` → 12 类快照写入 `flash_log/roundA_*.txt`，含 199,902 B 完整 dmesg（2 MiB log_buf）；每文件 sha 记录在 `roundA_manifest.json` |
| 3 次冷启动 | `tools/blm_coldboot_verify.py` → **3/3 PASS**，耗时 36.8 s / 58.1 s / 58.2 s，每次 `sys.boot_completed=1` 且内核仍 `3.18.120-perf`；报告 `flash_log/roundA_coldboot.json` |
| 触摸窗口 1 | 冷启动后未唤醒，35 s `getevent -l /dev/input/event4` → **0 行**，IRQ 482 = 5 |
| 锁屏唤醒 | `input keyevent 26` ×2 后 IRQ 482: 5 → 56 |
| 触摸窗口 2 | 唤醒后 25 s → **1266 行**，IRQ 87 → 474（+387）；含 `ABS_MT_TRACKING_ID` / `BTN_TOUCH DOWN` / `ABS_MT_POSITION_X 0x180` / `ABS_MT_POSITION_Y 0x5a3` / `SYN_REPORT` |
| 导航键 | `/proc/bus/input/devices` 中 `vivo_virtual_key` 计数 **0**；`gpio-keys`（event3）12 s 窗口 **0 行** |
| 回滚 | **已完成并验证**：`929fda99…` 一次 `Sending OKAY [1.512s]` / `Writing OKAY [0.389s]`，`reboot OKAY`；二次枚举后 `3.18.71-perf-g8a8c60dd #1`、`BOOT=1`、`bootanim=stopped`、`vibrator-1-0=running`、9 个 input 设备全在、fastboot 端口已退出 |

## [O] 完成度：从区间变成确定值

| 口径 | 分数 | UNVERIFIED |
|---|---|---|
| A 轮之前（`tier3_coverage_offline.json`） | `20 / 88` | 6 项（68 分） |
| A 轮静态证据（未含事件） | `40 / 63` | 2 项（23 分） |
| **严格口径**（冷启动 30 s 窗口 0 事件） | **`50 / 50`** | **0** |
| **唤醒后口径**（1266 行事件） | **`65 / 65`** | **0** |

报告：`flash_log/tier3_coverage_roundA_{static,strict,awake,final_strict,final_awake}.json`。

严格口径 8 门状态：

| gate | 权重 | 状态 | 依据 |
|---|---|---|---|
| boot | 20 | PASS | 3/3 冷启动 |
| touch_cold | 15 | FAIL | 冷启动后 35 s 无事件 |
| nav_keys | 8 | FAIL | 虚拟键设备不存在、无按键事件 |
| input_parity | 12 | FAIL | 5/9，缺 `vivo_virtual_key` / `goodixfp` / 2× tasha jack |
| i2c_parity | 15 | FAIL | 4/9，缺 `3-0028` `3-0067` `3-006b` `7-0050` `8-0048` |
| hal | 10 | PASS | 6 个常驻 HAL 服务全 running（见口径修正） |
| firmware_inventory | 5 | PASS | `offline/03_firmware_inventory.csv` |
| reproducible | 15 | PASS | 40/40 + 17/17 + 回滚基线 |

## [O] 口径修正（HAL 门）

原工具把所有 `init.svc.*` 含 `fingerprint` 的键都要求 `running`，导致 `hal` 误判 FAIL。实机证据：

- `/vendor/etc/init/init.vivo.fingerprint.rc:15-19`：`service vivo-fingerprint-sh ... /vendor/bin/init.vivo.fingerprint.sh`，带 **`disabled`** 和 **`oneshot`** ⇒ `stopped` 是正常终态，不是故障。
- `ps -A` 里指纹 HAL 进程 `vendor.vivo.hardware.biometrics.analysis@1.0-service` 正在运行。
- `round18_getprop.txt` / `round19_getprop.txt` 里同一服务也都是 `stopped`，与原厂一致。

修法：`blm_tier3_coverage.py` 增加显式 `--hal-ignore`，**默认行为不变**（不偷偷改口径），本轮传 `--hal-ignore init.svc.vivo-fingerprint-sh`。修正前后分数都留了 JSON：`tier3_coverage_roundA_strict.json`（40）与 `..._final_strict.json`（50）。

## [O] 新证据：I²C 绑定比原先判断的好

此前记忆写「自编译 #9 明确只有 fts 绑定」是低估。A 轮完整绑定表显示 **4 个**有 driver：`12-0049`（fts）、`7-0002`、`7-0072`、`8-0034`。原厂 9 个有 driver。这一项应作为后续 I²C 收敛的起点，不必从 1/9 开始。

## [H] 触摸「冷启动 30 s 内不生效」的机制线索（未实机验证）

dmesg 时间线：

```
[1.918] fts 12-0049: driver ver. 122.05 / DT dump 全过
[2.004] input: fts ... input4 ; Doing a system reset
[2.057] Interrupt Mode ; Received event 0x16
[7.072] [FTS]: fts_fw_update_auto: NO CRC Error 124 K firmware update
[7.072] [FTS]: fts_fw_update_auto: firmware update failed and retry!
[8.200] fts 12-0049: Doing a system reset
[8.236] [FTS]: fts_fw_update_auto: firmware update failed again!
```

`offline/03_firmware_inventory.csv` 已证实 `st_fts.bin` 不随系统提供。[H1] 自动固件更新在工作队列里重试并做 `system reset`，把芯片留在异常/升级模式，直到一次 suspend-resume（锁屏唤醒）触发 `fb_notifier` / resume 路径才恢复中断上报。IRQ 计数在唤醒后从 5 猛增到 474 与之一致。

**现成候选**：第四版 `images/boot_los16_blm_ftslow_20261114193500.img`（sha `a1a0e026…`）恰好跳过自动固件更新并改 `IRQF_TRIGGER_LOW | IRQF_ONESHOT`，当初因「#9 触摸实测可用」被作废。A 轮证明 #9 只是*唤醒后*可用，[H2] 第四版可能正是 `touch_cold` 的解。但它同时改了两个变量（固件更新 + 中断触发方式），B 轮应先拆成单变量再验证，不要直接宣布修复。

## [O] 新增/修改的工具

- `tools/blm_round_capture.py`（新）：一次抓 12 类证据，格式直接对齐覆盖率工具；可选 `--touch-secs` / `--nav-secs` / `--score`；输出带 sha256 的 manifest。
- `tools/blm_coldboot_verify.py`（新）：`adb reboot` → 等待离线→上线 → 二次确认 `sys.boot_completed=1`，N 轮 JSON 台账。
- `tools/blm_tier3_coverage.py`（改）：新增 `--hal-ignore`，默认不变。

## 未完成 / 下一轮入口

1. ~~回滚原厂~~ **已完成**（见上表）。设备当前原厂 `3.18.71-perf-g8a8c60dd` / `sys.boot_completed=1` / 不在 fastboot；设备内 `/data/local/tmp/stock_boot.img` 副本 sha 校验一致。
2. **`b6d5debb…` bootloop 复现 + 9008 读 BLM 固定槽**：`05_experiment_queue.md` 原 A 轮的 claim，本轮未做（本轮 A 是证据收窄）。仍需单独一轮，需 9008 手动介入。
3. **B 轮**：优先验证 `touch_cold`（拆单变量：跳过自动固件更新 / 中断触发方式），再补 `cyttsp irqflags |= IRQF_ONESHOT`。
4. `input_parity` 与 `i2c_parity` 的 4/5 项缺口仍是第 3 档主体工作量，其中 `goodixfp` 为长尾。

## 边界

- 所有分数以 `stock_baseline_*` 快照为分母；`stock_baseline_props.txt` 不存在，HAL 对照改用 `round18/19_getprop.txt` 与 rc 定义，属间接对照。
- 「唤醒后口径 65」仅用于说明触摸功能本身可用，**不作为 `touch_cold` 通过**；正式完成度以严格口径 `50` 为准。
- [H1]/[H2] 为离线假设，未实机验证。
