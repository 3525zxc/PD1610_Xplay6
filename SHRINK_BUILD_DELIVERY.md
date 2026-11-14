# 修复构建交付 · 裁剪内核使 `_end < 0x42000000`

> 2026-11-14 13:26–13:40，**全程离线**：未连接设备、未进 9008、未刷写。设备仍为回滚后的原厂系统。
> 目标：按 `ROUND12_ROOT_CAUSE.md` 的定位，把自编译内核的 BSS 清零区退出 aboot 放置 DTB 的 `0x42000000`。

## 0. 结论

**达成。** 只裁剪调试/追踪/符号表/日志缓冲类配置，不动 UFS、显示、电源、串口与 BLM 插桩，重编后：

| 指标 | Round 10 / 12 候选（失败） | 裁剪后（本次） |
|---|---|---|
| `image_size` | `0x207d000` = 34,066,432 | **`0x1d89000` = 30,969,856** |
| `_end` 物理 | `0x420fd000` | **`0x41e09000`** |
| BSS 物理 | `[0x41dbc400, 0x420f665c]` | `[0x41bbc000, 0x41e0261c]` |
| 与 FDT `0x42000000` 的关系 | **覆盖，越界 `0xfd000`** | **余量 `0x1f7000` ≈ 1.97 MiB** |
| `vmlinux` text/data/bss | 14,304,624 / 10,590,573 / 3,380,828 | 14,268,305 / 9,088,325 / 2,385,436 |
| 判定 | 必然失败 | `FDT_INSIDE_BSS=False` / `FDT_INSIDE_IMAGE=False` / `LOG_OUTSIDE_IMAGE=True` |

`Image.gz-dtb` 55,944,837 B（sha256 `f5f3c864…`），`boot.img` 58,483,968 B（sha256 `054df309…`）。

## 1. 裁剪内容（`tools/blm_shrink_config.py`）

生效 39 项，核心：

- `CONFIG_LOG_BUF_SHIFT 20 → 16`：`__log_buf` 1 MiB → 64 KiB（`bss` 减少 ~995 KiB 的来源之一）
- `CONFIG_LOG_CPU_MAX_BUF_SHIFT 15 → 12`
- 关闭 `KALLSYMS_ALL`、`DEBUG_INFO`、`FTRACE` 系列、`FUNCTION_TRACER`、`DYNAMIC_FTRACE`、`TRACING_SUPPORT`、`EVENT_TRACING`、`TRACEPOINTS`、`RING_BUFFER`、`PROFILING`、`KPROBES`、`UPROBES`、`JUMP_LABEL`、`SCHED_DEBUG`、`DEBUG_PREEMPT`、`SLUB_DEBUG`、`KMEMLEAK`、各 `*_TEST=m` 驱动等
- **`CONFIG_PERF_EVENTS` 保留 `y`**（首轮关闭会导致编译失败，见下文）
- `olddefconfig` 因依赖关系把 `DEBUG_KERNEL / TRACING / TRACEPOINTS / RING_BUFFER / EVENT_TRACING` 拉回 `y`，但 `FTRACE`、`KALLSYMS_ALL`、`DEBUG_INFO` 等实际关闭项已生效，体积目标不受影响

**保持不动**：`CONFIG_SCSI_UFSHCD / SCSI_UFSHCD_PLATFORM / SERIAL_MSM_HS / SERIAL_MSM_SMD`（configtest 已核验），显示、电源、ramdisk 相关，以及 BLM 的 7 个插桩函数。

**一次失败与修复**：首轮把 `CONFIG_PERF_EVENTS` 也关了，`drivers/devfreq/arm-memlat-mon.c` 引用 `perf_event_read_value()` 等接口，触发 `-Werror=implicit-function-declaration`（`make Image.gz-dtb rc=2`）。已从禁用列表移除 `PERF_EVENTS`，保留 `y`，用 `tools/blm_shrink_resume.sh` 增量续编成功。这是裁剪边界问题，不是根因方向问题。

## 2. 构建与验证结果（真实输出）

```
CONFIGTEST_OK  SHRINK_CONFIG_OK changes=39  OLDDEFCONFIG_RC=0
RESUME_OLDDEFCONFIG_RC=0  RESUME_MAKE_IMAGE_RC=0
VMLINUX_BLM_SYMBOLS=7  VMLINUX_C6_SYMBOLS=0  SRC_PURITY c6_files=0 makefile=0 hook=0
KERNEL_BUILD_OK ts=20261114133000 sha256=f5f3c864… size=55944837
BOOTIMG_BUILD_OK status=PASS pass=40/40 sha256=054df309… gzip_len=10711391 dtb_chain_len=30947277 pad=14892825
PREFLIGHT status=PASS pass=17/17 verdict=SAFE_TO_FLASH end_phys=0x41e09000 margin=0x1f7000
build_selfcheck.sh -> SELFCHECK_OK
```

