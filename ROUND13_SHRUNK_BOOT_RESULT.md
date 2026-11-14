# Round 13 · 裁剪内核实机验证：根因修复被证实，启动推进到 KERNEL_INIT

> 2026-11-14 13:43–13:52，第 13 次 Boot-only 实机。仅写 `boot` 分区；设备已回滚并二次核验原厂系统。
> 先回答现场疑问见 §1。

## 0. 一句话结论

**裁剪掉 BSS 覆盖后，自编译 3.18.120 内核第一次走过了此前卡死 10 次的 `SETUP_ARCH_ENTER`，连续跑完 12 个阶段直到 `KERNEL_INIT`（initcalls 阶段）；`0x42000000` 的 FDT 头也从全零恢复为合法设备树。根因「BSS 清零抹掉 DTB」被实机正反两面证实。** 新瓶颈已推进到 `kernel_init` 之后的驱动 probe / rootfs / Android ramdisk，尚未启动到系统。

## 1. 「回滚时又 bootloop、fastboot 里选开机还是 bootloop」的核查

**这次不是回滚失败，而是回滚根本还没执行完**，所以从 fastboot 界面选「开机」时 boot 分区里仍是裁剪候选镜像，当然继续 bootloop。

真实时间线：

```
13:44:43 刷入裁剪候选 + reboot               <- boot 分区 = 候选
13:45:01~13:46:35 观察，t=85s 自动进 9008
13:46:54~13:47:03 双读 FDT 头 + BLM 日志，最后带 --reset（设备复位回候选）
13:47:32 回滚脚本开始等 fastboot
13:47:32~13:50:39 等 180 s 未等到 -> ROLLBACK_NOT_EXECUTED  <- boot 分区仍是候选
13:49:58 用户手动进 fastboot、从界面选开机 -> 必然仍 bootloop
13:51:12 用户再次手动进 fastboot，回滚重试启动
13:51:44 刷入原厂 boot.img（sha 929fda99…）Sending/Writing OKAY
13:52:34 ROLLBACK_VERIFIED: 3.18.71-perf-g8a8c60dd / LOS16 / uptime 0 min
13:52:58 二次核验：adb 在线、uptime 1 min、fastboot 已退出、PnP = ADB Interface
```

回滚镜像 sha256 `929fda9985478078f0614a9c3709af69fe3b1c9c8badc50e783261f91ab241ae`，与前 10 次成功回滚同一个文件，现场复核一致。**没刷错。**

> 工程教训：双读用 `--reset` 后设备会复位回候选镜像并持续 bootloop，回滚不能靠被动等 fastboot（这次等 180 s 都没等到）。下一次应在双读时**不带 `--reset`**，或复位后立刻由用户/脚本主动切 fastboot 再回滚。

## 2. 观察 [O]

| 项 | 结果 |
|---|---|
| 刷前门槛 | `blm_preflight.py` `PASS 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`、余量 `0x1f7000` |
| 刷入 | 13:44:43 `Sending OKAY [1.583s]` / `Writing OKAY [0.392s]`；`reboot OKAY` |
| 启动观察 | t=0–80 s 无 fastboot/adb/9008；t=85 s 自动进 `9008 (COM5)`；`adb_seen=False` |
| 失败态 FDT | `flash_log/fdt_round13.bin`，65,536 B，sha256 `3629cfe3…`，**`nonzero=31502`**、`magic=0xd00dfeed`、`totalsize=410,533 (0x643a5)`、`off_struct=56`、`off_strings=374,076`、PD1610 model @108 |
| 失败态 BLM | `flash_log/blm_ram_round13.bin`，262,144 B，sha256 `d85913f8…`，`bank_count=1`、`meta_generation=1`、`last_stage=12 KERNEL_INIT`、`rule=initcalls` |
| 回滚 | 13:52:34 `ROLLBACK_VERIFIED`；13:52:58 二次核验 adb 在线、原厂内核 |

### 2.1 三态 FDT 头对照（决定性证据）

| 状态 | `nonzero` | magic | totalsize | model 字符串 |
|---|---|---|---|---|
| 原厂基线（不刷机） | 31,506 | `0xd00dfeed` | 410,405 | @108 |
| Round 12 未裁剪候选失败态 | **0** | 0 | 0 | 无 |
| **Round 13 裁剪候选失败态** | **31,502** | **`0xd00dfeed`** | **410,533** | @108 |

`410,533 − 410,405 = 128` B，正好是 `blm-ram-log` 节点的 128 B ⇒ 运行期 DTB 确实包含 BLM 节点且结构完整，aboot 搬运与内核早期解析都正常。同一地址、同一工具、同一 programmer，唯一差别是内核是否裁剪 ⇒ **BSS 清零覆盖 DTB 是 Round 10/11/12 卡在阶段 3 的原因**，本次修复生效。

### 2.2 BLM 阶段序列（从 3 推进到 12）

