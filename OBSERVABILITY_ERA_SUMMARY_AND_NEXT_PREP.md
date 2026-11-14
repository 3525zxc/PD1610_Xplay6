# 黑盒观察时代总结与下次测试准备

日期：2026-11-14 15:17
范围：自 9008 Firehose `peek` 通道打通、BLM 早期日志监测机制引入（Round 10）到 Round 16 的全部实证
状态：**实机测试暂停**；本文件为离线总结与准备，不刷机、不构建镜像、不碰设备
设备当前：原厂 `3.18.71-perf-g8a8c60dd` / LOS16，adb 在线（15:08:00 `ROLLBACK_VERIFIED`）

---

## 0. 一句话总览

**以前只知道「卡 logo 反复重启」，现在能读到内核自己在真实设备上写下的执行记录：前 10 次 bootloop 的根因（编译产物太大，BSS 把设备树抹零）已定位并修好；修好后内核连续通过 12 个阶段跑到 `KERNEL_INIT`，新瓶颈被逐级收窄到 `qpnp_vibrator_init` → `spmi_driver_register()` 这一处。**

同时必须诚实：**自编译内核仍未启动进系统**；当前卡点的内部机制仍是 [H] 假设，没有 PC、没有该 probe 内插桩。

---

## 1. 三层观察能力（工具链与边界）

| 层 | 能力 | 关键工具 | 硬性边界 |
|---|---|---|---|
| 9008 / Firehose | `adb reboot edl` 进 `Qualcomm HS-USB QDLoader 9008 (COM5)`；`QSaharaServer` 上传 programmer；`<peek address64="十进制" size_in_bytes="长度"/>` 读物理 RAM，响应是 `<log value="0xNN ...">` XML 文本 | `tools/blm_firehose_peek.py`、`blm_capture_edl.bat`、`blm_firehose_power.py` | 只验证过 `peek`；**`poke`/写分区未验证，禁止用于回滚**；`<power value="fastboot">` 本机 programmer 回 NAK，只有 `reset` 可用 |
| BLM 内核侧 | 固定物理区 `__fdt_pointer + 0x100000 = 0x42100000`，256 KiB，双 bank + meta/generation；阶段槽、行槽、panic 文本直写、`blm_watchdog_secs=N` 主动 panic | `kernel/bootloop_monitor.c`、`blm_layout.h`、`blm_apply_kernel_patch.py` | 日志区靠 `memblock_reserve()` 保留，不依赖 DTB 节点；warm reset 后 DRAM 内容保留已实证；CPU0 关中断时 watchdog timer 可能不触发 |
| 宿主判定 | dump → 阶段/规则/行槽/IC 反查/固定槽 | `blm_read.py`、`blm_forensics.py`、`blm_initcall_report.py`、`blm_trace_report.py`、`blm_verify_ab.py`、`blm_ab_audit.py` | 行槽 384 个环形槽会被 printk 洪水冲掉；**「最后一条」不可靠**，关键结论必须写固定槽 |

刷前门槛：`tools/blm_preflight.py` 从 boot.img 解出 Image、读 System.map 重算 `_end`，要求距 FDT `0x42000000` 至少 1 MiB 余量。新镜像 `17/17 SAFE_TO_FLASH`，旧失败候选 `13/17 REFUSE_TO_FLASH`（阴性对照成立）。**刷任何自编译内核前必须跑它。**

---

## 2. 发现了什么（[O] 现象，此前完全不可见）

