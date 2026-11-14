# Round 10 · BLM 首次实机取回：失败窗口收窄到 setup_arch 入口与 FDT 扫描标记之间

> 2026-11-14 11:38–11:44，第 10 次 Boot-only 实机。仅写 `boot` 分区；设备已回滚并验证原厂系统。
> 2026-11-14 11:56 依据外部复核修订证据口径：本报告不声称已捕获 PC、不声称已证明 `early_init_dt_scan()` 返回 false。

## 0. 一句话结论

**首次拿到自编译内核的实机阶段记录**：内核确实执行到 `start_kernel()` 之后并进入 `setup_arch()`，BLM 监测模块成功在物理 `0x42100000` 写入日志，两个独立 bank 一致停在 `SETUP_ARCH_ENTER`（阶段 3）。

严格结论应写为：**失败发生在 `setup_arch()` 入口之后、`setup_machine_fdt(__fdt_pointer)` 返回并产生下一阶段标记之前。** `rule=fdt_scan` 只是按最后阶段标记做的取证分类，不是采集到的 PC；`early_init_dt_scan()` 是否返回 false、CPU 是否停在 `while(true)` 上，均**未被证明**。

## 1. 观察 [O]

| 项 | 实测 |
|---|---|
| 候选镜像 | `images/boot_los16_blm_ddr40000000.img`，58,483,968 B，sha256 `4abe6ba6cb7fd6b3d78c8eebf30119954b8c14a73fce76070b5e54521a20f521` |
| 刷入 | `fastboot flash boot` `Sending/Writing OKAY`，`reboot OKAY` |
| 9008 | t=85 s 设备自动枚举 `Qualcomm HS-USB QDLoader 9008 (COM5)`，无需手动按键、`oem reboot-edl` 未触发 |
| 读回 | Firehose `<peek>` 4 × `0x10000` 块，`failed_blocks=0`，262,144 B，sha256 `9316f55fd829b02396409419a10756a146fe9dffedad77dd612055e5cfc4dd7a` |
| 日志头 | `314154454d4d4c42` = `BLM_META_MAGIC 0x424C4D4D45544131` 小端 |
| 回滚 | `fastboot flash boot` 原厂 `boot.img`（sha256 `929fda99…`），+50 s adb 上线，`3.18.71-perf-g8a8c60dd` / LOS16 `ROLLBACK_VERIFIED` |

## 2. BLM 判定输出（`tools/blm_read.py --already-region`）

```
bank_count=2   meta_generation=3   selected_bank=1
fdt_phys=0x42000000  log_phys=0x42100000  ddr_hint=0x40000000
last_stage=3 SETUP_ARCH_ENTER
rule=fdt_scan
last_lines: BLM monitor init
```

**两个 bank 完全一致**（`tools/blm_forensics.py`）：

| bank | generation | 阶段序列 | 行数 | 最后阶段 |
|---|---|---|---|---|
| 0 | 2 | START_KERNEL → BEFORE_SETUP_ARCH → SETUP_ARCH_ENTER | 1 (`BLM monitor init`) | 3 |
| 1 | 3 | START_KERNEL → BEFORE_SETUP_ARCH → SETUP_ARCH_ENTER | 1 (`BLM monitor init`) | 3 |

### 2.1 证据强度：写入机制本身已自校验

`blm_tools.decode_bank()` 只接受通过 `magic + CRC + build_tag` 三重校验的 bank header，且每个 stage slot 还需单独通过 `blm_crc32(slot[:24])`。两个 bank 各 3 个阶段槽全部解析成功 ⇒ 阶段 3 是**真实、完整、未被破坏的写入**，不是 RAM 噪声或残余数据。`meta` 同样有 CRC 校验。

`ddr_hint=0x40000000` 与实机 `/proc/iomem` 一致，是 `DDR_BASE` 与 `__fdt_pointer` 推导的交叉验证；但它**不等于**已证明 `phys_to_virt(__fdt_pointer)` 的运行时虚拟地址有效（见 §4 假设 3）。

