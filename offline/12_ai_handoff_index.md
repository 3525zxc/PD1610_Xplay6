# ⑫ 给接手 AI 的资源索引（贴这份就够）

日期 2026-11-14 23:00。用途：项目文件已从本机清空，未来恢复时**把本文件整份贴给 AI**，它就知道该让你从百度网盘取哪些文件、按什么顺序放回去、以及从哪一步继续。本文件设计为「不依赖任何其他上下文」可独立阅读。

---

## 0. 一句话背景

vivo Xplay6（PD1610，MSM8996，LineageOS 16）上，把**自编译 3.18.120 内核**从 bootloop 一路修到能进桌面并让触摸可用；建立了 BLM（`bootloop_monitor`）固定 RAM 日志 + 高通 9008 Firehose `peek` 的取证通道；定义了「第 3 档」（自编译内核 + 关键 vendor 驱动源码化）的可验收完成度。**当前严格完成度 50/50，`UNVERIFIED=0`，四门仍 FAIL**。

「以后继续做」= 从 B 轮开始（见 §5），不是从零开始。

---

## 1. 三个存放位置与分工

| 位置 | 放什么 | 体积 | 性质 |
|---|---|---|---|
| **GitHub 公开仓库** | `publish/` 全量文本细节 + **`prebuilt_extract/prebuilt_verbatim/`**（老路线文本成果，可并入同一仓库或独立仓库） | 5.08 MiB + 6.80 MiB | 全部细节公开，**不含二进制** |
| **百度网盘（主备份）** | `archive/volumes/*` 分卷 + `manifest.json` + `SHA256SUMS` + `RESTORE.md` | 969 MiB / 2 卷 | **全量冷备**，含所有二进制、WSL 重建集、prebuilt 提炼包 |
| **百度网盘（追加资源）** | 见 §3，原厂 ROM / 分区 dump / vendor blob / WSL 完整导出 | 约 2–45 GiB | 私有、可再下载，重建时最值钱 |

**关键**：GitHub 仓库只是「可读文档层」，**不能靠它重建**。真正能重建的是网盘分卷。分卷里已包含 `wsl_rebuild/`（1.6 GiB 最小重建集）和 `prebuilt_extract/`（老路线提炼包）。

### 两份「给 AI 看」的文档，别搞混

| 文件 | 回答什么 | 什么时候读 |
|---|---|---|
| `offline/12_ai_handoff_index.md`（本文件） | **资源在哪**：三处存放、分卷清单、追加资源、WSL 重建集、关键结论、开场白 | 恢复项目、决定要下载哪些文件时 |
| `offline/13_continuation_playbook.md` | **活怎么干**：单变量循环、人机分工、8 步 SOP、7 层定位方法库、给 AI 的提示词模板、坑速查 | 资源到位、准备开新一轮实验时 |
| `offline/14_prebuilt_upload_checklist.md` | **prebuilt 老路线**：未解 TODO、上传必要清单、续修方法 | 要修 prebuilt 路线的相机/sepolicy/诊断代码清理时 |

建议开场白里三份都点名，让 AI 先读索引再读手册。

---

## 2. 网盘必备：分卷清单与校验

```
archive/
  volumes/blm_full.tar.zst.part01    943,718,400 B (900 MiB)
  volumes/blm_full.tar.zst.part02     72,215,444 B (68.9 MiB)
  manifest.json                      81,742 B  (457 文件的路径/大小/sha256)
  SHA256SUMS                         279 B
  RESTORE.md                         恢复步骤
```

归档内容 = `D:/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/` 整个工程（排除 `publish/`、`publish_sanitized/`、`archive/`），**4.04 GiB / 457 文件 → zstd 压到 969 MiB**。包含：

