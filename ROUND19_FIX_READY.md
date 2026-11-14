# ROUND 19 · 把「绕过」升级为「修复」（SPMI stub + 恢复 vibrator 节点）

日期：2026-11-14 17:12–17:20
状态：**离线准备全部完成，等待实机拍板**；设备当前为原厂 `3.18.71-perf-g8a8c60dd` / LOS16（`sys.boot_completed=1`）
目标：让 `qpnp_vibrator_probe()` 正常返回并注册 `timed_output` 设备，使 vendor vibrator HAL 能打开，
`system_server` 不再死等 ⇒ 自编译 3.18.120 内核**完整启动进 Launcher**。

---

## 1. 上一轮留下的两个事实

- Round 18 证明：抹掉 `qcom,vibrator@5100` 节点后，自编译 3.18.120 内核能完整启动到 Android 用户态，
  但卡二屏，原因是 **vibrator HAL 打不开设备**：`/sys/class/timed_output/` 空 →
  `vibrator_open failed: -19 (ENODEV)` → HAL 每 5 s 崩溃重启 →
  `system_server` 主线程死在 `VibratorService.<init>` → `sys.boot_completed` 空。
- Round 17 证明：保留节点时，卡在 `qpnp_vib_read_u8()` 内第一次
  `spmi_ext_register_readl(ctrl, sid, QPNP_VIB_VTG_CTL(0x5100), &reg, 1)` 未返回。
- 且 `blm_bypass_inspect.py` 已排除「DT 资源写错」：候选与原厂 vibrator 属性、SPMI/PMIC-ARB 路径逐项一致。

⇒ 唯一缺的是「让 probe 走完，同时让设备节点存在」。

---

## 2. 修复做法

### 2.1 恢复节点
不传 `--idx79-dtb`，由默认补丁器从原厂链生成「含 `qcom,vibrator@5100` + `blm-ram-log@42100000`」的 idx79。
实测三份镜像对照：

| 镜像 | idx79 vibrator | BLM 节点 | 节点数 |
|---|---|---|---|
| 第 17 次 `boot_los16_blm_vib_…` | 有 | 有 | 1984 |
| 第 18 次绕过 `…vibbypass…` | **无** | 有 | 1983 |
| **第 19 次修复 `…vibfix…`** | **有** | 有 | **1984** |

### 2.2 把卡死的 SPMI 访问换成 stub
`blm_apply_kernel_patch.py` 新增可选 `--spmi-stub`（**默认关闭，旧构建零影响**），
把 `qpnp-vibrator.c` 的两个 helper 换成不碰总线的实现，并保留全部固定槽里程碑：

```c
static int qpnp_vib_read_u8(struct qpnp_vib *vib, u8 *data, u16 reg)
{
    /* BLM_SPMI_STUB_ACTIVE */
    (void)vib;
    blm_trace_note(27, "VIB_STUB_READ", (unsigned long)reg);
    *data = 0;
    return 0;
}
static int qpnp_vib_write_u8(struct qpnp_vib *vib, u8 *data, u16 reg)
{
    (void)vib; (void)data;
    blm_trace_note(28, "VIB_STUB_WRITE", (unsigned long)reg);
    return 0;
}
```

关键点：DT 节点**没有 `qcom,mode` 属性** ⇒ `vib->mode = QPNP_VIB_MANUAL`，
`qpnp_vibrator_config()` 里 `pwm_request` / `pwm_config` 分支不会进入，
所以只需处理 SPMI 读/写，不存在第二处等待。

`qpnp_vibrator_config()` 用 stub 返回的 0 值继续：
`reg_vtg_ctl` 按 `vtg_level` 计算、`reg_en_ctl` 按 `active_low` 计算，
`qpnp_vib_write_u8()` 返回 0 ⇒ config 返回 0 ⇒ probe 走到
`timed_output_dev_register(&vib->timed_dev)`，创建
`/sys/class/timed_output/vibrator/enable`。

**功能边界（必须如实说明）**：stub 后马达不会真的振动，硬件寄存器不再被写。
这是「让系统启动」的修复，不是「恢复 vibrator 功能」；SPMI 读卡死的真实机制仍是独立课题。

### 2.3 反汇编验证 stub 生效
`blm_verify_stub_disasm.sh`：

| 指标 | 第 17 次 | 第 19 次修复 |
|---|---|---|
| 全内核 `spmi_ext_register_readl` 调用点 | 83 | **81** |
| 全内核 `spmi_ext_register_writel` 调用点 | 67 | **66** |
| `qpnp_vibrator_probe` callee 中的 SPMI 调用 | 有 | **无** |
| `timed_output_dev_register` | 保留 | **保留** |
| `VIB_STUB_READ` / `VIB_STUB_WRITE` 标签 | 无 | 各 1 |

两个 helper 被编译器内联，System.map 无独立符号（不是缺失）。

---

## 3. 产物与门禁

