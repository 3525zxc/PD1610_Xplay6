# ⑭ prebuilt 路线：同时上传的必要清单与续修建议

日期 2026-11-14 23:28。用途：用户决定把 `D:/16/PD1610_81`（prebuilt 路线，40 GiB）与自编译内核工程**一起上传**，且以后可能要继续修这条路线未探明的 bug。本文给出「按修 bug 需求倒推」的必要上传清单。

---

## [O] 这条路线做到哪了

- 目标：vivo 未发布 PD1610/PD1619 的 3.18 内核源码，所以走「**原厂 prebuilt 内核 + 真机 vendor blobs + 借用 LeEco s2 / PD1619 设备树**」编译 LOS16 ROM，**不编译内核**。
- 时间 2026-11-10 → 11-12，早于 BLM 自编译内核路线（11-14）。
- **WiFi 已彻底修通**：`Wi-Fi is enabled`、`wpa_supplicant=running`、wlan0/p2p0 都在、设置页列出 9 个 AP。最终镜像 `out/system.img` = **sys13**，sha `686de5de21ad6c8837530836ba9483bd63e69ce660d2de289c4c0a2eecb88e9a`。
- WiFi 修复有 4 条因果链（AOSP9 源码版 wifi HAL、删 vivo `libwifi-hal.so` 覆盖规则、注释 `WIFI_DRIVER_FW_PATH_AP/STA`、supplicant conf 改单行 + 只留 `-iwlan0`），详见 `evidence/_log_append4.md`。

## [O] 未解 TODO（这就是「以后要修的 bug」）

| # | 问题 | 现状 | 需要什么才能修 |
|---|---|---|---|
| 1 | 相机 `Number of camera devices: 0` | 116 chromatix / 136 mmcamera 库都在镜像里，provider 已注册 | `mm-qcamera-daemon` 日志、权限、compat_libs、可刷的已知良好 system.img 做对照 |
| 2 | `xtwifi-inet-agent` 缺 `libcurl.so` | XTRA 辅助下载，非致命 | 从 8.1 抽库 + vendor mk 拷贝规则 |
| 3 | **发布前清诊断代码** | `init.cpp` PD1610 DIAG、`init.qcom.rc` kmsg 标记、`PD_WD_SECONDS 100000`、`init.rc` 的 `pd1610-crypto-fix`、`printk 7 7 7 7` | 最终版源码 + 构建脚本；清完须**重编 boot + system 并复测首启** |
| 4 | sepolicy 仍 permissive | `configstore-hal-1-0` 被 seccomp 拦 `getdents64`，每 5 s SIGSYS 重启 | avc denial 日志、seccomp policy、device 树 sepolicy 目录 |
| 5 | **已于 2026-11-15 更正：ROM zip 已产出** `PD1610_LOS16_20261112_UNOFFICIAL.zip`（935,087,013 B / sha `97c3137e…`，网盘 `15_`）；仍缺发布前清诊断代码后的重打包与 TWRP 卡刷验证 | — | 发布包脚本、签名/footer 工具 |

**三条已纠正的误判，别再走回头路**（`evidence/_log_append3.md` / `_log_append4.md`）：
1. 「设备卡死 / 内核 panic」是误判 —— 流式 logcat + 每 2 s dmesg 证明设备一直活着，只是点 WiFi 开关后 USB/adbd 断开一阵。
2. `WifiScanningService: wifi driver unloaded` 是关闭 WiFi 时的正常 `CMD_DRIVER_UNLOADED`，不是缺驱动。
3. 「AOSP9 wifi HAL 与 8.1 `libwifi-hal.so` ABI 不兼容」是错的 —— 真因是 8.1 同名 blob **覆盖**了新编的 AOSP9 版本，导致 `wifi_cleanup+28` SIGSEGV；删掉拷贝规则就好了。

---

## 上传建议（核心）

**一句话：GitHub 放「13.56 MiB 文本层」，百度网盘放「sys13 基线镜像 + 可重建这套源码的二进制」，40 GiB 里的其余部分不用传。**

理由：40 GiB 中 `migrated_from_C` 20 G（从 C 盘迁移的副本）、`backup` 8.9 G（分区 dump，可重新回读）、`out` 6.6 G（构建产物）、`release` 2.8 G（ROM 与 system.img）、各 `upload_*` 快照，绝大部分可再生或重复。**不可再生的是**：逆向结论、1042 行移植笔记、87 个自研工具、blob 依赖清单、以及 **sys13 那 7 个最终版源码改动文件**。

### A. GitHub（公开，13.56 MiB / 828 文件）

用 `prebuilt_extract/prebuilt_verbatim/`（按你决定的全量公开）或 `prebuilt_sanitized/`（脱敏备选）作为仓库根，也可并入主仓库的 `prebuilt/` 子目录。

| 组 | 内容 | 修 bug 时的作用 |
|---|---|---|
| `evidence/` | aboot 失败路径、ROUND3–5 状态机、GPL/移植路线、`_log_append1–4`（**WiFi 修复全过程与 TODO**）、`BLOBS_20261111.md` | 判断「之前试过什么、为什么错」 |
| `refs/` | **1042 行 `PD1619_PORTING_NOTES.md`**、BoardConfig、mk、fstab、extract-files.sh | 借树方法、非 Treble 的 ramdisk 坑 |
| `release/.../patches/` | **sys13 最终版 7 个源码改动 + 5 个工具脚本** | **改 bug 的起点**，与 `device_tree/` 基线 diff 后才知道改了什么 |
| `device_tree/device/vivo/pd1610/` | 完整 device 树文本（BoardConfig.mk、device.mk、init.pd1610.rc、fstab、manifest.xml、keylayout、sepolicy README） | 改功能的落点 |
| `scripts/` + `build/` | 87 个工具 + `build_pd1610.sh`（绕开 lunch 的编译脚本） | `bash ~/build_pd1610.sh systemimage`（约 75 s） |
| `blobs/` | 1824 文件 inventory、211 符号链接、1041 条 proprietary-files、1370 ELF 依赖闭包 | 相机/库依赖排查 |
| `work/` | 实机日志（含 `wifi_logcat_stream.txt`、`wifi_dmesg_seq.txt`） | 复现「点开关后 adbd 断开」的取证方法 |

