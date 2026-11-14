# ROUND 17 · 离线准备完成清单

日期：2026-11-14 16:00–16:10
状态：**离线准备全部完成；第 17 次实机已于 16:13–16:25 执行完毕并安全回滚**，设备保持原厂 `3.18.71-perf-g8a8c60dd` / LOS16
边界（准备阶段）：不碰设备、不刷机、不进 fastboot、不进 9008；仅编译、打包、校验与写脚本
实机结果见 `ROUND17_VIBRATOR_SPMI_RESULT.md`：判据第 4 行命中，卡点为 `qpnp_vib_read_u8()` 内第一次 `spmi_ext_register_readl()` 未返回。

---

## 1. 本轮完成了什么

1. 定位并复制 `qpnp-vibrator.c` 原始夹具（编译树 `drivers/platform/msm/qpnp-vibrator.c`，9,733 B）。
2. 固定槽从 16 扩到 **32**：普通 printk/initcall 行只占 `[32,384)`；`[0,32)` 保留给里程碑，布局 v1 不变、旧 dump 完全兼容。
3. 新增 **11 个 `qpnp_vibrator_probe()` 里程碑**（`id=16..26`），覆盖 `spmi_get_resource`、DT 解析、`qpnp_vibrator_config` 入口、两次 SPMI 读、`pwm_request`、config 完成、`timed_output_dev_register`。原有 `usb_bam` 里程碑 `id=1..11` 全部保留作对照。
4. 判定器 `blm_trace_report.py` 同步：`sid` 掩码 `0x1F`、`TRACE_NAMES` 增加 16..26、新增 `LAST_VIB_MILESTONE` 与 `VIB_SUSPECTED_WINDOW`（直接给出下一步嫌疑窗口）。
5. 增量编译 → 打包 → 预检 → 镜像级差分 → 全套自测，全部通过。
6. 预写第 17 次实机脚本 `tools/blm_round17_capture.ps1`（PowerShell 语法检查 `PS_SYNTAX_OK`，**未执行**）。

---

## 2. 产物清单

| 项 | 值 |
|---|---|
| 候选镜像 | `images/boot_los16_blm_vib_20261114160500.img` |
| sha256 / 大小 | `47034aafbfc355d184b363c7bd5d390fe83f3319b0b43b7a55a2fbf582a174a2` / 58,483,968 B |
| 内核 `Image.gz-dtb` | `build/vib-20261114160500/`，sha256 `b01a56fa…`，55,942,949 B |
| 构建 | `KERNEL_BUILD_OK`，`MAKE_IMAGE_RC=0`，9 个 BLM 符号，C6 全 0 |
| 构建自检 | `BOOTIMG_BUILD_OK 40/40 PASS` |
| 刷前预检 | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 镜像级差分 | `KERNEL_ONLY_VERIFY 10/10 PASS` |
| 全套自测 | `SELFCHECK_OK`；补丁 `KERNEL_PATCH_OK status=OK outputs=9`，12 个 vibrator 操作全 inserted |
| 实机脚本 | `tools/blm_round17_capture.ps1`（`PS_SYNTAX_OK`） |
| 新增工具 | `tools/blm_verify_kernel_only.py`、`tools/blm_vibrator_inspect.sh`、`tools/blm_trace_report.py`（更新）、`tools/blm_apply_kernel_patch.py`（更新）、`tools/blm_trace_build.sh`（更新） |
| 新增夹具 | `fixtures/qpnp-vibrator.c.orig` |

### 镜像级差分（与 Round 16 镜像 `9b11acf1…` 对比，`10/10 PASS`）

```
file size equal            58483968 / 58483968
header equal except id     OK
header id recomputed       OK
kernel_size fixed          56551493
ramdisk identical          1918798 B
signature identical        5376 B
DTB chain identical        30947277 B
tail padding all zero      14894713 B
gzip payload changed       10708708 -> 10709503 B
new gzip -> ARM64 Image    OK
```

⇒ **唯一变量是内核插桩代码**；DTB 链、ramdisk、签名、头部布局全部不变。

---

## 3. 固定槽映射