| 项 | 值 |
|---|---|
| 修复镜像 | `images/boot_los16_blm_vibfix_20261114171500.img` |
| sha256 / 大小 | `35f8a2e6607227b5a8fefcf82d97dc9d484330e34f70f4e8ef22ede1dcbd2052` / 58,483,968 B |
| 内核 `Image.gz-dtb` | `build/vibfix-20261114171500/`，sha `b7afd454…`，55,941,670 B |
| 构建 | `KERNEL_BUILD_OK`，`MAKE_IMAGE_RC=0`，9 个 BLM 符号，C6 全 0 |
| 补丁树 | `tests/patched_tree_vibfix/`，`KERNEL_PATCH_OK outputs=9`，13 个 `blm_trace_note` |
| 构建自检 | `BOOTIMG_BUILD_OK 40/40 PASS`（gzip 10,708,224 B，链 30,947,277 B，尾零 14,895,992 B） |
| 刷前预检 | `PREFLIGHT 17/17 SAFE_TO_FLASH`，`end_phys=0x41e09000`，`margin=0x1f7000` |
| 镜像级差分 | `KERNEL_ONLY_VERIFY 10/10 PASS`：与第 17 次镜像比**只有 gzip 变**（10709503→10708224 B），DTB 链/ramdisk/签名/头除 id 全同 |
| 全套自测 | `SELFCHECK_OK`；判定器对 Round 17 旧 dump 兼容 |
| 新增/改动工具 | `blm_apply_kernel_patch.py`(`--spmi-stub`)、`blm_trace_report.py`(id 27/28)、`blm_trace_build.sh`(可选补丁树目录)、`blm_verify_stub_disasm.sh` |

---

## 4. 第 19 次实机判据（写死）

固定槽 0=last-initcall，16–26=vibrator 里程碑，新增 27/28=stub 生效标记。

| 观察 | 结论 |
|---|---|
| **adb 上线 `3.18.120-perf` 且 `sys.boot_completed=1`，`init.svc.bootanim=stopped`** | **完整成功**：进 Launcher，项目目标达成 |
| adb 上线、`3.18.120-perf`，`sys.boot_completed` 空但 `init.svc.vibrator-1-0=running` | HAL 起来了，卡点后移到别的 Android 服务；按 logcat/栈继续追 |
| adb 上线，槽 22..28 全命中，`/sys/class/timed_output/vibrator/enable` 存在 | probe 走完、设备注册成功（stub 修复本身验证通过） |
| 仍卡二屏且 `vibrator_open failed: -19` | stub 未让设备注册成功，回查 `timed_output_dev_register` |
| 进 9008、BLM 固定槽最后到 22（VIB_READ1），无 27/28 | stub 未生效，检查镜像是否用错补丁树 |
| 进 9008、槽 27/28 有但停在 `KERNEL_INIT` | SPMI 之外还有卡点，按槽 0 的 last-initcall 追 |
| `last_stage` 回退到 3 `SETUP_ARCH_ENTER` | DTB 结构或内核体积回归，跑预检与双读 FDT 头 |

---

## 5. runbook（拆步，避免长脚本被中断）

设备起始为原厂系统、adb 在线。

```
# 1) 切 fastboot（短命令）
adb -s 5fccbfeb reboot bootloader
fastboot -s 5fccbfeb getvar product

# 2) 刷入 + 重启（短命令，写入失败不 reboot）
fastboot -s 5fccbfeb flash boot <vibfix.img>
fastboot -s 5fccbfeb reboot

# 3) 观察 180 s：同时检测 9008 / adb / sys.boot_completed
#    adb 上线即抓：uname -r、sys.boot_completed、init.svc.bootanim、
#                   init.svc.vibrator-1-0、ls /sys/class/timed_output/、
#                   dmesg、logcat、getprop（全部落盘）
#    若 9008：双读 0x42000000 + 0x42100000（不复位），跑 blm_trace_report.py

# 4) 判定后再决定保留或回滚（本轮不自动回滚）
fastboot -s 5fccbfeb flash boot <stock boot.img 929fda99…>
fastboot -s 5fccbfeb reboot
adb -s 5fccbfeb shell uname -r
```

> **与上一轮的差别**：第 18 次观察脚本只等 9008，adb 上线时脚本仍在循环里；
> 第 19 次必须把「adb 上线 + `sys.boot_completed=1`」当作成功分支立即抓取，不能只等 9008。
> 设备 adb 在线时可直接 `adb reboot bootloader` 回滚，无需手动按键。

---

## 6. 风险与边界

- 只刷 `blm_preflight.py 17/17 SAFE_TO_FLASH` 的镜像；不尝试 EDL 写分区。
- stub 禁用真实振动，属已知功能降级；SPMI 根因（3.18.120 驱动/时序差异）仍未查。
- 固定槽是 [O]，Android 侧机制推论仍标 [H]。
- 离线阶段未碰设备、未改既有 ROUND 文档中的实测数据；未执行第 19 次实机。
