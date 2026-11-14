# ⑪ WSL PD1610 环境说明、清理清单与重建 SOP

日期 2026-11-14。用途：解释 `D:\WSL\PD1610\ext4.vhdx` 里是什么、哪些能删、以及将来如何从零搭回可自编译内核的环境。**本文件只做只读盘点，不执行任何删除。**

## [O] 环境事实

| 项 | 值 |
|---|---|
| 发行版 | WSL2 / Ubuntu 20.04.5 LTS（Focal），`default user = builder` |
| 虚拟盘 | `D:\WSL\PD1610\ext4.vhdx`，**176.88 GiB**（内部 `df` 显示已用 175 G / 1007 G） |
| 主目录 | `/home/builder` = **173 G** |
| 关键挂载 | `/etc/wsl.conf`：`appendWindowsPath = false`（避免 AOSP 构建误用 Windows 的 `find`/`ln`）、`metadata,umask=22,fmask=11` |

`/home/builder` 构成：

| 目录 | 体积 | 是什么 |
|---|---|---|
| `los16/out` | **71 G** | LineageOS 16 整包编译产物（`target` 36 G、`soong` 30 G、`host` 4.9 G）。**全可再生** |
| `los16/prebuilts` | 31 G | AOSP 全树预编译工具链（clang 8.7 G、gradle 5.9 G、jdk、ndk…）。**内核自编译只用其中 101 M** |
| `los16/.repo` | 9.2 G | `repo sync` 的 git 元数据，可再生 |
| `los16/` 其余 | ≈15 G | AOSP 源码（external / frameworks / vendor / device…） |
| `ksrc/kout-*` | **29 G** | 8 套历史内核构建输出（每套 3.4–3.5 G），对应 Round10 之前的废弃实验 |
| `ksrc/msm8996-*` | 5.5 G | 6 份内核源码树副本（各 744–790 M） |
| `ksrc/*.tar.gz` | 278 M | 原始源码归档 `msm8996-lineage-16.0.tar.gz` 与 `los15.tar.gz` |

## [O] 当前自编译内核真正依赖的东西（已导出）

构建脚本 `tools/blm_trace_build.sh:12-14,55,57`：

```
SRC = /home/builder/ksrc/msm8996-lineage-16.0-blm-shrink-20261114133000   (790 M, 无 .git)
OUT = /home/builder/ksrc/kout-los16-blm-shrink-20261114133000              (755 M)
TC  = /home/builder/los16/prebuilts/gcc/linux-x86/aarch64/
      aarch64-linux-android-4.9/bin/aarch64-linux-androidkernel-          (101 M)
make O="$OUT" -j14 Image.gz-dtb    (ARCH=arm64 SUBARCH=arm64 LC_ALL=C)
```

已核验源码树里 6 个补丁文件都在：`fts.c`(132,409 B)、`fts.h`(8,773 B)、`cyttsp_button.c`(39,671 B)、`msm-poweroff.c`(15,398 B)、`qpnp-vibrator.c`(10,228 B)、`bootloop_monitor.c`(10,870 B)。`.config` 有 1468 个 `CONFIG_` 键。

**导出产物**：`wsl_rebuild/` 共 **1.6 G / 40 文件**，含 `SHA256SUMS`：

```
wsl_rebuild/
  src/kernel-src.tar          733,378,560 B   已打补丁源码树
  config/kout-shrink.tar      781,803,520 B   当前构建输出（含 .o / vmlinux）
  config/.config, System.map                 可直接复用的配置与符号表
  toolchain/aarch64-linux-android-4.9.tar    交叉编译器
  scripts/                                   构建脚本 + fixtures + BLM 模块源码
  env/environment.txt                        Ubuntu 版本、apt 包全表、wsl.conf、构建命令、路径
  SHA256SUMS                                 全部文件校验
```

依赖包（`env/environment.txt` 有全表）：`build-essential make bc bison flex libssl-dev libncurses5-dev libncurses-dev liblz4-tool lzop device-tree-compiler python2 python3 git ccache rsync unzip zip curl wget ca-certificates`。

## [O] 可清理清单（只读列出，**未删除任何文件**）

按「删了不影响重建」排序，合计约 **145 G**：

