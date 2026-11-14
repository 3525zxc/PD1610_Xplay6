# ROUND 14 · initcall 追踪与 printk 捕获修复结果

日期：2026-11-14 14:04–14:14
性质：第 14 次实机 + 离线修复；不改动既有 ROUND 文档
设备最终状态：原厂 `3.18.71-perf-g8a8c60dd` / LOS16，`ROLLBACK_VERIFIED`

---

## 1. 一句话结论

**「CONSOLE_REGISTERED 之后收不到 printk」是取证工具自身的缺陷，已修复；修复后第 14 次实机把失败点从「`kernel_init` 之后」进一步钉死到 `do_basic_setup()` 的 initcalls 中：`usb_bam` platform driver 的 probe 没有返回。**

这仍是「失败窗口」意义上的定位，不是采集到 PC 或 panic 调用栈。见 §8 证据边界。

---

## 2. 先修好的观测缺陷（离线，[O]）

### 2.1 根因

`kernel/printk/printk.c:2536`（3.18.120 源码树实测）：

```c
if (!(newcon->flags & CON_ENABLED))
        return;
```

`register_console()` 里只有两条路径会置 `CON_ENABLED`：

1. `preferred_console < 0` 时取第一个注册的 console（`printk.c:2488-2502`）；
2. console 名字与 `console_cmdline[]` 中某项匹配（`printk.c:2506-2533`）。

本机 `blm_console` 原定义：

```c
.flags = CON_PRINTBUFFER,   /* 缺少 CON_ENABLED */
.name  = "blm",
```

而原厂 `boot.img` header `[64,576)` 的 cmdline 实测为：

```
console=null androidboot.console=ttyHSL0 androidboot.hardware=qcom user_debug=31
msm_rtb.filter=0x237 ehci-hcd.park=3 lpm_levels.sleep_disabled=1
cma=32M@0-0xffffffff product.version=PD1610_D_8.19.16 ...
```

即 `console=null`，`preferred_console` 已定值、`console_cmdline` 只认 `null`。名字为 `blm` 且未置 `CON_ENABLED` 的 console 被 `printk.c:2536` **静默丢弃**：`blm_console_init()` 仍执行并打了 `CONSOLE_REGISTERED` 阶段卡，但 console 从未进入 `console_drivers` 链，`call_console_drivers()`（`:1422-1431`）永远跳过它。

这也解释了为何原厂自身 printk 全被吞掉（`console=null`）。`/proc/sys/kernel/printk = 7 7 7 7`，不是日志级别被压制。

### 2.2 修复

`kernel/bootloop_monitor.c`：

```c
.flags = CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER,
```

- `CON_ENABLED`：绕过 `printk.c:2536` 门槛，成为真实 printk 接收端；
- `CON_ANYTIME`：panic / CPU offline 时仍能收到（`call_console_drivers` 的 `:1429-1430`）；
- `CON_PRINTBUFFER`：注册时回放此前缓冲的 printk；
- 未设 `CON_CONSDEV`，不抢 `/dev/console` 首选；
- `blm_console_init()` 增写一行 `BLM console enabled` / `BLM console NOT enabled`，把注册结果直接写进日志。

### 2.3 新增 initcall 追踪

- `blm_note_initcall(unsigned long fn)`：手写 16 进制编码，把每个 initcall 入口写成 `IC <16 hex>\n` 行槽记录（不依赖 `snprintf`，可在 printk 上下文调用）。
- `tools/blm_apply_kernel_patch.py` 在 `do_one_initcall()` 的局部变量声明之后插入 `blm_note_initcall((unsigned long)fn);`，并在 `kernel_init_freeable()` 里加 10 个文本里程碑（`pre_smp_initcalls` / `smp_init` / `sched_init_smp` / `do_basic_setup` 进出 / `ramdisk_execute_command` 检查 / `prepare_namespace` 进出 / `kernel_init_freeable done`）。
- 布局（v1）、阶段编号、判定规则、DTB 节点、镜像打包格式**全部不变**，旧 dump 仍可读。
- 新增 `tools/blm_initcall_report.py`：把 `IC` 地址用 `System.map` 反查为 `symbol+offset`，输出最后 N 条与疑似卡住点。

