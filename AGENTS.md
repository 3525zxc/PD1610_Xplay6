# AGENTS.md — 给接手本仓库的 AI 的第一份指令

> Codex / WorkBuddy / 其他 Agent 在本仓库根目录启动时，请先读完本文件再动手。
> 默认用**简体中文**回答；使用者是刷机用户，不会写代码、不会做实验，请用大白话，
> 并且**先说清「现在需要他本人做什么」**，命令由你来跑。
> 本文件是硬规则摘要；完整方法论见 `offline/13_continuation_playbook.md`，
> 资源地图见 `offline/12_ai_handoff_index.md` §9，白话手册见 `docs/BEGINNER_GUIDE_CN.md`。

## 0. 开工前按序读

1. `AGENTS.md`（本文件）
2. `docs/BEGINNER_GUIDE_CN.md` — 使用者的能力与分工边界
3. `offline/12_ai_handoff_index.md` **§9** — 当前准确状态（前面 §1–§8 是 11-14 快照，数字已过期）
4. `offline/13_continuation_playbook.md` — 单变量循环、6 铁律、8 步 SOP、提示词模板
5. `offline/05_experiment_queue.md`、`offline/08_roundA_result.md` — 待办队列与最近一次实机结果
6. 按路线再读：`prebuilt/evidence/_log_append4.md`（路线 A）或 `ROUND10–19*.md` + `flash_log/`（路线 B）

**第一次回复不要动手机、不要编译**：先确认设备状态、说明两条路线区别、给出建议的第一轮、列出哪些动作必须由人做，等人确认。

## 1. 两条路线绝不能混

| | 路线 A：prebuilt ROM | 路线 B：自编译内核 |
|---|---|---|
| 内核 | 原厂 prebuilt 3.18.71，不编译内核 | 自编译 3.18.120 |
| 产物 | LOS16 ROM zip（网盘 `15_`），WiFi 已修 | boot.img 候选（网盘 `01_` 内有工程） |
| 常规写入 | `system` 分区 | **只写 `boot` 分区** |
| 基线/回滚 | `03_/sys13_system.img`（sha `686de5de…`） | `02_/images/boot.img`（sha `929fda99…`） |
| 剩余工作 | 4 项 TODO：相机、libcurl、清诊断代码、sepolicy | 4 门 FAIL：touch_cold、nav_keys、input 5/9、i2c 4/9 |

`03_/sys13_system.img` 与 `02_/images/system.img` 不是同一版本，别互换。
刷任何东西之前，必须明确写出「刷哪个文件 → 进哪个分区 → 回滚副本在哪」。

## 2. 六条铁律（前 26 轮验证过，不许改形式）

1. **单变量**：一轮只改一处（一个 config / 一个 DT 属性 / 一行 flag）。反例：第四版 `a1a0e026…` 同时改了固件更新与中断触发方式，至今无法归因，已作废。
2. **离线门禁优先**：能在 PC 上判定的绝不先刷机。刷任何自编译内核前必须跑 `tools/blm_preflight.py`，要求 `_end < 0x42000000` 且距 FDT ≥ 1 MiB；构建 40/40、预检 17/17 `SAFE_TO_FLASH`。
3. **只写 `boot`**（路线 B）；不碰 system/vendor/userdata，不双清，不格式化 data。
4. **证据先行**：每轮报告必须含输入镜像 sha256、预检结果、dmesg、input 全表、I²C 绑定、getprop、getevent；没有证据的「成功」一律不算。
5. **[O] / [H] 分离**：观察到写 `[O]`，推断写 `[H]` 并标未验证。Round14/15 把 `usb_bam` 假设写成结论，Round16 靠固定槽才推翻。
6. **不虚构**：哈希、编译结果、寄存器值、HTTP 响应、命令输出一律不许编。只报真实跑过的；没跑的写「未执行」并给可复现命令。

## 3. 人机分工（这条最容易被违反）