1. **自编译内核其实跑得很远**：Round 13 起连续 12 个阶段全过（`START_KERNEL → BEFORE_SETUP_ARCH → SETUP_ARCH_ENTER → FDT_SCAN_DONE → EARLY_IOREMAP → PAGING_INIT → UNFLATTEN_DT → AFTER_SETUP_ARCH → CONSOLE_INIT → CONSOLE_REGISTERED → REST_INIT → KERNEL_INIT`），不是「解包失败 / 没进内核」。
2. **前 10 次 bootloop 的真正死因**：候选内核 BSS 清零区覆盖 aboot 放 DTB 的 `0x42000000`，把 FDT 抹成全零 → `setup_machine_fdt()` 失败。实机双读：失败态 64 KiB 全零，原厂基线同地址 `d00dfeed` / `totalsize=410405`。
3. **修好后出现全新瓶颈**：DTB 头恢复为 `d00dfeed` / `totalsize=410533`（原厂 410405，+128 B 正是 BLM 节点），但内核仍停在 `kernel_init` 之后的 initcalls，未到 `INITCALLS_DONE`。
4. **失败现场可读**：console 修好后单次 dump 有 377 行日志 / 191 条 initcall 记录 / 185 条 printk；UFS、PCIe、camera、SDHCI、FG 等大量驱动已 probe 完成。
5. **取证工具自己有两个缺陷**：BLM console 缺 `CON_ENABLED` 被 `printk.c:2536` 静默丢弃（日志只有 2 行）；环形行槽的「最后一条」会被覆盖，导致 Round 14/15 误判卡点。
6. **归因被推翻过一次**：Round 14/15 认为卡在 `usb_bam` probe；Round 16 固定槽证明 `usb_bam` 注册已返回、其 probe 从未被调用，真正最后进入的 initcall 是 `qpnp_vibrator_init`。
7. **通道事实**：进 9008 + 上传 programmer 后 DDR 内容不清空；panic 后 `panic_timeout=5` 会主动重启，形成 bootloop 循环；watchdog panic 只抓到 CPU2 的 idle 栈，CPU0 未响应 IPI（[H] 关中断自旋）。
8. **fastboot USB 端点会瞬断**：首写 `Writing FAILED(31)`、重试 1 报 433、重试 2 约 3 分钟后成功；失败后不得 reboot。

---

## 3. 探明了什么（机制链，[O] 证据 + [H] 推论）

### 3.1 运行期内存布局（[O] 反推闭环）

- `/proc/iomem`：`System RAM 40000000-857fffff`，`Kernel code 40080000-...`。
- ROUND4 反汇编 [O]：aboot 在 `0x91D39E18` 把 `kernel_addr=B+0x80000`、`tags_addr=B+0x2000000`、`ramdisk_addr=B+0x2200000` 覆写 ⇒ **`B = DDR_BASE = 0x40000000`**。
- 运行期 DTB 落点 `0x42000000`，BLM 日志区 `__fdt_pointer+0x100000 = 0x42100000`。
- **boot.img header 里 `0x8000xxxx` 只是静态占位值，运行期会被 aboot 覆写**，不能当物理布局读（曾据此生成过错误的 `0x82100000` 节点，已修正）。

### 3.2 BSS 覆盖链（[O] 区间 + [H] 动作）

| 项 | 原厂 3.18.71 | 未裁剪 3.18.120 | 裁剪后 |
|---|---|---|---|
| `image_size` | `0x1c9a000` | `0x207d000` | **`0x1d89000`** |
| `_end` 物理 | `≈0x41d1a000` | `0x420fd000` | **`0x41e09000`** |
| 与 FDT `0x42000000` | 余量 2.94 MiB | **覆盖 1.01 MiB** | 余量 `0x1f7000` ≈ 1.97 MiB |

机制 [H]：内核 `head.S` 进 `start_kernel` 前清 BSS，把 aboot 放好的 DTB 一起抹零 → `early_init_dt_scan()` 读到无效 FDT → 死循环。实机 [O]：裁剪后 FDT 头从全零恢复为 `d00dfeed`/`totalsize=410533`，BLM 阶段从卡住的 3 推进到 12。这解释了「换 3.18.66/3.18.120 基线没用（不是版本语义，是产物体积）」「去掉 BLM 节点没用」「`phys_to_virt` 正常」。

### 3.3 console 门槛（[O] 源码 + 实机）

- 3.18 `register_console()`：`if (!(newcon->flags & CON_ENABLED)) return;`（printk.c:2536）。
- 原厂 boot.img header cmdline：`console=null androidboot.console=ttyHSL0 ...`；`preferred_console` 已定值、`console_cmdline` 只认 `null` ⇒ 名字 `blm` 且未置 `CON_ENABLED` 的 console 被丢弃。
- 修为 `CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER` 后：2 行 → 377 行。
- 已验证 aboot 会把 header cmdline 传入内核 `/proc/cmdline`（`adb root` 实测），所以 `--append-cmdline blm_watchdog_secs=20` 生效（panic 时间戳 20.07 s）。

### 3.4 当前卡点（[O] 位置 + [H] 机制）

