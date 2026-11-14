# ROUND 16 · 固定槽探针：卡点改判为 `qpnp_vibrator_init`

日期：2026-11-14 14:49–15:08
性质：第 16 次实机（重编译内核，新增固定 trace 槽与 `usb_bam_probe` 里程碑）
设备最终状态：原厂 `3.18.71-perf-g8a8c60dd` / LOS16，`ROLLBACK_VERIFIED`

---

## 1. 一句话结论

**固定槽证明最后进入的 initcall 是 `qpnp_vibrator_init`（`0xffffffc00184c050`），而 12 个 `usb_bam_probe` 里程碑一个都没触发 ⇒ `usb_bam` 注册早已返回，Round 14/15 的「卡在 usb_bam probe」是基于环形行槽最后一条记录造成的误判。真正卡点在 `spmi_driver_register(&qpnp_vibrator_driver)` 或其同步 probe。**

---

## 2. 为什么要做固定槽

Round 15 的 watchdog panic 把 384 个行槽冲满（`IC_ENTRIES=0`），Round 14 的「最后一条 IC」也只是环形缓冲里恰好未被覆盖的最后一行。两者都不是可靠的「最后一个 initcall」。

本轮改动（`BLM` 布局版本仍为 v1，旧 dump 完全兼容）：

- 行槽 `[0,16)` 预留给**固定位置里程碑**：`blm_trace_note(id, tag, val)` 写 `TRC <tag> <16hex>\n` 到 `idx=id`，`seq = 0xF0000000 | id`（强制排在普通行之后）；
- 普通 printk / initcall 文本只用 `[16,384)`：`idx = 16 + seq % 368`；
- `do_one_initcall()` 每次覆盖写 `id=0`，因此 **槽 0 永远是最后进入的 initcall**，任何 printk 洪水都冲不掉；
- `blm_watchdog_fn()` 写 `id=15` 快照；
- `usb_bam_probe()` / `enable_usb_bam()` 内 11 个点写 `id=1..11`（`BAM_ENTER`、DT 解析前后、workqueue、`enable_usb_bam` 前后、IPA 分支前后、`usb_bam_init` 前后等）；
- 新增 `tools/blm_trace_report.py` 解析固定槽并列出「到达 / 缺失」。

补丁器新增 `patch_usb_bam()`，从 `fixtures/usb_bam.c.orig` 生成 `drivers/platform/msm/usb_bam.c`；`KERNEL_PATCH_OK status=OK outputs=8`，12 个插桩点全部 `inserted`，`SELFCHECK_OK`。

---

## 3. 镜像与实机（[O]）

| 项 | 值 |
|---|---|
| 镜像 | `images/boot_los16_blm_probe_20261114150000.img` |
| sha256 / 大小 | `9b11acf147fff661c49bf9871dcce9d29bdef7b88c709697d04d176e7a7dc106` / 58,483,968 B |
| 构建 | `KERNEL_BUILD_OK`，`MAKE_IMAGE_RC=0`，9 个 BLM 符号，C6 全 0 |
| 自检 / 预检 | `40/40 PASS`；`17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 与 Round 15 差异 | 内核重编译（新增插桩）+ 不加 `blm_watchdog_secs`；DTB 链/ramdisk/签名/头部布局不变 |

过程：15:03:58 一次 `Sending/Writing OKAY` + reboot（本次未出现端点瞬断）；t=60 s 自动进 `9008 (COM5)`；15:05:47 读回 `blm_ram_round16.bin`（262,144 B，`nonzero=108903`，sha256 `620b1c78…`，4/4 块 `failed_blocks=0`，不带 reset）；15:06:17 `power reset` ACK；15:07:07 用户手动进 fastboot 接上；15:07:09 刷原厂 `929fda99…`；15:08:00 `ROLLBACK_VERIFIED`。

时间线：`flash_log/20261114_blm_round16_timeline.txt`

---

## 4. 判定结果（[O]）

```
bank_count=1  gen=1  last_stage=12 KERNEL_INIT  rule=initcalls
lines=360  IC_ENTRIES=191
--- fixed trace slots ---
  id=00 LAST_INITCALL  tag=IC  val=0xffffffc00184c050  -> qpnp_vibrator_init+0x0
