# ROUND 18 · qpnp-vibrator 绕过实验（离线准备完成）

日期：2026-11-14 16:33–16:40
状态：**离线门禁全部通过，准备就绪**；设备保持原厂 `3.18.71-perf-g8a8c60dd` / LOS16
目的：回答第 17 次留下的问题 —— 「第一次 SPMI 读卡死」是 `qpnp-vibrator` 这一台设备独有，还是 SPMI/PMIC-ARB 访问的共性瓶颈。

---

## 1. 做法：等长 FDT_NOP 抹掉设备节点，单变量对照

不重编译内核，**复用第 17 次完全相同的内核二进制**（tag `vib-20261114160500`），只改 idx79 DTB：

```
/soc/qcom,spmi@400f000/qcom,pm8994@1/qcom,vibrator@5100
  struct 块 [183160, 183308)  148 B  →  37 个 FDT_NOP 标签
```

节点消失 ⇒ `spmi_driver_register(&qpnp_vibrator_driver)` 仍会执行，但没有匹配的 SPMI 设备，
`qpnp_vibrator_probe()` 不会被调用 ⇒ 第 17 次卡住的 `spmi_ext_register_readl(...)` 路径被绕开。

`blm-ram-log@42100000` 节点保留，BLM 日志机制与读回地址完全不变。

### 为什么是严格单变量

DTB 头部 10 个字段、`totalsize=409688`、strings 块、`size_dt_struct`、`off_dt_strings`、
DTB 链长 30,947,277 B、尾零 14,894,713 B 全部逐字节不变；
镜像里 gzip 10,709,503 B、前 79 份 DTB、ramdisk、签名块、除 id 外的头部全同。

镜像级差分 `26/26 PASS`：整个 58,483,968 B 里 `unexpected=0`，
差异只有 `[576,596)` header id 与 idx79 内 `[41434348,41434496)` 节点区。

---

## 2. 离线审计顺带排除的一个假设

新增 `tools/blm_bypass_inspect.py` 做 stock vs custom 资源对照（`images/vibrator_resource_diff.json`）：

| 项 | 结果 |
|---|---|
| `qpnp-vibrator` 节点（候选 / 原厂） | 各 1 个，路径同一 |
| 节点属性逐项比对 | **`vibrator_props_identical=True`**（compatible / reg / status / vdd-supply / vib-timeout-ms / vib-vtg-level-mV 全同） |
| SPMI / PMIC-ARB 节点路径 | `spmi_node_paths_identical=True`（各 1 个 SPMI 控制器 + 1 个 PMIC-ARB） |
| 节点 phandle | 无 phandle 属性、无其他节点引用 ⇒ 整节点 NOP 安全 |

⇒ **候选 DTB 的 vibrator 资源、SPMI 控制器描述与原厂一致**，「DT 资源写错 / 节点被裁剪」这条假设被排除。
卡点更可能在这套 3.18.120 的 `spmi_ext_register_readl` 实现、PMIC-ARB 控制器驱动状态或运行时时序。

---

## 3. 产物与门禁

| 项 | 值 |
|---|---|
| 绕过镜像 | `images/boot_los16_blm_vibbypass_20261114160500.img` |
| sha256 / 大小 | `27493588b78c9a2d6e0b62efa1e951322063c92762fe904ab512bb142e8bbcdb` / 58,483,968 B |
| 对照基线 | `images/boot_los16_blm_vib_20261114160500.img`（第 17 次，sha `47034aaf…`） |
| 绕过 DTB | `images/idx79_vibrator_bypass_nop.dtb`，sha `62f2b0af…` |
| DTB 结构审计 | `BYPASS_DTB 15/15 PASS`（节点外零差异、header 全字段相同、BLM 节点保留） |
| 构建自检 | `BOOTIMG_BUILD_OK 40/40 PASS` |
| 刷前预检 | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 镜像级差分 | `BYPASS_VERIFY 26/26 PASS`，`unexpected=0` |
| 全套自测 | `SELFCHECK_OK`（回归通过） |
| 新增工具 | `blm_bypass_inspect.py`、`blm_bypass_dtb.py`、`blm_verify_bypass.py` |

