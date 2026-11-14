# Round 12 · 根因基本坐实：自编译内核的 BSS 清零区覆盖了 aboot 放置的 DTB

> 2026-11-14 13:10–13:18，第 12 次 Boot-only 实机（双读实验）。仅写 `boot` 分区；设备已回滚并二次核验原厂系统。
> 先回答现场疑问：**回滚没有刷错**，详见 §1。

## 0. 一句话结论

**自编译 3.18.120 内核比原厂大约 3.9 MiB，其 `image_size` / BSS 清零区一路延伸到 `0x420fd000`，把 aboot 放在 `0x42000000` 的设备树整个抹成全零；内核随后在 `setup_machine_fdt()` 里读到无效的 FDT 而停住。** 这解释了五天来全部 10 次自编译内核 bootloop，也解释了为什么 BLM 日志能幸存。

失败态实机读回 `0x42000000`：64 KiB **全零**（`magic=0`、`nonzero=0`）；原厂基线同一地址：结构完整 FDT（`0xd00dfeed`、`totalsize=410,405`、含 PD1610 model 字符串）。

## 1. 「回滚时又 bootloop，是不是刷错了」的核查

**没有刷错。** 回滚镜像是前 9 次成功回滚的同一个 `boot.img`，sha256 `929fda9985478078f0614a9c3709af69fe3b1c9c8badc50e783261f91ab241ae`（13:18:41 现场复核一致）。

```
13:13:27 刷入剥离节点候选 + reboot          <- boot 分区是候选
13:13:58 t=15s 自动进 9008(COM5)
13:14:22~13:14:31 双读 FDT 头 + BLM 日志，最后一次带 --reset
13:15:46 开始等 fastboot 准备回滚
13:15:46~13:17:02 设备仍在跑候选镜像 -> bootloop 75 s   <- 用户看到的就是这段
13:17:02 fastboot_ready t=75s                <- 用户手动进 fastboot 接上了这一步
13:17:04 刷原厂 boot + reboot（Sending/Writing OKAY）
13:17:54 adb 上线 ROLLBACK_VERIFIED
13:18:41 二次核验：adb 在线、3.18.71-perf-g8a8c60dd、uptime 1 min、fastboot 已退出
```

bootloop 是候选镜像在等待回滚窗口期间的正常表现，不是原厂 boot 写坏。这与 Round 11 的情形相同。

## 2. 观察 [O]

| 项 | 结果 |
|---|---|
| 原厂基线 FDT（不刷机，仅进 9008 读） | `flash_log/fdt_baseline_stock.bin`，65,536 B，sha256 `63a0b7a1…`，`nonzero=31506` |
| 基线 FDT 头 | `magic=0xd00dfeed`、`totalsize=410,405 (0x64325)`、`off_dt_struct=56`、`off_dt_strings=373,948`、`size_dt_strings=36,457`、`size_dt_struct=373,892`、`version=17`/`last_comp=16`；`vivo MSM 8996 v3 + PMI8996 PD1610` @108；`d00dfeed` 计数 1 |
| 失败态 FDT | `flash_log/fdt_failed_state.bin`，65,536 B，sha256 `de2f2560…`，**`nonzero=0`**，头 32 B 全 0，`d00dfeed` 计数 0 |
| 失败态 BLM | `flash_log/blm_ram_round12.bin`，262,144 B，sha256 `181ff409…`，`bank_count=1`、`meta_generation=1`、`last_stage=3 SETUP_ARCH_ENTER`、阶段序列 `START_KERNEL → BEFORE_SETUP_ARCH → SETUP_ARCH_ENTER`，`fdt/log/ddr = 0x42000000 / 0x42100000 / 0x40000000` |
| 9008 时序 | 基线：进 9008 后 30 s 复位回原厂；Round 12：t=15 s 自动进 9008 |
| 回滚 | 13:17:54 `ROLLBACK_VERIFIED`；13:18:41 二次核验 ADB 在线、原厂内核、uptime 1 min |

**两态使用同一台设备、同一 COM5、同一 `prog_ufs_firehose_8996_ddr.elf`、同一 `<peek>` 工具、同一地址 `0x42000000`**，唯一差别是 boot 分区里是原厂还是候选内核。因此「全零」不是工具/端口/Sahara 上传造成的假象。

## 3. 区间计算（`tools/blm_root_cause_calc.py`，可复现）

来源：`build/20261114011739/System.map`（候选 3.18.120 编译产物）、`images/boot_los16_blm_ddr40000000.report.json` 的 ARM64 Image 头、实机 `/proc/iomem`。

| 对象 | 值 |
|---|---|
| `DDR_BASE` | `0x40000000`（`/proc/iomem` Kernel code 起点 `0x40080000` = `B+0x80000`） |
| 内核加载物理地址 | `0x40080000` |
| aboot 覆写后的 `tags_addr` / FDT 落点 | `B+0x2000000 = 0x42000000` |
| BLM 日志区 | `__fdt_pointer+0x100000 = 0x42100000` |
| **候选** `__bss_start` / `__bss_stop` / `_end`（虚拟） | `0xffffffc001dbc400` / `0xffffffc0020f665c` / `0xffffffc0020fd000` |
| **候选** 换算物理 | `[0x41dbc400, 0x420f665c]`，`_end=0x420fd000` |
| **候选** `image_size` | `34,066,432 (0x207d000)`，占用 `[0x40080000, 0x420fd000)` |
| **原厂** `image_size` | `29,990,912 (0x1c9a000)`，`_end≈0x41d1a000`，与 iomem `Kernel data 41800000-41d19fff` 吻合 |
| 原厂 `_end` 到 FDT 的余量 | `0x2ef000 = 3,080,192 B ≈ 2.94 MiB` |
| **候选 `_end` 越过 FDT 的量** | `0xfd000 = 1,036,288 B ≈ 1.01 MiB` |