---

## 3. 第 14 次实机过程（[O]）

| 时间 | 事件 |
|---|---|
| 14:04:23 | 起始 adb 未在线；候选镜像 sha256 `5400e85d…`；预检 `17/17 SAFE_TO_FLASH` |
| 14:07:11 | 等设备约 2 分 48 秒后出现 `5fccbfeb fastboot`，`getvar product = QC_REFERENCE_PHONE` |
| 14:07:13 | `flash boot` `Sending/Writing OKAY`，`reboot OKAY` |
| 14:08:27 | t=60 s 自动进 `9008 (COM5)`，`adb_seen=False` |
| 14:08:48 | FDT 头 peek：`nonzero=31504`，`head=d00dfeed 000643a5`，`failed_blocks=0` |
| 14:08:54 | BLM 日志 peek：4/4 块，262,144 B，`nonzero=93794`，sha256 `4698dae6…`，**不带 `--reset`** |
| 14:09:20 | `power value=fastboot` 被 programmer 回 `NAK`（不支持） |
| 14:10:03 | `power value=reset` ACK；设备复位回候选镜像持续 bootloop |
| 14:12:09 | 等 120 s 未出现 fastboot，`ROLLBACK_NOT_EXECUTED` |
| 14:13:17 | 用户手动进 fastboot，复查 `Android Bootloader Interface OK` |
| 14:13:50 | 原厂 `boot.img`（sha256 `929fda99…`）`Sending/Writing OKAY` + reboot |
| 14:14:40 | adb 上线，`3.18.71-perf-g8a8c60dd` / LOS16 / uptime 0 min，`ROLLBACK_VERIFIED` |

时间线：`flash_log/20261114_blm_round14_timeline.txt`

---

## 4. 失败现场（[O]）

```
bank_count=1  meta_generation=1  selected_bank=0
fdt_phys=0x42000000  log_phys=0x42100000  ddr_hint=0x40000000
last_stage=12 KERNEL_INIT      rule=initcalls
stage_seq=START_KERNEL,BEFORE_SETUP_ARCH,SETUP_ARCH_ENTER,FDT_SCAN_DONE,
          EARLY_IOREMAP,PAGING_INIT,UNFLATTEN_DT,AFTER_SETUP_ARCH,
          CONSOLE_INIT,CONSOLE_REGISTERED,REST_INIT,KERNEL_INIT
lines=377  IC_ENTRIES=191  PRINTK_LINES=185  BLM_TAGS=0
```

- `lines` 从 Round 13 的 **2 行** 变成 **377 行**：console 修复生效，printk/IC 真的进日志。
- `BLM_TAGS=0` 不是插桩失效：行槽是 384 个环形槽，最后一行 `seq=1571`，早期 `BLM monitor init` / `BLM console enabled` / `BLM do_basic_setup enter` 已被后续 1,500+ 行覆盖。
- 阶段 13 `INITCALLS_DONE` **未打**，说明 `do_basic_setup()` 尚未返回；阶段 14/15（rootfs / user init）从未开始。
- 没有 `Kernel panic`、没有 `Call trace`、没有 oops 文本；最后 printk 时间 `[1.577887]`，之后只有 4 条 IC 再无任何输出。设备 t=60 s 由 watchdog 复位进 9008。
- 日志里 UFS / SCSI / sda–sdf 分区、PCIe、crypto、camera、FG、SDHCI 等均已完成 probe，说明存储与大部分平台层初始化正常。

### 四态 FDT 头对照（`0x42000000`，同一工具/programmer）

| 状态 | nonzero | magic | totalsize |
|---|---|---|---|
| 原厂基线 | 31,506 | `d00dfeed` | 410,405 |
| R12 未裁剪失败态 | **0（全零）** | 0 | 0 |
| R13 裁剪后 | 31,502 | `d00dfeed` | 410,533 |
| **R14 追踪内核** | **31,504** | **`d00dfeed`** | **410,533** |

BSS 覆盖 DTB 的根因修复在 R14 依然成立，未复发。

---

## 5. 精确到函数（[O] 地址 / [H] 机制）