| 优先级 | 路径 | 体积 | 理由 |
|---|---|---|---|
| 1 | `/home/builder/los16/out` | 71 G | AOSP 整包产物，`m clean` 或重新 sync 即可再生；内核构建完全不碰 |
| 2 | `ksrc/kout-*` 中除 `kout-los16-blm-shrink-20261114133000` 外的 8 套 | ≈28 G | 早期废弃实验的编译输出 |
| 3 | `los16/prebuilts` 中除 `gcc/.../aarch64-linux-android-4.9` 外 | ≈31 G | 全树编译才用；内核只需 101 M（已导出） |
| 4 | `los16/.repo` | 9.2 G | repo 元数据，可再生 |
| 5 | `ksrc/msm8996-*` 中除 shrink 树外的 5 份 | ≈4.7 G | 旧源码副本 |
| 6 | `ksrc/*.tar.gz` | 278 M | 原始归档，已由 `kernel-src.tar` 覆盖（补丁版更有价值） |
| 7 | `/home/builder/*.log` | ≈20 M | 构建日志，D 盘 `build/*/build.log` 已有副本 |

**注意**：`ext4.vhdx` 是稀疏动态盘，WSL 内删文件**不会自动缩小** Windows 侧占用，需另行 `wsl --shutdown` 后 `Optimize-VHD -Mode Full` 或 `diskpart compact vdisk` 才能把 176 G 压回实际用量。

## 重建 SOP（以后从零搭回「原样」）

### 路线 A：完整镜像还原（最省事，但要搬 176 G）

```powershell
# 备份（现在做）
wsl --shutdown
wsl --export PD1610 D:\backup\PD1610_full.tar     # 约 175 G
# 还原（以后）
wsl --import PD1610 D:\WSL\PD1610 D:\backup\PD1610_full.tar --version 2
wsl -d PD1610 -u builder
```
缺点：产物 175 G，GitHub / 百度网盘都很难传，且里面 145 G 是垃圾。**不推荐**。

### 路线 B：最小集重建（推荐，只搬 1.6 G）

1. 装 WSL2 + Ubuntu 20.04，按 `env/wsl.conf` 内容写 `/etc/wsl.conf`，建用户 `builder`。
2. `apt install` 上面那串包（版本见 `env/environment.txt`）。
3. 解包到原路径，保持绝对路径一致（构建脚本硬编码了路径）：
   ```bash
   mkdir -p /home/builder/ksrc /home/builder/los16/prebuilts/gcc/linux-x86/aarch64
   tar -xf wsl_rebuild/src/kernel-src.tar      -C /home/builder/ksrc
   tar -xf wsl_rebuild/config/kout-shrink.tar  -C /home/builder/ksrc
   tar -xf wsl_rebuild/toolchain/aarch64-linux-android-4.9.tar \
       -C /home/builder/los16/prebuilts/gcc/linux-x86/aarch64
   ```
4. 把 `scripts/` 放回 D 盘原工程路径 `D:/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/`，因为 `blm_trace_build.sh` 用 `/mnt/d/...` 绝对路径定位 `build/` 与 `images/`。
5. 校验：`cd wsl_rebuild && sha256sum -c SHA256SUMS`。
6. 试编译（不刷机）：
   ```bash
   MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl.exe -d PD1610 -- \
     bash /mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/tools/blm_trace_build.sh \
     rebuild-check /mnt/d/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/tests/patched_tree_vibfix
   ```
   预期 `BUILD_RC=0`，产物 `Image.gz-dtb` 与 `System.map`；随后 `python tools/blm_preflight.py ...` 应 17/17 `SAFE_TO_FLASH`。
7. **刷机前必做**：按 `offline/07_handoff_baseline.md` 的回滚 SOP 准备原厂镜像，且每轮由人明确说「请进 fastboot」。

### 路线 B 的前提与风险

- **D 盘工程目录必须一起备份**。WSL 最小集只解决「编译环境」，`images/ *.img`、`flash_log/` 证据、`offline/` 报告、`tools/` 脚本全在 D 盘，缺了就无法重建 boot.img、无法复跑覆盖率。两者是一个整体。
- 源码树**没有 `.git`**，是 tar 解出来的裸树；补丁已直接改在文件里。想做版本管理需自己 `git init` 并把 `fixtures/` 里的适配版源码做基线。
- `env/environment.txt` 只记录 apt 包名/版本，不记录 pip 包与手工改过的系统配置；若将来换了 Ubuntu 版本，3.18 内核可能要补 `python2` 与旧 `bison`/`flex` 兼容处理。

## 边界

- 本轮所有操作为**只读盘点 + 复制导出**，没有删除、移动或改写 WSL 内任何原文件。
- 「清理」只给出清单。按约定，任何删除动作需你明确确认具体路径，且应先完成云端备份与 `sha256sum -c` 校验。