- 固定槽 0：`0xffffffc00184c050 -> qpnp_vibrator_init+0x0`；12 个 `usb_bam_probe` 里程碑全空；`avtimer_init`、`clock_late_init` 未进入。
- 反汇编：`qpnp_vibrator_init` = `spmi_driver_register(&qpnp_vibrator_driver)`；其 probe 调 `spmi_ext_register_readl` ×2、`pwm_request`、`timed_output_dev_register`。
- ⇒ [H] 卡在 **SPMI 寄存器读 / PWM 请求 / `spmi_driver_register` 的同步 probe**。日志里另有 `spi_qsd ... unable to get core_clk`、`scm_call failed: func id 0x42000c02, ret: -2`，但因果关系未验证（UFS 后续正常枚举）。
- Round 15 watchdog panic 时 CPU0 未响应 IPI，与「关中断自旋」相容，但那是 [H]。

---

## 4. 确认了什么（可复现硬证据）

| 结论 | 证据 |
|---|---|
| `DDR_BASE=0x40000000`、FDT `0x42000000`、日志 `0x42100000` | `/proc/iomem` + aboot 反汇编 + 双 bank header 自证 |
| 9008 + programmer 后 DRAM 保留、peek 可读 | 原厂基线探针 256 B / 2 块 / 全量 256 KiB 多次 `failed_blocks=0` |
| BLM 日志跨多次失败留存 | Round 10 双 bank gen2/gen3 阶段序列逐格相同；Round 11 一份 dump 里 gen3/gen4 并列 |
| 「BLM 保留区节点」不是失败原因 | 等长 NOP 单变量 A/B：`AB_AUDIT 14/14`、镜像差分 `24/24`、58 MB 仅 2 处差异，剥离组仍停阶段 3 |
| 裁剪修复有效且可前置拦截 | `blm_preflight.py` 新镜像 `17/17 SAFE_TO_FLASH`，旧候选 `13/17 REFUSE_TO_FLASH` |
| config 未动 usb_bam 依赖 | 74 项差异全是调试/追踪/测试模块；`USB_BAM / SPS / IPA / MSM_SCM` 全为 `y` |
| 单变量镜像可做到字节级 | watchdog 镜像与 Round 14 追踪镜像**仅差 21 字节**（` blm_watchdog_secs=20`），header id 相同 |
| header cmdline 通路可用 | 原厂 `/proc/cmdline` 含 header 原文；`blm_watchdog_secs=20` 实机 20.07 s 触发 `WATCHDOG_PANIC` |
| 回滚可靠 | 11 次成功，始终同一个原厂 `boot.img` sha256 `929fda99…`；用户看到的「回滚时 bootloop」都是回滚前等待窗口内仍在跑候选镜像 |
| 产物状态 | 9 份 ROUND 报告、17 份 JSON；当前最新镜像 `boot_los16_blm_probe_20261114150000.img` sha `9b11acf1…`，`40/40` + `17/17 SAFE_TO_FLASH` |

---

## 5. 归因演进（含被推翻的结论）

| 轮次 | 观察到的卡点 | 结论状态 |
|---|---|---|
| Round 10–11 | 阶段 3 `SETUP_ARCH_ENTER`，两 bank 一致 | [O]；A/B 排除 BLM 节点因素 |
| Round 12 | `0x42000000` 失败态全零 + 区间计算 | 根因坐实：BSS 覆盖 DTB |
| Round 13 | 阶段 12 `KERNEL_INIT`，FDT 头恢复 | 根因修复被实机证实；新瓶颈出现 |
| Round 14 | 最后 IC = `0x184c02c` usb_bam 注册 | **后被推翻**：环形行槽最后一条不可靠 |
| Round 15 | watchdog panic，CPU2 idle 栈 | 证明 cmdline/panic 链可用；CPU0 栈未取到 |
| Round 16 | 固定槽 0 = `qpnp_vibrator_init`，usb_bam 里程碑全空 | **当前结论**；卡点改判 |

工程教训（已写入长期记忆）：**关键 last-known-good 点必须写固定槽；任何基于环形缓冲「最后一条」的归因都可能被覆盖/CRC 偏差误导。**

---

## 6. 还要深一步研究的方向

### A. 当前卡点（最高优先，直接闭环）

