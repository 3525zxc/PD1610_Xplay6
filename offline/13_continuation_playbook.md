# ⑬ 接续工作指导手册（人 + AI 都能照着做）

日期 2026-11-14 23:20。用途：项目暂停后，任何人或任何模型接手，读这一份就能按**前面 26 轮验证过的工作形式**继续编译、刷机、取证、定位和修复，不需要重做历史调查。

> 与 `12_ai_handoff_index.md` 的分工：那份是**资源地图**（文件在哪、要取哪些）；这份是**工作方法**（一轮怎么做、怎么给 AI 下指令、怎么验证它没编造、出错了往哪走）。先读索引取资源，再读本手册开工。

---

## 1. 这个项目的「工作形式」到底是什么

前面 26 轮能从一个纯黑盒 bootloop 走到进桌面，靠的不是一次性大改，而是下面这个固定循环。**接手后不要改这套形式**：

```
离线门禁  →  单变量改动  →  增量编译  →  出镜像  →  预检
   →  人工进 fastboot  →  只刷 boot  →  重启  →  二次枚举
   →  全量取证  →  判据判定  →  写报告  →  回滚原厂验证
```

六条铁律：

1. **单变量**：一轮只改一个东西（一个 config 开关 / 一处 DT 属性 / 一行 IRQ flag）。改两个变量，出了问题就分不清是谁导致的 —— 第四版 `a1a0e026…` 就吃了这个亏（同时改固件更新和中断触发方式，至今没验）。
2. **离线门禁优先**：能在 Windows/WSL 上用脚本判定的，绝不先刷机。`blm_preflight.py` 是硬门槛。
3. **只写 `boot` 分区**：不动 system/vendor/用户数据，回滚路径永远在。
4. **证据先行**：一轮结束后，报告里必须能查到这一轮的输入镜像 sha、预检结果、dmesg、input 全表、I²C 绑定、getprop。没有证据的「成功」一律不算。
5. **[O] / [H] 分离**：观察到的写 `[O]`，推断的写 `[H]` 并标注未验证。历史上把假设写成结论，导致 Round14/15 的 `usb_bam` 错误结论被沿用了两轮。
6. **不虚构**：AI 说「已完成」必须附真实命令输出；没跑的步骤写「未执行」并给可复现命令。哈希、编译结果、寄存器值、HTTP 响应一律不许编。

---

## 2. 人与 AI 的分工边界（必须遵守）

| 只能人做 | AI 做 |
|---|---|
| **手动进 fastboot / 9008**（`adb reboot bootloader` 在候选内核里失效） | 离线分析、源码比对、反汇编、符号差分 |
| 插拔 USB、按键、点屏幕、按返回键 | 改配置、写补丁、增量编译、出 boot.img |
| 判断「屏幕能不能点」「导航键有没有反应」 | 跑预检、刷机命令、等待枚举、抓全量证据 |
| 决定继续 / 暂停 / 回滚 | 按判据给 PASS/FAIL，如实写报告 |
| 明确说「请进 fastboot」 | **绝不推断设备自动进入** |

**约定**：每轮由 AI 明确说「请进 fastboot」，人操作完回复，AI 才动手刷。反过来，AI 不得因为检测到端口在线就假定是人刚进去的（历史教训：Round17 把用户手动介入误写成「自动进入」）。

---

## 3. 环境准备（一次做完）

### 3.1 从冷备恢复

按 `archive/RESTORE.md` 解出工程到**原路径**：
```
D:/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/
```
路径写死在脚本里，换了要改一堆 `ROOT=`、`SRC=`、`OUT=`、`TC=`。

### 3.2 WSL 重建

`offline/11_wsl_rebuild_guide.md` 路线 B：Ubuntu 20.04.5 + apt 包（`wsl_rebuild/env/environment.txt` 有全表）+ 解三个 tar 到原路径。**只需 1.6 G**，不用还原 176 G 的 vhdx。

验证重建成功（不刷机）：
```bash
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl.exe -d PD1610 -- \
  bash /mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/tools/blm_trace_build.sh \
  rebuild-check /mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/tests/patched_tree_vibfix
```
预期 `BUILD_RC=0`。

