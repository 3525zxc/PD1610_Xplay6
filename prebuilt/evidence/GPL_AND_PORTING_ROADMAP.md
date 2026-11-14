# 酷安 72735509 线索核查 + PD1610 自编译设备树/做包路线

日期：2026-11-10　全程纯离线 / 只读，零设备写入
来源：https://www.coolapk.com/feed/72735509 （やえみこ，2026-07-11，Vivo X9Plus PD1619 / LineageOS 16.0 非官方自编译）

---

## 一、结论速览

1. 博主的 GPL 指控**可以独立佐证**：vivo 官方开源站只发布 2019 年后的新机型内核源码，`PD1610 / Xplay6 / PD1619 / X9 Plus` 全部没有；XDA 2018 年就有同类 GPLv2 违反讨论与请愿，社区工具直接把 vivo Open Source 标为无用。老机型源码**事实上拿不到**。
2. 因此博主采用的是「**原厂预编译内核 + 厂商 blobs + 借用同平台其它机型设备树**」路线，而不是编译内核。这条路线**对 PD1610 可复制**，而且我们手里的基线比博主更完整（真机回读的 47 分区、可编译 DTS、完整 system ext4 解析、打包工具链）。
3. 「自编译设备树」在本文语境里 = **编译 LOS 设备树（BoardConfig/mk 文件体系）产出 system.img 与 ramdisk**，不是编译内核 DTS。内核保持 prebuilt；DTS 我们已有反编译基线，只做等长补丁，不重编。
4. 本机 3.18.71 内核**未发现 X9 那套 `do_mount_check` 反 /system 挂载检测**（字符串级），所以 wuxianlin 的 hexpatch 大概率不需要；但 PD1619 的 32 位 magiskinit 限制属「vivo Linux 3.x 通病」，需实机验证。

---

## 二、GPL 线索（逐条核查）

| 线索 | 核查结果 |
|---|---|
| 原文①：「Vivo 极其恶劣地违反 GPL、拒绝公开本设备的 Linux 内核源码，不得不完全依赖原厂预编译内核以及大量厂商私有库」 | 属实。见下三条 |
| vivo 官方开源站 `opensource.vivo.com/Project` | 可见列表全是 Android 12/15/16 新平台内核包（UMS9230 / MT6991T / SM8850 / SM8475 / MT6985 …），**无任何 2016–2018 机型、无 PD1610 / PD1619 / msm8996 / msm8976 内核包** |
| 社区历史 | XDA 帖 `forum.xda-developers.com/posts/77245806/`（2018-08）：「Vivo, Oppo have a poor history of complying with open source licenses... constantly in violation with GPLv2 by failing to release kernel source」，并给出 GNU GPL violation report 流程；change.org / ipetitions 有 Vivo Y51L、Y21L 的「Release kernel sources」请愿 |
| 社区工具态度 | `4accccc/vivo-4.x-kernel-autopatch` README credits 直接写 `vivo Open Source — useless shit`；其存在本身（靠二进制 hexpatch 绕内核限制）就是无源码的后果 |
| 博主自己的移植笔记 | `PD1619_PORTING_NOTES.md` §Kernel Policy 第一句：「vivo did not provide usable kernel source for this bring-up. Use the stock/prebuilt closed-source kernel.」 |

**判断**：这是长期、成体系的历史欠账，靠申诉短期内拿不到 2018 年 3.18.71 的源码。技术路线应直接按「prebuilt kernel」设计，不再等 GPL 源码。维权线索仅作背景，不构成工程依赖。

---

## 三、原文给出的可复用资产（已落到 D 盘）