关键布局：gzip 10,711,391 B + DTB 链 30,947,277 B（前 80 份，idx79 含 `blm-ram-log@42100000`）+ 尾零 14,892,825 B，`kernel_size=56,551,493` 固定；ramdisk、签名块、除 `id` 外的头部逐字节保持原厂。

## 3. 新增刷前门槛（`tools/blm_preflight.py`）

把「`_end < 0x42000000`」从人工判断变成**镜像级强制检查**：直接从 `boot.img` 的 kernel 段解出 Image、读 `System.map` 重算物理 `_end`，并核对嵌入镜像与编译产物一致、M1 紧邻边界、DTB 链 80 份、idx79 model 与 BLM 节点存在。要求 `margin >= 0x100000`，否则 `REFUSE_TO_FLASH`。

**阴性对照已验证**：把旧的失败候选 `boot_los16_blm_ddr40000000.img` 喂进去，得到
`PREFLIGHT status=FAIL pass=13/17 verdict=REFUSE_TO_FLASH end_phys=0x420fd000 margin=-0xfd000`，
精确列出 `END_BELOW_FDT / FDT_OUTSIDE_BSS / FDT_OUTSIDE_IMAGE / MARGIN_AT_LEAST_MIN` 四项失败。⇒ 这个门槛能挡住已知会失败的镜像，不是摆设。

## 4. 产物

| 文件 | 说明 |
|---|---|
| `images/boot_los16_blm_shrink_20261114133000.img` | **可刷候选**，58,483,968 B，sha256 `054df30969c299c2d14be505ff12a4e43ed0aff94ebc1065ebaad8b68d0f72a8` |
| `build/shrink-20261114133000/Image.gz-dtb` | 编译产物，55,944,837 B，sha256 `f5f3c864…` |
| `build/shrink-20261114133000/{System.map,vmlinux,config_los16_blm_shrink.txt,kernel_build.env,build.log,vmlinux_size.txt,config_diff.json}` | 构建证据 |
| `images/boot_los16_blm_shrink_20261114133000.{report.json,preflight.json,root_cause.json}` | 40/40 自检、17/17 预检、根因区间计算 |
| `images/boot_los16_blm_ddr40000000.preflight.json` | 阴性对照（应被拒绝） |
| `tools/blm_shrink_config.py`、`blm_shrink_kernel.sh`、`blm_shrink_resume.sh`、`blm_configtest.sh`、`blm_preflight.py` | 可复现工具链 |

## 5. 未执行 / 边界

> 2026-11-14 13:52 更新：**第 13 次实机已完成**，见 `ROUND13_SHRUNK_BOOT_RESULT.md`。裁剪根因修复被实机证实（FDT 头从全零恢复合法、BLM 阶段从 3 推进到 12 `KERNEL_INIT`），但未启动到系统；新瓶颈在 initcalls / rootfs / ramdisk。设备已回滚并二次核验原厂系统。

**已完成第 13 次实机**（此前表述已过时）。仍未闭环：3.18.120 与原厂 3.18.71 的语义差异、initcall 阶段具体失败点、BLM 行槽为何在 `CONSOLE_REGISTERED` 后不再捕获 printk。裁剪本身也引入了 39 项配置变化（虽然都在调试类）。

设备当前：原厂 `3.18.71-perf-g8a8c60dd` / LOS16，adb 在线，fastboot 已退出。

## 6. 第 13 次实机命令（待拍板）

```
& 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\tools\fastboot.exe' -s 5fccbfeb flash boot 'D:\xplay6\evidence\kernel_re\out\stage2\bootloop_monitor\images\boot_los16_blm_shrink_20261114133000.img'
& 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\tools\fastboot.exe' -s 5fccbfeb reboot
```
若仍失败：等自动进 9008，`tools\blm_capture_edl.bat 5` 读回 BLM 日志判定阶段；同时用
`python tools\blm_firehose_peek.py --com 5 --address 0x42000000 --size 0x40 --chunk 0x40 --no-upload --out flash_log\fdt_head_round13.bin --workdir edl_probe`
确认 FDT 头这次是否还是全零（可区分「BSS 覆盖已修好」与「另有原因」）。最后按既有流程回滚原厂 `boot.img`。