> **WSL 调用坑**：Git Bash 会吞掉 shell 变量、把 `/mnt/d/...` 转成 Windows 路径。必须 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`，复杂逻辑写成独立 `.sh` 再让 WSL 执行。

### 3.3 工具与回滚基线

- `adb.exe` / `fastboot.exe`：`D:/xplay6/tools/platform-tools/`
- 原厂 boot：`D:/16/PD1610_81/release/PD1610_LOS16_20261112/images/boot.img`，sha `929fda998547…`，58,483,968 B
- 9008：`QSaharaServer.exe -u 5 -s 13:D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf`
- 设备内副本 `/data/local/tmp/stock_boot.img` 亦在（运行态 boot 只读，只有 fastboot 能写）

---

## 4. 一轮实验的标准操作（照抄即可）

### 步骤 0：写死本轮 claim

在 `offline/05_experiment_queue.md` 里加一行，格式：
```
| B | 补 irqflags |= IRQF_ONESHOT 后 3-0028 probe 完成 | 3-0028 有 driver 绑定 + vivo_virtual_key 出现 + getevent 收到 172/158/139 | nav_keys/input_parity | 仍失败则看 request_threaded_irq 返回值 |
```
**先写判据再动手**，避免事后找理由说「算成功」。

### 步骤 1：离线改单变量

在 `fixtures/` 里复制一份源码改（不要直接改 WSL 源码树），例如 `fts_vivo_dt2.c` → `fts_vivo_dt3.c`。用 `diff` 确认只有预期行数变化。

### 步骤 2：增量编译

```bash
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl.exe -d PD1610 -- \
  bash -c 'cp <适配源码> /home/builder/ksrc/.../drivers/input/touchscreen/fts.c; <确认 grep>'
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl.exe -d PD1610 -- \
  bash <工程根>/tools/blm_trace_build.sh <TAG> <工程根>/tests/patched_tree_vibfix
```
后台跑，取 `BUILD_RC=0` 与 `build/<TAG>/build.log` 尾部。检查 `System.map` 里目标符号数量（例：`fts_probe` 是否出现）。

### 步骤 3：出 boot.img + 预检

```bash
python tools/blm_build_bootimg.py --root <工程根> --tag <TAG> \
  --build-dir build/<TAG> --kernel-image build/<TAG>/Image.gz-dtb \
  --system-map build/<TAG>/System.map \
  --stock-boot D:/16/PD1610_81/release/PD1610_LOS16_20261112/images/boot.img \
  --output images/boot_los16_blm_<TAG>.img --report images/...report.json \
  --ddr-base-status "[O]" --append-cmdline "log_buf_len=2M audit=0 loglevel=8"

python tools/blm_preflight.py --image build/<TAG>/Image.gz-dtb \
  --system-map build/<TAG>/System.map --bootimg images/...img \
  --bootimg-report images/...report.json --report images/...preflight.json
```
**门禁**：构建 40/40、预检 **17/17 `SAFE_TO_FLASH`**、`_end` 距 FDT `0x42000000` ≥1 MiB。任一不过 → 停，不刷。

> 为什么必须预检：自编译内核 BSS 清零区曾覆盖 aboot 放在 `0x42000000` 的 DTB，造成前 10 轮 bootloop。裁剪配置后 `_end=0x41e09000`。

### 步骤 4：明确说「请进 fastboot」，等人操作

人确认后：
```bash
FB=/d/xplay6/tools/platform-tools/fastboot.exe
for i in 1 2 3; do "$FB" -s <serial> flash boot <IMG> && break; done   # 失败只重试，不 reboot
"$FB" -s <serial> reboot
```
**USB 端点瞬断**（错误 31/121/433）时停在 fastboot 不重启，约 2 分钟自恢复。

### 步骤 5：重启后二次枚举

reboot 后 adb 常先连上重启前残留会话再掉线。必须 `wait-for-device` 后再取一次 `devices -l`，确认 `transport_id` 变化、`uname -r` 是候选内核、`sys.boot_completed=1`。

### 步骤 6：全量取证（一条命令）

```bash
python tools/blm_round_capture.py --tag roundNN --image <IMG> --score
```
产出 12 类快照 + `roundNN_manifest.json`（每文件 sha256）。事件窗口另跑：
```bash
timeout 35 adb shell 'timeout 30 getevent -l /dev/input/event4' > flash_log/roundNN_touch_events.txt
```
冷启动触摸判据要求 **30 秒内**有 `ABS_MT_*` 事件；需要人配合点屏幕，务必在窗口开始前提示。

### 步骤 7：判定与报告

```bash
python tools/blm_tier3_coverage.py \
  --baseline-input flash_log/stock_baseline_input_devices.txt \
  --baseline-i2c flash_log/stock_baseline_i2c_bindings.txt \
  --current-input flash_log/roundNN_input_devices.txt \
  --current-i2c flash_log/roundNN_i2c_bindings.txt \
  --props flash_log/roundNN_props.txt \
  --touch-events flash_log/roundNN_touch_events.txt \
  --nav-events flash_log/roundNN_nav_events.txt \
  --inventory offline/03_firmware_inventory.csv \
  --preflight images/<...>.preflight.json \
  --boot-ok --hal-ignore init.svc.vivo-fingerprint-sh \
  --report flash_log/tier3_coverage_roundNN.json