| 资产 | 地址 / 本地路径 |
|---|---|
| 设备树 | `github.com/ShionKanagawa/android_device_vivo_PD1619`（默认分支 `lineage-16.0`，LOS 15.1 bring-up，基于 **LeEco s2 MSM8976** 树） |
| Vendor blobs | `github.com/ShionKanagawa/android_vendor_vivo_PD1619`（`lineage-16.0`，约 210 MB） |
| ROM 发布 | `.../releases/tag/lineage-16.0-20260711` |
| 移植笔记（1,042 行） | `D:\16\PD1610_81\refs\PD1619_PORTING_NOTES.md` |
| BoardConfig / README / AndroidProducts / lineage_*.mk / extract-files.sh | 同目录 `refs\` |
| TWRP fstab 模板 | `refs\twrp_fstab.qcom` |
| 内核反 system 挂载补丁 | `wuxianlin/build_magisk_vivo` → `patch_vivo_do_mount_check.diff`：`magiskboot hexpatch kernel 0092CFC2C9CDDDDA00 0092CFC2C9CEC0DB00`（`/system`→`/syswxl`），另有 `821B8012→E2FF8F12` |
| 自动化补丁工具 | `4accccc/vivo-4.x-kernel-autopatch`（P1–P6；只支持 4.x 内核，3.x 用上面手工 hexpatch） |
| Magisk 特殊构建 | `wuxianlin/build_magisk_vivo`（SU→SUU，绕 vivo 内核 su 限制） |
| 解锁工具 | viQOO 工具箱（@某贼） |
| 教程 | `shionkanagawa.github.io/posts/vivo-x9-系列解锁-root-并开启-volte-教程`（当前 404，搜索引擎仍有摘要：改 fstab.qcom 删 `,forceencrypt=footer` + 上述 hexpatch） |

---

## 四、博主方法拆解（PD1619 bring-up 实操）

1. **借树**：以 LeEco s2 / MSM8976 的 LOS 15.1 设备树为底，把产品身份换成 `PD1619` / vivo（`lineage_PD1619-userdebug`、`full_PD1619.mk`、`vendor/vivo/PD1619`）。
2. **prebuilt kernel**：从官方 boot 拆出 `boot.img-kernel` → `prebuilt/kernel`，`TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel`，`BOARD_KERNEL_IMAGE_NAME := Image.gz-dtb`。**不编译内核**。
3. **内核头文件另找**：用 s2 的 MSM8976 源码 `make headers_install` 只生成 `KERNEL_OBJ/usr/include`，满足老 CAF 模块编译依赖，不产出内核镜像。
4. **blobs 从真机/官方 dump 抽**：`extract-files.sh` 起 245 个种子，用 `DT_NEEDED` 依赖闭包反复扩展，最终 `proprietary-files.txt` 达 **1,041** 条；刻意排除 libc / libbinder / libhidlbase 等源码已有库。
5. **非 Treble 的关键坑**：`init.qcom.rc` / `init.target.rc` / `ueventd.qcom.rc` / `fstab.qcom` 必须装到 **ramdisk 根**，不能装 `/system/vendor`；`/system` 条目在 fstab 里标 `recoveryonly`（first-stage init 已挂过，否则 `mount_all` 返回 255、`ro.crypto.state` 不置位、zygote 不启动）。
6. **cmdline 原样抄官方**，另加 `androidboot.selinux=permissive` 做早期 bring-up。
7. **构建环境**：Docker 内跑完整 ROM；LOS 15.1 还有 Python 2 脚本（`findleaves.py`），主机需 `python→python2` wrapper。
8. **Magisk**：24+ 的 64 位 `magiskinit` 作为 ramdisk `/init` 会 bootloop，必须强制 32 位；「32 位 early init + 64 位 runtime」。
9. **已知未解**：AVBv1 签名/footer 无法复现（重打包 boot 哈希不匹配官方）；qseecomd / gatekeeper 等 secure-world HAL 依赖。

---

## 五、PD1619 ↔ PD1610 对照（决定哪些能直接抄）

| 项 | PD1619（博主） | PD1610（本机） | 可复用性 |
|---|---|---|---|
| SoC | MSM8976 / `msm8952` | MSM8996 / `msm8996` | ❌ 平台树要换 |
| 内核 | 3.10.84-prebuilt | **3.18.71-perf-g8a8c60dd**（2018-11-07, GCC 4.9） | 方法同，二进制不同 |
| 底包 | Funtouch 4.0 / 8.1 | Funtouch 4.0 / 8.1（`PD1610_D_8.19.16`） | ✅ 同代 |
| Treble | 否，`/vendor`→`/system/vendor` | **否**，`vendor` 在 system 内、DTB 里 vendor fstab `disabled` | ✅ 坑一致 |
| system 分区 | 3,221,225,472 B | **3,221,225,472 B**（逐字节同尺寸） | ✅ BoardConfig 值可直接用 |
| boot / recovery | 64 MB / 64 MB | 96 MB / 96 MB | 改数值 |
| page size | 2048 | **4096** | 必须改 |
| kernel_size | — | **56,551,493 B**（Image.gz ≈9.4 MB + 47 MB 未压缩 DTB 链，122 份） | 本机特性 |
| ramdisk_size | — | 2,162,779 B | 本机特性 |
| boot header | v0 | v0 | ✅ |
| VINTF manifest | `/vendor/manifest.xml` | `/vendor/manifest.xml`（73 HAL）+ 根 `manifest.xml`（11 HAL） | ✅ |
| fstab | 文件 + 官方 | **DTB 里 system=`wait,verify`，`/vendor/etc/fstab.qcom` 里 system 行被注释** | 见下 |
| 私有 cmdline | `securebootkey=alpha … ver=1` | **`securebootkey=beta` / `hash=da758fd5…` / `ver=2`** | 必须原样保留 |
| dm-verity | 有 | 有（DTB `fsmgr_flags`） | 已可等长去掉 |
| 反 /system 挂载 | 有（需 hexpatch） | **解压内核中 `do_mount_check` / `syswxl` / `mount_check` 均 0 命中** | 大概率无需补丁 |
| 内核模块 | — | `CONFIG_MODULE_SIG_FORCE=y` + SHA512 | 自编模块需密钥或关闭 |

### 本机本轮新增的离线实测（可复现）

- 解压 `work\boot_81_official.img` 的 kernel 段（gzip member @ offset 0x1000）→ `work\kernel_81_decompressed.bin`，26,549,760 B，版本串 `Linux version 3.18.71-perf-g8a8c60dd (compiler@compiler0171) ... #1 SMP PREEMPT Wed Nov 7 16:08:09 CST 2018`；尾部 `unused_data` 47,159,172 B 即 DTB 链。
- 官方 cmdline（boot header offset 64）：
  `console=null androidboot.console=ttyHSL0 androidboot.hardware=qcom user_debug=31 msm_rtb.filter=0x237 ehci-hcd.park=3 lpm_levels.sleep_disabled=1 cma=32M@0-0xffffffff product.version=PD1610_D_8.19.16 fingerprint.abbr=8.1.0/OPM1.171019.026 buildvariant=user androidboot.securebootkey=beta androidboot.securebootkeyhash=da758fd52632ba6649d61830a88bbe76a616e4b083b9358b3e98e13772dc139d androidboot.securebootkeyver=2`
