<a id="zh-cn" name="zh-cn"></a>
# PD1610 / Xplay6 自编译内核与 bootloop 取证

> 语言 / Language：**简体中文（默认）** · [English ↓](#english) · [英文独立文件](README.en.md)

vivo Xplay6（MSM8996 / LineageOS 16）自编译 `3.18.120` 内核的完整取证记录：
从 bootloop 一路定位到能进桌面、触摸可用。手段是自写的 RAM 日志监测模块
（BLM）+ 高通 9008 Firehose `peek` 读取物理内存，把黑盒启动失败变成可复现的证据链。
本仓库同时收录较早的 **prebuilt 路线** 文本成果（原厂内核 + vendor blobs +
借用 PD1619 设备树编译 LOS16 ROM），两条路线一并交接。

> **两种读法，同一份事实**（任选其一；数据、哈希、判据都不删减、不改写）
> - **专业版**：直接看下面的「从这里开始」路线树 → 项目进展与归因 → 名词解释 →
>   轮次总览 → 百度网盘逐文件索引 → 各轮报告与原始证据。术语保持原样。
> - **小白版**：跳到本页靠后的「**小白版：只会刷机也能接着做**」，或整份读
>   `docs/BEGINNER_GUIDE_CN.md`。那里把**同一批文件、同一套流程**用大白话重讲一遍，
>   附可直接复制的 Codex / WorkBuddy 开场白、逐轮剧本和黑话对照表。
> - 两版指向同一批文件、同一套结论，小白版只换说法不简化证据；
>   `AGENTS.md` 是给 AI 读的硬规则，两版共用。


## 从这里开始（先选路线，再翻文件）

本仓库同时放着**两条不同路线**的成果。先判断你要做哪件事，别一上来就翻报告：

```
README.md（你在这里）
│
├─【路线 A】prebuilt 路线续修 —— 想修 ROM 的相机 / WiFi / sepolicy / 打包
│   │  目标：把 LOS16 ROM 做成可发布的日常包
│   │  内核：原厂 prebuilt 3.18.71，不自己编内核
│   │
│   ├─ prebuilt/evidence/_log_append4.md ........ WiFi 修复 4 条因果链、4 项 TODO、3 条误判纠正
│   ├─ prebuilt/release/.../patches/ ........... sys13 最终版 7 个源码改动（改 bug 前必须先 diff）
│   ├─ prebuilt/refs/PD1619_PORTING_NOTES.md ... 1042 行移植笔记（设备树怎么借来的）
│   ├─ offline/14_prebuilt_upload_checklist.md . 上传必要清单 + 续修差异（刷 system 不刷 boot）
│   ├─ 网盘 03_prebuilt_续修基线/sys13_system.img  WiFi 修通的基线（sha 686de5de…）
│   ├─ 网盘 15_LOS16_ROM刷机包/*.zip .......... 可刷 ROM（935 MB，sha 97c3137e…）
│   └─ 网盘 02_原厂回滚与发布包/images/boot.img  回滚基线（sha 929fda99…）
│
└─【路线 B】自编译 3.18.120 内核继续修 —— 想达到完整第 3 档
    │  目标：补完 4 个 FAIL 门（触摸冷启动 / 导航键 / input / I2C）
    │  现状：设备已回滚原厂，刷候选前须按约定手动进 fastboot
    │
    ├─ offline/12_ai_handoff_index.md .......... 【先读】资源地图，整份贴给 AI 即可恢复上下文
    ├─ offline/13_continuation_playbook.md ..... 【再读】单变量 6 铁律、人机分工、8 步 SOP、7 层定位法
    ├─ offline/05_experiment_queue.md .......... 实验队列 A–D：每轮 claim / 判据 / 采集清单
    ├─ offline/08_roundA_result.md ............. A 轮实测：3/3 冷启动、50/50、已回滚
    ├─ offline/07_handoff_baseline.md .......... B0′ 可交接基准与发布边界
    ├─ ROUND10–19*.md + flash_log/round*.txt ... 前 26 轮实机结论与原始日志
    ├─ fixtures/ + tools/ ..................... 驱动适配源码、BLM、预检 / 覆盖率 / 归档脚本
    └─ 网盘 01_全量冷备分卷/ ................. 二进制与完整工程（恢复主副本）

两条路线共用的钥匙
├─ 网盘 00_必读_恢复说明/ .................... RESTORE / SHA256SUMS / 清单 / 索引 / 操作卡
├─ docs/BEGINNER_GUIDE_CN.md .............. 只会刷机的人先看（§3 开场白可直接复制）
└─ offline/12_ai_handoff_index.md §9 ......... 当前准确状态（16 类 / 76 GiB / 两条路线产物）
```

**一句话分清**：`prebuilt/` 与网盘 `02`/`03`/`15` 是「原厂内核 + 现成 ROM」；
`ROUND*`、`flash_log/`、`fixtures/`、`offline/05–08` 是「自己编内核 + 取证」。
两条线的镜像不能混用，`03_/sys13_system.img` 与 `02_/images/system.img` 也不是同一个文件。


## 仓库内容

| 目录 | 内容 |
|---|---|
| `ROUND*.md`、`offline/` | Round10–19 报告、6 份离线分析、B0′ 交接基准与 A 轮结果 |
| `flash_log/` | 每轮实机 dmesg / input / I2C 绑定 / 冷启动台账 / 覆盖率 JSON |
| `fixtures/`、`tools/`、`tests/` | 驱动源码适配副本、BLM 与归档/度量脚本、门禁自测 |
| `prebuilt/` | prebuilt 路线 829 份文本：1042 行移植笔记、WiFi 修复全程、sys13 最终版 `patches/` |
| `prebuilt_c/` | 第一阶段（C 盘 `寒霜刷机`）验签 / 解锁 / 原厂 DTS / ROM 设备树 / `20261112` 日志包，约 80 份文本 |
| `docs/` | 零基础接续手册中英双版：人机分工、AI 开场白、逐轮剧本、黑话对照、保命清单 |
| `AGENTS.md` | 给接手 AI 的硬规则（Codex 在仓库根启动即自动读取） |

## 项目进展与更新记录

> 本节是主页摘要。逐轮证据见 `ROUND*.md`、`offline/`、`flash_log/`；
> 资源地图见 `offline/12_ai_handoff_index.md` §9，工作手册见 `offline/13_continuation_playbook.md`。

### 三条工作线（别混成一条）

| 线 | 时间 | 原始目录 | 产物 |
|---|---|---|---|
| 第一阶段：验签 / 解锁 | 11-08 → 11-12 | `C:/Users/Tse/WorkBuddy/寒霜刷机` | aboot 验签与启动状态机、boot hash 数据流、跨机型对照、原厂 DTS 反编译、临时 root / 解锁工具链；文本层 → `prebuilt_c/` |
| prebuilt 路线 | 11-10 → 11-12 | `D:/16/PD1610_81` | 原厂 prebuilt 内核 + vendor blobs + 借 PD1619 设备树编译 LOS16；WiFi 修通；可刷 ROM zip |
| 自编译内核取证 | 11-14 → 11-15 | 本仓库 | `3.18.120-perf` + BLM / 9008 观察通道、bootloop 根因、触摸驱动源码重建、完成度 50/50 |

vivo 从未发布 PD1610/PD1619 的 3.18 内核源码，所以 prebuilt 路线**不编译内核**；
自编译路线用的是上游 LineageOS msm8996 3.18 开源树，两条线的镜像不能混用。

### 时间线

| 日期 | 阶段 | 关键结果 |
|---|---|---|
| 11-08 → 11-12 | 第一阶段研究 | 验签 / 解锁 / 设备树取证，30+ 份报告；`20261112.zip` 整理包 |
| 11-10 → 11-12 | prebuilt 路线 | LOS16 ROM 编译，WiFi 4 条因果链修复（sys13 `system.img` sha `686de5de…`），产出 `PD1610_LOS16_20261112_UNOFFICIAL.zip`（935,087,013 B） |
| 11-14 上午 | Round10–13 | BLM / 9008 `peek` 观察通道；查到 FDT 全零根因 = 自编译内核 BSS 清零区覆盖 `0x42000000` 的 DTB；裁剪调试配置后恢复 `d00dfeed` |
| 11-14 下午 | Round14–19 | 固定槽推翻 `usb_bam` 误判 → 定位 `qpnp_vibrator_init` 第一次 SPMI 读 → `FDT_NOP` 绕过 → SPMI stub + 恢复节点，`#5` 首次 `sys.boot_completed=1` |
| 11-14 傍晚 | Round20–26 | 触摸从「无驱动」推进到「事件链打通」：`CONFIG_TOUCHSCREEN_ST_FTS`、DT 属性、pinctrl、`IRQF_ONESHOT`、`vdd_ana`/`vcc_i2c`；导航键绑定成功但 probe 未完；最后一版报 bootloop 已回滚 |
| 11-14 夜 | 离线 6 项 + A 轮 | 8 门完成度定义、332 固件清单、原厂/自编译 `do_msm_restart` 反汇编差分；A 轮 3/3 冷启动、唤醒后 1266 行触摸事件，`UNVERIFIED` 全消 → 严格 50/50 |
| 11-15 | 归档与交接 | 双版 README、16 类 / 76 GiB 网盘冷备、WSL 最小重建集、第一阶段记录与 ROM 包补全、AI 索引 §9 |

### 归因演进（最容易走错的地方）

- **Round14/15 判 `usb_bam` 是错的**，Round16 固定槽证据推翻；真正卡点是
  `qpnp_vibrator_init` → 第一次 `spmi_ext_register_readl()` 未返回。
- Round18 用 DTB `FDT_NOP` 绕过 vibrator 只进到用户态（HAL 缺项卡二屏）；
  Round19 换成 SPMI stub 并恢复节点才完整进桌面。
- 触摸不是 probe 延迟，是**驱动根本没编进内核**（`System.map` 里无 `fts_driver_init`）。
- `adb reboot bootloader` 失效不是缺配置开关：原厂 `do_msm_restart` 1492 B vs
  自编译 740 B，原厂独有 `set_dload_mode_bbk` / `set_aee_system_restarting` /
  `deassert_ps_hold` 等 BBK 私有调用。[H1] aboot 读私有标志，未实机验证。

### 完成度口径演进

`20/88`（6 项 UNVERIFIED）→ 静态 `40/63` → A 轮**严格 `50/50`**、唤醒后对照 `65/65`（仅说明触摸能通，不算 `touch_cold` 通过）。正式采用 **50**。
区间从 68 点收窄到 0，靠的是补齐证据，不是补写代码 —— 早期 68% 是「没留证据」，不是「68% 代码没写」。
`hal` 门必须带 `--hal-ignore init.svc.vivo-fingerprint-sh`（该服务 `disabled`+`oneshot`，`stopped` 是正常态）。

### 2026-11-15 文档与资源更新

- README 改为**简体中文首选** + 页内 `English ↓` 切换 + 独立 `README.en.md`；新增百度网盘冷备索引。
- 补 `prebuilt_c/`（97 份第一阶段研究文本），网盘新增 `14_寒霜刷机_C盘工作目录/`（84 文件，含会话日志，仅私有）与 `15_LOS16_ROM刷机包/`（ROM zip + `SHA256SUMS`）。
- **更正过期结论**：「无 ROM zip / 未解 TODO 5 项」→「ROM 已产出 / 4 项 TODO」。
- `offline/12_ai_handoff_index.md` 新增 §9 当前准确状态，13/14 号文档同步；网盘扩为 16 类 / 76 GiB。
- 归档 `01` 两卷保持 01:34 版本（避免改动已上传的 973 MiB 分卷），其内的索引是旧版，以本仓库 / 网盘 `00` 目录为准。

### 当前状态与剩余工作

- 设备：原厂 `3.18.71-perf-g8a8c60dd` / LOS16 / `sys.boot_completed=1` / 不在 fastboot。
- 仍 FAIL 四门：`touch_cold`、`nav_keys`、`input_parity` 5/9、`i2c_parity` 4/9。
- 最大长尾：`goodixfp` 指纹（自编译内核里相关符号 0 个，需反汇编重建，5–15 工作日且不保证成功）。
- 这是**可交接快照 B0′，不是完成的第 3 档移植**。接续实验从 `offline/05_experiment_queue.md` 的 B 轮开始，先按 `13_continuation_playbook.md` 的单变量循环走。

## 名词解释：A 轮 / 实验队列 / 完成度（小白先看这里）

这些词在仓库里反复出现，先讲清楚它们指什么、别去哪找。

**「实验队列」= `offline/05_experiment_queue.md`**，一张待办实验表。
自编译内核还有 4 个验收门没过，所以把「接下来要验证的假设」排成 A–D 四轮，
每轮写死五件事：claim（假设）→ 前置条件 → 量化判据 → 影响哪个 gate → 失败分支；
每轮结束必须跑一次覆盖率工具，否则不算完成。

```
实验队列（A–D，claim-driven）
│
├─ A 复现 b6d5debb… 的 bootloop，进 9008 读 BLM 固定槽
│     判据：last_stage=12 KERNEL_INIT 且最后 initcall 落在 cyttsp_button_init 附近 ⇒ 真卡死
│     注意：这是队列里「原 A 轮」，实际没做；已执行的 A 轮是下面的证据收窄
├─ B 补 irqflags |= IRQF_ONESHOT → 3-0028 probe 完成、虚拟键三键可用、冷启动 30s 有触摸
│     实际入口：先拆单变量验 touch_cold（跳过自动固件更新 / 中断触发方式）
├─ C 恢复两个 tasha jack input 设备（对比两边 ASoC 注册日志）
├─ D 验证 adb reboot bootloader 的 BBK 私有写入标志（源自 01_reboot_root_cause.md 的 H1）
│
├─ 长尾（不进队列）：goodixfp 指纹 —— 自编译内核相关符号 0 个，需反汇编重建，
│                     估计 5–15 工作日且不保证成功，建议单独立里程碑
└─ 收尾判据：3 次冷启动 / input 9/9 / I2C ≥8/9 / 冷启动 30s 触摸 / 证据齐全 / 17-17 + 回滚
```

**「A 轮结果」= `offline/08_roundA_result.md`**，注意有**两个 A 轮**：
- 队列定义的**原 A 轮**：重刷 `b6d5debb…` 复现 bootloop、进 9008 读固定槽 —— **未做**，仍需单独一轮。
- **实际执行的 A 轮**（11-14 21:45–22:04）：用户说「先走完 1 小时的 A」，改成
  **不修任何东西**，只刷已知可用的 `#9` 基线 → 抓全量证据 → 回滚原厂。

```
实际 A 轮做了什么
│
├─ 刷入 5f164490…（#9 可用基线）→ 3.18.120-perf #9 进桌面
├─ blm_round_capture.py 抓 12 类静态快照（含 199 KB 完整 dmesg、带 sha256 manifest）
├─ blm_coldboot_verify.py → 3/3 冷启动 PASS（36.8 / 58.1 / 58.2 s）
├─ 触摸：冷启动 35 s 窗口 0 事件；锁屏唤醒后 25 s 窗口 1266 行、IRQ 87→474
├─ 导航键：vivo_virtual_key 计数 0、按键窗口 0 行 ⇒ FAIL
├─ 完成度 20/88 → 静态 40/63 → 严格 50/50（UNVERIFIED 全消）；唤醒后 65/65 仅作对照
├─ 修工具口径 bug（hal 门把 oneshot 服务误判 FAIL）+ 新增两个采集工具
└─ 回滚原厂 929fda99… 并验证：3.18.71 / BOOT=1 / 9 个 input 设备全在
```

**「完成度」= `tools/blm_tier3_coverage.py` 的 8 门加权评分**：
boot(20) / touch_cold(15) / nav_keys(8) / input_parity(12) / i2c_parity(15) /
hal(10) / firmware_inventory(5) / reproducible(15)。
分母取**原厂实机枚举到的设备清单**，每项只认三证（设备节点 + 驱动绑定 + 真实事件），
没留证据记 `UNVERIFIED` 而不是算通过。所以早期 `20/88` 的 68 点区间
是「证据没留齐」，不是「68% 代码没写」；A 轮靠补齐快照把区间收窄到 0。

## 小白版：只会刷机也能接着做

> 这一节是**与上文并行的小白版**：上面那份专业版原样保留，这里把同一件事
> 用大白话再说一遍。你不需要会写代码、不需要懂内核，前 26 轮就是
> 「人管手机 + AI 管代码和证据」这么做出来的：

**专业版 ↔ 小白版对照**（同一件事的两种说法，指同一批文件）

| 专业版（上文） | 小白版去哪看 |
|---|---|
| 从这里开始：两条路线树 | 本节开头 + `docs/BEGINNER_GUIDE_CN.md` §0.2 |
| 名词解释：A 轮 / 实验队列 / 完成度 | 本页下面「三步开局」+ 手册 §5 黑话对照表 |
| 轮次总览 ROUND1–9 / 10–26 | 手册 §0.3 真实状态 + §10 阅读顺序 |
| 已验证状态 50/50、4 门 FAIL | 手册 §0.3 / §9 常见问题 |
| 百度网盘冷备索引（逐文件树） | 手册 §2「只下哪几类」+ §5 |
| `offline/13` 工作手册 8 步 SOP | 手册 §4 逐轮剧本表（AI 说 / 你做 / 你回） |
| `offline/05` 实验队列 A–D | 手册 §8 零风险第一轮怎么提要求 |
| `fixtures/` `tools/` 源码与脚本 | 手册 §1「其余全交给 AI」 |
| `AGENTS.md` 给 AI 的硬规则 | 手册 §3 开场白会自动让它读到 |


```
你（会刷机就够）                    AI（Codex / WorkBuddy）
├─ 把仓库和网盘文件放到电脑上       ├─ 读日志、查报错、比对源码、改代码
├─ 按提示手动进 fastboot ──────────> ├─ 增量编译、生成 boot.img、跑预检
├─ 点屏幕 / 按导航键 ─────────────> ├─ 刷入、抓全量证据、判定 PASS / FAIL
├─ 如实说「能点 / 不能点」          └─ 收尾回滚原厂并验证
└─ 决定继续 / 暂停 / 回滚
```

**三步开局（建议第一轮零风险）**

1. 从网盘下 `00` `01` `02` `04` 四类，让 AI 跑 `sha256sum -c SHA256SUMS`，**必须 3/3 OK**。
2. 用 Codex 或 WorkBuddy 打开仓库根目录（`AGENTS.md` 会被自动读取），把
   `docs/BEGINNER_GUIDE_CN.md` §3 的开场白**整段复制粘贴**进去。
3. 第一轮明确要求「**不编译、不刷机、不动分区**」，只让 AI 核对设备状态、抓一份基线日志、
   出一份白话「当前状态报告」。流程跑通后再按 `offline/05` 队列进实验轮。

| 你现在想弄明白的 | 直接翻这里 |
|---|---|
| 第一次跟 AI 说什么（可直接复制的整段话） | `docs/BEGINNER_GUIDE_CN.md` §3 |
| 一轮实验里 AI 说什么、我做什么、我回什么 | 同上 §4 剧本表 |
| fastboot / dmesg / 预检 / 单变量这些黑话 | 同上 §5 对照表 |
| 什么时候必须停、怎么回滚、哪 8 件事绝不能做 | 同上 §6 |
| 怎么判断 AI 有没有在瞎编 | 同上 §7 |
| 零风险的第一轮怎么提要求 | 同上 §8 |
| AI 自己要守的硬规则 | `AGENTS.md`（仓库根，Codex 启动即读） |
| 深入：一轮实验的完整方法论 | `offline/13_continuation_playbook.md` |

> 英文版 `docs/BEGINNER_GUIDE_EN.md`。两条路线的镜像不能混用；
> **`03_/sys13_system.img`（修 WiFi 的系统）≠ `02_/images/system.img`（原厂发布包）**。


## 轮次总览：ROUND1–9 与 ROUND10–26（三套编号别混）

仓库里出现三套「ROUND」，它们**不是同一串实验**，编号体系各自独立：

```
项目轮次全图
│
├─ ① 验签 / 解锁状态机（11-08 → 11-12，C 盘「寒霜刷机」+ D 盘 evidence）
│   ├─ ROUND3_LOOP_LIFECYCLE.txt ............... aboot 验签循环生命周期
│   ├─ ROUND4_FLAG_BEQ_DATAFLOW.txt ............ flag 分支 / BEQ 数据流
│   ├─ ROUND5_RETVAL_CLASSIFICATION_AND_STATE_PATH.txt  返回值分类与状态路径
│   ├─ aboot_verification_analysis.md .......... 验签反汇编（现收在 prebuilt_c/）
│   ├─ boot_state_machine_analysis.md .......... 启动状态机
│   ├─ PD1610_原厂设备树_81916.dts ............. 原厂设备树反编译
│   └─ xplay6_unlock/ .......................... 9008 解锁 / 读回工具链
│
├─ ② 离线逆向 + 多模型评审 ROUND1–9（11-12 → 11-13，kernel_re/out/）
│   │   这里的 ROUND 是「第几轮送出去给 GPT / Claude 评审的简报」，不是刷机次数
│   ├─ round3/ ....... aboot 解压轨迹、ARM64 Image 内存审计、boot 地址区间重叠、
│   │                 config diff 归因、cpu_do_switch_mm 审计、DTB selector 反汇编
│   ├─ round4/ ....... aboot handoff、早期 MMU 证据、FDT 链解析、BOOT_ONLY 可行性、
│   │                 Unicorn 解压重放、memory_lifecycle_and_observability.md
│   ├─ ROUND3_REVIEW_LANDING.md、ROUND4..9_FOLLOWUP_FOR_GPT.md ... 逐轮送审简报
│   ├─ BRIEF_*_BATTLE.md、multimodel_capture/（18 份）... 多模型对抗评审与回复存档
│   ├─ STAGE1..30*.md .... 反编译阶段编号（又一套，别与 ROUND 混淆）
│   ├─ MASTER_FINDINGS.md / MASTER_HANDOFF_20261113.md / COMPILABLE_SOURCE_PROGRESS.md
│   └─ h6/ROUND5_BOOT_ONLY_DELIVERY.md、ROUND5_FLASH_RESULT.md ... boot-only 实机验证准备
│
└─ ③ BLM 实机取证 ROUND10–26（11-14，本工程 stage2/bootloop_monitor/）
    ├─ ROUND10–13 ... BLM / 9008 通道、FDT 全零根因、裁剪、推进到 KERNEL_INIT
    ├─ ROUND14–17 ... usb_bam 误判 → 固定槽推翻 → qpnp_vibrator_init → 第一次 SPMI 读
    ├─ ROUND18–19 ... FDT_NOP 绕过进用户态 → SPMI stub + 恢复节点 → sys.boot_completed=1
    ├─ ROUND20–26 ... 触摸驱动源码重建、导航键、reboot 通道排查、bootloop 回滚
    └─ A 轮 ......... 不是 ROUND，是「实验队列」的第 A 轮（证据收窄）
```

**为什么第一份报告就叫 ROUND10**：它接着 ② 的评审轮次编号往后排，不是「第 10 次刷机」。
ROUND1–9 的成果不在本仓库的 `ROUND*.md` 里，而在
`prebuilt_c/`（第一阶段文本）、网盘 `11_逆向证据_全量分卷/`（`kernel_re` 全量 tar）、
`14_寒霜刷机_C盘工作目录/`（C 盘原貌）与 `prebuilt/evidence/`（验签状态机 txt）。

## 已验证状态（2026-11-14）

- 第 3 档完成度 **严格口径 50/50，`UNVERIFIED = 0`**
  （`flash_log/tier3_coverage_roundA_final_strict.json`）；起点为 `20/88`。
- 仍 FAIL 四门：`touch_cold`、`nav_keys`、`input_parity` 5/9、`i2c_parity` 4/9。
- A 轮：**3/3 连续冷启动**通过（36.8 / 58.1 / 58.2 s）；锁屏唤醒后 25 秒窗口抓到
  **1266 行触摸事件**，IRQ 87→474。冷启动 30 秒窗口 0 事件。
- 设备已回滚原厂 `3.18.71-perf-g8a8c60dd`，`sys.boot_completed=1`，不在 fastboot。

## 已知缺口与诚实限制

- 触摸需一次锁屏 / 唤醒才生效（怀疑与 `st_fts.bin` 缺失、自动固件更新失败有关，未验证）；
  导航键无 `vivo_virtual_key` 输入设备。
- 自编译内核里 `adb reboot bootloader` 仍退化成普通重启，misc BCB 通道已排除。
- 最后一版导航键候选 `b6d5debb…` 报 bootloop 并已回滚，**卡点未隔离**。
- **归因演进必须注意**：Round14/15 判 `usb_bam`，被 Round16 固定槽证据推翻；
  真正卡点是 `qpnp_vibrator_init` → 第一次 SPMI 读。别从旧结论接着做。
- prebuilt 路线**已产出可刷 ROM** `PD1610_LOS16_20261112_UNOFFICIAL.zip`
  （935,087,013 B，sha256 `97c3137e…`，在百度网盘 `15_LOS16_ROM刷机包/`）；
  仍留 4 项 TODO（相机 0 设备、缺 `libcurl.so`、发布前清诊断代码须重编、
  sepolicy/configstore），见 `prebuilt/evidence/_log_append4.md`。
  第一阶段验签 / 解锁 / 设备树研究见 `prebuilt_c/`。

## 本仓库不包含的内容

19 个 `boot.img`、DTB 二进制、332 个固件 blob、RAM dump、原厂 `vmlinux`、
WSL 重建集与 sys13 `system.img` 都在**百度网盘冷备分卷**（约 973 MiB / 2 卷，zstd tar）。
本仓库是纯文本文档层，恢复步骤见 `offline/12_ai_handoff_index.md` §2 与
`archive/RESTORE.md`（后者在分卷内）。

## 百度网盘冷备索引（2026-11-15）

二进制、原始工程与可刷镜像不上 GitHub，放在百度网盘私有目录
**`PD1610_Xplay6/`**（约 76 GiB / 约 7160 文件，16 个分类）。

- 分享链接：<https://pan.baidu.com/s/5OL1VH3h9Pn_uOQllg29MSQ>
  （若页面要求提取码，请向维护者索取；分享链接可能随设置失效）
- 目录结构与逐文件清单：云端 `00_必读_恢复说明/上传清单.md` 与 `UPLOAD_CHECKLIST.csv`
- 恢复入口：云端 `00_必读_恢复说明/RESTORE.md`、`12_ai_handoff_index.md`

| 分类 | 内容 |
|---|---|
| `00`–`06` 必传 6.7 GiB | 恢复说明与校验文件、`01` 两卷冷备（973 MiB，zstd tar，权威副本）、原厂发布包、sys13 基线、9008 工具、固件、WSL 最小重建集 |
| `07`–`09` 可选 | GitHub 文本层冗余、48 分区 dump、官方 OTA |
| `10` / `11` 全量分卷 | `D:\16\PD1610_81` 40 GiB（22 卷）、`kernel_re` 11 GiB（6 卷），1.9 GiB tar 分卷 |
| `12` / `13` 原貌 | 自编译工程原始全量、其它资料与工具 |
| `14` / `15` 追加 | C 盘 `寒霜刷机` 工作目录全量（4.9 MiB）、LOS16 可刷 ROM zip（935 MB）与校验 |

### 分类内文件逐个说明（树状索引）

> 下面是「点开每个文件夹会看到什么、每个文件干什么」。完整 7260 行的逐文件清单在
> `00_必读_恢复说明/UPLOAD_CHECKLIST.csv`（含本地源路径、字节数、分类、必传标记）。

```
PD1610_Xplay6/                                   ← 云端根目录（16 类 / 76 GiB）
│
├─ 00_必读_恢复说明/          【先看这里】17 个文件，恢复与核对的入口
│   ├─ RESTORE.md .................. 分卷重组 → zstd 解压 → tar 提取的完整命令
│   ├─ SHA256SUMS .................. 两卷 + manifest.json 的 3 行哈希，下载后先跑 sha256sum -c
│   ├─ manifest.json ............... 2121 个文件的路径 / 大小 / sha256，恢复后逐个核对
│   ├─ 上传清单.md ................. 16 类的文件数 / 体积 / 用途汇总表
│   ├─ UPLOAD_CHECKLIST.csv ........ 逐文件清单（本地源、字节数、必传标记）
│   ├─ 12_ai_handoff_index.md ...... 给接手 AI 的资源地图，§9 是当前准确状态
│   ├─ 13_continuation_playbook.md . 单变量 6 铁律 / 8 步 SOP / 7 层定位法 / 提示词模板
│   ├─ 14_prebuilt_upload_checklist.md  prebuilt 的 4 项 TODO 与续修必要文件
│   ├─ 11_wsl_rebuild_guide.md ...... WSL 环境最小重建 SOP 与清理清单
│   ├─ 07_handoff_baseline.md ....... B0′ 可交接基准 / 发布边界
│   ├─ 百度网盘索引_草稿.md ........ 云端目录 + 分享链接 + 16 类 + 校验（已定稿）
│   ├─ 增量补传清单_20261115.md ..... 本次新增 / 修改文件，核对云端是否同步完
│   ├─ 百度网盘上传操作卡.md、逐步上传操作卡_20261115.md ... 客户端点法与两条线上传步骤
│   ├─ PD1610_DESKTOP_UPLOAD.md ..... GitHub Desktop 推送步骤
│   └─ baidu_upload_prep.py / baidu_upload_expand.py ... 生成本地上传树与分卷的脚本
│
├─ 01_全量冷备分卷/          【恢复主副本】2 个文件，973 MiB
│   ├─ blm_full.tar.zst.part01 ...... 900 MiB，4.06 GiB 工程压缩后的第一段
│   └─ blm_full.tar.zst.part02 ...... 72.5 MiB，第二段；缺一不可、不能改名
│
├─ 02_原厂回滚与发布包/      【路线 A】42 文件 / 1.9 GiB
│   ├─ images/boot.img .............. 回滚基线 sha 929fda99…（58,483,968 B）
│   ├─ images/recovery.img .......... 原厂 recovery
│   ├─ images/system.img ............ 发布包版本（1.85 GiB），≠ 03_ 的 sys13
│   ├─ patches/ ..................... sys13 最终版 7 个源码改动（device/vendor/system/…）
│   │   ├─ compat_libs/ ............. 兼容库
│   │   └─ device/ 与 vendor/ ....... 设备树与 vendor 改动（改 bug 前先 diff）
│   ├─ tools/ ....................... adb / fastboot（Windows + Linux）与依赖 DLL
│   ├─ flash_all.bat / flash_all.sh . 一键刷机脚本
│   ├─ flash_first_time.bat、verify.bat ... 首次刷机与校验
│   └─ sha256sums.txt ............... 发布包内各镜像哈希
│
├─ 03_prebuilt_续修基线/     【路线 A 修 bug 用】26 文件 / 2.3 GiB
│   ├─ sys13_system.img ............. WiFi 已修通的已知良好基线（sha 686de5de…）
│   ├─ prebuilt_kernel .............. 原厂 prebuilt 内核（54 MiB，prebuilt 路线不编内核）
│   ├─ vendor_blobs/_vendor.tar ..... 设备端 vendor 权威归档（471 MiB / 1824 文件）
│   ├─ vendor_blobs/modules/ ........ 13 个 .ko（含 wlan.ko）
│   └─ compat_libs/lib、lib64/ ...... 相机 / HAL 依赖排查用兼容库
│
├─ 04_9008与刷机工具/        【救砖通道】102 文件 / 32 MiB
│   ├─ qfil/ ........................ QFIL / QSaharaServer / fh_loader + 4 个 firehose .elf
│   ├─ platform-tools/ .............. adb.exe / fastboot.exe
│   └─ firehose_scripts/ ............ 本项目 9008 peek 脚本与 programmer
│
├─ 05_固件blob/              【固件依赖】4 文件 / 101 MiB
│   ├─ 03_firmware_inventory.csv .... 332 个固件的路径 / 大小 / 子系统分类
│   ├─ firmware_partial_76.zip ...... 已从设备拉到的 76 个散装 blob（约 5.5 MiB）
│   ├─ firmware_partition_FAT16.img . /firmware 分区 FAT16 原始镜像（含其余 256 个文件）
│   └─ 固件说明.md .................. 缺哪些、怎么用 mtools/7-Zip 提取、st_fts.bin 缺失说明
│
├─ 06_WSL重建集/             【重建编译环境】40 文件 / 1.6 GiB
│   ├─ src/kernel-src.tar ........... 打过补丁的内核源码树（790 MiB）
│   ├─ config/kout-shrink.tar ....... 当前构建输出（755 MiB）
│   ├─ config/.config、System.map ... 配置与符号表
│   ├─ toolchain/aarch64-linux-android-4.9.tar ... 交叉工具链（101 MiB）
│   ├─ scripts/ ..................... 打补丁 / 编译 / 出镜像 / 预检脚本
│   ├─ env/environment.txt .......... apt 包全表、wsl.conf、硬编码路径说明
│   └─ SHA256SUMS ................... 本目录校验
│
├─ 07_GitHub发布树_冗余/     GitHub 公开仓库同一份文本层（离线冗余，1100+ 文件）
├─ 08_分区dump_可选/         48 个分区原始 dump（8.4 GiB，含 aboot/modem/devinfo）
├─ 09_原厂OTA_可选/          vivo 官方 OTA zip 与签名固件（4.1 GiB，含 NON-HLOS.bin）
│
├─ 10_prebuilt工程_全量分卷/  D:/16/PD1610_81 原貌（22 卷 / 40 GiB）
│   ├─ PD1610_81_full.tar.part001..022 ... 1.9 GiB 一卷，cat 合并后 tar -xf
│   ├─ SHA256SUMS / RESTORE.txt ..... 校验与恢复命令
│   └─ _PACK_DONE ................... 分卷全部生成完毕的标记
├─ 11_逆向证据_全量分卷/      kernel_re 原貌（6 卷 / 11 GiB，含上面 ROUND1–9 全部证据）
│
├─ 12_自编译工程原始全量/    bootloop_monitor 工程根原貌（4324 文件 / 5.1 GiB）
├─ 13_其它资料与工具/        D:/16 其它资料、dist、github 本地仓库、tools、根目录文档
│
├─ 14_寒霜刷机_C盘工作目录/  【第一阶段原貌】84 文件 / 4.9 MiB，仅私有
│   ├─ aboot_*.md、boot_*.md ........ 验签 / 启动状态机 / hash 数据流分析
│   ├─ PD1610_原厂设备树_81916.dts/.dtb、1151_6.0.1.dts ... 原厂设备树
│   ├─ pd1610_rom/ .................. ROM 设备树源码（BoardConfig.mk / device.mk / build.sh /
│   │                                  proprietary-files.txt / extract-files.sh / *.mk）
│   ├─ xplay6_unlock/ ............... 解锁 / 读回 Python 工具 + 4 个 firehose programmer
│   ├─ PD1610_H1_测试包/ ............ H1 操作手册、readback XML、chain manifest
│   ├─ 20261112.zip ................. 28 份整理日志（文本副本已进 GitHub prebuilt_c/）
│   ├─ GPT回复_*.md、小白研究vivo.md . 多模型评审与科普
│   ├─ .workbuddy/memory/ ........... 会话日志（**仅私有，不进 GitHub**）
│   └─ README_目录说明.md ........... 本目录各文件作用
│
└─ 15_LOS16_ROM刷机包/       【可刷 ROM】3 文件 / 892 MiB
    ├─ PD1610_LOS16_20261112_UNOFFICIAL.zip ... 935,087,013 B，sha 97c3137e…
    ├─ SHA256SUMS .................... sha256sum -c 校验
    └─ README_刷机与校验.md ......... 来源、prebuilt 路线说明、4 项 TODO、回滚基线
```

只读了文本层、想直接找某个文件：用 `00_必读_恢复说明/UPLOAD_CHECKLIST.csv` 按文件名搜索。

**校验**：把 `00` 的 `SHA256SUMS`、`manifest.json` 与 `01` 两个分卷下载到同一目录，
跑 `sha256sum -c SHA256SUMS`（必须 3/3 OK），再按 `RESTORE.md` 重组解压。
`10_`/`11_` 各自目录内也有 `SHA256SUMS` 与 `RESTORE.txt`（`cat *.part* > xxx.tar`）。

> ⚠️ `10_prebuilt工程_全量分卷/` 内含原厂 OTA 解包出的 `imei.der` / `donuts_key`
> 设备密钥材料，**该子目录不应公开分享**。若分享链接覆盖整个 `PD1610_Xplay6/`，
> 请改为只分享 `00`–`09`，或在云端把 `10_` 移出分享范围。
> 另：`03_prebuilt_续修基线/sys13_system.img` 是已修通 WiFi 的已知良好基线，
> 与 `02_原厂回滚与发布包/images/system.img` 不是同一版本，别混用。

## 许可证

自研工具 MIT；文档 CC-BY-4.0；内核补丁沿用上游 LineageOS msm8996 3.18 的
GPL-2.0 并保留版权头。

> 这是可交接快照（B0′），**不是**已完成的第 3 档移植。

---

## English

> [↑ 返回中文](#zh-cn) · [README.en.md](README.en.md) · **English (default in this file: Chinese above)**

vivo Xplay6 (MSM8996, LineageOS 16) self-compiled `3.18.120` kernel:
from bootloop to a bootable desktop with working touch, using a custom
RAM-log monitor (BLM) and Qualcomm 9008 Firehose `peek` to observe failures.
The same repository also ships the text results of the older **prebuilt**
route (stock kernel + vendor blobs + borrowed PD1619 device tree -> LOS16 ROM).

> **Two reading tracks, the same facts.** Pick either one; no data, hash or
> criterion is simplified or removed.
> - **Technical track**: the route tree below, changelog, glossary, round
>   lineage, per-file netdisk index, reports and raw evidence - all unchanged.
> - **Plain-language track**: jump to "**Plain-language track**" further down
>   this page, or read `docs/BEGINNER_GUIDE_EN.md` in full. It retells the same
>   files and the same workflow in everyday language, with copy-paste AI prompts.
> - Both tracks point at the same files and conclusions. `AGENTS.md` holds the
>   hard rules for the AI and is shared by both.

**Start here - pick your route first.** This repository holds **two different
lines of work**; decide which one you are continuing before opening any report:

```
Route A - continue the PREBUILT ROM (fix camera / WiFi / sepolicy / packaging)
  prebuilt/evidence/_log_append4.md ...... WiFi fix chain, 4 open TODOs, corrected misjudgements
  prebuilt/release/.../patches/ ......... final sys13 source changes (diff before editing)
  prebuilt/refs/PD1619_PORTING_NOTES.md . 1042-line porting note
  offline/14_prebuilt_upload_checklist.md  upload checklist and continuation notes
  netdisk 03_/sys13_system.img .......... known-good WiFi-fixed baseline
  netdisk 15_/*.zip ..................... flashable LOS16 ROM
  netdisk 02_/images/boot.img ........... rollback baseline

Route B - continue the SELF-COMPILED 3.18.120 kernel (finish Tier-3 gates)
  offline/12_ai_handoff_index.md ........ resource map; paste as-is to an AI
  offline/13_continuation_playbook.md ... single-variable loop, 8-step SOP
  offline/05_experiment_queue.md ........ experiment queue A-D (claims / criteria)
  offline/08_roundA_result.md ........... A-round evidence result
  ROUND10-19*.md + flash_log/ .......... per-round evidence and raw logs
  fixtures/ + tools/ .................... adapted drivers, BLM, preflight/coverage scripts
  netdisk 01_/ .......................... authoritative cold-storage volumes

Shared entry: netdisk 00_必读_恢复说明/ (RESTORE, SHA256SUMS, checklists, indexes).
Beginner on-ramp: docs/BEGINNER_GUIDE_EN.md (plain-language guide with copy-paste AI prompts).
`prebuilt/` and netdisk 02/03/15 use the stock prebuilt kernel; `ROUND*` and
`flash_log/` are the self-compiled line. Their images are not interchangeable.
```


### Project status & changelog

> Summary for the front page. Per-round evidence: `ROUND*.md`, `offline/`,
> `flash_log/`. Resource map: `offline/12_ai_handoff_index.md` section 9;
> working manual: `offline/13_continuation_playbook.md`.

**Three separate lines of work (do not merge them)**

| Line | When | Original tree | Output |
|---|---|---|---|
| Phase 1: signature / unlock | Nov 8-12 | `C:/Users/Tse/WorkBuddy/寒霜刷机` | aboot verification & boot state machine, boot hash datapath, cross-device comparison, stock DTS decompilation, temp-root / unlock tooling; text layer -> `prebuilt_c/` |
| Prebuilt route | Nov 10-12 | `D:/16/PD1610_81` | LOS16 built from stock prebuilt kernel + vendor blobs + borrowed PD1619 device tree; WiFi fixed; flashable ROM zip |
| Self-compiled kernel forensics | Nov 14-15 | this repo | `3.18.120-perf` + BLM / 9008 observation chain, bootloop root cause, touch driver rebuilt from source, completion meter 50/50 |

vivo never released 3.18 kernel sources for PD1610/PD1619, so the prebuilt route
does not compile a kernel; the self-compiled route uses the upstream LineageOS
msm8996 3.18 tree. Images from the two routes are not interchangeable.

**Timeline**

| Date | Stage | Result |
|---|---|---|
| Nov 8-12 | Phase 1 research | signature / unlock / device-tree forensics, 30+ reports, `20261112.zip` bundle |
| Nov 10-12 | Prebuilt route | LOS16 built, WiFi fixed after four causal fixes (sys13 `system.img` sha `686de5de...`), `PD1610_LOS16_20261112_UNOFFICIAL.zip` produced (935,087,013 B) |
| Nov 14 AM | Round 10-13 | BLM / 9008 `peek` chain; root cause = BSS clear range overwrote the DTB at `0x42000000`; shrinking debug config restored `d00dfeed` |
| Nov 14 PM | Round 14-19 | fixed-slot evidence overturned the `usb_bam` claim -> `qpnp_vibrator_init` first SPMI read -> `FDT_NOP` bypass -> SPMI stub + restored node, `#5` reached `sys.boot_completed=1` |
| Nov 14 evening | Round 20-26 | touch went from "no driver" to a working event chain (`CONFIG_TOUCHSCREEN_ST_FTS`, DT props, pinctrl, `IRQF_ONESHOT`, regulators); nav-key bind succeeded but probe incomplete; last candidate bootlooped and was rolled back |
| Nov 14 night | 6 offline studies + A round | 8-gate completion meter, 332-firmware inventory, stock/custom `do_msm_restart` disassembly diff; A round 3/3 cold boots, 1266 touch events after resume, all `UNVERIFIED` removed -> strict 50/50 |
| Nov 15 | Archive & handoff | bilingual README, 16-category / 76 GiB netdisk cold storage, minimal WSL rebuild set, phase-1 records and ROM package added, AI index section 9 |

**Attribution changes (the easiest way to go wrong)**

- Round 14/15 blamed `usb_bam`; **Round 16 fixed-slot evidence overturned it**.
  The real stall was `qpnp_vibrator_init` -> the first `spmi_ext_register_readl()`.
- Round 18 (`FDT_NOP` bypass) only reached userspace; Round 19's SPMI stub plus
  restoring the node produced a full desktop.
- Touch was not a probe deferral: the driver was **not compiled in at all**
  (no `fts_driver_init` in `System.map`).
- `adb reboot bootloader` is not a missing config switch: stock `do_msm_restart`
  is 1492 B vs 740 B in our build, with BBK-private calls such as
  `set_dload_mode_bbk` / `set_aee_system_restarting` / `deassert_ps_hold`.
  [H1] aboot reads a private flag; not verified on hardware.

**Completion-meter evolution**

`20/88` (6 UNVERIFIED) -> static `40/63` -> A round **strict `50/50`**, with a
`65/65` post-resume control that only proves touch can work (not `touch_cold`).
The official number is **50**. The 68-point interval was an evidence gap, not
68% of the code being unwritten. The `hal` gate needs
`--hal-ignore init.svc.vivo-fingerprint-sh` (that service is `disabled`+`oneshot`,
so `stopped` is normal).

**Nov 15, 2026 documentation & resource updates**

- README is now Chinese-first with an in-page English switch plus standalone
  `README.en.md`; added a Baidu Netdisk cold-storage index.
- Added `prebuilt_c/` (97 phase-1 texts); netdisk gained
  `14_寒霜刷机_C盘工作目录/` (84 files, private only) and
  `15_LOS16_ROM刷机包/` (ROM zip + `SHA256SUMS`).
- **Corrected a stale claim**: "no ROM zip / 5 open TODOs" -> "ROM shipped /
  4 open TODOs".
- `offline/12_ai_handoff_index.md` gained section 9; docs 13/14 synced; netdisk
  is now 16 categories / 76 GiB.
- Archive volumes `01` stay at the 01:34 build (repacking would change 973 MiB
  already uploading); their bundled index is older - use this repo / netdisk `00`.

**Current state & remaining work**

- Device: stock `3.18.71-perf-g8a8c60dd` / LOS16 / `sys.boot_completed=1` / not in fastboot.
- Four gates still FAIL: `touch_cold`, `nav_keys`, `input_parity` 5/9, `i2c_parity` 4/9.
- Longest tail: `goodixfp` fingerprint (zero related symbols in our build; needs
  disassembly-based reconstruction, 5-15 workdays, no guarantee).
- This is a **handoff snapshot (B0'), not a finished Tier-3 port**. Resume from
  round B in `offline/05_experiment_queue.md`, following the single-variable loop
  in `offline/13_continuation_playbook.md`.

### Glossary: A round / experiment queue / completion meter

**Experiment queue** = `offline/05_experiment_queue.md`, a claim-driven TODO
table. Four gates still fail, so each planned experiment fixes a claim, its
precondition, a numeric criterion, the gate it affects and a failure branch;
every round must end with a coverage-tool run.

```
Experiment queue
  A  reproduce the b6d5debb bootloop, read BLM fixed slots over 9008   (original claim, NOT executed)
  B  add IRQF_ONESHOT -> nav keys + cold-boot touch                     (split into single variables first)
  C  restore two tasha jack input devices
  D  verify the BBK private restart flag behind adb reboot bootloader
  long tail (not queued): goodixfp fingerprint - zero symbols, 5-15 days, no guarantee
  exit criteria: 3 clean cold boots / input 9/9 / I2C >=8/9 / 30s touch / full evidence / 17-17 + rollback
```

**A round result** = `offline/08_roundA_result.md`. There are **two "A rounds"**:
the queue's original A (bootloop reproduction, not done) and the A actually
executed on Nov 14 21:45-22:04, which fixed nothing - it flashed the known-good
`#9` baseline, captured full evidence and rolled back to stock, in order to
close the `UNVERIFIED` gap.

```
Executed A round
  flash 5f164490 (#9) -> 3.18.120-perf #9 reaches the desktop
  blm_round_capture.py -> 12 snapshots (199 KB dmesg, sha256 manifest)
  blm_coldboot_verify.py -> 3/3 cold boots PASS (36.8 / 58.1 / 58.2 s)
  touch: 35s cold window 0 events; after resume 1266 events, IRQ 87 -> 474
  nav keys: no vivo_virtual_key, 0 key events -> FAIL
  score 20/88 -> static 40/63 -> strict 50/50 (UNVERIFIED=0); 65/65 control only
  fixed a HAL gate false positive; added two capture tools
  rolled back to stock 929fda99... and verified
```

**Completion meter** = `tools/blm_tier3_coverage.py`: 8 weighted gates -
boot(20), touch_cold(15), nav_keys(8), input_parity(12), i2c_parity(15),
hal(10), firmware_inventory(5), reproducible(15). The denominator is the
device list enumerated on the stock system, and each item needs three proofs
(device node + driver binding + real events). `UNVERIFIED` means "evidence not
captured", not "work not done": the early 68-point interval was an evidence gap.

### Plain-language track: continuing if you only know how to flash

> This section runs **in parallel with the technical sections above**, which
> stay unchanged. It restates the same facts in everyday language. No coding or
> kernel knowledge is required: all 26 earlier rounds were run as "human
> handles the phone, AI handles code and evidence".

**Technical track ↔ plain-language track** (same files, two wordings)

| Technical (above) | Plain-language version |
|---|---|
| Start here: two-route tree | this section + `docs/BEGINNER_GUIDE_EN.md` §0.2 |
| Glossary: A round / queue / meter | "Three-step start" below + guide §5 jargon table |
| Round lineage ROUND1-9 / 10-26 | guide §0.3 current state + §10 reading order |
| Verified status 50/50, 4 FAILs | guide §0.3 / §9 FAQ |
| Baidu Netdisk index (file-by-file tree) | guide §2 "what to download" + §5 |
| `offline/13` 8-step SOP | guide §4 round script (AI says / you do / you reply) |
| `offline/05` experiment queue A-D | guide §8 zero-risk first round |
| `fixtures/` `tools/` source and scripts | guide §1 "the AI does the rest" |
| `AGENTS.md` hard rules for the AI | guide §3 opening prompt makes it read that file |


```
You (flashing is enough)            AI (Codex / WorkBuddy)
├─ restore repo + netdisk files     ├─ read logs, diff source, edit code
├─ enter fastboot when asked ──────> ├─ compile, build boot.img, preflight
├─ tap screen / press nav keys ────> ├─ flash, capture evidence, PASS/FAIL
├─ report "works / does not work"   └─ roll back to stock and verify
└─ decide continue / pause / rollback
```

**Three-step start (round one should be zero-risk)**

1. Download netdisk `00` `01` `02` `04`; have the AI run
   `sha256sum -c SHA256SUMS` and require **3/3 OK**.
2. Open the repo root with Codex or WorkBuddy (`AGENTS.md` is read
   automatically), then paste the opening prompt from
   `docs/BEGINNER_GUIDE_EN.md` section 3 verbatim.
3. Explicitly require **no compile, no flash, no partition writes** in round
   one: status check, baseline capture, one plain-language state report.
   Only then follow `offline/05_experiment_queue.md` into real rounds.

| What you need | Where |
|---|---|
| First message to the AI (copy-paste) | `docs/BEGINNER_GUIDE_EN.md` §3 |
| Round script: AI says / you do / you reply | §4 |
| Jargon translator (fastboot, dmesg, preflight, single variable) | §5 |
| When to stop, how to roll back, 8 things never to do | §6 |
| How to tell if the AI is fabricating results | §7 |
| Zero-risk first round | §8 |
| Hard rules the AI must follow | `AGENTS.md` (repo root) |
| Full methodology | `offline/13_continuation_playbook.md` |

> Chinese version: `docs/BEGINNER_GUIDE_CN.md`. Never mix the two routes'
> images: `03_/sys13_system.img` (WiFi-fixed) is not `02_/images/system.img`.

### Round lineage: ROUND1-9 vs ROUND10-26

Three independent ROUND numbering schemes appear in this project:

```
(1) Signature / unlock state machine, Nov 8-12 (C-drive + prebuilt/evidence)
      ROUND3_LOOP_LIFECYCLE.txt, ROUND4_FLAG_BEQ_DATAFLOW.txt,
      ROUND5_RETVAL_CLASSIFICATION_AND_STATE_PATH.txt,
      aboot_verification_analysis.md, boot_state_machine_analysis.md,
      original DTS, xplay6_unlock/ tooling

(2) Offline RE + multi-model review ROUND1-9, Nov 12-13 (kernel_re/out/)
      these numbers count review briefings sent to GPT/Claude, NOT flashes
      round3/  aboot decompress trace, ARM64 Image memory audit, address overlap,
               config diff attribution, DTB selector disassembly
      round4/  aboot handoff, early MMU evidence, FDT chain, BOOT_ONLY feasibility,
               Unicorn replay, memory_lifecycle_and_observability.md
      ROUND3_REVIEW_LANDING.md, ROUND4..9_FOLLOWUP_FOR_GPT.md, BRIEF_*_BATTLE.md,
      multimodel_capture/ (18 files), STAGE1..30*.md (yet another numbering),
      MASTER_FINDINGS.md, MASTER_HANDOFF_20261113.md, COMPILABLE_SOURCE_PROGRESS.md,
      h6/ROUND5_BOOT_ONLY_DELIVERY.md

(3) BLM on-device forensics ROUND10-26, Nov 14 (this tree)
      ROUND10-13  BLM / 9008 chain, all-zero FDT root cause, config shrink
      ROUND14-17  usb_bam claim overturned -> qpnp_vibrator_init -> first SPMI read
      ROUND18-19  FDT_NOP bypass -> SPMI stub + restored node -> sys.boot_completed=1
      ROUND20-26  touch driver rebuilt from source, nav keys, reboot path, rollback
      A round     not a ROUND: it is queue letter A (evidence narrowing)
```

The first report here is called ROUND10 because it continued the numbering of
(2); it is not "the tenth flash". ROUND1-9 material lives in `prebuilt_c/`,
netdisk `11_逆向证据_全量分卷/`, `14_寒霜刷机_C盘工作目录/` and `prebuilt/evidence/`.

### Verified status (2026-11-14)

- Tier-3 completion meter: **50/50 strict**, `UNVERIFIED = 0`
  (report: `flash_log/tier3_coverage_roundA_final_strict.json`).
- Still FAIL: `touch_cold`, `nav_keys`, `input_parity` (5/9), `i2c_parity` (4/9).
- A round: `3/3` clean cold boots (36.8 / 58.1 / 58.2 s); after a
  suspend/resume cycle the touch panel produced 1266 `getevent` lines.
- Device rolled back to stock `3.18.71-perf-g8a8c60dd`, `sys.boot_completed=1`.
- A round result: `offline/08_roundA_result.md`. Queue: `offline/05_experiment_queue.md`.

### Honest limitations

- Touch works only after a suspend/resume cycle; the cold-boot 30 s window has
  no events. `nav_keys` has no `vivo_virtual_key` input device.
- `adb reboot bootloader` still reboots normally on the candidate kernel.
- The last navigation-key candidate `b6d5debb...` was reported as bootloop
  and rolled back; the cause was never isolated.
- Round 14/15 blamed `usb_bam`; **Round 16 fixed-slot evidence overturned
  that**. The real stall was `qpnp_vibrator_init` -> first SPMI read.
  Do not continue from the old conclusion.
- The prebuilt route **did ship a flashable ROM** `PD1610_LOS16_20261112_UNOFFICIAL.zip`
  (935,087,013 B, sha256 `97c3137e...`, in netdisk `15_LOS16_ROM刷机包/`).
  4 issues remain open (camera, libcurl, diagnostic-code cleanup before release,
  sepolicy/configstore); see `prebuilt/evidence/_log_append4.md`.
  Phase-1 signature/unlock/device-tree research is in `prebuilt_c/`.

### What this repository does not contain

Boot images, DTB binaries, firmware blobs, RAM dumps and the WSL build
environment are in a separate private cold-storage archive (about 973 MiB,
2 volumes, zstd tar). This repo is the text-only documentation layer;
see `offline/12_ai_handoff_index.md` section 2 for the restore procedure.

### Baidu Netdisk cold storage (2026-11-15)

Binary assets, original project trees and flashable images are not on GitHub.
They live in the private Baidu Netdisk folder **`PD1610_Xplay6/`** (~76 GiB,
~7160 files, 16 categories).

- Share link: <https://pan.baidu.com/s/5OL1VH3h9Pn_uOQllg29MSQ>
  (an extraction code may be required; ask the maintainer. Links can expire.)
- Layout and per-file manifest: `00_必读_恢复说明/上传清单.md` and `UPLOAD_CHECKLIST.csv`
- Restore entry points: `00_必读_恢复说明/RESTORE.md`, `12_ai_handoff_index.md`

| Groups | Contents |
|---|---|
| `00`–`06` (required, 6.7 GiB) | restore notes/checksums, `01` two cold-storage volumes (973 MiB, zstd tar, authoritative copy), stock release package, sys13 baseline, 9008 tools, firmware, minimal WSL rebuild set |
| `07`–`09` (optional) | redundant GitHub text tree, 48 partition dumps, official OTA packages |
| `10` / `11` | full `D:\16\PD1610_81` 40 GiB (22 volumes) and `kernel_re` 11 GiB (6 volumes), 1.9 GiB tar volumes |
| `12` / `13` | raw self-compiled project tree, misc resources and tools |
| `14` / `15` | full phase-1 C-drive workspace (4.9 MiB), flashable LOS16 ROM zip (935 MB) + checksum |

### File-by-file tree (what each item is for)

The full 7260-row manifest is `00_必读_恢复说明/UPLOAD_CHECKLIST.csv`.
The trees below explain the files you will actually open.

```
PD1610_Xplay6/                         16 categories / 76 GiB
  00_必读_恢复说明/                    restore entry (17 files)
     RESTORE.md ..................... reassemble -> zstd -> tar extraction
     SHA256SUMS / manifest.json ..... 3-line checksum + 2121 file hashes
     上传清单.md / UPLOAD_CHECKLIST.csv ... summary and per-file manifest
     12_ai_handoff_index.md ......... AI resource map (section 9 = current state)
     13_continuation_playbook.md .... single-variable loop and SOP
     14_prebuilt_upload_checklist.md  prebuilt TODOs and must-keep files
     11_wsl_rebuild_guide.md ........ minimal WSL rebuild
     百度网盘索引_草稿.md / 增量补传清单 / 操作卡 ... indexes and upload steps
  01_全量冷备分卷/                    part01 900 MiB + part02 72.5 MiB (both required)
  02_原厂回滚与发布包/                images/boot.img rollback, recovery, system,
                                     patches/ (7 final source changes), tools/, flash_all.*
  03_prebuilt_续修基线/               sys13_system.img (WiFi fixed), prebuilt_kernel,
                                     vendor_blobs/_vendor.tar, modules/, compat_libs/
  04_9008与刷机工具/                  qfil/ (QFIL, QSaharaServer, fh_loader, firehose .elf),
                                     platform-tools/, firehose_scripts/
  05_固件blob/                        332-file inventory CSV, 76 pulled blobs zip,
                                     FAT16 /firmware image, extraction notes
  06_WSL重建集/                       src/kernel-src.tar, config/kout-shrink.tar,
                                     .config + System.map, toolchain tar, scripts/, env/
  07_GitHub发布树_冗余/               offline copy of the public text tree
  08_分区dump_可选/                    48 raw partition dumps (8.4 GiB)
  09_原厂OTA_可选/                     official OTA zips and signed firmware
  10_prebuilt工程_全量分卷/            22 x 1.9 GiB tar volumes of D:/16/PD1610_81
  11_逆向证据_全量分卷/                6 tar volumes of kernel_re (ROUND1-9 evidence)
  12_自编译工程原始全量/               raw bootloop_monitor tree
  13_其它资料与工具/                   misc D:/16 material, dist, local git repo
  14_寒霜刷机_C盘工作目录/              phase-1 workspace: signature/aboot studies,
                                     original DTS/DTB, pd1610_rom/ device tree,
                                     xplay6_unlock/ tooling, H1 test pack,
                                     20261112.zip log bundle, .workbuddy/memory/ (private)
  15_LOS16_ROM刷机包/                 flashable ROM zip + SHA256SUMS + flashing notes
```

**Verify after download**: put `SHA256SUMS`, `manifest.json` and the two `01`
volumes in one directory, run `sha256sum -c SHA256SUMS` (3/3 OK required), then
follow `RESTORE.md`. `10_`/`11_` carry their own `SHA256SUMS` + `RESTORE.txt`.

> `10_prebuilt工程_全量分卷/` contains device key material (`imei.der`,
> `donuts_key`) from the stock OTA. Do not share that subfolder publicly.
> `03_.../sys13_system.img` is the known-good WiFi-fixed baseline and is NOT
> the same image as `02_.../images/system.img`.

### Licensing

Self-written tools: MIT. Documentation: CC-BY-4.0. Kernel patches follow
the upstream LineageOS msm8996 3.18 GPL-2.0 with copyright headers intact.

> This is a handoff snapshot (B0'), not a finished Tier-3 port.