# 离线差分审计 · A/B 单变量对照镜像就绪

> 2026-11-14 12:08–12:14，**全程离线**：未连接设备、未进 9008、未刷写、未执行第 11 次实验。
> 目的：按外部复核建议，先完成 BLM 新增节点的离线差分审计，再决定是否需要第 11 次 A/B 实机验证。

## 0. 结论

**严格单变量对照已构建并通过三层验证，A/B 两组在整个 58,483,968 B 镜像里只差 2 处**：`boot.img` header 的 `id`（20 B，按 mkbootimg 算法重算）与 idx79 DTB 内 `blm-ram-log` 节点的 128 B。其余字节逐字节相同。对照镜像已具备随时刷写的条件。

## 1. 关键设计：等长 `FDT_NOP` 覆盖

直接删除节点会让 idx79 从 409,688 B 缩回 409,557 B，链长短 131 B、尾零由 14,361,006 变 14,361,137 —— 会引入新的链布局变量。因此改用 FDT 规范的 `FDT_NOP` 标签**等长覆盖节点字节**：

| 项 | 含节点组 | 剥离节点组 |
|---|---|---|
| idx79 大小 | 409,688 B | 409,688 B（不变） |
| `totalsize` / 全部 10 个 FDT 头字段 | — | 逐字节相同 |
| `off_dt_struct` / `off_dt_strings` / `size_dt_struct` / `size_dt_strings` | 56 / 373264 / 373208 / 36421 | 完全相同 |
| strings 块 | — | 逐字节相同 |
| FDT 节点数 | 1984 | 1983 |
| `/reserved-memory` 子节点数 | 10 | 9 |
| `blm-ram-log` 节点 | 存在 | `ABSENT` |
| DTB 链长 / 尾零 / M1 边界 | 30,947,277 / 14,361,006 / PASS | 完全相同 |

节点位于 struct 块 `[370360, 370488)`，共 128 B，被 32 个 `FDT_NOP` 标签替换；`parse_nodes()` 与 `blm_patch_dtb.py inspect` 均确认对照 DTB 结构合法、节点平衡、`FDT_END` 存在。

## 2. 三层验证结果（真实输出）

| 层 | 工具 | 结果 |
|---|---|---|
| FDT 结构全量审计 | `tools/blm_ab_audit.py` | `AB_AUDIT status=PASS pass=14/14`，`outside=0`、`header_same=True`、`strings_same=True` |
| 对照镜像构建 | `tools/blm_build_bootimg.py` | `BOOTIMG_BUILD_OK status=PASS pass=40/40`，`log_phys=0x42100000` |
| 镜像级二进制差分 | `tools/blm_verify_ab.py` | `AB_VERIFY status=PASS pass=24/24`，`diff_4b=37`、`unexpected=0` |

差异区间（4 B 对齐扫描）：
```
[576, 596)          -> header id (0x240..0x254)
[42155256, 42155384) -> idx79 内 log node 128 B
```

全套既有自测 `tools/build_selfcheck.sh` 末尾 `SELFCHECK_OK`；6 份 JSON 报告全为 `PASS`（40/40、40/40、40/40、24/24、19/19、14/14）。含节点镜像 sha256 未变：`4abe6ba6…`。

## 3. 产物

| 文件 | 说明 | sha256 |
|---|---|---|
| `images/idx79_control_nonode_nop.dtb` | 等长 NOP 对照 DTB，409,688 B | `6bfeb46c40582748f2d9a6588435d545237ff663161a7ddfd48349bba7136edc` |
| `images/boot_los16_blm_control_nonode.img` | **剥离节点组**镜像，58,483,968 B | `13bd3242d2efabfbc52ccb2155d6b86c9f99b5ce16baa2916279a524a5fd675b` |
| `images/boot_los16_blm_ddr40000000.img` | **含节点组**镜像（Round 10 实测组） | `4abe6ba6cb7fd6b3d78c8eebf30119954b8c14a73fce76070b5e54521a20f521` |
| `images/idx79_control_nonode_nop.audit.json` | FDT 结构审计明细 | — |
| `images/boot_los16_blm_control_nonode.report.json` | 对照镜像 40 项自检 | — |
| `images/boot_los16_blm_control_nonode.abverify.json` | 镜像级差分明细 | — |

新增工具：`tools/blm_ab_audit.py`（结构审计 + NOP 生成）、`tools/blm_verify_ab.py`（镜像级差分）；`tools/blm_build_bootimg.py` 增加 `--idx79-dtb` / `--expect-log-node` 两个可选参数，默认行为不变。

## 4. 口径与边界

- **这是「移除节点」的一种实现，不等价于「从未插入节点」**：对照 DTB 的 strings 块仍保留补丁器新增过的属性名字符串（未引用但合法），struct 块多 32 个 NOP 标签。二者在 A/B 两组中完全一致，因此不构成变量；但它意味着对照组不是「原厂 idx79 原样」。
- 两组内核二进制、gzip、ramdisk、签名块、BLM 插桩代码、候选配置、地址口径、`122→80` 链截断与尾零全部相同，**BLM 仍按 `__fdt_pointer + 0x100000` 写 `0x42100000`**，读回流程与 `blm_capture_edl.bat 5` 完全不用改。
- 剥离节点组的日志区不再有 `/reserved-memory` 标注，但 `blm_reserve_logmem()`（`memblock_reserve`）仍会在阶段 4 之后执行，与 DTB 节点无关。
- 本次**未验证**任何实机行为：剥离组能否走过 `FDT_SCAN_DONE` 仍是未知。判据不变：走过阶段 4 ⇒ BLM 节点引入故障；仍停阶段 3 ⇒ 排除节点因素，转查 `0x42000000` 处实 FDT 头与链尾零。

## 5. 第 11 次 A/B 实机：**已执行，结果见 `ROUND11_AB_RESULT.md`**

2026-11-14 12:57–13:04 刷入剥离组镜像，t=95 s 自动进 9008，全量读回 `blm_ram_round11.bin`（sha256 `8fd368a7…`，`generation=4`）。

**结论：剥离节点组仍停在 `SETUP_ARCH_ENTER`（阶段 3），阶段序列与含节点组逐格相同 ⇒ 假设 1「BLM 保留区节点引入故障」已排除。** 首要嫌疑转为「`0x42000000` 处实际 FDT 内容/头部无效」，其次为 `122→80` 链尾零。设备已回滚并二次核验原厂系统。

后续可复现命令（**未执行**）：下一次候选失败进 9008 时，除 BLM 区外顺手读 FDT 头：
```
python tools\blm_firehose_peek.py --com 5 --address 0x42000000 --size 0x40 --chunk 0x40 --no-upload --out flash_log\fdt_head.bin --workdir edl_probe
```
再按既有流程回滚原厂 `boot.img` 并验证 `uname -r = 3.18.71-perf-g8a8c60dd`。
