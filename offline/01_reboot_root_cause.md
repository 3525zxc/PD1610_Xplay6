# ① `adb reboot bootloader` 失效 —— 离线符号/反汇编差分

状态：**离线结论完成，未实机验证**。方法取自非 ARIS 的 `binary-diff` 技能（「内核缺符号时用旧版推导」），全部证据落在本目录。

## 输入与可复现步骤

| 项 | 值 |
|---|---|
| 原厂镜像 | `D:/16/PD1610_81/release/PD1610_LOS16_20261112/images/boot.img` sha `929fda99…` |
| 原厂运行时符号 | `flash_log/stock_kallsyms_addr.txt`，96,829 符号，真实地址（`echo 0 > /proc/sys/kernel/kptr_restrict` 后取得） |
| 原厂内核 Image | `offline/stock_Image.bin`，gzip 起点 offset 4096，解压后 26,549,760 B，DTB 链尾部 47,159,172 B |
| 自编译内核 | `build/ftsirq-20261114192500/System.map` + `vmlinux`（`3.18.120-perf #9`） |
| 反汇编 | `offline/01_disasm.sh`（原厂 raw binary）、`offline/01_disasm_custom.sh`（自编译 ELF） |

`_text = 0xffffffc000080000`，raw Image 文件偏移 0 对应该虚拟地址；`do_msm_restart` 原厂 VA `0xffffffc0008a2d4c`、自编译 VA `0xffffffc0009d44dc`。

## [O] 观察

**符号大小差分**（相邻符号地址间隔，单位字节）：

| 符号 | 原厂 3.18.71 | 自编译 3.18.120 | 差 |
|---|---|---|---|
| `do_msm_restart` | 1492 | 740 | **-752** |
| `msm_restart_probe` | 936 | 752 | -184 |
| `qpnp_pon_set_restart_reason` | 128 | 128 | 0 |
| `qpnp_pon_system_pwr_off` | 292 | 292 | 0 |
| `mdm_get_restart_reason` | 148 | 148 | 0 |
| `esoc_msm_restart_handler` | 52 | 52 | 0 |

⇒ PMIC 侧 reason 写入相关函数**逐字节同尺寸**，差异集中在 `do_msm_restart` 本身。`msm_restart_prepare` 两版都无独立符号（被内联进 `do_msm_restart`）——这解释了 Round26 改它的写入顺序为何无效。

**原厂 `do_msm_restart` 调用表**（`01_do_msm_restart_calls.json`，21 个唯一目标）中，自编译版**没有**的：

`set_dload_mode_bbk`、`set_aee_system_restarting`、`set_aee_dump_param`、`uncached_logk`、`msm_trigger_wdog_bite`、`scm_disable_sdi`、`halt_spmi_pmic_arbiter`、`deassert_ps_hold`、`__const_udelay`、`__stack_chk_fail`

自编译版调用表止于 `flush_cache_all`（`01_do_msm_restart_custom.asm`，192 行 / 31 条 `bl`），没有上述底层复位动作。

**原厂函数引用的字面字符串**（`01_do_msm_restart_strings.json`）：`bootloader`、`recovery`、`dm-verity device corrupted`、`dm-verity enforcing`、`keys clear`，另有 vivo 私有的 **`silent`、`survival`、`bsptmode`**。

**符号集合差分**：原厂独有 restart/pon 相关符号 12 个，含 `set_dload_mode_bbk`、`qpnp_pon_reason_str`、`g_aee_system_restarting`、`set_aee_system_restarting`。自编译"独有"77 个中绝大多数是 `__kcrctab_*` / `__kstrtab_*`（`CONFIG_MODVERSIONS` 导出符号 CRC），**不是实现差异**，勿误读。

## [H] 假设（待实机验证，不写成结论）

1. **H1（最可能）**：本机 aboot 读的 bootloader 标志由 BBK 私有路径写入（`set_dload_mode_bbk` → IMEM/dload 区，或 `uncached_logk` 写 uncached log 区），自编译内核完全没走这段，因此 IMEM `0x77665500` 和 `qpnp_pon_set_restart_reason` 都写了也不被 aboot 采信。
2. **H2**：自编译 `do_msm_restart` 缺 `deassert_ps_hold` / `halt_spmi_pmic_arbiter`，复位由别的路径完成，aboot 上电时看到的状态与原厂不同。
3. **H3（已由实机排除）**：reason 写入顺序 —— Round26 (`864b0522…`) 把写入提前到 `qpnp_pon_system_pwr_off` 之前，`adb reboot bootloader` 仍是普通重启。

## 下一步（离线可继续，不必先刷机）

1. 反汇编原厂 `set_dload_mode_bbk`（VA 由 `stock_kallsyms_addr.txt` 查）与 `uncached_logk` 调用点，确认它们写的是哪个物理地址/寄存器；用 9008 `peek` 在 `adb reboot bootloader` 前后读该地址比对。
2. 若确认是 IMEM/dload 标志，把对应写入移植进自编译 `do_msm_restart`（约 1–2 处 `__raw_writel`），而不是继续改 `msm_restart_prepare`。
3. 验证命令：`adb reboot bootloader` 后 60 s 内 `fastboot devices` 出现 `5fccbfeb fastboot`。

## 边界

- 本结论只到「两版实现不同 + 差异位置」，**未证明** H1 就是 aboot 不进 fastboot 的原因。
- 原厂 `Image` 是 raw binary 无 ELF 符号，函数边界按 kallsyms 相邻符号推断，尺寸是近似值。
- `stock_kallsyms_addr.txt` 需 root 且临时把 `kptr_restrict` 置 0 才能取得地址；该改动不写分区、重启即失效。