最后 4 条 initcall：

```
seq=1568 0xffffffc00184bd60 -> seemp_logk_init+0x0
seq=1569 0xffffffc00184bff0 -> qpnp_haptic_init+0x0
seq=1570 0xffffffc00184c00c -> gpio_usbdetect_driver_init+0x0
seq=1571 0xffffffc00184c02c -> init+0x0        ← 最后一条，之后无任何记录
```

`init` 在本树 `System.map` 有 3 个同名静态符号；`0xffffffc00184c02c` 的反汇编（`aarch64-linux-androidkernel-objdump`）：

```
ffffffc00184c02c <init>:
    stp  x29, x30, [sp,#-16]!
    adrp x0, ffffffc001b08000
    mov  x1, #0x0
    add  x0, x0, #0xe40
    mov  x29, sp
    add  x0, x0, #0x8          ; x0 = 0xffffffc001b08e48
    bl   ffffffc0006cc650 <__platform_driver_register>
    ldp  x29, x30, [sp],#16
    ret
```

用 `System.map` 反查 `0xffffffc001b08e48`：

```
0xffffffc001b08e40 enable_event_log
0xffffffc001b08e48 usb_bam_driver        ← 精确命中
0xffffffc001b08ef8 usb_bam_panic_blk
0xffffffc001b08f10 qpnp_vibrator_driver
```

⇒ 最后一个 initcall 是 **`usb_bam` 驱动的注册**（函数被编译器保留为通用名 `init`），它只做 `__platform_driver_register(&usb_bam_driver, NULL)`。`platform_driver_register` 会**同步**触发 `usb_bam_probe()`；`do_one_initcall()` 卡在 `ret = fn()` 里，因此没有返回、没有后续 IC、没有 `INITCALLS_DONE`、没有 panic 文本。

相邻未执行的 initcall 还有 `qpnp_vibrator_init`、`avtimer_init`、`msm_11ad_driver_init`、`clock_late_init` 等，说明失败发生在 initcall 序列末段但并非最后一个。

**机制仍是 [H]**：`usb_bam_probe()` 内部等什么（SPS/IPA/USB 时钟、SCM、DBM 设备、completion、`msleep`）未采集调用栈。日志里可见的相关线索（均非致命证据）：

- `[1.069993] scm_call failed: func id 0x42000c02, rat: -2`
- `[1.249...] msm-dwc3 6a00000.ssusb: unable to get dbm device`
- `[1.464068] msm_fd aa4000.qcom,fd: Face detection halt timeout`
- `[1.473384] unable to find DT imem DLOAD mode node`

UFS 后续正常枚举（`SAMSUNG KLUDG8J1CB-B0B1`、`sda..sdf`），故 SCM 失败至少不是全局致命。

---

## 6. 镜像与工程产物

| 项 | 值 |
|---|---|
| 追踪内核镜像 | `images/boot_los16_blm_trace_20261114140000.img` |
| sha256 / 大小 | `5400e85dd225d0537bd7d5c7b90e8ade4c473b684932fdc12c40f5b21a50354b` / 58,483,968 B |
| 构建自检 | `BOOTIMG_BUILD_OK 40/40 PASS` |
| 刷前预检 | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 内核构建 | `KERNEL_BUILD_OK tag=trace-20261114140000`，8 个 BLM 符号，C6 全 0，`MAKE_IMAGE_RC=0` |
| `Image.gz-dtb` | 55,942,234 B，sha256 `b0c55bd2…` |
| 布局 | gzip 10,708,788 + DTB 链 30,947,277 + 尾零 14,895,428；`log_phys=0x42100000` |

新增/修改文件：

- `kernel/bootloop_monitor.c`、`kernel/bootloop_monitor.h`
- `tools/blm_apply_kernel_patch.py`（10 个新插桩点）
- `tools/blm_initcall_report.py`（IC → 符号反查）
- `tools/blm_trace_build.sh`（增量编译）
- `tools/blm_firehose_power.py`（firehose `<power>` 命令，本次实测 `fastboot` NAK / `reset` ACK）
- `build/trace-20261114140000/`（内核产物与 `kernel_build.env`）
- `flash_log/blm_ram_round14.bin`、`fdt_round14.bin`、`blm_ram_round14.forensics.json`、`blm_ram_round14.initcalls.json`、`20261114_blm_round14_timeline.txt`

