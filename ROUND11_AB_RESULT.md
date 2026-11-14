# Round 11 · A/B 实机对照：BLM 保留区节点不是失败原因

> 2026-11-14 12:57–13:04，第 11 次 Boot-only 实机。仅写 `boot` 分区；设备已回滚并二次核验原厂系统。
> 本轮回答一个问题：去掉 `/reserved-memory/blm-ram-log@42100000` 后，内核能否走过阶段 4。

## 0. 结论

**不能。假设 1 被排除。**

剥离组（等长 `FDT_NOP` 覆盖节点、其余 58 MB 全同）实机启动后，`generation=4` 的新记录仍停在 `SETUP_ARCH_ENTER`（阶段 3），阶段序列与含节点组**逐格相同**。取证工具自己引入的 `reserved-memory` 节点不是这个 bootloop 的原因。

| 组 | 镜像 sha256 | 记录 | 最后阶段 | 阶段序列 |
|---|---|---|---|---|
| 含节点（Round 10） | `4abe6ba6…` | gen 2、gen 3 | 3 `SETUP_ARCH_ENTER` | START_KERNEL → BEFORE_SETUP_ARCH → SETUP_ARCH_ENTER |
| **剥离节点（Round 11）** | `13bd3242…` | **gen 4** | **3 `SETUP_ARCH_ENTER`** | **完全相同** |

## 1. 观察 [O]

| 项 | 实测 |
|---|---|
| 刷入 | 12:57:35 `fastboot flash boot` `Sending OKAY [1.512s]` / `Writing OKAY [0.392s]`；`reboot OKAY` |
| 启动观察 | t=0–90 s 无 fastboot/adb/9008；**t=95 s 自动进 9008 (COM5)**；全程 `adb_seen=False`、`candidate_kernel=False` |
| 读回 | 13:00:00 Sahara 上传 OK，`<peek>` 4 × `0x10000`，`failed_blocks=0` |
| dump | `flash_log/blm_ram_round11.bin`，262,144 B，sha256 `8fd368a729e8b6315690f12259717e20067c367c74a8a1a662afdb312af295b2` |
| 日志头 | `314154454d4d4c42 04000000...` = `BLM_META_MAGIC` + **generation=4**（Round 10 是 3） |
| 判定 | `bank_count=2`、`meta_generation=4`、`selected_bank=0 gen=4`、`last_stage=3 SETUP_ARCH_ENTER`、`rule=fdt_scan` |
| 回滚 | 13:03:01 刷原厂 `boot.img`（sha256 `929fda99…`）`Sending/Writing OKAY`；13:03:51 adb 上线 `ROLLBACK_VERIFIED` |
| 二次核验 | 13:04:40 adb 在线、`3.18.71-perf-g8a8c60dd`、uptime 1 min、fastboot 已退出、PnP 为 ADB Interface |

`blm_forensics.py` 明细：本轮 dump 里**同时保留了两次实验的记录**，且都在同一块 RAM 中：

```
BANK 0  gen=4  last_stage=3(SETUP_ARCH_ENTER)  stages=3  lines=1
        stage_seq=START_KERNEL,BEFORE_SETUP_ARCH,SETUP_ARCH_ENTER
        fdt=0x42000000 log=0x42100000 ddr=0x40000000
BANK 1  gen=3  last_stage=3(SETUP_ARCH_ENTER)  stages=3  lines=1
        stage_seq=START_KERNEL,BEFORE_SETUP_ARCH,SETUP_ARCH_ENTER
```

⇒ gen=3（含节点）与 gen=4（剥离节点）并列对照，结论一致；同时再次证明 warm reset 跨多次失败启动后日志区仍可留存。

## 2. 关于「回滚时又 bootloop，是不是刷错了」的核查

**没有刷错**，回滚镜像是前 8 次成功回滚的同一个文件 `D:\16\PD1610_81\release\PD1610_LOS16_20261112\images\boot.img`，sha256 `929fda9985478078f0614a9c3709af69fe3b1c9c8badc50e783261f91ab241ae`（13:04:40 现场复核一致）。

真实时间线（用户看到的 bootloop 发生在**回滚之前**）：

```
12:57:35 刷入剥离节点候选镜像 + reboot        <- 此时 boot 分区是候选
12:57:52~12:59:38 观察，t=95s 自动进 9008
13:00:00~13:00:07 peek 捕获，带 --reset       <- firehose 复位，设备重启回候选镜像
13:00:43 开始回滚流程，等待设备回到 fastboot
13:00:43~13:02:59 设备仍在跑候选镜像 -> 持续 bootloop（用户看到的就是这一段，共 135 s）
13:02:59 fastboot_ready t=135s                <- 用户手动进 fastboot 很可能正是这一步
13:03:01 刷入原厂 boot + reboot
13:03:51 adb 上线原厂内核，ROLLBACK_VERIFIED
13:04:40 二次核验：adb 在线、uptime 1 min
```

即：bootloop 是**候选镜像**（本轮实验对象）在等待回滚窗口期间的正常表现，不是原厂 boot 写坏。手动进 fastboot 让脚本接上了回滚，结果是好的。

## 3. 假设表更新

| # | 假设 | 状态 |
|---|---|---|
| 1 | `blm-ram-log` 保留区节点干扰早期 DT 扫描 | **已排除 [O]**（本轮 A/B） |
| 2 | `0x42000000` 处实际 FDT 内容/头部无效 | **未验证，升为首要嫌疑** |
| 3 | DTB 链 `122→80` + 14,361,006 B 尾零 | 未验证，次优先 |
| 4 | `phys_to_virt()` / 线性映射异常 | 已降级（BLM 用同一映射写日志成功） |
| 5 | x0 / SCM / TZ 交接 | 暂保留 |

排除假设 1 后，失败窗口仍在 `setup_arch()` 入口之后、`setup_machine_fdt()` 返回之前，最直接的下一个未知量变成「aboot 放在 `0x42000000` 的那份 FDT，内核读到的到底是什么」。

## 4. 下一步建议（未执行，成本从低到高）

1. **不改动内核、不改镜像**：下一次候选失败进 9008 时，除 `0x42100000` 的 BLM 区外，顺手 peek `0x42000000` 起 64 B，核对 `d00dfeed` 与 `totalsize` 是否等于 409,688。`blm_firehose_peek.py --address 0x42000000 --size 0x40 --chunk 0x40 --no-upload` 即可。设备已回滚，现在读只能看到原厂运行期内容，必须配合一次失败启动。
2. **在 `setup_machine_fdt()` 内加细粒度插桩**（本机 3.18.120 补丁树实际布局）：`dt_phys` 是否为 0、`phys_to_virt(dt_phys)` 前 4 字节、`early_init_dt_scan()` 进入/返回、失败分支是否命中。需重编译 + 第 12 次刷写。
3. **验证链尾零假设**：构造保留完整 122 份 DTB 的候选（需解决 gzip 变大塞不进固定 `kernel_size` 的旧问题），或构造等长的另一种链布局。

## 5. 未执行 / 边界

未读 `0x42000000` 候选 FDT 头、未加 `setup_machine_fdt()` 内插桩、未做第 12 次实验、未采集 PC/earlycon。阶段结论为 [O]，具体根因仍为 [H]；`rule=fdt_scan` 是分类不是 PC。

## 6. 证据文件

`flash_log/blm_ram_round11.bin`、`flash_log/blm_ram_round11.forensics.json`、`flash_log/20261114_blm_round11_timeline.txt`、`images/boot_los16_blm_control_nonode.img`、`images/boot_los16_blm_control_nonode.abverify.json`、`OFFLINE_AB_AUDIT.md`。