- `images/` 19 个 `boot.img`（每个 58,483,968 B）及各自的 `.preflight.json` / `.report.json`
- `build/` 各轮 `Image.gz-dtb` / `System.map` / `vmlinux_size.txt` / `build.log`
- `flash_log/` round10–roundA 全部 dmesg / input / I²C / props / getevent / 时间线、RAM dump、原厂基线
- `fixtures/` 适配版源码 `fts_vivo_dt*.c` / `fts_vivo.h` / `cyttsp_button_vivo*.c` / `msm-poweroff_vivo.c` / 原厂 DTB
- `offline/` 01–12 全部离线报告 + 脚本（含本文件）
- `tools/` 全部自研 Python / shell 工具
- `wsl_rebuild/` **WSL 最小可重建集**（见 §4）
- `kernel/` BLM 模块 C 源码

恢复步骤见 `archive/RESTORE.md`。恢复后第一件事：`sha256sum -c SHA256SUMS`，再按 `manifest.json` 逐文件核对。

---

## 3. 网盘「追加资源」清单（容量够就全放）

这些**不在分卷里**，因为它们在工程目录之外。按重要度排序：

| # | 路径 | 体积 | 用途 | 缺了会怎样 |
|---|---|---|---|---|
| 1 | `D:/16/PD1610_81/release/PD1610_LOS16_20261112/` | **1.9 GiB** | prebuilt 路线产出的 LOS16 发布包，含 `images/boot.img`（sha `929fda998547…`，58,483,968 B）、`system.img`、`flash_all.sh`、`sha256sums.txt` | 没有一键回滚基线，刷机无法自救 |
| 2 | `D:/16/PD1610_81/scripts/prog_ufs_firehose_8996_ddr.elf` + `QSaharaServer.exe` / `fh_loader.exe` | ≈946 KiB | 9008 Firehose programmer，读物理 RAM 的唯一通道 | bootloop 时无法抓 BLM 固定槽 |
| 3 | `/vendor/firmware`、`/firmware`、`/bt_firmware` 全量 blob | **≈83 MiB / 332 文件** | 原厂固件本体；清单见 `offline/03_firmware_inventory.csv` | 无法复现固件依赖，`st_fts.bin` 缺失一类问题无从对照 |
| 4 | `D:/16/PD1610_81/blobs/_vendor.tar` + `blobs/modules/` + `refs/device_PD1619.tar.gz` | **≈499 MiB** | 设备端 `/system/vendor` 权威归档（1824 文件）、13 个 `.ko`、借用的 PD1619 设备树 | prebuilt 路线的 blob 依赖闭包无法重建 |
| 5 | `D:/16/PD1610_81/backup/` | **8.9 GiB / 48 分区** | 真机回读的 aboot / modem / devinfo / boot 等原始分区 dump | 分区级取证与救砖不可复现（设备可能已不在手边） |
| 6 | `D:/xplay6/tools/platform-tools/` | 11 MiB | `adb.exe` / `fastboot.exe` | 换机后要重新找版本 |
| 7 | `D:/WSL/PD1610/ext4.vhdx` 完整导出（`wsl --export`） | 176 GiB | 完整 WSL 原样还原（路线 A） | 只是失去「一键原样」；路线 B（§4）照样能重建 |
| 8 | `D:/16/PD1610_81/out/`、`migrated_from_C/`、各 `upload_*` 快照 | ≈26 GiB | 构建中间物、从 C 盘迁移的副本、历史上传快照 | 基本可再生/重复，**不用放** |

**建议**：#1–#6 必放（合计约 11 GiB）；#7 看网盘余量，176 GiB 里约 145 GiB 是可再生垃圾，**不放也不影响重建**；#8 不用放。

### `D:/16/PD1610_81` 是什么（prebuilt 路线）