`build_selfcheck.sh` 修复后仍 `SELFCHECK_OK`；`blm_initcall_report.py` 对 Round 13 旧 dump 兼容（正确输出 `IC_ENTRIES=0`）。

---

## 7. 工程教训

1. **`power value=fastboot` 在本机 firehose programmer 上返回 NAK**，只有 `power value=reset` 可用。所以「双读后自动切 fastboot 回滚」这条路本机走不通；设备复位后仍回到候选镜像持续 bootloop，回滚依旧需要现场手动进一次 fastboot。
2. 双读**不带 `--reset`** 是可行的：设备停在 firehose，`--no-upload` 可继续发命令，DRAM 内容不丢。这给后续「多地址读取」留了通道。
3. 行槽 384 个环形槽在 console 修好后会被 1,500+ 行 printk 冲掉早期里程碑。若后续要保留里程碑，应单独开一个不参与环形覆盖的小区域或提高槽数。
4. 回滚文件始终是同一个原厂 `boot.img`（sha256 `929fda99…`）；用户在等待窗口看到的 bootloop 是候选镜像的表现，不是回滚刷错。

---

## 8. 证据边界

| 结论 | 等级 |
|---|---|
| `printk.c:2536` 的 `CON_ENABLED` 门槛与本机 `console=null` 导致 BLM console 被丢弃 | [O] 源码 + header 实测 |
| 修复后 printk 进入日志（2 行 → 377 行、191 条 IC） | [O] 实机 dump |
| 四态 FDT 头、BSS 覆盖根因修复持续有效 | [O] 实机双读 |
| 最后阶段 `KERNEL_INIT`、`INITCALLS_DONE` 未到达、无 panic 文本 | [O] 实机 dump |
| 最后一条 IC = `0xffffffc00184c02c`，反汇编为 `__platform_driver_register(&usb_bam_driver)` | [O] `System.map` + `objdump` |
| 「卡在 `usb_bam_probe()` 内部的某个等待」 | [H]，未采集 PC / 调用栈 |
| `scm_call failed` / `unable to get dbm device` 与卡死的因果关系 | [H]，未验证（UFS 后续正常） |

---

## 9. 下一步（按成本排序，均未执行）

1. **不重编译，拿调用栈**：在 boot.img header 的 `extra_cmdline` 追加 `blm_watchdog_secs=20`（BLM 已有 `early_param` 与 `panic()` 插桩）。20 秒后主动 panic，printk 会带出 `usb_bam_probe` 卡住时的调用栈；只需改 header + 重算 `id`，再跑一次第 15 次实机 + 双读。
2. **在 `usb_bam_probe()` 内加细粒度 `blm_write_text` 里程碑**（需重编译）：定位到具体等待点（SPS/IPA/SCM/DBM/completion）。
3. **config 差分**：核对 `build/trace-20261114140000/config_los16_blm_trace.txt` 与原厂/基准 config，确认裁剪是否动了 `usb_bam` 依赖（`CONFIG_SPS`、`CONFIG_IPA`、`CONFIG_USB_DWC3` 等）。
4. **stock vs custom 同驱动对照**：原厂 3.18.71 的 `usb_bam_probe` 行为与 DTB 节点差异；本工程原厂 DTB 已导出在 `fixtures/pd1610_81916_vivo.dtb`。
5. 若确认是私有驱动语义差异，回到「④ vivo 私有层」的逐模块重建路线；若只是 `122→80` 链尾零/配置差异，则属可修的工程变量。

---

## 10. 未执行

第 15 次实机、watchdog panic 镜像生成、`usb_bam_probe` 细粒度插桩、config 差分、stock 同驱动对照、直接读取 aboot DDR_BASE 全局 `0x91FFF990`。本轮未修改既有 ROUND/BRIEF/入口文档，未改动原 WSL 源码树（只在 `blm-shrink-20261114133000` 副本上增量编译）。