- 内核内 `vivo` 386 次、`bbk` 51 次、`verity` 36 次，但**无** `do_mount_check`、无 `syswxl`、无 `forceencrypt`；`/system` 仅 2 次。边界：字符串缺失不绝对等于无检测（可能改名/内联），需实机或反汇编确认。
- X9 的 hexpatch 字节 `0092CFC2C9CDDDDA00` 在本机整个 boot.img **未命中**，确认不可照搬。
- GitHub 上 PD1610 只有 `mitcarlsonlin/vivo-xplay6-downgrade-guide` 与 `AlexIllinois2/xplay6-tmproot` 两个仓库，**没有现成类原生设备树 / TWRP 树**。

---

## 六、可执行路线（按博主方法映射到本机）

**阶段 0 — 已完成（本会话，纯离线）**
- 8.1 全分区回读 47 个 / 3.67 GB（`backup\81_*.bin`）+ 一键全盘还原 `restore_81_all.{xml,bat}`
- 8.19.16 aboot 验签失败不阻断（指令级证据 `aboot_81916_failure_path.txt`）
- 8.1 DTB 基线：122 份中第 79 份 vivo 专用，可编译 DTS 16,797 行、board-id / msm-id、fstab 节点（`evidence\dtb_81_baseline\`）
- system 素材：ext4 只读解析器提取 90 个配置/清单文件、内核 config、VINTF HAL 矩阵（`evidence\system_81_extract\`）
- 打包工具链：`boot_tool.py`（含 `patch-noverify` 等长去 verify，只改 7 字节）、`updater-script.template`、`make_rom_zip.py`、`flash_custom_rom.xml`
- 门槛镜像 `work\boot_81_noverify.img`（签名失配 + 去 dm-verity），实机实验**仍未执行、零写入**

**阶段 1 — 设备树骨架（现在就能做，纯文本，几百 KB）**
- 以 **msm8996 的 LOS 15.1/16.0 设备树**为底（一加3 / Le Pro3 / ZUK Z2 Pro / Mi5；或博主 PD1619 树作结构模板但换平台）
- 生成 `device/vivo/PD1610/`：`AndroidProducts.mk`、`lineage_PD1610.mk`、`BoardConfig.mk`、`device.mk`、`manifest.xml`、`system.prop`、`rootdir/`（fstab.qcom + init rc 装 ramdisk 根）、`twrp/fstab.qcom`、`prebuilt/kernel`、`extract-files.sh` + `proprietary-files.txt`
- `BoardConfig.mk` 必填本机值：`TARGET_BOARD_PLATFORM := msm8996`、`TARGET_ARCH := arm64`、`BOARD_KERNEL_PAGESIZE := 4096`、`BOARD_SYSTEMIMAGE_PARTITION_SIZE := 3221225472`、`BOARD_RECOVERYIMAGE_PARTITION_SIZE := 100663296`、`TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel`、`BOARD_KERNEL_IMAGE_NAME := Image.gz-dtb`、完整官方 cmdline（含 `securebootkey=beta`）、`TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/twrp/fstab.qcom`
- `prebuilt/kernel` 由 `boot_tool.py unpack` 从官方 boot 拆出，保留 122 份 DTB 链；改 fstab 用现成 `patch-noverify` 等长补丁，**不重编 DTB**

**阶段 2 — vendor blobs**
- 优势：博主从真机/ROM dump 抽，我们有 `81_system_LUN4.bin`（raw ext4 全量）+ `ext4_extract.py`，可**离线全量抽取** `/system/vendor`、`/oem`、`/apps` 的 blobs，不需设备在线
- 生成 `vendor/vivo/PD1610/proprietary-files.txt`，按 `DT_NEEDED` 闭包扩展，排除 libc/libbinder/libhidlbase 等源码库
- 把 `/vendor/manifest.xml`（73 HAL）与 `compatibility_matrix.xml` 对齐 LOS 15.1 的 VINTF 要求

**阶段 3 — 构建环境**
- 需要 Linux（Docker / WSL2 / 实体机），约 100–150 GB；本机 WSL 被策略拦、C 盘仅 32 GB，**当前不可行**
- LOS 15.1/16.0 源码 + `lineage_PD1610-userdebug`；内核头文件从任意 msm8996 3.18 源码 `make headers_install` 生成（不编内核）
- `brunch PD1610` 产出 `system.img` + `boot.img`（ramdisk 来自设备树，kernel 来自 prebuilt）

**阶段 4 — boot**
- 用 `boot_tool.py repack` 把 LOS ramdisk + 官方 prebuilt kernel + 补丁后 DTB 合成 boot；cmdline 保持官方私有参数
- 官方 recovery 只认 vivo 证书，自签 zip 会被拒 → **走 EDL/9008 直刷**（`flash_custom_rom.xml`）或自编 TWRP

**阶段 5 — 实机顺序（硬件排线修好后）**
1. 冷启动确认 8.1 正常 → 2. EDL 刷 `boot_81_noverify.img` 做门槛判定 → 3. 通过后刷 TWRP → 4. 刷 LOS system + boot（保留 17 分区官方链）→ 5. 失败用 `restore_81_all.bat` 全盘还原

**阶段 6 — TWRP（可选但强烈建议）**
- 用 `refs\twrp_fstab.qcom` 作模板，改分区路径/尺寸（本机 59 个 by-name 分区，另有 `apps` / `oem` / `persist` / `dsp` / `modem`）
- 需要 msm8996 同代 TWRP device tree（3.2.x/3.3.x，`prebuilt` kernel + dt.img、`BoardConfig.mk`、`recovery.fstab`、`init.recovery.*.rc`）

---

## 七、还需要用户提供 / 张罗的（回答上轮的问题）

1. **msm8996 的 LOS 15.1/16.0 设备树**（一加3 / Le Pro3 / ZUK Z2 Pro / Mi5，或 `LineageOS/android_device_*_msm8996-common`）— 优先，决定阶段 1 能否开工
2. **同代 TWRP device tree**（3.2.x/3.3.x，含 `prebuilt/kernel` + `dt.img`、`BoardConfig.mk`、`recovery.fstab`、`init.recovery.*.rc`）
3. **同平台类原生 ROM 的 OTA zip / system.img + boot.img**（参照 fstab、init.rc、HAL 集合、分区布局；用户 D 盘「联想P8刷ROM回官方全套」里若有 LOS 包一并给）
4. **Linux 构建环境**：放行 WSL2 或自备机器（≥150 GB）；Docker 方案 `lineageos4microg/docker-lineage-cicd`
5. ~~Xplay6 GPL 内核源码~~ — 已确认官方未发布，不必再等；若能从第三方渠道拿到 3.18.71 源码，用途仅限 `make headers_install` 生成头文件

模板**不能直接套**：本机非 Treble、`vendor` 在 system 内、page=4096、boot 96 MB、3.18.71、`CONFIG_MODULE_SIG_FORCE=y`、cmdline 含 vivo 私有 securebootkey。

---

## 八、边界与风险

- GPL 部分为公开资料核查，非法律结论；`opensource.vivo.com/Project` 只核了当前可见列表，未逐页翻查历史归档。
- 「无 `do_mount_check`」是**字符串级**结论，不等于内核无等价挂载限制；需反汇编或实机验证。
- 设备树、ROM、TWRP 均**尚未编译**；本轮只完成线索核查与路线设计，设备状态未改变，门槛实验仍零写入。
- 官方 recovery 拒刷自签包；EDL 直刷必须按 17 分区官方链配套，只刷 boot+system 会卡 logo（11-10 实测）。
- 当前硬件限制：音量上键、电源键损坏，拆壳点触可用但成本高；排线到货前不做实机写入。