```
START_KERNEL → BEFORE_SETUP_ARCH → SETUP_ARCH_ENTER → FDT_SCAN_DONE
→ EARLY_IOREMAP → PAGING_INIT → UNFLATTEN_DT → AFTER_SETUP_ARCH
→ CONSOLE_INIT → CONSOLE_REGISTERED → REST_INIT → KERNEL_INIT
```

`bank0 gen=1`、`stages=12`、`lines=2`（`BLM monitor init` / `BLM memblock reserve`）。判定 `rule=initcalls`：失败落在 `kernel_init` 之后的 `do_basic_setup()` / initcalls / `prepare_namespace()` / rootfs / Android ramdisk 一带。

此前 10 次全部停在阶段 3；这是**首次越过 DTB 扫描、MMU 初始化、设备树展开、console 注册**。

## 3. 证据边界

- [O]：FDT 头恢复有效、12 个阶段标记（每个都过 magic+CRC+build_tag 校验）、设备 t=85 s 进 9008、回滚验证。
- [H]：具体卡在哪个 initcall / 驱动 probe / 挂载步骤。判定器的 `rule=initcalls` 是按最后阶段做的分类，不是 PC；没有采集到 PC、没有 earlycon 文本、没有 `dmesg`。
- **异常观察未闭环**：`CONSOLE_REGISTERED`（阶段 10）之后行槽仍只有 2 行，`BLM memblock reserve` 之后没有任何 printk 被捕获。原因未查（可能是 printk 未流入 BLM console、行槽写入路径在 initcall 阶段失效，或失败发生在 console 真正可用前）。因此不能据「没有错误文本」推断「内核无报错」。
- 设备进 9008 而非 adb，说明启动在 `kernel_init` 之后失败并触发重启/watchdog 路径；具体触发点未知。

## 4. 假设表更新

| # | 假设 | 状态 |
|---|---|---|
| 1 | `blm-ram-log` 节点引入故障 | 已排除 [O]（Round 11 A/B） |
| 2 | `0x42000000` FDT 内容无效 | **已定位并修复 [O]**：BSS 覆盖 DTB；裁剪后 FDT 恢复合法、阶段推进到 12 |
| 3 | `122→80` 链尾零布局 | 不再是早期阶段瓶颈（已走过 FDT_SCAN_DONE / UNFLATTEN_DT），但对后期是否仍有影响未验证 |
| 4 | `phys_to_virt` / 线性映射 | 已排除 [O]（走过 PAGING_INIT） |
| 5 | x0 / SCM / TZ 交接 | 已排除为早期瓶颈 [O]（内核已到 kernel_init） |
| 6 | **新瓶颈：initcalls / 驱动 probe / rootfs / ramdisk / FBE** | **当前首要嫌疑，未定位** |

## 5. 下一步（按成本，均未执行）

1. **修 BLM 行槽捕获**：查清 `CONSOLE_REGISTERED` 之后为何没有 printk 进入行槽（检查 `blm_console` 的 `CON_PRINTBUFFER`/`CON_ENABLED` 标志、`register_console` 顺序、`printk` 是否被 `console_loglevel` 过滤）。这是最便宜的一步——一旦能拿到 initcall 阶段的 printk，很可能直接看到失败原因。
2. **加细粒度阶段插桩**：在 `kernel_init_freeable()` 内 `do_basic_setup()`、`prepare_namespace()`、`init_post()` 前后，以及 `run_init_process()` 处加 BLM 阶段标记，把窗口从「阶段 12 之后」收窄。
3. **用 `blm_watchdog_secs` 主动 panic**：在候选内核 cmdline 加 `blm_watchdog_secs=N`，让看门狗在卡住时 panic 并把 panic 文本写进 BLM 日志区，可能带出调用栈。
4. **stock vs custom 逐项对照**：`ramdisk` 的 `fstab` / `init.rc`、vendor 挂载、FBE/keymint/vold 启动依赖，以及裁剪掉的 39 项配置是否影响某个必需驱动。
5. **临时扩大日志缓冲**：本轮把 `LOG_BUF_SHIFT` 降到 16 以腾出空间；若行槽问题与 printk 有关，可评估在保持 `_end < 0x42000000` 的前提下回调到 17（余量 1.97 MiB，仍有空间）。

## 6. 未执行 / 设备状态

未修 BLM 行槽、未加细粒度插桩、未做第 14 次实验、未采集 PC/earlycon/dmesg、未验证 warm reset 跨本轮保留性。**设备当前为原厂系统** `3.18.71-perf-g8a8c60dd` / LOS16，13:52:58 二次核验 adb 在线、fastboot 已退出。

## 7. 证据文件

`flash_log/fdt_round13.bin`、`flash_log/blm_ram_round13.bin`、`flash_log/blm_ram_round13.forensics.json`、`flash_log/20261114_blm_round13_timeline.txt`、`images/boot_los16_blm_shrink_20261114133000.img`、`images/boot_los16_blm_shrink_20261114133000.preflight.json`、`ROUND12_ROOT_CAUSE.md`、`SHRINK_BUILD_DELIVERY.md`。