1. **`qpnp_vibrator_probe()` 内插桩**：源码 `drivers/platform/msm/qpnp-vibrator.c`（编译树与归档 `msm8996-lineage-16.0.tar.gz` 均含）。在 `spmi_ext_register_readl`、`pwm_request`、`timed_output_dev_register` 前后写固定槽 `id=1..8`，保留槽 0 的 last-initcall。判据：若 `spmi_ext_register_readl` 前的槽有、之后的槽无 ⇒ 卡在 SPMI 读。
2. **先确认 probe 是否被调用**：若 probe 里程碑也全空 ⇒ 卡在 `spmi_driver_register()` 内部（总线/设备匹配），转查 SPMI 控制器与 DT 节点。
3. **资源差分**：原厂 DTB vs 候选 idx79 的 `qcom,qpnp-vibrator` 节点、PWM/SPMI 资源；`122→80` 链尾零是否影响相关节点。
4. **stock 3.18.71 同驱动对照**：原厂为何不卡（是否同一驱动、DT 节点差异、初始化时序差异）。
5. **CPU0 栈**：在 `blm_watchdog_fn()` panic 前用 `smp_call_function_single(0, ...)` 主动抓；若仍无响应，反而坐实关中断自旋。

### B. 工程方法（降低下一次实验成本）

1. 行槽改为「固定槽 + 环形槽」已是正解；后续所有里程碑都走固定槽。
2. 刷机脚本内建端点重试（最多 3 次）与「失败后不 reboot」；已实现。
3. 双读**不带 `--reset`**，读完直接发 `power value=reset`，再等手动 fastboot 回滚；`power value=fastboot` 本机不可用。
4. 每次刷前强制 `blm_preflight.py`；镜像级单变量差分（`blm_verify_ab.py`）作为发布门禁。
5. 设备状态、镜像 sha、时间线统一写入 `flash_log/` 与报告，避免「回滚是否刷错」的歧义。

### C. 第二阶段衔接（整颗内核 + 可刷 boot.img 路线）

本轮实证改变了路线判断：**瓶颈不在静态像不像，而在运行期的具体驱动/资源依赖**。此前研究的「编译对象层级差异」「非 prebuilt 整颗内核路线」现在有了可验证的落点：

- 自编译内核已经能过 DTB 扫描、MMU、设备树展开、console、大部分 initcall——说明内核骨架与打包链是成立的；
- 剩下的是**厂商私有层/平台驱动的运行期语义**（vivo 私有层、SPMI/PWM/IPA 等），应逐模块做 stock vs custom 对照，而不是继续换基线或盲刷；
- 「④ vivo 私有层原封不动移植」不可行（统一链接的 Image 里地址、ABI、initcall 槽位都随版本走），正确做法是逐模块按接口/Kconfig/initcall 对齐，并用本工程的固定槽做每次接入后的实机验证。

外部调研结论仍有效：严格意义上没有「Ghidra 伪 C 全量还原整颗闭源 Android 内核并启动」的公开案例；有整颗内核 + 可刷 boot.img 的 LibreHU 成功路线可借鉴，但本工程的差异化优势是**已有真机执行记录**。

---

## 7. 下次测试准备（离线可做，本轮未执行）

### 7.1 已就绪（无需重做）

- 设备：原厂系统，adb 在线，`blm_preflight.py` 门槛已固化。
- 源码：`/home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000` 完整（3118 个 .o），裁剪 config、BLM 补丁树 `tests/patched_tree/` 可复现。
- 工具链：gcc 4.9 交叉编译器、`blm_trace_build.sh`（增量编译）、`blm_build_bootimg.py`（支持 `--append-cmdline` / `--idx79-dtb`）、全套判定器。
- 证据：Round 10–16 全部 dump / JSON / 时间线；`build_selfcheck.sh` 最近一次 `SELFCHECK_OK`。

### 7.2 离线待办（下次实机前完成，均不碰设备）

1. 复制 `qpnp_vibrator.c` 原始夹具到 `fixtures/`，在 `blm_apply_kernel_patch.py` 增加 `patch_qpnp_vibrator()`，插入 6–8 个固定槽里程碑。
2. 更新 `blm_trace_build.sh` 复制新补丁文件；`blm_trace_report.py` 的 `TRACE_NAMES` 增加新槽位定义。
3. 增量编译 → `blm_preflight.py 17/17` → `blm_build_bootimg.py 40/40` → `build_selfcheck.sh`。
4. 镜像级差分：确认与 Round 16 镜像只差内核代码，DTB/ramdisk/签名/头部布局不变。
5. 预先写好第 17 次实机脚本：刷入（内建重试）→ 观察 9008 → 双读（FDT 头 + BLM，不带 reset）→ 判定 → `power reset` → 手动 fastboot → 回滚 `929fda99…` → `ROLLBACK_VERIFIED`。

### 7.3 下次实机判据（写死，避免再误判）