40 GiB 的**老工程**，时间 2026-11-10 → 11-12，早于 BLM 自编译内核路线。因为 vivo 从未发布 PD1610/PD1619 的 3.18 内核源码，这条路用的是「**原厂 prebuilt 内核 + 真机 vendor blobs + 借用 LeEco s2 / PD1619 设备树**」编译 LOS16 ROM，**不编译内核**。核心结论在 `evidence/GPL_AND_PORTING_ROADMAP.md` 与 1042 行的 `refs/PD1619_PORTING_NOTES.md`。

**已提炼**：`tools/blm_prebuilt_extract.py` 把 39.8 GiB 里不可再生的文本层抽成 **442 文件 / 6.80 MiB**，落在 `prebuilt_extract/`：

```
prebuilt_extract/
  README.md, manifest.json          说明 + 458 项清单（含二进制资产体积/路径）
  prebuilt_verbatim/               verbatim 全量文本（按用户决定可公开）
  prebuilt_sanitized/              脱敏版，可选
```

分 8 组：`evidence/`（aboot 失败路径、ROUND3–5 状态机、GPL/移植路线）、`refs/`（移植笔记、BoardConfig、mk、fstab）、`scripts/`（87 个自研工具）、`build/`（WSL 供给与 LOS16 构建）、`device_tree/`（反编译 DTS 基线）、`blobs/`（1824 文件 inventory、211 符号链接、1041 条 proprietary-files、1370 ELF 依赖闭包）、`work/`（实机日志）、`release/`（flash_all / sha256sums）。

**上传分工**：`prebuilt_verbatim/` 或 `prebuilt_sanitized/` 是 **828 文件 / 13.56 MiB**（含 sys13 最终版补丁源码），直接推 GitHub（可并入主仓库的 `prebuilt/` 子目录或独立仓库）；上表 #1/#4/#5 的二进制**只走百度网盘**，`prebuilt_extract/manifest.json` 里列了原路径与体积，不会复制进提炼包。提炼包本身已在全量分卷里，不用单独再传。

**以后要修 prebuilt 的 bug**：完整清单与建议在 `offline/14_prebuilt_upload_checklist.md`。最关键是两份别丢 —— `release/.../patches/`（sys13 最终版 7 个源码改动）和 `out/system.img`（sha `686de5de…`，WiFi 修通的已知良好基线）。未解 TODO 有 5 项（相机 0 设备、libcurl、诊断代码清理、sepolicy/configstore、ROM zip 未产出），全文在 `evidence/_log_append4.md`。

补一条：`fixtures/pd1610_81916_vivo.dtb`（400 KiB，原厂 DTB 二进制）和 `offline/stock_Image.bin`（26 MiB，原厂内核镜像）**已在分卷里**了，不用单独传。

---

## 4. WSL 重建集（`wsl_rebuild/`，已在分卷里）

| 文件 | 体积 | 是什么 |
|---|---|---|
| `src/kernel-src.tar` | 733,378,560 B | 打过全部补丁的内核源码树 `msm8996-lineage-16.0-blm-shrink-20261114133000`（无 `.git`） |
| `config/kout-shrink.tar` | 781,803,520 B | 当前构建输出，含 `.o` / `vmlinux` |
| `config/.config` / `System.map` | 124 KiB / 5 MiB | 1468 个 CONFIG 键；符号表 |
| `toolchain/aarch64-linux-android-4.9.tar` | 101 MiB | 交叉编译器 |
| `scripts/` | 小 | `blm_trace_build.sh` / `blm_build_bootimg.py` / `blm_preflight.py` / fixtures / BLM 模块源码 |
| `env/environment.txt` | 小 | Ubuntu 20.04.5、apt 包全表、`/etc/wsl.conf`、构建命令、绝对路径 |
| `SHA256SUMS` | 小 | 40 个文件校验 |

**重建 SOP 全文在 `offline/11_wsl_rebuild_guide.md`**。核心三条硬编码路径（构建脚本写死，不能改）：

```
SRC = /home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000
OUT = /home/builder/ksrc/kout-los16-blm-shrink-20261114133000
TC  = /home/builder/los16/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-
make O="$OUT" -j14 Image.gz-dtb     (ARCH=arm64 SUBARCH=arm64 LC_ALL=C)
```

