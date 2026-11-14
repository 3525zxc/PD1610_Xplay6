# ROUND 19 · 自编译 3.18.120 内核首次完整启动进桌面

日期：2026-11-14 17:12–17:35
状态：**实机成功，项目目标达成**；设备当前运行在自编译内核，`sys.boot_completed=1`，但**触摸屏不可用**
镜像：`images/boot_los16_blm_vibfix_20261114171500.img`，sha256 `35f8a2e6607227b5a8fefcf82d97dc9d484330e34f70f4e8ef22ede1dcbd2052`

---

## 1. 一句话结论

恢复 `qcom,vibrator@5100` 节点 + 把卡死的 SPMI 读/写换成 stub 后，
**自编译 3.18.120 内核完整启动、Android 完成开机、进入 Launcher**。
剩下的是一个新的、独立的外设问题：触摸驱动没有绑定成功，屏幕点不了。

```
uname = Linux localhost 3.18.120-perf #5 SMP PREEMPT
        Sat Nov 14 17:22:43 CST 2026 aarch64
sys.boot_completed      = 1          ← 完成开机
init.svc.bootanim       = stopped    ← 开机动画已退出
init.svc.surfaceflinger  = running
init.svc.zygote         = running
init.svc.vold           = running
init.svc.vibrator-1-0   = running    ← 上一轮崩溃循环的 HAL 已稳定
/sys/class/timed_output/vibrator/enable  存在  ← stub 修复让设备节点注册成功
```

`ro.build.fingerprint = vivo/lineage_pd1610/pd1610:9/PQ3A.190801.002/...userdebug/test-keys`
（同一套 LOS16 用户态，只换 boot 分区）。

---

## 2. 修复了什么

| 环节 | Round 17（有节点） | Round 18（抹掉节点） | **Round 19（修复）** |
|---|---|---|---|
| `qpnp_vibrator_probe` | 卡在第一次 SPMI 读 | 不执行 | **走完** |
| `/sys/class/timed_output/vibrator` | 未创建 | 未创建 | **创建** |
| vibrator HAL | 未到 | 崩溃循环 `ENODEV` | **running** |
| `system_server` | 未到 | 死等 `IVibrator` | **继续** |
| `sys.boot_completed` | — | 空 | **1** |

做法（`ROUND19_FIX_READY.md` 详述）：
- `blm_apply_kernel_patch.py --spmi-stub`（默认关闭，旧构建零影响）把
  `qpnp_vib_read_u8()` / `qpnp_vib_write_u8()` 换成不碰总线的 stub，新增固定槽 27/28；
- 不传 `--idx79-dtb`，恢复含 vibrator 节点的原始 idx79（1984 节点，BLM 节点保留）；
- DT 无 `qcom,mode` ⇒ `QPNP_VIB_MANUAL`，不走 `pwm_request`，只有 SPMI 一处等待。

**功能边界**：stub 后马达不会真的振动，硬件寄存器不再写入。这是「让系统启动」的修复，
不是「恢复 vibrator 功能」；SPMI 读卡死的真实机制（3.18.120 驱动/时序差异）仍是独立课题。

---

## 3. 门禁与单变量

| 项 | 结果 |
|---|---|
| DTB 审计（Round 18） | `BYPASS_DTB 15/15`；本轮恢复节点后 1984 节点、BLM 节点在 |
| 补丁树 | `tests/patched_tree_vibfix/`，`KERNEL_PATCH_OK outputs=9`，13 个 `blm_trace_note` |
| 构建 | `KERNEL_BUILD_OK`，`MAKE_IMAGE_RC=0`，9 个 BLM 符号，C6 全 0 |
| 构建自检 | `BOOTIMG_BUILD_OK 40/40 PASS` |
| 刷前预检（实机前现场重跑） | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 镜像级差分 | `KERNEL_ONLY_VERIFY 10/10`：与第 17 次镜像比**只有 gzip 变**（10709503→10708224 B），DTB 链/ramdisk/签名/头除 id 全同 |
| 反汇编验证 | 全内核 `spmi_ext_register_readl` 调用点 83→81、write 67→66；`qpnp_vibrator_probe` callee 无 SPMI、保留 `timed_output_dev_register` |
| 全套自测 | `SELFCHECK_OK`；判定器对旧 dump 兼容 |

新增/改动工具：`blm_apply_kernel_patch.py`、`blm_trace_report.py`、`blm_trace_build.sh`、
`blm_verify_stub_disasm.sh`、`blm_bypass_inspect.py`、`blm_bypass_dtb.py`、`blm_verify_bypass.py`。

---

## 4. 实机过程