---

## 4. 第 18 次实机判据（写死）

固定槽机制与第 17 次完全一致（0=last-initcall，1..11=usb_bam，16..26=vibrator），
`blm_trace_report.py` 无需改动。

| 观察 | 结论 |
|---|---|
| adb 上线、`uname -r = 3.18.120` | **绕过成功且内核完整启动**；vibrator 是唯一瓶颈，进入系统验证阶段 |
| `last_stage` 越过 `KERNEL_INIT`，到 `INITCALLS_DONE` / `ROOTFS_READY` | 绕过成功，瓶颈转到 initcalls 后段 / rootfs / ramdisk；按新 last-initcall 继续追 |
| 槽 0 变成 `avtimer_init` / `clock_late_init` 等后续 initcall，vibrator 槽 16..26 全空 | **绕过生效**：probe 确未调用，且内核走过了 `qpnp_vibrator_init`；`qpnp-vibrator` 是当时的唯一卡点 |
| 仍停 `KERNEL_INIT`，槽 0 仍是 `qpnp_vibrator_init`，但 vibrator 槽全空 | 异常：`spmi_driver_register` 本身卡住，与 probe 无关；转查 SPMI 总线注册路径 |
| 仍停 `KERNEL_INIT`，槽 0 是**另一个** SPMI/PMIC 设备 | SPMI/PMIC-ARB 共性问题，不是 vibrator 独有；转查控制器驱动与运行时状态 |
| 仍停 `KERNEL_INIT`，`last_stage` 回退到 3 `SETUP_ARCH_ENTER` | DTB 结构改动引入新问题，回滚并复核 NOP 结构 |

**注意**：`unexpected=0` 只保证字节级单变量，不保证语义零影响 —— 节点消失本身会改变
`of_platform` 设备枚举顺序，这属于实验要观察的效应，不是额外变量。

---

## 5. runbook（拆步执行，不跑一键脚本）

设备起始可能在 fastboot 或原厂系统；先读状态再决定是否需要 `adb reboot bootloader`。

```
fastboot -s 5fccbfeb flash boot <bypass.img>     # 最多重试 3 次；失败不 reboot，直接刷回原厂
fastboot -s 5fccbfeb reboot
# 观察最长 180 s，等 9008 (COM5)
blm_firehose_peek.py --com 5 --address 0x42000000 --size 0x10000 --chunk 0x10000 --out fdt_round18.bin --workdir edl_probe
blm_firehose_peek.py --com 5 --address 0x42100000 --size 0x40000 --chunk 0x10000 --no-upload --out blm_ram_round18.bin --workdir edl_probe
blm_trace_report.py --input blm_ram_round18.bin --system-map build/vib-20261114160500/System.map --report blm_ram_round18.trace.json
blm_firehose_power.py --com 5 --mode reset --workdir edl_probe
# 等 fastboot（本轮可能仍需现场手动进一次）
fastboot -s 5fccbfeb flash boot <stock boot.img 929fda99…>
fastboot -s 5fccbfeb reboot
adb -s 5fccbfeb shell uname -r   # 期望 3.18.71-perf-g8a8c60dd
```

双读**不带 `--reset`**；复位后设备会回到绕过镜像持续 bootloop，这是等待回滚窗口的正常表现，
不是刷错。回滚镜像始终是前 10 次成功的同一个 `929fda99…`。

---

## 6. 风险与边界

- 只刷 `blm_preflight.py 17/17 SAFE_TO_FLASH` 的镜像；不尝试 EDL 写分区。
- 固定槽是 [O]，机制推论仍标 [H]；本轮未采集 PC、未抓 SPMI 控制器寄存器。
- 本实验**只做绕过判定**，不追求「自编译内核完整启动」；即使 adb 上线也需要单独验证系统功能。
- 离线阶段未碰设备、未改既有 ROUND 文档中的实测数据。
