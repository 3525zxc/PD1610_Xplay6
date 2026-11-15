# PD1610 内存态临时 Root 工具链发现（xplay6-tmproot）

> 日期：2026-11-10 13:10｜来源：GitHub 公开仓库 `AlexIllinois2/xplay6-tmproot`（提交者邮箱 AlexIllinois@163.com）
> 性质：外部公开资料整理，**纯离线**。未在设备上安装/运行任何东西。

## 一、它是什么

面向 **vivo Xplay6 / PD1610 / msm8996** 的**内存态临时 root**工具链：

- **不需要解锁 Bootloader、不写任何分区**——效果只存在于 RAM 与运行中的 SELinux 策略表，重启即恢复原厂（README 原文）。
- 应用曾用名「**月虹提权助手**」，v1.9.33 起显示名 `xplay6 tmproot`，包名 `com.xplay6.temproot`。
- 自带 **Magisk 30.7 用户态运行时**（Magisk 格式模块引擎，**无需修补 boot 镜像**）。
- 最新发布：**v1.9.39**（`release/1.9.39/`，APK 5,483,312 B，sha256 `029c1b43fd3e1bd6cf630c04a23b1c256a3705f08e99f8c09311e824ac265ae9`，与仓库 INTEGRITY.txt 一致，已下载到 `C:\qfilx\exp\gh_xiaochen20\`）。

## 二、支持矩阵（README「Supported devices and firmware」，其余内核一律拒绝）

| ROM | Android | 内核 | 路线 |
|---|---|---|---|
| **PD1610_D_1.15.1** | **6.0.1** | **3.18.20-perf-gb6998a3** | **Route 6：modprobe_path / usermode helper** |
| PD1610_D_1.17.12 | 6.0.1 | 3.18.20-perf-geb775ef-dirty | Route 6（按 UTS release 选 profile） |
| PD1610_D_7.12.15 | 7.1.1 | 3.18.31-perf-g9dce1fbc9 | Route 7：内核内提权 + per-domain permissive_map 豁免 |
| PD1610_D_8.19.16 | 8.1 | 3.18.71-perf-g8a8c60dd | Route 8：CVE-2019-2215 binder UAF 当内核写 |

**我们的设备：官方 1.15.1 / 6.0.1 → Route 6 在支持列表内。**

## 三、对我们的意义

1. **「临时 Root 采集」从不确定项变成现成方案**（原先设想需借漏洞或工程手段）：装 APK → 授权 → 只读采集，重启无痕、零刷写风险。
2. 可采集：devinfo 真实字节、`/proc/config.gz`（IKCONFIG_PROC=y）、`/proc/kallsyms`、dmesg、分区只读内容——直接服务 U6（设备最终状态核实）、T3 基线、EDL 回读对照。
3. **不改变 13.4 四条件、不构成启动入口**：root 在开机之后，aboot 验签在它之前。「能写，不能启」结论不变。
4. 旁证：8.1 原厂 config（`ota8/config.txt`，3.18.71）证实 **CONFIG_KEXEC 未设置**、`MODULE_SIG_FORCE=y`（自编译模块不可 insmod）、`# CONFIG_DEVMEM is not set`（root 也无 /dev/mem）——与既有结论一致。

## 四、仓库内的高价值材料（可离线使用）

- `art/ledger-20261013/14/15/16/21/26.md`：约 2 MB 的工程台账（CVE-2019-2215 链、PXN、clobber、SELinux 写入、APK 化、`su` 名称门规避），日期覆盖案例构建日 `20261014`。
- `art/kallsyms-{7,1712}-real.txt` + `art/kallsyms_real.txt`（各 ~3.5 MB）：对应 build 的内核符号表。
- `art/pol1712-live.bin` / `policy-types-*.tsv`：实际 SELinux 策略转储。
- `ota8/config.txt`（3.18.71 原厂 config）+ `ota8/syms8.txt`。
- `exp8/` + `pocs/cve2019-2215-3.18-master/`：实验与公开 PoC 源码。
- `art/UNLOCK-ADB-INPUT.md`：vivo `vivo_adb_simulate_input` 开关的绕过细节（uid 2000 + INJECT_EVENTS）。
- `art/PORT-RUNBOOK-7.md`（201 KB）：换基线到 6.0.1/1.15.1 后的复现核对序。

## 五、待办（设备回来时）

1. 安装 v1.9.39 APK（或按 README-build 自建），确认运行内核 = `3.18.20-perf-gb6998a3`（Route 6 接受条件）。
2. 只读采集：`/proc/config.gz`、`/proc/kallsyms`、`dmesg`、devinfo 分区、boot/aboot 分区 hash → 归档并与本地已有样本对照。
3. 用采集结果核实 11-08 实验后设备真实状态（U6）。
4. **不做**：任何分区写入、任何"用 root 改 boot/aboot"的尝试（aboot 验签在 root 之前，无效且危险）。

## 六、身份与边界（2026-11-10 13:10 用户确认更正）

- **本工具链作者是另一位酷安博主，不是「成功案例」博主（UID 3298502 / 鼠鼠鼠鼠）**。用户确认：这位博主**也没有做出 Xplay6 的类原生方案**，其公开成果止步于内存态临时 root。
- 证据等级意义：这是继我们自身、以及案例博主之外的**第三个独立数据点**——一位有能力写出 CVE-2019-2215 链 + Magisk 运行时替代的开发者，最终也只做到「stock ROM 上的内存态 root」，**没有**产出可启动的类原生系统。它不能证明类原生不可行，但**强化**了「公开渠道尚无 Xplay6 类原生方案；唯一公开案例（LineageOS 17.1）仍无法验证其启动链来源（工程机/放宽 aboot 的怀疑未被推翻）」这一判断。
- 与 13.4 的关系：本工具链是**开机后**的 root，aboot 验签在它之前，**不构成启动入口**；四条件仍零命中。
- 关于 `xiaocheng20`（GitHub）：69 个仓库均为 OPPO R9s / 魅族 M3 Note / 小米 Scorpio、Platina、sdm660 等旧机型 ROM 开发，无 PD1610/vivo 相关仓库，最后推送 2025-04；与本工具链作者（AlexIllinois@163.com）也不是同一人。案例博主的 GitHub 身份仍未知。
- 附带发现：GitHub 全站 PD1610/Xplay6 相关仓库仅 2 个——本仓库，以及 `mitcarlsonlin/vivo-xplay6-downgrade-guide`（8.1→6.0.1 降级实录，2026-10-22）。
