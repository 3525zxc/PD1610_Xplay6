# ROUND 15 · watchdog panic 抓栈结果与 IPA 线索

日期：2026-11-14 14:28–14:44
性质：第 15 次实机（不重编译内核，只改 boot.img header cmdline）+ 离线反汇编
设备最终状态：原厂 `3.18.71-perf-g8a8c60dd` / LOS16，`ROLLBACK_VERIFIED`

---

## 1. 一句话结论

**`blm_watchdog_secs=20` 生效并成功触发 panic，但只抓到 CPU2 的 idle 栈，没有抓到 CPU0 上卡在 `usb_bam_probe` 的栈**；panic 日志与 `usb_bam_probe` 反汇编共同把嫌疑收窄到 **IPA 依赖 / 关中断写锁自旋**。这是 [O] 现象 + [H] 机制，未采集到 CPU0 的 PC。

---

## 2. 离线前置（[O]）

### 2.1 cmdline 通路验证

原厂 `adb root` 后 `cat /proc/cmdline` 实测包含 boot.img header 的全部原文：

```
sched_enable_hmp=1 ... kpti=1 console=null androidboot.console=ttyHSL0
androidboot.hardware=qcom user_debug=31 msm_rtb.filter=0x237 ...
androidboot.securebootkeyver=2 androidboot.selinux=permissive ...
androidboot.bootdevice=624000.ufshc androidboot.verifiedbootstate=orange ...
```

⇒ aboot 确实把 header cmdline 传给内核（并前后追加自己的参数），追加 `blm_watchdog_secs=20` 可生效。这也进一步坐实 Round 14 的 `console=null` 诊断。

### 2.2 config 差分

基准 `config_los16_blm.txt` vs 追踪内核 `config_los16_blm_trace.txt`：3884 个键、74 项差异，全部是调试/追踪/符号表/日志缓冲/测试模块（`DEBUG_INFO y→n`、`FTRACE y→n`、`KALLSYMS_ALL y→n`、`LOG_BUF_SHIFT 20→16`、若干 `=m → n`）。

`CONFIG_USB_BAM=y`、`CONFIG_SPS=y`、`CONFIG_SPS_SUPPORT_NDP_BAM=y`、`CONFIG_RMNET_IPA=y`、`CONFIG_RNDIS_IPA=y`、`CONFIG_USB_DWC3_MSM=y`、`CONFIG_MSM_SCM=y` 全部保留 ⇒ **排除「裁剪动到 usb_bam 依赖」**。

### 2.3 镜像（严格单变量）

`blm_build_bootimg.py` 新增 `--append-cmdline`，把 token 追加到 v0 header 的 `cmdline` 字段 `[0x40,0x240)`，并把 `header unchanged except id` 检查改为条件化（仍 40 项）。

| 项 | 值 |
|---|---|
| 产物 | `images/boot_los16_blm_watchdog20.img` |
| sha256 / 大小 | `5f18f41d5057b682e53581d2df9a93bd3d5f8d41f337079e1b29314cbfac2afa` / 58,483,968 B |
| 自检 | `BOOTIMG_BUILD_OK 40/40 PASS` |
| 预检 | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 与 Round 14 追踪镜像差异 | **仅 21 字节** `[0x213,0x227)` = ` blm_watchdog_secs=20`；header id 相同；内核/ramdisk/DTB/签名/尾零全同 |

---

## 3. 实机过程（[O]）

| 时间 | 事件 |
|---|---|
| 14:33:57 | 首次 flash：`Sending OKAY` 但 `Writing FAILED (usb_read failed: ...31)`，`FLASH_FAIL_STOP`，未 reboot |
| 14:34:33–14:35:14 | 端点恢复尝试：`getvar` 三次超时（121），`retry_flash_1` 报端点不存在（433） |
| 14:38:35 | `retry_flash_2` 等设备约 3 分钟后 `Sending/Writing OKAY` + `reboot OKAY`（完整写入覆盖首次半成品） |
| 14:40:23 | t=80 s 自动进 `9008 (COM5)`，`adb_seen=False` |
| 14:40:52 | BLM 日志 4/4 块读回，262,144 B，`nonzero=111538`，sha256 `66662112…`，**不带 `--reset`** |
| 14:41:30 | `power value=reset` ACK |
| 14:42:56 | 用户手动进 fastboot，脚本在 t=85 s 接上 |
| 14:42:58 | 原厂 `boot.img`（sha `929fda99…`）`Sending/Writing OKAY` + reboot |
| 14:43:48 | `ROLLBACK_VERIFIED`：`3.18.71-perf-g8a8c60dd` / LOS16 |

时间线：`flash_log/20261114_blm_round15_timeline.txt`

---

