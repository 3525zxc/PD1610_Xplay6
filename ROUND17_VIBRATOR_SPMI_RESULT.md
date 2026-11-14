# ROUND 17 · qpnp_vibrator 第一次 SPMI 读卡死（第 17 次实机结果）

日期：2026-11-14 16:13–16:25
状态：**实机闭环完成，设备已回滚并二次核验** `3.18.71-perf-g8a8c60dd` / LOS16
镜像：`images/boot_los16_blm_vib_20261114160500.img`，sha256 `47034aafbfc355d184b363c7bd5d390fe83f3319b0b43b7a55a2fbf582a174a2`
刷前门禁：现场重跑 `blm_preflight.py` → `PASS 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000`

---

## 1. 一句话结论

`qpnp_vibrator_probe()` **确实被调用**，DT 解析与 SPMI 资源获取全部成功（`base=0x5100`），然后卡在
`qpnp_vib_read_u8()` 内部的**第一次 `spmi_ext_register_readl()` 未返回**；
第二次 SPMI 读、`pwm_request`、config 返回、`timed_output_dev_register` 全部未到达。
这是 [O] 固定槽事实 + [H] 机制推论，**未采集 PC**。

---

## 2. 实机过程（含 USB 端点故障与恢复）

| 时间 | 事件 |
|---|---|
| 16:14:00 | 设备已在 fastboot `5fccbfeb`，`getvar product = QC_REFERENCE_PHONE`；候选/回滚哈希复核一致 |
| 16:14:30 | 首次刷候选：3 次重试全部 `FAILED`（`Sending OKAY` / `Writing FAILED(31)`、`121`）；**脚本按失败分支未 reboot** |
| 16:16:02 | 失败分支尝试刷回原厂，写入同样 `FAILED(121)`；设备**保持在 fastboot**，不重启 |
| 16:17–16:18 | `getvar` 连续 4 次 `121`；`pnputil /restart-device` 拒绝访问、`Disable-PnpDevice` 常规故障；端点仍不通 |
| 16:18:57 | 长间隔探测中端点**自行恢复**（`getvar` OK）；立即刷回原厂 `929fda99…` → `Sending/Writing OKAY` → reboot |
| 16:19:49 | `ROLLBACK_VERIFIED`：`3.18.71-perf-g8a8c60dd` / LOS16 |
| 16:20:18 | `adb reboot bootloader` → fastboot，端点一次探测即 OK |
| 16:20:20 | 候选一次写入成功（`Sending OKAY [1.513s]` / `Writing OKAY [0.388s]`）+ reboot |
| 16:21:38 | t=60 s 轮询检测到 `9008 (COM5)`，`adb_seen=False`（进入方式未现场确认） |
| 16:21:51–57 | 双读（**不复位**）：FDT 头 64 KiB `nonzero=31506`；BLM 256 KiB `nonzero=132636`，`failed_blocks=0` |
| 16:22:29 | `power value=reset` ACK |
| 16:23:20 | t=50 s 脚本轮询检测到 fastboot；**由用户现场手动进 fastboot**（脚本轮询无法区分自动/手动，以现场说明为准） |
| 16:23:22 | 原厂 boot 写入 `Sending/Writing OKAY` + reboot |
| 16:24:12 | `ROLLBACK_VERIFIED` |
| 16:25:10 | 二次核验：adb 在线、`3.18.71-perf-g8a8c60dd`、uptime 1 min、fastboot 已退出 |

> 工程教训补充：端点瞬断时**停在 fastboot 不重启**是安全做法；端点可自行恢复（本轮约 2 分钟），恢复后优先刷回原厂再继续实验。
> **本轮 `power reset` 后仍需用户手动进一次 fastboot，与前几轮一致**。`fastboot_ready t=50s` 只表示脚本在第 50 s 检测到端口，不代表设备自动进入；此前写成「自动出现、无需手动介入」是推断过头，已按现场说明更正。

---

## 3. 决定性结果：32 个固定槽