判定：`fdt_inside_candidate_bss=True`、`fdt_inside_candidate_image=True`、`fdt_inside_stock_image=False`、`blm_log_outside_candidate_image=True`。

⇒ **候选内核的 BSS 清零区精确覆盖 `0x42000000`；原厂完全不覆盖。** 且 BLM 日志区 `0x42100000` 恰好在候选 `_end=0x420fd000` 之后 12 KiB，因此没被清掉——这解释了为什么 BLM 记录能读回、FDT 却全零。

## 4. 机制链条（[O] 事实 + [H] 推断，分开标注）

- **[O]** 内核已进 `start_kernel` 并到 `setup_arch` 入口（BLM 阶段 3），说明 aboot 解压、加载、交棒、`head.S` 早期页表都成功。
- **[O]** 失败态 `0x42000000` 全零；原厂同地址为合法 FDT。
- **[O]** 候选 BSS 物理区间覆盖该地址，原厂不覆盖。
- **[H]** ARM64 3.18 `head.S` 在跳转 `start_kernel` 前按 `__bss_start..__bss_stop` 清零 BSS；候选区间把 aboot 刚放好的 DTB 一并抹掉。随后 `setup_machine_fdt()` 调用 `early_init_dt_scan(phys_to_virt(0x42000000))` 读到全零、返回 false，进入 `while(true) cpu_relax()` 死循环 —— 与「不 panic、不重启、卡住、无错误文本」一致。
- **[H]** 另一条尚未完全排除的可能：aboot 因 `122→80` 链尾零布局而未能把 DTB 搬到该地址。但基线证明该地址在正常启动时确有 FDT，且候选内核 BSS 覆盖是独立成立的定量事实，故前者概率显著更低。

**证据边界**：没有采集 PC、没有抓到 BSS 清零发生的瞬间、没有 earlycon 输出；本机 3.18.120 源码树已清理（`head.S` 不在位），本轮未能逐行核对清零指令。因此「BSS 清零抹掉 DTB」是高可信 [H]，不是 [O] 现场录像。区间计算与两态 FDT 读回是 [O]。

## 5. 这解释了此前所有困惑

| 现象 | 解释 |
|---|---|
| 10 次自编译内核全部 bootloop | 所有候选都比原厂大，`image_size` 越过 `0x42000000` |
| 停在 `SETUP_ARCH_ENTER`、无 panic 文本 | `early_init_dt_scan` 失败分支是死循环，`early_print` 不经 printk 行槽 |
| 换 3.18.66 / 3.18.120 基线无用 | 问题不是版本语义，是编译产物体积 |
| Round 11 去掉 BLM 节点仍失败 | 与节点无关，假设 1 已排除 |
| `phys_to_virt` 曾被怀疑 | BLM 用同一映射成功写日志，映射正常 |
| BLM 日志区能读回 | `0x42100000` 在候选 `_end` 之后，未被 BSS 清零波及 |
| ROUND4 评审的「`image_size` 扩张 → BSS 后移 → 覆盖 aboot 对象」P1 假设 | **本轮实机证实**（当时因 S4 未闭环而未降级） |

## 6. 下一步（按成本，均未执行）

1. ~~**裁剪内核**~~：**已完成**，见 `SHRINK_BUILD_DELIVERY.md`。实际把 `image_size` 从 `0x207d000` 降到 `0x1d89000`（减 2.95 MiB），`_end` 从 `0x420fd000` 退到 `0x41e09000`，距 FDT 余量 `0x1f7000`。
2. ~~**编译期验证**~~：**已完成并升级为强制门槛**：`tools/blm_preflight.py` 直接从 `boot.img` 解出 Image 重算 `_end`，新镜像 `PASS 17/17 SAFE_TO_FLASH`，旧失败候选 `FAIL 13/17 REFUSE_TO_FLASH`（阴性对照成立）。
3. **可选实机闭环**：在 `head.S` BSS 清零前后各加一个早期标记（或直接 peek `0x41dbc400` 与 `0x420f665c` 附近），把 [H] 升为 [O]。
4. **链尾零假设**：若裁剪后仍失败，再回查 `122→80` 链布局。

## 7. 未执行 / 设备状态

未裁剪内核、未重新编译、未做第 13 次刷写、未在 `head.S` 加插桩、未采集 PC。**设备当前为原厂系统**，`3.18.71-perf-g8a8c60dd` / LOS16，13:18:41 二次核验 adb 在线、fastboot 已退出。

## 8. 证据文件

`flash_log/fdt_baseline_stock.bin`、`flash_log/fdt_failed_state.bin`、`flash_log/blm_ram_round12.bin`、`flash_log/blm_ram_round12.forensics.json`、`flash_log/20261114_blm_round12_timeline.txt`、`images/round12_root_cause_calc.json`、`tools/blm_root_cause_calc.py`。