```
17:29:49  出发状态：原厂 3.18.71-perf-g8a8c60dd / boot_completed=1
17:29:58  adb reboot bootloader → fastboot 5fccbfeb / QC_REFERENCE_PHONE
17:30:17  修复镜像一次写入 OKAY (Sending 1.552s / Writing 0.389s) + reboot
17:30:42  adb 上线，3.18.120-perf #5；此时 boot_completed 尚空，timed_output/vibrator 已存在
17:30:54  sys.boot_completed=1、bootanim=stopped  ⇒ 进 Launcher
17:31:26  二次核验全部服务 running，抓 dmesg/logcat/getprop/ps
```

**未回滚**：boot 分区仍是修复镜像 `35f8a2e6…`，设备可交互（adb root 已开），
是否回滚由用户决定。回滚镜像 `929fda99…`（前 12 次成功回滚同一个文件）。

---

## 5. 新的缺口：触摸屏不可用

用户报告「点不了屏幕」。这是**驱动层缺口，不是启动失败**，也不是输入分发卡住。

### 证据

| 观察 | 结果 |
|---|---|
| `/dev/input/` | 只有 4 个设备：`qpnp_pon`(电源)、`qbt1000_key_input`(虚拟键)、`hbtp_vm`(虚拟鼠标)、`gpio-keys`(音量) |
| `getevent -i` | **没有任何带 `ABS_MT_*` 的多点触摸设备** |
| `InputReader` | 只添加 4 个设备；系统配置里是 `-touch` |
| 显示器 | 正常：`BUILT_IN 1440x2560, touch INTERNAL` |
| 内核 config | 触摸驱动**全部保留**：`CONFIG_TOUCHSCREEN_SYNAPTICS_DSX*` / `ATMEL_MXT` / `INPUT_TOUCHSCREEN` / `OF_TOUCHSCREEN` / `SECURE_TOUCH` 等 16 项全是 `y`；与基准 config 唯一差异是无关的 `CONFIG_INPUT_EVBUG m→n` |
| DTB | 触摸节点都在：`/soc/i2c@75ba000/synaptics@20`、`rmi_i2c@49`、`/soc/i2c@7577000/cyttsp_i2c@28`、`/soc/touchscreencfg` |
| I2C 枚举 | `12-0020`(modalias `i2c:dsx`)、`12-0049`(`i2c:fts`)、`3-0028` 都已枚举 |
| 驱动注册 | `/sys/bus/i2c/drivers/synaptics_dsxv26/`、`atmel_mxt_ts/` 存在 |
| **绑定** | **三个设备都没有 `driver` 软链；两个驱动目录内都没有绑定设备** ⇒ probe 未成功 |
| 手动 bind | `echo 12-0020 > .../synaptics_dsxv26/bind` 静默失败，无新 input 设备、无新增内核日志 |

⇒ 卡在「I2C 触摸驱动 probe / 绑定」阶段，原因尚未采集到。

### 为什么看不到原始错误（观测缺口）

裁剪时把 `CONFIG_LOG_BUF_SHIFT 20→16`（1 MiB→64 KiB）以缩小 BSS 避开 DTB 覆盖，
导致早期内核日志被冲掉：`round19_dmesg.txt` 从 **6.97 s** 才开始（触摸 probe 通常在 1–3 s）。
同时系统处于 SELinux permissive，AVC denied 洪水量极大，日志里出现
`audit: audit_lost=327` / `audit: rate limit exceeded`，进一步挤占缓冲。

⇒ 这不是新的死机，是**观察能力被裁剪配置削弱**。

### 下一步（按成本排序，均未执行）

1. **只改 header、不重编译**：用 `--append-cmdline "audit=0 loglevel=8 ignore_loglevel"`
   重打包（单变量 20 余字节），减少审计洪水，重启后立刻在 adb 上线时抓 dmesg，
   争取保住触摸 probe 的原始错误文本。
2. **适度恢复日志缓冲**：`LOG_BUF_SHIFT 16→18`（+192 KiB BSS），当前余量 `0x1f7000 ≈ 1.97 MiB`
   仍充足，跑 `blm_preflight.py` 确认 `margin ≥ 1 MiB` 后再刷。这能显著延长早期日志保留时间。
3. 拿到错误后按类型处理：regulator/`vdd-supply` 未就绪、pinctrl、固件缺失、
   `probe deferral` 循环、或 3.18.120 与 3.18.71 的 DSX 驱动语义差异。
4. **stock 对照**：回滚原厂 boot 后抓一份正常触摸的 `getevent -i` / dmesg，
   明确目标设备名与 probe 路径，再逐项对照候选。

---

## 6. 证据文件

`flash_log/20261114_blm_round19_timeline.txt`、
`round19_{dmesg,logcat,getprop,ps,dumpsys_input}.txt`、
`images/boot_los16_blm_vibfix_20261114171500.{report,preflight,kernel_only}.json`、
`ROUND19_FIX_READY.md`。

本轮未重编译两次（仅一次增量编译）、未写系统分区（除 boot）、未改既有 ROUND 文档的实测数据。