**缺一不可的两份**：`evidence/_log_append4.md`（TODO 与 WiFi 因果链）和 `release/.../patches/`（最终源码）。少了前者接手者会重做误判，少了后者改 bug 会基于旧基线。

### B. 百度网盘（私有，按优先级）

| 优先级 | 路径 | 体积 | 为什么必须 |
|---|---|---|---|
| **P0** | `out/system.img`（sys13, `686de5de…`） | 1.85 GiB | **已知良好基线**。没有它，改出来的回归和原本就坏的状态分不清 |
| **P0** | `device_tree/device/vivo/pd1610/prebuilt/kernel` | 56 MiB | prebuilt 路线的核心：`TARGET_PREBUILT_KERNEL` 指向它，不编译内核全靠它 |
| **P0** | `release/.../images/boot.img`（`929fda99…`） | 58 MiB | 回滚基线，刷错能自救 |
| **P0** | `blobs/_vendor.tar` + `blobs/modules/` | 494 MiB | 1824 个 vendor 文件权威副本 + 13 个 `.ko`（含 `wlan.ko`）；相机 TODO 要查库 |
| **P1** | `release/.../patches/compat_libs/` | 3.7 MiB | 8.1 兼容库 `.so`（camera / GNSS / wifi 私有实现），修相机必需 |
| **P1** | `refs/device_PD1619.tar.gz` | 5 MiB | 借用的设备树打包副本 |
| **P1** | `backup/` 48 个分区 dump | 8.9 GiB | 设备可能不在手边时，唯一能重新取证/救砖的副本；其中 `aboot`/`devinfo`/`modem` 最值钱 |
| **P2** | `release/.../UNOFFICIAL.zip` | 935 MiB | 最终可刷 ROM，但可由 system/boot 重打 |
| **P2** | `release/.../images/system.img` | 1.85 GiB | 与 `out/system.img` 同版，二选一即可，不必两份都传 |
| **P2** | `scripts/prog_ufs_firehose_8996_ddr.elf` + QSaharaServer/fh_loader | ≈1 MiB | 9008 通道，救砖用（自编译工程归档里已有一份） |
| 不传 | `migrated_from_C/`、`upload_*`、`work/*.img`、`out/*.bin`、`build/_repo-src*` | ≈26 GiB | 重复/中间产物/历史快照 |

**网盘合计**：P0+P1 ≈ 11.4 GiB；加 P2 约 14 GiB。相比原始 40 GiB 省一半以上，且每一项都有明确用途。

### C. 已经不用单独传的

`prebuilt_extract/`（含两套发布树 + `manifest.json` + `README.md`）**已在自编译工程的全量分卷 `archive/volumes/` 里**，随那 969 MiB 一起上传即可。它的 `manifest.json` 列了所有二进制资产的原路径、体积与用途，是百度网盘那批文件的索引。

---

## 续修时的工作形式（和自编译路线一致）

沿用 `offline/13_continuation_playbook.md` 的循环，差异点：

1. **单变量**：改 `device/vivo/pd1610/` 或 `vendor/vivo/pd1610/` 里一处，重编 `systemimage`，刷 `system` 分区（不是 boot）。
2. **先 diff 基线**：`device_tree/` 是早期基线，`release/.../patches/` 是 sys13 最终版。改之前先 `diff -ru` 两者，确认自己站在最终版上。
3. **对照镜像**：任何改动前先确认手上 `system.img` 的 sha 是 `686de5de…`（sys13），否则结论不可比。
4. **编译**：`bash ~/build_pd1610.sh systemimage`（约 75 s）；`lunch lineage_pd1610-userdebug` 在这棵树上会卡死，别用。
5. **取证**：相机/服务类问题用 `logcat -v time -b all` 流式抓 + 每 2 s 采 dmesg；不要因为 USB 掉线就判「设备挂了」。
6. **清理诊断代码那条 TODO 要特别小心**：清完必须**同时重编 boot + system** 并复测首启，只编一边会引入不同步。

---

## 边界

- 本清单按 2026-11-14 的 `D:/16/PD1610_81` 实盘盘点；体积与哈希以 `prebuilt_extract/manifest.json` 和 `release/.../sha256sums.txt` 为准。
- 提炼包**不含**二进制本体（只列路径/体积/用途），需从原路径上传网盘。
- **本机尚未清空**；删除任何路径需人明确确认且云端校验通过，见 `offline/12_ai_handoff_index.md` §8。

---

## 2026-11-15 补充：ROM 包与 C 盘记录已入网盘

- 可刷 ROM：`15_LOS16_ROM刷机包/PD1610_LOS16_20261112_UNOFFICIAL.zip`，935,087,013 B，sha `97c3137e…`，同目录有 `SHA256SUMS` 与 `README_刷机与校验.md`（`sha256sum -c` 已通过）。
- 第一阶段研究：`14_寒霜刷机_C盘工作目录/`（84 文件 / 4.9 MiB 全量），
  GitHub 文本层 `prebuilt_c/`（97 份，会话日志未公开）。
- 网盘现为 16 类 / 76 GiB，逐类清单见 `00_必读_恢复说明/上传清单.md`。