- **只有人能做**：手动进 fastboot / 9008、插拔 USB、按键、点屏幕、判断「能不能点」、决定继续/暂停/回滚、确认清空路径。
- **AI 能做**：离线分析、源码比对、反汇编、改配置/写补丁、增量编译、出 boot.img、跑预检、发刷机命令、等枚举、抓证据、写报告。
- **fastboot 握手**：必须明确说「**请进 fastboot**」，等人回复确认后才动手刷。
  `adb reboot bootloader` 在自编译内核里**退化成普通重启**（未修好），misc BCB 方案也已排除。
  **绝不因为检测到端口在线就推断设备自动进入或由人刚进入** —— 这是历史明确教训。
- 每轮收尾**回滚原厂并验证** `3.18.71` + `sys.boot_completed=1`，设备停在系统态。

## 4. 面向小白的输出要求

- 先给「你只需要做这三步」，再给技术细节；黑话在 `docs/BEGINNER_GUIDE_CN.md` §5 有对照表，必要时直接引用。
- 命令由你执行并贴真实输出；不要让他手敲编译/刷机命令。
- 每轮结束主动给「三问复核」的答案：输入 sha、证据文件与行号、未执行项。
- 判定触摸是否可用必须以 `getevent` 行数 + IRQ 计数为准；**设备注册成功 ≠ 有事件**。
- 出现 bootloop / 黑屏 / 反复失败时，立刻停手并回滚，不要继续试第四次。
- 用户说「暂停」就停在当前状态，不做任何推断性收尾。

## 5. 环境与路径

- 工程根 `D:/xplay6/evidence/kernel_re/out/stage2/bootloop_monitor/`；WSL 发行版 `PD1610`（Ubuntu 20.04.5）。
- 构建脚本写死 `SRC` / `OUT` / `TC` 三路径与 D 盘工程路径，恢复必须放回原位置，见 `offline/11_wsl_rebuild_guide.md` 路线 B。
- fastboot/adb 在 `/d/xplay6/tools/platform-tools/`；WSL 调用需 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'` + 独立 `.sh`，否则 Git Bash 会吞变量、转换 `/mnt/d/...` 路径。
- 网盘冷备 16 类 / 约 76 GiB，云端目录 `PD1610_Xplay6/`；权威副本是 `01_全量冷备分卷/` 两卷 + `manifest.json` + `SHA256SUMS`（`sha256sum -c` 必须 3/3 OK）。
- 归档分卷 `01_` 生成于 2026-11-15 01:34，早于后续文档增量；恢复时以 GitHub 仓库 / 网盘 `00_必读_恢复说明/` 的最新文档为准。

## 6. 不要重做的调查（省时间）

- bootloop 根因：自编译内核 BSS 清零覆盖 `0x42000000` 的 DTB → FDT 全零；裁剪调试配置后 `_end=0x41e09000` 修复。
- Round14/15 `usb_bam` 是**错误结论**；真卡点是 `qpnp_vibrator_init` 第一次 `spmi_ext_register_readl()`，Round19 `--spmi-stub` 后首次进桌面。
- 触摸不可用根因是 `CONFIG_TOUCHSCREEN_ST_FTS` 未编译进内核，不是 probe deferral；逐层适配见 `fixtures/fts_vivo_dt*.c`。
- `adb reboot bootloader` 未修好：已排除 config 开关、`qcom,pshold`/`pshold-base`、`qcom,msm-imem-restart_reason`、misc BCB、reason 写入顺序。原厂 `do_msm_restart` 1492 B vs 自编译 740 B，独有 BBK 私有逻辑，见 `offline/01_reboot_root_cause.md`。
- 队列原 A 轮（复现 `b6d5debb…` bootloop + 9008 读固定槽）**未做**；实际执行的 A 轮是「刷 #9 抓全量证据 + 回滚」，见 `offline/08_roundA_result.md`。
- `hal` 门必须加 `--hal-ignore init.svc.vivo-fingerprint-sh`（该服务 `disabled`+`oneshot`，`stopped` 是正常态）。