```
TRACE_REPORT bank=0 gen=1 last_stage=12(KERNEL_INIT) lines=356
  id=00 LAST_INITCALL   val=0xffffffc00184c050 -> qpnp_vibrator_init+0x0
  id=16 VIB_ENTER       val=0x0
  id=17 VIB_SPMI_SET    val=0x0
  id=18 VIB_RES_BEFORE  val=0x0
  id=19 VIB_RES_AFTER   val=0x5100          ← SPMI base 地址已正确取到
  id=20 VIB_DT_BEFORE   val=0x0
  id=21 VIB_CONFIG_BEFORE
  id=22 VIB_READ1                           ← 最后一个里程碑
MISSING_SLOTS [1..11, 15, 23, 24, 25, 26]
LAST_BAM_MILESTONE none (probe not entered)
LAST_VIB_MILESTONE id=22 VIB_READ1
VIB_SUSPECTED_WINDOW 第一次 SPMI 读 qpnp_vib_read_u8
```

- 12 个阶段全过：`START_KERNEL → … → CONSOLE_REGISTERED → REST_INIT → KERNEL_INIT`；`INITCALLS_DONE` 未打。
- 192 条 initcall、163 条 printk、356 行日志；最后 initcall 序列 `… qpnp_haptic_init → gpio_usbdetect_driver_init → init(usb_bam 注册) → qpnp_vibrator_init`。
- `usb_bam` 槽 1–11 仍全空 ⇒ 再次确认 Round 14/15 的 `usb_bam` 归因**作废**。
- 硬件 watchdog 在 `[20.341696] Watchdog bark!`、`last pet at 0.341283`、`Causing a watchdog bite!` ⇒ CPU0 自 0.34 s 起未喂狗近 20 s，与「卡在不可返回的 SPMI 读」相容。
- 无 panic、无 call trace、无 SPMI 控制器报错文本（probe 卡在读内部，未走到打印）。

### FDT 头三态对照（BSS 覆盖根因未复发）

| dump | nonzero | magic | totalsize |
|---|---|---|---|
| 原厂基线 `fdt_baseline_stock.bin` | 31,506 | `d00dfeed` | 410,405 |
| R14 `fdt_round14.bin` | 31,504 | `d00dfeed` | 410,533 |
| **R17 `fdt_round17.bin`** | **31,506** | **`d00dfeed`** | **410,533** |

`410,533 − 410,405 = 128 B` 仍是 BLM 节点，运行期 DTB 结构完整。

---

## 4. 卡点精确到源码行

`tests/patched_tree/drivers/platform/msm/qpnp-vibrator.c`：

```
:103  blm_trace_note(22, "VIB_READ1", 0);                    ← 最后写入
:104  rc = qpnp_vib_read_u8(vib, &reg, QPNP_VIB_VTG_CTL(vib->base));   ← 未返回
...
:115  blm_trace_note(23, "VIB_READ2", 0);                    ← 从未写入

:71   static int qpnp_vib_read_u8(struct qpnp_vib *vib, u8 *data, u16 reg)
:75       rc = spmi_ext_register_readl(vib->spmi->ctrl, vib->spmi->sid,
:76                                   reg, data, 1);
```

即失败窗口 = `spmi_ext_register_readl(ctrl, sid, QPNP_VIB_VTG_CTL(0x5100), &reg, 1)` 这一次 SPMI 扩展寄存器读。
`VIB_RES_AFTER val=0x5100` 证明 `spmi_get_resource` / `qpnp_vib_parse_dt` 均成功，地址与 DT 资源不是问题。

日志中可见但未验证因果的线索：`spi_qsd 75b9000.spi: init_resources: unable to get core_clk`、
`FG: fg_probe: FG Probe success - PMIC subtype=19`、`msm_fd … Face detection halt timeout`。

---

## 5. 与 `ROUND17_READY.md` 判据对照