```
`--hal-ignore` 不能省：`vivo-fingerprint-sh` 是 `disabled`+`oneshot`，`stopped` 是正常终态。

报告写 `offline/08_roundNN_result.md`，格式照 A 轮：执行事实表、完成度、口径修正、[H] 线索、未完成项。

### 步骤 8：回滚原厂并验证

```bash
fastboot flash boot <原厂 boot.img> ; fastboot reboot
adb wait-for-device ; adb wait-for-device   # 二次枚举
adb shell 'uname -r; getprop sys.boot_completed'
```
确认 `3.18.71-perf-g8a8c60dd` + `BOOT=1` 才算 `ROLLBACK_VERIFIED`。

---

## 5. 定位与修复的方法库（按成本从低到高）

| 层次 | 做法 | 判读 |
|---|---|---|
| ① 只读日志 | `dmesg`（2 MiB log_buf）里搜驱动名 / `probe` / `Failed` | 精确到函数名与错误码（如 `error -22`、`invalid GPIO -2`） |
| ② sysfs 对照 | `/proc/bus/input/devices`、`for d in /sys/bus/i2c/devices/*; readlink $d/driver` | 设备枚举了但无 driver ⇒ 匹配表或 config 问题 |
| ③ config 差分 | `zcat /proc/config.gz` vs `kout/.config` 全量比对 | 驱动根本没编进去（触摸根因） |
| ④ DT 属性对照 | `blm_patch_dtb.py` 解析节点属性 vs 驱动 `of_property_read_*` | 属性名不匹配（`fts,*` vs vivo 的 `synaptics,*`） |
| ⑤ 符号/二进制差分 | 解锁 `kptr_restrict=0` → kallsyms 地址 → 函数大小差分 → 反汇编 | 原厂独有私有逻辑（`do_msm_restart` 1492 B vs 740 B） |
| ⑥ 固定槽取证 | bootloop 时进 9008，Firehose `peek` 读 `0x42100000` | 最后进入的 initcall，判定真卡死还是误判 |
| ⑦ 事件链 | `getevent` + `/proc/interrupts` 计数差 | 有 IRQ 无事件 / 有中断无上报，区分硬件与驱动 |

**关键**：环形行槽的「最后一条」不可靠，关键 `last-known-good` 必须写 BLM 固定槽（`blm_trace_note`）。console 必须带 `CON_ENABLED`（3.18 `printk.c:2536` 门槛）。

---

## 6. 怎么给 AI 下指令（可直接复制的模板）

### 开场（恢复项目时）

```
我在恢复一个已归档的 Android 内核逆向项目（vivo Xplay6 / PD1610 /
LineageOS 16 / 自编译 3.18.120 内核）。工程已按 archive/RESTORE.md
恢复到原路径 D:/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/。

请先读，不要凭名字猜：
  1. offline/12_ai_handoff_index.md   资源地图
  2. offline/13_continuation_playbook.md   本手册（工作形式与 SOP）
  3. offline/08_roundA_result.md      最近一轮实机结果
  4. offline/05_experiment_queue.md   实验队列

当前：严格完成度 50/50，UNVERIFIED=0；设备原厂 3.18.71，不在 fastboot。
按本手册 §4 从队列的下一轮开始。约束：单变量；每轮先写 claim 与判据；
刷机前 blm_preflight.py 必须 17/17；由我明确说「请进 fastboot」你才刷；
每轮用 blm_round_capture.py 抓全量证据并重算完成度；[O]/[H] 分开写；
未执行的步骤写「未执行」并给命令，不要虚构任何结果。
```

### 单轮任务

```
本轮 claim：<一句话>。判据：<可机判的条件>。失败分支：<...>。
只改 <具体文件/行>，不改其他变量。先离线 diff 给我看改动，
等我确认再编译。编译后先报 BUILD_RC 和 System.map 目标符号数，
再出镜像和预检。预检不过就停，不要刷。
```

### 复核 AI 结果（每轮结束必问）

```
请给出：① 本轮所有实际执行过的命令及退出码 ② 输入镜像 sha256 与
preflight.json 的 verdict ③ dmesg 里支撑结论的原始行（带时间戳）
④ 完成度 JSON 的 gate 状态 ⑤ 哪些步骤「未执行」及可复现命令。
不要用「应该」「预计」代替观测，不要复述我给过的结论当新发现。
```

---

## 7. 已知坑速查

| 现象 | 原因 / 处理 |
|---|---|
| `adb reboot bootloader` 只普通重启 | 候选内核的 reboot 通道未修（BBK 私有路径）；人工进 fastboot |
| 刷写 `Sending FAILED (31/121/433)` | USB 端点瞬断；**停在 fastboot 不重启**，约 2 分钟自恢复 |
| reboot 后 `no devices` | 残留 adb 会话；二次枚举 |
| `dd of=/dev/block/.../boot` 报 `Read-only file system` | 运行态 boot 只读，只有 fastboot 能写 |
| toybox `dd` 不支持 `conv=sync` | 换写法，别照搬 GNU 命令 |
| misc BCB `bootonce-bootloader` 不生效 | 本机 aboot 不认，已排除 |
| `kptr_restrict=2` 看不到符号地址 | `adb root` 后 `echo 0 > /proc/sys/kernel/kptr_restrict` |
| WSL 里变量被吞、`/mnt/d` 路径转坏 | `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'` + 独立 `.sh` |
| 9008 双读带 `--reset` | 会复位回候选镜像持续 bootloop，回滚需复位后主动切 fastboot |
| `<power value=fastboot>` 回 NAK | 本机 programmer 只有 `reset` 可用 |
| dmesg 早期日志被冲掉 | header 加 `log_buf_len=2M audit=0 loglevel=8` |
| `vivo-fingerprint-sh: stopped` 被判 FAIL | `disabled`+`oneshot` 正常态，加 `--hal-ignore` |
| 触摸冷启动点不了 | 锁屏唤醒后才生效；`fts_fw_update_auto` 两次失败 + `st_fts.bin` 缺失，[H] 待验 |

---

## 8. 当前从哪接（2026-11-14 状态）

- 完成度 **50/50 严格**（`UNVERIFIED=0`）；FAIL 四门：`touch_cold`、`nav_keys`、`input_parity` 5/9、`i2c_parity` 4/9。
- A 轮已完成；`b6d5debb…` bootloop 原因**未区分**（真卡死 vs 二屏误判），需 9008 单独一轮。
- 下一轮优先 **B**（`cyttsp irqflags |= IRQF_ONESHOT`）与 **B′**（`touch_cold` 拆单变量验 `a1a0e026…` 的跳过固件更新）。
- `goodixfp` 指纹是长尾（自编译符号 0 个，需反汇编重建，5–15 工作日且可能失败）。
- 可用基线镜像：`images/boot_los16_blm_ftsirq_20261114192500.img`（`5f164490…`，`3.18.120-perf #9`，触摸唤醒后可用）。
- **两条路线的关系**：`D:/16/PD1610_81` 是 prebuilt 路线（原厂内核 + vendor blob + 借 PD1619 设备树做 LOS16 ROM），本工程是自编译内核路线。前者的 `evidence/`、`refs/PD1619_PORTING_NOTES.md`、`blobs/` 清单对「vendor 驱动源码化」仍有参考价值，提炼结果见 `prebuilt_extract/README.md`。
- **要修 prebuilt 路线的 bug**：读 `offline/14_prebuilt_upload_checklist.md`。5 项未解 TODO，已知良好基线是 `out/system.img`（sys13 / `686de5de…`），最终版源码在 `release/.../patches/`（与 `device_tree/` 早期基线不同，改前先 diff）。那条路线刷 `system` 分区而非 `boot`，编译用 `bash ~/build_pd1610.sh systemimage`（`lunch` 在此树会卡死）。同样遵守单变量、证据先行、[O]/[H] 分离。

---

## 边界

- 本手册写于设备回滚原厂、工程已归档之后；**本机文件尚未清空**。
- 清空前置条件见 `offline/12_ai_handoff_index.md` §8：网盘上传并校验完成、GitHub push 完成、人明确确认具体路径。
- 所有命令路径基于当前工程布局；若恢复时换了盘符或目录，需同步改 `ROOT`/`SRC`/`OUT`/`TC` 与脚本内 `/mnt/d/...` 常量。

> **2026-11-15 补充**：第一阶段（C 盘）验签 / 解锁 / 设备树研究的文本层在 GitHub `prebuilt_c/`，全量在网盘 `14_寒霜刷机_C盘工作目录/`。prebuilt 路线的可刷 ROM zip 在网盘 `15_LOS16_ROM刷机包/`，`offline/12_ai_handoff_index.md` §9 是当前准确状态入口。

