# ROUND 18 · qpnp-vibrator 绕过实验：自编译内核首次完整启动到 Android 用户态

日期：2026-11-14 16:33–16:55
状态：**实机完成，设备当前仍运行在自编译 `3.18.120-perf` 内核上，卡 LOS16 开机动画（二屏），adb 在线**
镜像：`images/boot_los16_blm_vibbypass_20261114160500.img`，sha256 `27493588b78c9a2d6e0b62efa1e951322063c92762fe904ab512bb142e8bbcdb`

---

## 1. 一句话结论

把 idx79 里的 `qcom,vibrator@5100` 节点用 37 个 `FDT_NOP` 等长抹掉后，
**前 17 次所有内核卡点全部消失**：自编译 3.18.120 内核完整跑完 initcalls、挂载 rootfs、
启动 `zygote / system_server / surfaceflinger / vold`，adb 在线，进入 Android 开机动画。

当前停在二屏的**原因不是内核**，而是绕过手段的副作用：
vibrator 设备节点消失 ⇒ vibrator HAL 打不开设备反复崩溃 ⇒ `system_server` 主线程死等这个必需 HAL
⇒ `sys.boot_completed` 永不置位 ⇒ 开机动画一直转。

⇒ **「第一次 SPMI 读卡死」是当时的唯一内核瓶颈，且是 vibrator 设备专属，不是 SPMI 总线共性问题。**

---

## 2. 运行态硬证据（16:50 抓取，设备 uptime 5→7 分钟，未重启）

```
uname -a = Linux localhost 3.18.120-perf #4 SMP PREEMPT
           Sat Nov 14 16:07:25 CST 2026 aarch64
init.svc.bootanim        = running
init.svc.surfaceflinger  = running
init.svc.zygote          = running
init.svc.vold            = running
ro.crypto.state          = unencrypted
sys.boot_completed       = (空)
init.svc.vibrator-1-0    = restarting
```

`ro.build.fingerprint = vivo/lineage_pd1610/pd1610:9/PQ3A.190801.002/...userdebug/test-keys`，
即跑的是与回滚镜像同一套 LOS16 用户态，只有 boot 分区换成了自编译内核。

产物：`flash_log/round18_dmesg.txt` (63,412 B)、`round18_logcat.txt` (246,665 B)、
`round18_getprop.txt` (18,880 B)、`round18_ps.txt` (40,226 B)、
`round18_system_server_stack.txt` (70,157 B)、`20261114_blm_round18_timeline.txt`。

---

## 3. 卡二屏的因果链（全部有日志直接支撑）

| 环节 | 证据 |
|---|---|
| ① 节点被抹掉 | `idx79_vibrator_bypass_nop.dtb`：148 B 节点 → 37 FDT_NOP，**无 phandle、无引用**；`vibrator_absent=True` |
| ② 内核 probe 不执行 | 因此 `/sys/class/timed_output/` 为**空目录**，`/sys/class/timed_output/vibrator/enable`、`/dev/vibrator`、`/sys/class/leds/vibrator` 全部 No such file |
| ③ HAL 声明仍为必需 | `/vendor/manifest.xml:263` `<name>android.hardware.vibrator</name>` |
| ④ HAL 打不开设备 | `Vibrator device does not exist. Cannot start vibrator` / `VibratorService: vibrator_open failed: -19 (ENODEV)` / `Passthrough failed to open legacy HAL` |
| ⑤ HAL 崩溃循环 | dmesg 每 5 s：`init: starting service 'vibrator-1-0'` → `exited with status 1` → kill；logcat 中 `E VibratorService` 122 次、`E android.hardware.vibrator@1.0-service` 61 次 |
| ⑥ system_server 死等 | logcat 每秒 `W ServiceManagement(system_server): Waited one second for android.hardware.vibrator@1.0::IVibrator/default. Waiting another...`（98 次） |
| ⑦ 栈证据 | `adb root` 后 `debuggerd -b 1087`：`com.android.server.VibratorService.<init>` → `android::vibratorInit` → `halCall<...IVibrator>` → `getServiceInternal<IVibrator>` → `IPCThreadState::waitForResponse` |
| ⑧ 结果 | `systemReady()` 之后的服务未继续、`sys.boot_completed` 空、bootanimation 不退出 |

`configstore-hal-1-0` 也在每 5 s 重启（SIGSYS / libminijail blocked `getdents64`），
但 `system_server` 的栈明确停在 vibrator HAL 等待，故它是并行噪声而非本次阻塞主因（未做因果排除实验）。

---

## 4. 与 `ROUND18_BYPASS_READY.md` 判据对照

| 判据 | 实测 | 结论 |
|---|---|---|
| adb 上线 `3.18.120` | ✅ `3.18.120-perf` | **命中第一行**（比预期更完整：内核完整启动） |
| 越过 `KERNEL_INIT` 到 `INITCALLS_DONE`/`ROOTFS_READY` | ✅ 已进 system_server | 瓶颈进入 Android 用户态 |
| 槽 0 变成后续 initcall、vibrator 槽全空 | 未取 BLM dump（设备还在运行、无 9008） | 未验证，但由内核完整启动间接成立 |
| 仍停 `KERNEL_INIT` / 卡在别的 SPMI 设备 | ❌ 未发生 | **排除 SPMI/PMIC-ARB 共性问题** |
| `last_stage` 回退到 3 | ❌ 未发生 | NOP 结构未引入 DTB 解析问题 |