## 4. watchdog 生效证据（[O]）

```
bank_count=1  meta_generation=1  selected_bank=0
fdt_phys=0x42000000  log_phys=0x42100000  ddr_hint=0x40000000
last_stage=17 WATCHDOG_PANIC      rule=kernel_oops
stage_seq=BEFORE_SETUP_ARCH,SETUP_ARCH_ENTER,FDT_SCAN_DONE,EARLY_IOREMAP,
          PAGING_INIT,UNFLATTEN_DT,AFTER_SETUP_ARCH,CONSOLE_INIT,
          CONSOLE_REGISTERED,REST_INIT,KERNEL_INIT,PANIC_ENTER,WATCHDOG_PANIC
lines=363  IC_ENTRIES=0  PRINTK_LINES=363
```

- `PANIC_ENTER` + `WATCHDOG_PANIC` 两个阶段均到达 ⇒ `blm_watchdog_fn()` 执行，`panic()` 被调用。
- panic 输出时间戳 `[20.070xxx]`，与 `blm_watchdog_secs=20` 精确吻合 ⇒ **early_param 解析成功**。
- `[21.432568] Rebooting in 5 seconds..` → `[27.801770] Going down for restart now` ⇒ `panic_timeout=5`，内核主动重启；这解释了「watchdog 实验里设备多次 bootloop 后 t=80 s 进 9008」。
- 日志里大量 `LR: 0x...:` / `SP: 0x...:` 十六进制寄存器与栈 dump，把 384 个行槽冲满 ⇒ **IC 记录与早期里程碑全部被覆盖**（`IC_ENTRIES=0`）。这是本轮的新工程缺口。

---

## 5. 为什么没抓到 CPU0 的栈（[O] + [H]）

抓到的唯一 `Call Trace` 是：

```
CPU: 2 PID: 0 Comm: swapper/2 Not tainted 3.18.120-perf #2
Hardware name: vivo MSM 8996 v3 + PMI8996 PD1610 (DT)
[<ffffffc000208494>] dump_backtrace+0x0/0x240
[<ffffffc0002086e8>] show_stack+0x14/0x1c
[<ffffffc000e94b20>] dump_stack+0x84/0xa8
[<ffffffc00020d920>] handle_IPI+0x1a0/0x334
[<ffffffc000200704>] gic_handle_irq+0xb4/0xd0
[<ffffffc000203f3c>] el1_irq+0x7c/0xf0
[<ffffffc000266654>] cpu_startup_entry+0x214/0x348
[<ffffffc00020d268>] secondary_start_kernel+0x120/0x12c
```

这是 **CPU2 在 idle loop 被 IPI 打断**打印的栈，不是卡在 initcall 的 CPU0。`panic()` 只 dump 当前 CPU，并通过 IPI 要求其它 CPU 打印；CPU0 没有出现，配合 `[21.431435] SMP: failed to stop secondary CPUs`，**[H] 说明 CPU0 处于关中断 / 不可中断自旋状态**。

`_raw_write_lock_irqsave` 会关中断后自旋等锁，与这个现象相容（见 §6）。

---

## 6. 新线索：IPA / uC 未加载（[O] 现象，[H] 因果）

panic notifier 输出：

```
[21.431494] msm_bus_panic_callback: fab-a2noc: active max_ib: 960000000: client-name: ipa
[21.432451] ipa ipa2_active_clients_panic_notifier:311
[21.432451] ---- Active Clients Table ----
[21.432451] Total active clients count: 1
[21.432527] ipa ipa2_uc_state_check:301 uC is not loaded
```

`usb_bam_probe` 反汇编（`0xffffffc000b77ab4..0xffffffc000b78d38`，共 1192 行指令）的完整调用列表：

| 次数 | 调用 |
|---|---|
| 19 | `of_property_read_u32_array` |
| 18 | `printk` / `put_timestamp` / `_raw_write_lock_irqsave` |
| 9 | `snprintf` |
| 7 | `_raw_write_unlock_irqrestore` |
| 4 | `warn_slowpath_null` / `of_get_next_child` / `of_find_property` / `devm_kmalloc` |
| 2 | `strcpy` / `ipa_rm_create_resource` / `dev_err` / `complete` / `__init_waitqueue_head` |
| 1 | `usb_bam_init.isra.16` / `ipa_is_ready` / `ipa_get_transport_type` / `usb_bam_register_panic_hdlr` / `platform_get_irq` / `devm_ioremap` / `pm_runtime_enable` / `__alloc_workqueue_key` / `destroy_workqueue` / `__mutex_init` 等 |

要点：