### 2.2 「只有一行」不携带「内核无输出」的信息

`BLM monitor init` 是 `blm_early_init()` 里 `blm_write_text()` 的**直接写入**，不是 printk。BLM 的 console 由 `console_initcall` 注册，而 `console_init()` 在 `start_kernel()` 中位于 `setup_arch()` **之后**；因此在阶段 3 之前，printk 根本不会流入 BLM 行槽。**只有一行是机制决定的必然结果，不能解读为「内核没有产生任何 printk」。**

## 3. 失败窗口（源码级）

`tests/patched_tree/arch/arm64/kernel/setup.c`：

```c
330  void __init setup_arch(char **cmdline_p)
331  {
332      blm_mark(BLM_STAGE_SETUP_ARCH_ENTER);   /* ← 日志最后到达 */
333      pr_info("Boot CPU: AArch64 Processor [%08x]\n", read_cpuid_id());
335      setup_machine_fdt(__fdt_pointer);
336      blm_mark(BLM_STAGE_FDT_SCAN_DONE);      /* ← 未到达 */
337      blm_reserve_logmem();                   /* ← 未到达 */
```

`setup.c:214-225`（本机 3.18.120 补丁树实际代码，非其他版本套用）：

```c
static void __init setup_machine_fdt(phys_addr_t dt_phys)
{
    if (!dt_phys || !early_init_dt_scan(phys_to_virt(dt_phys))) {
        early_print("\nError: invalid device tree blob ...\n");
        while (true)
            cpu_relax();
    }
    ...
}
```

⇒ 阶段 3 与阶段 4 之间唯一实质调用是 `setup_machine_fdt()` → `early_init_dt_scan()`。该失败分支若被触发会进入 `while(true) cpu_relax()`，**与「卡住、不 panic、不主动 reboot」的现象相容**；`early_print` 走 earlycon、不经过 printk 行槽，所以 BLM 里也没有那句错误文本。

**但相容 ≠ 已证实**：本次没有 PC 采样、没有 earlycon 输出、没有 `0x42000000` 处 FDT 头读回。不能直接断言 `early_init_dt_scan()` 返回 false，也不能断言 CPU 停在该循环上；同样不能排除阶段 3 到 `setup_machine_fdt()` 之间的 `pr_info()`、`read_cpuid_id()` 路径。

## 4. 假设 [H]（未验证，按当前证据价值排序）

1. ~~**新增 `/reserved-memory/blm-ram-log@42100000` 节点干扰早期 DT 扫描**~~：**已排除 [O]**。Round 11 用等长 NOP 剥离节点后，`generation=4` 仍停在阶段 3，阶段序列逐格相同。详见 `ROUND11_AB_RESULT.md`。
2. **`0x42000000` 处实际 FDT 内容/头部无效** → **已由 Round 12 双读实机证实，且找到机制**：失败态该地址 64 KiB 全零，原厂基线同地址是合法 FDT；候选内核 BSS 清零区 `[0x41dbc400, 0x420f665c]` 覆盖该地址，原厂不覆盖。详见 `ROUND12_ROOT_CAUSE.md`。
3. **DTB 链被截断为前 80 份 + 14,361,006 B 尾零**（第 8 次起引入的额外变量）：idx79 `totalsize` 由 409,557 → 409,688；M1 紧邻模型 40/40 自检通过，但链尾零布局仍是未排除变量。
4. **`phys_to_virt()` / 线性映射异常（已大幅降级）**：`blm_early_init()` 第 116 行正是 `phys_to_virt(0x42100000)`，且它成功写入的 meta/header/文本被 EDL 从**物理** `0x42100000` 逐字节读回并通过 CRC ⇒ 线性映射在 `start_kernel` 最开头已可用且指向正确物理地址。而 `0x42000000` 与 `0x42100000` 同属 `head.S` 映射的同一个 2 MiB block（`blm_layout.py` 口径 `[0x42000000, 0x42200000)`）⇒ 该假设基本可削弱，但仍建议直接 peek `0x42000000` 前 8 字节做最终确认。
5. `x0` / SCM / TZ 交接后 `__fdt_pointer` 语义异常（ROUND4 遗留 `[U]`）：现有阶段证据不足以优先怀疑，暂保留。