| 判据 | 实测 | 结论 |
|---|---|---|
| 槽 16..26 全空 ⇒ probe 未调用 | 槽 16..22 全部命中 | **否**，probe 已调用 |
| 最后到 22、无 23 ⇒ 第一次 SPMI 读 | `LAST_VIB_MILESTONE=VIB_READ1`，23 缺失 | **命中** |
| 槽 0 不再是 `qpnp_vibrator_init` ⇒ 卡点后移 | 槽 0 仍是 `0x184c050` | **否**，卡点未后移 |
| 阶段到 `INITCALLS_DONE` / `ROOTFS_READY` | 停在 `KERNEL_INIT` (12) | **否**，未进 rootfs |

⇒ Round 16 的 [H]「卡在 SPMI 读或 PWM 请求」被收窄为**卡在第一次 SPMI 读**，PWM 分支被排除（尚未执行到）。

---

## 6. 证据边界

- [O]：固定槽 0/16–22 的 magic+CRC+build_tag 全过；`base=0x5100`；两态 FDT 头；watchdog bark 时间戳；12 阶段；回滚验证。
- [H]：`spmi_ext_register_readl()` 内部挂起（可能在 SPMI PMIC-ARB 控制器、总线时钟、TZ/SCM 权限、或等待完成量），**未采集 PC、未抓 SPMI 控制器寄存器、未做中断态快照**。
- 不能说「SPMI 总线坏了」：同 DTB 下 `qpnp-rtc`、`FG`、`qpnp_coincell` 等其他 SPMI/PMIC 设备均已成功 probe，说明总线整体可用，问题更可能是**该 vibrator 的特定 sid/base 组合或控制器状态**。
- 仍未排除：`122→80` DTB 链尾零、3.18.120 与原厂 3.18.71 的 SPMI 驱动语义差异。

---

## 7. 下一步（按成本排序，均未执行）

1. **绕过实验最便宜**：在候选 DTB 把 `qpnp-vibrator` 节点设为 `status = "disabled"`（或裁掉 `CONFIG_QPNP_VIBRATOR`），看内核能否越过该 initcall。若能，确认它是当前唯一瓶颈；若又卡在下一个 SPMI 设备，说明是 SPMI/PMIC 访问的共性问题。
2. **更细插桩**：在 `qpnp_vib_read_u8()` 内 `spmi_ext_register_readl` 前后各加固定槽，记录 `ctrl/sid/reg` 与返回值；若「前」有「后」无，直接坐实 SPMI 读内部挂起。
3. **DT 资源差分**：idx79 中 `qpnp-vibrator`、`qcom,spmi-pmic-arb`、各 `qcom,spmi@` 节点与 stock 基线逐项对照（含 `122→80` 链尾零影响）。
4. **驱动/时序对照**：stock 3.18.71 同驱动的 `spmi_ext_register_readl` 实现、SPMI 控制器 probe 顺序、PMIC ARB 时钟/权限初始化时序。
5. 若要拿现场：在 watchdog bark 前主动抓 CPU0 栈（Round 15 的 IPI 方案未成功，需换 `nmi` / `dump_stack` 路径）。

---

## 8. 产物

| 文件 | 说明 |
|---|---|
| `flash_log/blm_ram_round17.bin` | 262,144 B，sha `88ef0c4262dc7b2ab02b86093f984186332232acff03482a03a7e857e363b89d` |
| `flash_log/fdt_round17.bin` | 65,536 B，sha `9a0f83d8073be2ef0b8b19fe5401e633dc6a19f87d87b72fa79c55b7f0535384` |
| `flash_log/blm_ram_round17.trace.json` | 32 槽判定结果 |
| `flash_log/blm_ram_round17.forensics.json` | 双 bank/阶段/356 行明细 |
| `flash_log/blm_ram_round17.initcalls.json` | 192 条 initcall 与符号反查 |
| `flash_log/20261114_blm_round17_timeline.txt` | 含端点故障、恢复、两次回滚的完整时间线 |
| `images/boot_los16_blm_vib_20261114160500.img` | 本轮候选（已通过 40/40 + 17/17） |

设备状态：原厂 `3.18.71-perf-g8a8c60dd` / LOS16，adb 在线，fastboot/9008 已退出。
本轮未改动既有 ROUND 文档中的实测数据；未执行 SPMI/DT 差分、未构建新镜像、未做第 18 次实机。