- probe 明确调用 **`ipa_is_ready()`、`ipa_get_transport_type()`、`ipa_rm_create_resource()` ×2、`usb_bam_init()`**，即 `usb_bam` 与 IPA 资源管理器强耦合；
- 有 `complete` / `__init_waitqueue_head`（completion 初始化与发信号），但**没有** `wait_for_completion` / `msleep` / `scm_call` 的直接调用（等待可能发生在被调函数内部）；
- `write_lock_irqsave` 18 次、`write_unlock_irqrestore` 7 次，且末尾有一条向后跳转 `b 0xffffffc000b78ab0`（遍历 DT 子节点的循环）；
- ⇒ [H] 卡点最可能是 **`ipa_is_ready()` / `usb_bam_init()` 内部的 IPA 就绪等待**，或 **关中断写锁自旋**；两者都与「CPU0 不响应 IPI」相容。

`ipa2_uc_state_check: uC is not loaded` 出现在 panic notifier 阶段，**不能直接断言它就是 probe 卡住的原因**（uC 未加载在正常启动也可能出现），但它是目前最值得优先验证的方向。

---

## 7. 工程改进点（本轮暴露）

1. **行槽被 panic 的寄存器 dump 冲满**：363 行里 `IC_ENTRIES=0`、`BLM_TAGS=0`，Round 14 的 initcall 追踪信息全部丢失。后续若再用 watchdog，需要给 trace 单独开一块不参与环形覆盖的区域，或在 `blm_watchdog_fn()` 里先把「最后 IC / 当前阶段」快照到固定位置。
2. **fastboot USB 端点瞬断**：首次 `Writing FAILED (31)`、重试 1 报 433，重试 2 等待约 3 分钟后成功。刷机脚本应内建「失败后重试 + 等待设备重新枚举」，且失败后不得 reboot；本轮已按此处理。
3. **`power value=reset` 后仍需现场手动进 fastboot**（t=85 s 用户手动接上）。firehose `power value=fastboot` 的 NAK 结论再次确认。
4. panic 后 `panic_timeout=5` 会主动重启，多次循环后才进 9008；`meta_generation=1` / `bank_count=1` 说明最终读回的是最后一次启动的日志，之前的 panic 记录疑似被 reboot 清掉。

---

## 8. 证据边界

| 结论 | 等级 |
|---|---|
| `blm_watchdog_secs=20` 生效、20 s 触发 panic、阶段 17 | [O] |
| header cmdline 追加只带来 21 字节差异、id 不变 | [O] |
| panic 后 `Rebooting in 5 seconds..` 与 bootloop 循环 | [O] |
| 抓到的 Call Trace 是 CPU2 idle，CPU0 未响应 IPI | [O]（前者）/ [H]（后者推论） |
| `usb_bam_probe` 调用 `ipa_is_ready` / `ipa_rm_create_resource` / `usb_bam_init` / 多处 `write_lock_irqsave` | [O] 反汇编 |
| 「卡在 IPA 就绪等待或关中断写锁自旋」 | [H]，未采集 CPU0 PC |
| `ipa2_uc_state_check: uC is not loaded` 与卡死的因果关系 | [H]，未验证 |

---

## 9. 下一步（按成本排序，均未执行）

1. **在 `usb_bam_probe()` 内加里程碑**（需重编译，最确定）：在 `ipa_is_ready()` 前、`ipa_rm_create_resource()` 前后、`usb_bam_init()` 前后、每个 `write_lock_irqsave` 前后写 `blm_write_text`，直接定位卡在哪一步；同时把 trace 写入独立固定槽，避免被 panic dump 冲掉。
2. **给 `blm_watchdog_fn()` 加 CPU0 栈抓取**：panic 前用 `smp_call_function_single(0, dump_stack, ...)` 或 `show_stack()` 对 `kernel_init` 任务；若 CPU0 关中断则仍会失败，这本身也是结论。
3. **对照 stock 3.18.71**：原厂内核同驱动是否同样调用 `ipa_is_ready()`、DT 节点与 IPA uC 加载时序差异。
4. **验证 IPA 假设**：若确认卡在 IPA 就绪，检查 `122→80` DTB 链 / 尾零是否影响 IPA 相关 DT 节点，或自编译 3.18.120 与原厂 3.18.71 的 IPA 驱动语义差异。

---

## 10. 未执行

`usb_bam_probe` 插桩重编译、CPU0 栈主动抓取、stock 同驱动对照、IPA 假设验证、第 16 次实机。本轮未改动既有 ROUND 文档，未改原 WSL 源码树；只修改了 `tools/blm_build_bootimg.py`（新增 `--append-cmdline`，默认行为不变）。修改后已复跑全套 `build_selfcheck.sh` → `SELFCHECK_OK`；镜像报告 `PASS 40/40`、预检报告 `PASS 17/17 SAFE_TO_FLASH`。