## 5. 下一步：离线差分审计已完成，A/B 对照镜像就绪

> 2026-11-14 13:04 更新：离线审计与**第 11 次 A/B 实机均已完成**，见 `OFFLINE_AB_AUDIT.md` / `ROUND11_AB_RESULT.md`。
> 离线结果：`AB_AUDIT 14/14`、对照镜像 `40/40`、镜像级差分 `24/24`，58 MB 仅 2 处差异，`unexpected=0`。
> 实机结果：剥离节点组 `generation=4` 仍停阶段 3 ⇒ **假设 1 排除**，首要嫌疑转为 `0x42000000` 处实际 FDT 头；设备已回滚并二次核验。

### 5.1 单变量约束（硬要求，已落实）

`blm_build_bootimg.py` 中 `pad = kernel_size - len(gzip) - len(new_chain)`，idx79 插入节点后 `totalsize=409,688`、尾零 `14,361,006 B`。**如果直接删节点，idx79 变回 409,557 B，链长短 131 B、尾零变成 14,361,137 B —— 这会引入新的链布局变量，破坏单变量对照。**

正确做法：把 `blm-ram-log@...` 节点及其 props 用等长 `FDT_NOP` 标签**原地覆盖**，保持 `totalsize=409,688`、`off_dt_struct/off_dt_strings/size_dt_*/链长/尾零/M1 边界` 全部不变，仅节点字节不同。

离线审计项：
- 对 `images/idx79_blm_ddr40000000.dtb` 做 FDT 结构全量校验（header 各字段、struct/strings 块边界、节点与属性遍历、CRC/对齐）。
- 生成等长 NOP 对照 DTB 并做二进制差分，证明除节点字节外零差异。
- 重打包对照镜像，跑 40/40 自检 + `blm_verify_rebuild.py` 差异验证，确认 `diff_regions` 只落在 idx79 节点区域。

### 5.2 之后才决定 A/B

- **剥离节点组**（本报告的 A 组，外部复核里称 B 组）：等长 NOP、其余全同。
- **本轮组**（本报告的 B 组，外部复核里称 A 组）：含节点，已测，稳定停在阶段 3。

若剥离组走过阶段 4 ⇒ 假设 1 成立，取证工具自身引入失败；若同样停在阶段 3 ⇒ 排除节点因素，转向假设 2/3，并在 `setup_machine_fdt()` 内 `early_init_dt_scan()` 前后加更细的安全阶段标记（须以本机 3.18.120 补丁树的实际函数布局为准）。

可复现命令（设备进 9008 后）：
```
tools\blm_capture_edl.bat 5
python tools\blm_forensics.py flash_log\blm_ram.bin flash_log\blm_ram.forensics.json
```

## 6. 本轮未执行

未做第 11 次 A/B 实机（离线对照镜像已就绪）、未在 `setup_machine_fdt()` 内加细粒度插桩、未读候选失败后 `0x42000000` 处 FDT 头、未验证 warm reset 跨 bootloop 保留性（但双 bank/generation 已证明多次失败日志留存同一 RAM 区）、未直接读 aboot `0x91FFF990`。离线差分审计已完成，见 `OFFLINE_AB_AUDIT.md`。

## 7. 证据文件

`flash_log/blm_ram.bin`、`flash_log/blm_ram.forensics.json`、`flash_log/20261114_blm_round10_timeline.txt`、`flash_log/20261114_blm_bootonly_timeline.txt`、`tools/blm_forensics.py`、`tools/blm_firehose_peek.py`、`tools/blm_capture_edl.bat`、`tools/blm_round10_capture.ps1`。