| id | 名称 | 含义 |
|---|---|---|
| 0 | `LAST_INITCALL` | 最后进入的 initcall（每次覆盖） |
| 1–11 | `BAM_*` / `EBAM_*` | `usb_bam_probe` 里程碑（Round 16 全空，保留作对照） |
| 15 | `WATCHDOG` | watchdog panic 快照（本轮镜像未带 `blm_watchdog_secs`） |
| 16 | `VIB_ENTER` | probe 已分配 `vib` 结构体 |
| 17 | `VIB_SPMI_SET` | `vib->spmi = spmi` 完成 |
| 18 | `VIB_RES_BEFORE` | 即将 `spmi_get_resource` |
| 19 | `VIB_RES_AFTER` | 拿到 base 地址 |
| 20 | `VIB_DT_BEFORE` | 即将 `qpnp_vib_parse_dt` |
| 21 | `VIB_CONFIG_BEFORE` | DT 解析完成，即将 `qpnp_vibrator_config` |
| 22 | `VIB_READ1` | 即将第一次 `qpnp_vib_read_u8`（内含 `spmi_ext_register_readl`） |
| 23 | `VIB_READ2` | 即将第二次 `qpnp_vib_read_u8` |
| 24 | `VIB_PWM` | 即将 `pwm_request` / `pwm_config` |
| 25 | `VIB_CONFIG_DONE` | config 已返回 |
| 26 | `VIB_TIMED` | 即将 `timed_output_dev_register` |

---

## 4. 第 17 次实机判据（写死，避免再误判）

| 固定槽观察 | 结论 |
|---|---|
| 槽 16..26 全空，槽 0 仍为 `qpnp_vibrator_init` | probe **未被调用**，卡在 `spmi_driver_register()` 内部 / 设备未匹配 → 转查 SPMI 控制器与 DT 节点 |
| 最后到 18，无 19 | 卡在 `spmi_get_resource` |
| 最后到 20，无 21 | 卡在 `qpnp_vib_parse_dt` |
| 最后到 22，无 23 | 卡在**第一次 SPMI 读**（`spmi_ext_register_readl`） |
| 最后到 23，无 24 | 卡在**第二次 SPMI 读** |
| 最后到 24，无 25 | 卡在 `pwm_request` / `pwm_config` |
| 最后到 25，无 26 | 卡在 mutex / work / hrtimer 段 |
| 最后到 26 | 卡在 `timed_output_dev_register` |
| 槽 0 不再是 `qpnp_vibrator_init` | 卡点后移，按新 last-initcall 继续追 |
| 阶段到 `INITCALLS_DONE` / `ROOTFS_READY` | 瓶颈转向 rootfs / ramdisk / FBE |

判定器会自动打印 `VIB_SUSPECTED_WINDOW`，无需人工查表。

---

## 5. 第 17 次实机 runbook（脚本已封装，**待拍板执行**）

前置：设备 adb 在线、原厂系统；脚本自带预检报告校验（非 `SAFE_TO_FLASH` 直接退出）。

```
& 'D:\xplay6\evidence\kernel_re\out\stage2\bootloop_monitor\tools\blm_round17_capture.ps1' -ComPort 5
```

脚本内顺序：

1. `adb reboot bootloader` → 等 fastboot；
2. `fastboot flash boot` 最多重试 3 次（应对 USB 端点瞬断），**失败则不 reboot**，直接回滚原厂并退出；
3. reboot → 观察最长 180 s 等 9008；
4. 一次 firehose 会话双读：`0x42000000` FDT 头 64 KiB + `0x42100000` BLM 日志 256 KiB，**不带 `--reset`**；
5. 宿主跑 `blm_trace_report.py`，把关键判定行写进时间线；
6. `power value=reset` ACK → 等 fastboot 最长 120 s → 刷原厂 `929fda99…` → reboot → 等 50 s → `ROLLBACK_VERIFIED`。

**需要现场配合**：`power value=fastboot` 本机 programmer 回 NAK，复位后设备会回到候选镜像持续 bootloop；如 120 s 内未出现 fastboot，需手动进一次 fastboot（前几轮均如此），脚本会记录 `ROLLBACK_NOT_EXECUTED` 并退出，之后单独补跑回滚。

---

## 6. 风险与边界

- 只刷过 `blm_preflight.py 17/17 SAFE_TO_FLASH` 的镜像；不尝试 EDL 写分区（`poke`/program 未验证）。
- 双读不复位；读完先发 `power value=reset`，再等 fastboot。
- 固定槽是 [O]，机制推论仍标 [H]；`usb_bam` 里程碑保留但已不是嫌疑对象。
- 本轮所有工作离线完成，**未改动设备状态**，既有 ROUND 文档未改。

---

## 7. 未执行（准备阶段记录，实机已于 16:13–16:25 完成）

准备阶段未执行：任何设备连接操作（fastboot/adb/9008）、`blm_round17_capture.ps1` 的实际运行、probe 内部机制的实机验证。
实机因设备已在 fastboot、脚本 STEP1 需 adb 在线而改为**拆步执行**（等价流程，全程留痕于 `flash_log/20261114_blm_round17_timeline.txt`）；结果见 `ROUND17_VIBRATOR_SPMI_RESULT.md`。
实机之后仍未执行：SPMI/PWM/DT 资源差分、stock 3.18.71 同驱动对照、绕过实验、第 18 次实机。