D 盘工程路径也写死在脚本里：`/mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/`。**恢复时必须放回同一路径**，否则所有脚本要改。

---

## 5. 从哪一步继续：实验队列与当前判据

完整版见 `offline/05_experiment_queue.md`，A 轮结果见 `offline/08_roundA_result.md`。

| 轮 | Claim | 量化判据 | 状态 |
|---|---|---|---|
| **A** | 全量采集收窄完成度 | 12 类证据 + 3/3 冷启动 + 覆盖率区间收窄 | ✅ **已完成**（`20/88` → `50/50`） |
| **A′** | `b6d5debb…` bootloop 是 pinctrl 后新代码卡死同步 initcall，还是误判 | 刷候选 → 9008 读 BLM 固定槽；`last_stage=12 KERNEL_INIT` 且最后 initcall 落在 `cyttsp_button_init` ⇒ 真卡死 | ⬜ 未做，需 9008 |
| **B** | 补 `irqflags \|= IRQF_ONESHOT` 后导航键可用 | `3-0028` 绑定、`vivo_virtual_key` input 出现、`getevent` 收到 172/158/139 | ⬜ 下一轮 |
| **B′** | `touch_cold` 修复（冷启动 30 s 内触摸可用） | 冷启动 30 s 内 `getevent` 有 `ABS_MT_*` | ⬜ 线索见 §6 |
| **C** | 两个 tasha jack input 恢复 | input 列表出现 `msm8996-tasha-cdp-snd-card Headset/Button Jack` | ⬜ |
| **D** | `adb reboot bootloader` 走 BBK 私有路径 | 补 `__raw_writel` 后 60 s 内 `fastboot devices` 出现 | ⬜ |
| 长尾 | `goodixfp` 指纹驱动源码化 | input 9/9 | ⬜ 5–15 工作日，可能失败 |

**每轮强制动作**（这是之前「干了活却算不出完成度」的根因）：

```bash
python tools/blm_round_capture.py --tag roundNN --image <boot.img> --score
python tools/blm_coldboot_verify.py --cycles 3 --report flash_log/roundNN_coldboot.json
# 覆盖率工具必须带：
#   --hal-ignore init.svc.vivo-fingerprint-sh   （该服务 disabled+oneshot，stopped 是正常态）
```

---

## 6. 复现必备的关键结论（别重新踩）