| 观察 | 结论 |
|---|---|
| `spmi_ext_register_readl` 前有槽、后无槽 | 卡在 SPMI 寄存器读 |
| `pwm_request` 前有槽、后无槽 | 卡在 PWM 请求 |
| probe 里程碑全空 | 卡在 `spmi_driver_register()` 内部 / 设备未匹配 |
| 固定槽 0 不再停留 `qpnp_vibrator_init` | 卡点后移，按新 last-initcall 继续追 |
| 阶段到 `INITCALLS_DONE` / `ROOTFS_READY` | 瓶颈转向 rootfs / ramdisk / FBE |

### 7.4 风险与边界

- 不刷任何未过 `blm_preflight.py` 的镜像；不尝试 EDL 写分区（`poke`/program 未验证）。
- 回滚仍需现场手动进 fastboot 一次；`power value=reset` 后等待窗口内设备会持续 bootloop，属正常现象。
- 所有机制推论标 [H]，只有固定槽、dump、反汇编、字节级差分为 [O]。

---

## 8. 未执行清单

`qpnp_vibrator_probe` 插桩、SPMI/PWM/DT 资源差分、stock 同驱动对照、CPU0 栈主动抓取、第 17 次实机、任何新的镜像构建。本文件为只读总结与准备，未改动设备状态、未改动既有 ROUND 文档。

---

## 9. 更新（16:10）：§7.2 的离线待办已全部完成

用户随后要求「go on」，已在**纯离线**状态下把下次测试的准备全部做完（仍不碰设备、不刷机）：

- §7.2 第 1–5 项全部完成：新增 `qpnp-vibrator.c` 夹具与 `patch_qpnp_vibrator()`（11 个固定槽里程碑，id 16..26，固定槽扩到 32）；固定槽、判定器、构建脚本、全套自测、增量编译、打包、预检、镜像级差分、第 17 次实机脚本均已落地并通过校验。
- 候选镜像：`images/boot_los16_blm_vib_20261114160500.img`，sha256 `47034aaf…`，`40/40` + 预检 `17/17 SAFE_TO_FLASH` + 差分 `10/10`（唯一变量是内核 gzip，DTB/ramdisk/签名/头布局全同）。
- 实机脚本 `tools/blm_round17_capture.ps1` 已通过 `PS_SYNTAX_OK`，**未执行**。
- 完整清单、固定槽映射、写死的判据表与 runbook 见 `ROUND17_READY.md`。

§7.2 因此由「待办」转为「已就绪」；§8 中除「任何新的镜像构建」已完成外，其余（第 17 次实机、SPMI/PWM/DT 差分、stock 对照、CPU0 栈抓取）当时仍未执行。

---

## 10. 更新（16:25）：第 17 次实机已完成，卡点精确到第一次 SPMI 读

用户进入 fastboot 后执行第 17 次实机，设备已安全回滚到原厂 `3.18.71-perf-g8a8c60dd` / LOS16。

- **§8 中的「第 17 次实机」已执行完毕**；因设备起始已在 fastboot、一键脚本 STEP1 需 adb 在线，改为等价的拆步执行（全程留痕 `flash_log/20261114_blm_round17_timeline.txt`）。
- 结论：11 个 vibrator 固定槽中 `id=16..22` 全命中（`VIB_RES_AFTER=0x5100` 证明 SPMI 资源与 DT 解析成功），`id=23..26` 全空，`LAST_VIB_MILESTONE=VIB_READ1` ⇒ **卡在 `qpnp_vib_read_u8()` 内第一次 `spmi_ext_register_readl()` 未返回**。probe 确被调用，PWM 分支排除；Round 16 的 [H]「SPMI 读或 PWM」收窄为「第一次 SPMI 读」。硬件 watchdog 20.34 s bark。仍无 PC，机制 [H]。
- 归因演进表新增一行：`Round 17 | 固定槽 16..22 命中、23..26 空 | 卡点精确到 spmi_ext_register_readl`。
- **现场更正**：t=50 s 的 fastboot 是用户手动介入的；脚本轮询 `fastboot_ready` 不能推断「自动进入」。此前误述已在结果报告、时间线与项目记忆中更正。
- §8 剩余未执行：SPMI/PWM/DT 资源差分、stock 3.18.71 同驱动对照、CPU0 栈主动抓取、绕过实验、第 18 次实机。详见 `ROUND17_VIBRATOR_SPMI_RESULT.md` §7。