MISSING_SLOTS [1,2,3,4,5,6,7,8,9,10,11,15]
LAST_BAM_MILESTONE none (probe not entered)
```

最后几条普通 IC 行（与固定槽一致）：

```
seq=1569 0xffffffc00184bff0 -> qpnp_haptic_init
seq=1570 0xffffffc00184c00c -> gpio_usbdetect_driver_init
seq=1571 0xffffffc00184c02c -> init            (= usb_bam_driver 注册)
seq=1572 0xffffffc00184c050 -> qpnp_vibrator_init
seq=4026531840 TRC IC ffffffc00184c050          (= 固定槽 0，最后 initcall)
```

关键推论：

1. `0xffffffc00184c02c`（`__platform_driver_register(&usb_bam_driver)`）**之后还有一条 initcall 被进入** ⇒ 该注册已返回；
2. `id=1..11` 全空 ⇒ `usb_bam_probe()` 在本轮启动中**从未被调用**（platform device 未匹配），因此不可能是卡点；
3. `avtimer_init` (`0xffffffc00184c06c`)、`msm_11ad_driver_init`、`clock_late_init` (`0xffffffc00184c0f4`) 均未进入 ⇒ 卡在 `qpnp_vibrator_init` 内部；
4. 阶段仍停 `KERNEL_INIT`，`INITCALLS_DONE` 未到，无 panic 文本（本轮未加 watchdog）。

**Round 14/15 误判的技术原因**：行槽是 384 个环形槽，`blm_line_write()` 的 `idx = seq % 384`；Round 14 恰好读完 191 条 IC 后没有更多 printk，最后一条被读回的是 `0x184c02c`，而实际 `qpnp_vibrator_init` 的记录可能在那次启动里因 CRC/时序未落槽，或被后续输出覆盖。固定槽 0 消除了这个不确定性。

---

## 5. 离线反汇编（`probe-20261114150000/vmlinux`，[O]）

```
ffffffc00184c050 <qpnp_vibrator_init>:
    stp  x29, x30, [sp,#-16]!
    adrp x0, ffffffc001b08000
    mov  x29, sp
    add  x0, x0, #0xf10          ; x0 = 0xffffffc001b08f10 = qpnp_vibrator_driver
    bl   ffffffc000aa62f0 <spmi_driver_register>
    ldp  x29, x30, [sp],#16
    ret
```

即 `qpnp_vibrator_init()` 只做 `spmi_driver_register(&qpnp_vibrator_driver)`（SPMI 总线驱动注册，同步触发 probe）。

`qpnp_vibrator_probe` (`0xffffffc000b78308`) 的调用列表：

| 次数 | 调用 |
|---|---|
| 6 | `dev_err` |
| 5 | `of_property_read_u32_array` |
| 4 | `__pi_strcmp` |
| 2 | `spmi_ext_register_readl` / `qpnp_vib_write_u8.isra.5` |
| 1 | `timed_output_dev_register` / `pwm_request` / `hrtimer_init` / `devm_kmalloc` / `__mutex_init` / `spmi_get_resource` / `warn_slowpath_null` 等 |

⇒ [H] 卡点最可能是 **`spmi_driver_register()` 的同步 probe 在 SPMI 寄存器读（`spmi_ext_register_readl`）或 `pwm_request` 上阻塞**，也可能 SPMI 总线本身在此时未就绪。日志里此前已有 `spi_qsd ... unable to get core_clk`、`scm_call failed: func id 0x42000c02, ret: -2`，说明 SPMI/时钟/ SCM 资源存在缺失，但因果关系未验证。

---

## 6. 证据边界

| 结论 | 等级 |
|---|---|
| 最后进入的 initcall = `qpnp_vibrator_init` | [O] 固定槽 0，CRC 自校验 |
| `usb_bam` 注册已返回、`usb_bam_probe` 未调用 | [O] 后续 IC + 12 个里程碑全空 |
| `qpnp_vibrator_init` = `spmi_driver_register(qpnp_vibrator_driver)` | [O] 反汇编 |
| probe 调用 `spmi_ext_register_readl` / `pwm_request` | [O] 反汇编 |
| 「卡在 SPMI 读 / PWM 请求 / 总线锁」 | [H]，无 PC、无 probe 内插桩 |
| Round 14/15 的 usb_bam 归因 | **已被本轮 [O] 推翻** |

---

## 7. 下一步（按成本排序，均未执行）

1. **在 `qpnp_vibrator_probe()` 内插桩**（源码 `drivers/platform/msm/qpnp-vibrator.c`，已在编译树中）：在 `spmi_ext_register_readl`、`pwm_request`、`timed_output_dev_register` 前后写固定槽 `id=1..8`，直接定位卡点；同时保留槽 0 的 last-initcall。
2. **检查 probe 是否被调用**：若 probe 里程碑也全空，则卡在 `spmi_driver_register()` 内部（总线/设备匹配），转查 SPMI 控制器与 DT 节点。
3. **DT / 资源对照**：`122→80` 链尾零是否影响 `qpnp-vibrator` 相关节点；原厂 DTB 与候选 DTB 的 `qcom,qpnp-vibrator` 节点、PWM/SPMI 资源差异。
4. **stock 3.18.71 对照**：原厂是否同样注册该驱动、是否有 DT 节点差异或时序差异。

---

## 8. 未执行

`qpnp_vibrator_probe` 插桩重编译、SPMI/DT 差分、stock 同驱动对照、第 17 次实机。本轮未改动既有 ROUND 文档；修改的工程文件：`kernel/bootloop_monitor.c`、`kernel/bootloop_monitor.h`、`tools/blm_apply_kernel_patch.py`、`tools/blm_trace_build.sh`，新增 `tools/blm_trace_report.py`、`tools/blm_probe_inspect.sh`、`fixtures/usb_bam.c.orig`。全套 `build_selfcheck.sh` 复跑 `SELFCHECK_OK`。

**工程教训**：任何基于「环形行槽最后一条」的归因都可能被覆盖/CRC 偏差误导；关键 last-known-good 点必须写固定槽。前两轮的 `usb_bam` 结论应以此轮为准。