1. **bootloop 根因**：自编译内核 `_end=0x420fd000` 的 BSS 清零区覆盖 aboot 放在 `0x42000000` 的 DTB → FDT 全零 → `setup_machine_fdt` 失败。裁剪 39 项调试配置后 `_end=0x41e09000`，余量 `0x1f7000`。**刷任何自编译内核前必须跑 `tools/blm_preflight.py`**，要求 17/17 `SAFE_TO_FLASH` 且距 FDT ≥1 MiB。
2. **归因演进（README 必须标注，否则会走错路）**：Round14/15 判 `usb_bam` → Round16 固定槽**推翻** → 真卡点 `qpnp_vibrator_init` → Round17 精确到第一次 `spmi_ext_register_readl()` 未返回 → Round18 DTB `FDT_NOP` 绕过 → Round19 `--spmi-stub` 替换 SPMI 读写后进桌面。
3. **触摸根因**：自编译 config 缺 `CONFIG_TOUCHSCREEN_ST_FTS`。补齐后逐层修：DT 属性 `synaptics,*`、pinctrl 宏改 `default`、`IRQF_ONESHOT`、regulator `vdd_ana`/`vcc_i2c`。**可用基线 = `boot_los16_blm_ftsirq_20261114192500.img`（sha `5f164490…`，`3.18.120-perf #9`）**。
4. **触摸冷启动不生效**（`touch_cold` FAIL）：dmesg `[7.072]`/`[8.236]` `fts_fw_update_auto` 两次失败 + `Doing a system reset`，`st_fts.bin` 未随系统提供；[H] 自动固件更新把芯片留在异常态，直到锁屏唤醒的 suspend-resume 才恢复（唤醒后实测 1266 行事件、IRQ +387）。**现成候选 `a1a0e026…` 跳过固件更新，但它同时改了中断触发方式，B′ 轮必须拆单变量验证**。
5. **`hal` 门口径**：`--hal-ignore init.svc.vivo-fingerprint-sh` 不能省，否则误判 FAIL。
6. **reboot 通道未修**：已排除 config 开关、`qcom,pshold`、`qcom,msm-imem-restart_reason`、misc BCB、reason 写入顺序。原厂 `do_msm_restart` 1492 B vs 自编译 740 B，原厂独有 `set_dload_mode_bbk` 等 BBK 私有调用。[H1] aboot 读私有标志，未实机验证。
7. **用户约定**：每轮由人明确说「请进 fastboot」才进，**绝不推断设备自动进入**。`adb reboot bootloader` 在自编译内核里退化成普通重启；运行态 boot 分区只读，只有 fastboot 能写；reboot 后 adb 常先连上残留会话再掉线，需二次枚举；fastboot USB 端点瞬断时**停在 fastboot 不重启**，约 2 分钟自恢复。
8. **WSL 调用坑**：Git Bash 会吞 shell 变量并把 `/mnt/d/...` 转坏，必须 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'` + 独立 `.sh` 脚本或 PowerShell 直调 `wsl.exe -d PD1610 -- bash ...`。

---

## 7. 可直接复制给 AI 的开场白

```
我在恢复一个已归档的 Android 内核逆向项目（vivo Xplay6 / PD1610 /
LineageOS 16 / 自编译 3.18.120 内核）。工程全量分卷已从百度网盘下载并
按 archive/RESTORE.md 恢复到原路径：
  D:/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/
WSL 重建集在 wsl_rebuild/，重建 SOP 在 offline/11_wsl_rebuild_guide.md。

请先读这三份，不要凭名字猜：
  1. offline/12_ai_handoff_index.md   （本文件：资源索引 + 从哪一步继续）
  2. offline/08_roundA_result.md      （A 轮实机结果与完成度）
  3. offline/07_handoff_baseline.md   （B0 基准与回滚 SOP）

当前状态：严格完成度 50/50，UNVERIFIED=0；设备已回滚原厂
3.18.71-perf-g8a8c60dd / sys.boot_completed=1，不在 fastboot。
下一步是 offline/05_experiment_queue.md 的 B 轮（导航键 IRQF_ONESHOT）
或 B′ 轮（touch_cold 拆单变量）。

约束：每轮刷机前我先明确说「请进 fastboot」你再动手；刷任何自编译
内核前必须跑 tools/blm_preflight.py 达 17/17 SAFE_TO_FLASH；每轮结束
用 tools/blm_round_capture.py 抓全量证据并重算完成度。不要虚构结果，
未执行的步骤写「未执行」。
```

---

## 8. 边界

- 本文件写于 A 轮完成、设备回滚原厂之后；**本机文件尚未清空**，清空动作需人确认且必须先完成云端备份 + `sha256sum -c` 校验。
- 公开仓库 `publish/` 为 **verbatim 全量细节**（按用户决定不脱敏），含设备序列号等唯一信息；`publish_sanitized/` 是可替换的脱敏版，若日后需要改用，直接把它当作仓库根即可。
- 分卷**未加密**（未指定密码）。加密版可用 `python tools/blm_archive.py --root <工程根> --password <密码>` 重跑；密码不会写进归档，务必另行保存。
- 体积与哈希以 `archive/manifest.json` / `SHA256SUMS` 为准，本文件里的数字是 2026-11-14 的快照。