---

## 5. 严格单变量与门禁（离线）

| 项 | 结果 |
|---|---|
| DTB 结构审计 | `BYPASS_DTB 15/15 PASS`（节点外零差异、头部 10 字段全同、`vibrator_absent=True`、BLM 节点保留） |
| image 构建 | `BOOTIMG_BUILD_OK 40/40 PASS` |
| 刷前预检（实机前现场重跑） | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 镜像级差分 | `BYPASS_VERIFY 26/26 PASS`，58,483,968 B 中 `unexpected=0`，差异仅 `[576,596)` header id 与 `[41434348,41434496)` 节点区 |
| 全套自测 | `SELFCHECK_OK` |
| DT 资源差分 | `vibrator_props_identical=True`、`spmi_node_paths_identical=True`（候选与原厂逐项一致） |

新增工具：`blm_bypass_inspect.py`、`blm_bypass_dtb.py`、`blm_verify_bypass.py`。

> 一次检查项修正：`BYPASS_VERIFY` 初版假设节点内每个 4B 块都会变化，实测 37 块中 34 块变化
> （3 块原本就等于 FDT_NOP），改为验证「bypass 区间全为 FDT_NOP」后 `26/26`。

---

## 6. 工程事实与偏差

- 16:44:18 `pre_kernel` 读取报 `device not found`（adb daemon 重启瞬态）；随后 `adb reboot bootloader` 正常进入 fastboot，不影响流程。
- 16:44:39 绕过镜像**一次写入成功**（`Sending OKAY [1.502s]` / `Writing OKAY [0.396s]`）+ reboot。
- 观察阶段未进 9008、未 bootloop，因此**未做双读、未回滚、未执行 `power reset`**；用户报告「进二屏、卡 LOS16 logo 动画」后转为运行态取证。
- 第一次运行态取证脚本因正则 `device\s*$` 过严，`adb devices -l` 的行尾带 `product:...` 而误判 `ADB_NOT_ONLINE`；改用 `device\b` 后抓到全部证据。**这是脚本判断错误，不是设备状态变化。**
- `debuggerd -b` 首次因非 root 失败（381 B 错误文本），`adb root` 后得 70,157 B 有效栈；`adb root` 只重启 adbd，内核未重启（`uname` 前后均为 `3.18.120-perf`）。
- 设备当前 adb 为 **root** 身份；重启后自动恢复。

---

## 7. 下一步方向（均未执行）

1. **让系统进桌面（最便宜，需一次增量重编译）**：恢复 `qcom,vibrator@5100` 节点，
   在 `qpnp_vibrator_config()` 中跳过卡死的两次 `qpnp_vib_read_u8()` / SPMI 写，用默认 `reg` 值继续
   `timed_output_dev_register()`。这样 probe 能返回、设备节点存在、HAL 能打开，
   `system_server` 不再阻塞 ⇒ 预计可直接进 Launcher。这是把「绕过」升级为「修复」。
2. **不重编译的替代验证**：在 vendor 侧让 `android.hardware.vibrator@1.0` 不再是必需 HAL
   （改 `/vendor/manifest.xml` 或提供 stub HAL），需写系统分区、风险高，不推荐优先。
3. **补 BLM dump**：设备仍在运行，若需固定槽证据可在回滚后进 9008 读 `0x42100000`；
   本轮未做。
4. **查 SPMI 读卡死的真实机制**（保留作独立课题）：DT 资源与 stock 完全一致，
   更可能是 3.18.120 的 SPMI/PMIC-ARB 驱动实现或运行时时序差异；
   可在 `spmi_ext_register_readl` 前后插桩定位。

---

## 8. 设备状态与回滚（17:04 更新：已回滚）

**最终状态：已回滚到原厂并验证**。用户在 16:58 选择「先回滚到原厂」；
第一次回滚脚本在 `adb reboot bootloader` 后被中断，**未写入任何分区**，
设备重启后仍是绕过镜像、仍卡二屏（用户报告「又卡二屏了」）。
17:02 拆步重做后完成：

```
17:02:40  adb reboot bootloader        → 17:03:11 fastboot 5fccbfeb / QC_REFERENCE_PHONE
17:03:31  flash boot 929fda99…         → Sending OKAY [1.502s] / Writing OKAY [0.391s]
17:03:31  reboot                       → OKAY
17:04:33  adb 上线  uname = 3.18.71-perf-g8a8c60dd
          fingerprint = vivo/lineage_pd1610/pd1610:9/...userdebug/test-keys
          sys.boot_completed = 1      ← 进桌面，不是卡二屏
          ROLLBACK_VERIFIED
```

`sys.boot_completed=1` 是又一条交叉证据：**同一套 LOS16 用户态 + 原厂内核可以正常完成启动**，
所以卡二屏确属绕过镜像的 vibrator HAL 副作用，而非系统分区被改坏。

回滚镜像 sha256 `929fda99…`，与前 11 次成功回滚完全相同。
本轮未改动既有 ROUND 文档中的实测数据；未重编译内核；未写系统分区（除 boot）。

> 时间线中 16:58:53 的 `=== USER DECISION: ROLLBACK TO STOCK ===` 块只到 STEP1；
> 17:02:40 起的 `=== ROLLBACK RETRY (split steps, after abort) ===` 才是实际完成的回滚。
