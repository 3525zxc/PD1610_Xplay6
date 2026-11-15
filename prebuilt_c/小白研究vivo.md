# 小白研究vivo — 阶段同步与重启清单

> 同步时间：2026-11-09 22:30
> 项目状态：**暂停**。主报告 `Xplay6_最终报告_v7.md` 以 **v7.4（1046 行）归档封存**，不再升版、不再改动。
> 本文件是以后重启计划时的**唯一入口**：先看第 1 节结论，再按第 2 节待办执行。
> **2026-11-10 09:06 结论更新**：原 1.1「实际 SHA‑256 哈希输入未闭合」**已闭合**；
> 签名封装确认为 AOSP 标准 `AndroidVerifiedBootSignature`，不是 vivo 私有格式。
> 详见 `PD1610_哈希输入闭合与BootSignature标准格式.md`。主报告 v7.4 按封存约定不改动，
> 其 3.3/3.5/6 节相关表述以该简报为准。
> **2026-11-10 09:38 结论更新**：X9s 官方 / 修补 boot 与处理后 devinfo 的字节级对照完成
> （`PD1616B_X9s_官方与修补boot字节级对照.md`）：AOSP 哈希模型 **6/6 命中**；X9s 官方 boot
> 证书与 PD1516A **逐字节相同**（跨 SoC 复用）；修补 boot `L==size` 无签名尾部却能启动 →
> 「解锁态放行无签名 boot」事实链已确认，PD1610 的差异只能落在 aboot 解锁态控制流。
> **2026-11-10 午后结论更新（P0 静态闭合 + 第二轮复核）**：`Device is unlocked! Skipping verification...`
> 分支已纯离线定位并全链闭合（`0x91839944` / xref `0x918399A4-A8`）：解锁态=设 `boot_state=1`
> +打日志，**验签调用不被跳过**。**第二轮复核（§10）修正**：验签失败的最终拦截是
> tampered assert 重启循环（`is_tampered=1` → ASSERT(0) → 关中断 → platform_halt(reboot)），
> **锁定/解锁一视同仁**；解锁只绕过 RED 升级的表现层（无错误屏/30s/关机尝试），
> 绕不过 assert 重启。「解锁+验签失败=继续启动」**不成立**；11-08「改 1 字节卡 logo」
> 真归因 = aboot 内重启循环，**内核从未执行，单字节实验不能评估内核好坏**。
> 详见 `PD1610_解锁跳过验签分支P0静态闭合_补充记录.md`（§10）。
> **2026-11-10 14:40 结论更新（P2 定案 + 新假设 H1）**：拿到 X9s 官方 aboot（8.20.30，经官方 CDN
> Range 单条目抽取）与 X9s 7.1.2 aboot（1.13.10，123 云盘包流式解压）后，五 build 对照证明——
> **tampered 致命断言是代际差异：7.x 世代（PD1610 1.15.1/7.13.15、X9s 1.13.10）有；
> 8.x 世代（PD1610 8.19.16、X9s 8.20.30）已删除**，验签失败后仅做状态处理并继续装载。
> 由此提出 **H1：把 aboot 升级为官方 8.19.16（vivo 签名、SBL 可过）即可获得"失败不阻断"**。
> 离线核对已把三项风险压到低：boot 验签公钥三代逐字节相同（换 aboot 不改变判定）、
> boot 格式串清单两版完全一致（legacy v0，无 dtbo/vbmeta/AVB）、smc 4/4 与 bl 9852/9853
> （TZ 接口面未变）。**唯一未定：aboot↔旧 XBL 加载接口，需实机。**
> 执行手册与回读配置见 `PD1610_H1_测试包/`（`H1_操作手册.md` + `readback_chain.xml`）。
> 详见补充记录 §18–§21。**H1 未验证；13.4 四条重启条件仍未被绕过（H1 不依赖私钥或 CVE）。**
> 目标（不要跑偏）：vivo Xplay6 / PD1610 / MSM8996 **跑类原生 Android（LineageOS 类），不是 root**；当前阶段是搞定启动链。
> 设备/引导：官方 1.15.1 / Android 6.0.1 / 7.13.15 aboot / devinfo BL 解锁 / `secure:yes` / `verifiedbootstate=green` / `veritymode=enforcing` / 9008 可恢复。

---

## 0. 一句话现状

**能写，不能启——但"不能启"的机制已经完全查清，并且第一次出现了一条不需要私钥的候选入口。**

- 已确认：验签照跑，失败后 7.x 世代的 aboot 会 `tampered assert` 直接重启（**内核从未执行**），解锁状态绕不过去。
- **新线索（H1，未验证）**：8.x 世代的官方 aboot **删掉了这条致命断言**。如果把它换上去，验签仍会失败，但**不再致命**——理论上就能启动自编译镜像。执行手册见 `PD1610_H1_测试包/`。

---

## 1. 截至目前得出的结论

### 1.1 启动链主报告（v7.4，分层结论）

| 层 | 命题 | 状态 |
|---|---|---|
| 1 | 能刷入任意镜像（devinfo 解锁有效） | **成立** |
| 2 | 自编译 boot 能通过已识别的启动验证并被引导 | **当前没有可行路径**；验签失败后的最终装载结果**尚未完全闭合**（U1） |
| 3 | 存在「少验一次」的分支（缺签名 / 别的分区 / 老 aboot / fastboot boot） | 其余基本证伪；**「缺签名」仍是较强推断** |
| 4 | 信任根可替换（keystore 分区 / 镜像自带证书） | **证伪**（公钥编译进 aboot） |
| 5 | 用内存破坏绕过（ASN.1 / 解析器） | 本轮审计**未发现可用缺陷**，不排除其它类型内存破坏 |
| 6 | 换 system 也能得到类原生 | **不成立**（dm-verity enforcing） |

已确认的技术事实：

- **签名结构（2026-11-10 定性修正）**：boot 尾部 DER 就是 AOSP `system/extras/verity/BootSignature.java` 定义的标准 `AndroidVerifiedBootSignature`，**不是 vivo 私有格式**：`SEQUENCE { formatVersion INTEGER 1, certificate X.509, algorithmIdentifier SEQUENCE(sha256WithRSA OID), authenticatedAttributes SEQUENCE(PrintableString "/boot", INTEGER L), signature OCTET STRING 256B }`；签名在 DER 内 `L+0x400`（recovery `L+0x404`）；`L = getSignableImageSize = page_size + ALIGN(kernel) + ALIGN(ramdisk)`（本项目 5 份镜像 `second_size=0`、header v0），5 份逐字节吻合。算法 RSA-2048 + SHA-256 + PKCS#1 v1.5。vivo 自有的是**证书/密钥材料与 aboot 验证策略**。
- **验签链**：`0x91839B18`（验签子过程）→ `0x9181167C verify_image(data,len,"/boot")` → `0x91810CB0 verify_sig` → `0x9182154C` → `0x9186CC54`；全二进制**直接 BL** 搜索只有两处调用点 `0x91839B78`（/boot、/survival）、`0x91839C4C`（/recovery）。
- **公钥来源**：aboot 内嵌静态 DER（`0x91878F28`，模数 `E1146086…`），证书 985 B / SHA256 `8a1ee2d0…`；**不是**镜像自带证书，当前 RSA 路径也未发现读取独立 keystore 分区。
- **失败路径三层要分开**（v7.4 最核心的收紧）：
  1. RSA 验签本身失败 —— 已确认；
  2. 验签子过程 `0x91839B18` 设置 `skip_flag[0x91B92D08]=1`、清零 `[0x9192BBF0]`、`beq 0x91839C04` 提前返回 —— 指令级确认；
  3. 调用者 `0x9183E05C` 是否最终停止内核装载 —— **尚未完全闭合**。
  `0x91843B58` 是 getter `return [0x91B944B0]`（1 读 0 写、静态初值 0、间接写入未排除），`0x9183E398` 的零值分支很可能实际经过；`0x9183E9A0` 经空函数汇合到 `0x9183E5DC`，不构成第二道阻断。
- **结构复核**：`0x9183E3B0 → 0x9183E5DC` **不是**线性路径（E3B0–E5DC 段内无跳转到 E5DC；E5DC 全函数仅 `E9B4`/`EBA4` 两个前驱）；`0x9183E81C: bl 0x9183D63C` 是候选跳核调用点，条件未追踪。反汇编必须按 **ARM (A32)** 模式（`adis.py` 默认 Thumb 会错解），映射 `file_off = VA - 0x91800000 + 0x8000`。
- **实际 SHA-256 哈希输入【2026-11-10 已闭合】**：`signable = boot[:L] ‖ DER(authenticatedAttributes)`，即镜像前缀后**追加重新编码的** `SEQUENCE{"/boot", L}`（如 1.15.1 = `300d13052f626f6f74020403257000`）。`SHA256(signable)` 在 5/5 份镜像（PD1610×3 + PD1516A×2）上与 RSA 恢复摘要逐字节一致；8 个控制变体全不匹配。旧 9–10 个候选全是「L 起始的连续区间」，故长期未命中。**这不改变「能写，不能启」**：验签侧已无私有格式歧义可利用，缺的仍只是可信私钥。
- 已关闭路线：`CONFIG_KEXEC=n`、`fastboot boot`/多数 `oem` 命令被拒、poke 注入重启失效、老官方 aboot 无收益、换 system 受 dm-verity 限制、OpenSSL-LK ASN.1 无直接可利用边界缺陷。

### 1.2 同平台对照（PD1516A / Xplay5S 旗舰版）

用 vivo 官方 OTA 包按 HTTP Range 只取 `boot.img` / `emmc_appsboot.mbn` / `otacert`（CRC 全对，未下整包）后离线比对：

- **评审的关键判据被证伪**：两机型虽同为骁龙 820、签名结构同构，**不复用同一把 boot 签名公钥**。PD1610 = `OU/CN=scm_beta`、`E1146086…`；PD1516A = `OU/CN=scm`、`A5CEEE3D…`（证书 SHA256 `4b063c75…`）。
- **「aboot 内嵌公钥」被字节级独立复核**：PD1610 的 1.15.1 / 8.19.16 / 16 MB 分区 dump 三份 aboot（`0x80FE5` / `0x83F15` / `0x81059`）都内嵌与 boot 尾部完全相同的 scm_beta 证书；PD1516A aboot 里没有其 boot 证书，只有非 beta CA 与一张 `C=US, ST=CA, O=Android LK` 证书。
- OTA `otacert` 是**第三把密钥**（`B96ADA8B…`），不能当 boot 验签公钥。
- 5/5 份镜像用各自证书公钥都恢复出标准 SHA-256 DigestInfo → 证书即验签公钥、两机型算法一致；哈希输入 **2026-11-10 已按同一 AOSP 模型跨机型闭合**。
- 边界：只关闭 PD1516A 这一个样本，不排除其它机型/工程固件共用密钥；**未发现任何私钥**。

### 1.3 新主题第一轮（非传统启动路径 / 内核移植）

- **Fastboot 内存启动路径关闭，且比预想更彻底**：不是「两条路径共用同一套验签」，而是**只有一条分区启动路径**。五个 aboot（PD1610 ×3 + PD1516A ×2）精确字符串 `"boot"` 全部 0 命中；OEM 表无内存启动变体；7.13.15 注册区 `0x9183C3B4–0x91840C24` 的 23 处 `movw/movt` / 18 个命令里没有 boot；全镜像 A32 BL 解码显示验签只在重启后的加载链。与实测 `fastboot boot → unknown command or device is lock` 一致。
- **原厂设备树已拿到手（本轮最大产出）**：boot header 5/5 都是 `second_size=0 / dt_size=0`，无独立 dtbo/dt.img，但 **boot.img 的 kernel 区是首尾相接的真实 DTB 链**（1.15.1 = 106 份、8.19.16 = 122 份、stock = 3、PD1516A = 3 / 59）。8.19.16 第 79 份即 `vivo MSM 8996 v3 + PMI8996 PD1610`（409,557 B）。
  PD1610：`qcom,msm-id=<0xf6 0x30001>`、`board-id=<0x1 0xa 0x1000001 0x0>`、`pmic-id=<0x20009 0x10013 0 0>`（PD1516A 仅 board-id 第二项为 `0x9`）。可直接填进 mainline DTS，**不需要实机临时 Root 读 `/proc/device-tree`**。样本在 `C:\qfilx\compare\dtb\`。
- **MSM8996 Mainline 基础存在，但不是启动入口**：`gts3lwifi-mainline` README 实测是 **Linux 7.3.1**（评审写的 6.19.5 已过时）；`gitlab.com/msm8996-mainline/linux` 存在（`msm8996-staging`）；postmarketOS wiki 有组件状态表。评审给的「UFS 4.18 / DSI 5.14…版本号表」未找到可核对来源，**未采信**。关键限制：**lk2nd 也必须打包成原厂 boot image 由原厂 bootloader 加载**，其 `fastboot boot` 是 lk2nd 自己的接口，不是绕过 PD1610 验签的独立入口。本轮检索未发现 PD1610 现成 mainline 移植。
- **目标 A（启动入口）目前仍无可行路径；目标 B（准备可运行的系统）可以完全离线推进**，但两者汇合的前提仍是找到能让自编译镜像真正执行的入口。临时 Root ≠ 能加载任意内核，也 ≠ 能替换 boot.img。

### 1.4 设备状态（重启时第一件事）

- 引导层、基带、IMEI、NV、分区表**全程未改动**。
- **最终状态未确认**：已执行「刷回 `boot_00_baseline.img`」的恢复操作，但最后一次 `fastboot flash`（19:15）被中断，写入是否完成、设备能否正常开机**待实际核实**（U6）。不要再写成「已恢复至官方 1.15.1」。
- 拿到设备：先开机看是否正常进系统；**卡 logo** → 按住「音量下 + 电源」进 fastboot → `fastboot flash boot C:/qfilx/boottest/boot_00_baseline.img`。备用：9008（EDL）+ 1.15.1 官方完整包，已验证可用。

### 1.5 案例博主线索（2026-11-10 新增，纯离线整理）

- **身份闭环**：酷安 UID 3298502「鼠鼠鼠鼠」= GitHub **`xiaocheng20`**（2021 年内核构建主机名 `xiaocheng20@…` + 评论区自述"搜 xiaocheng20"）。
- **时间线**：2021 年 LOS 14.1（7.1.2，`14.1-20210717-UNOFFICIAL-pd1610`）+ 内核 `3.18.31-perf-gb3d31da62-dirty`（基于 7.1.1 原厂树改）→ 2026 年 LOS 17.1 eng + 内核 `3.18.124-perf-g2363427e-dirty`（stable 合并）。**该机至少 2021 年起就在启动自定义内核。**
- **判读**：3.18.124/3.18.31 均非 vivo 原厂版本 → 自定义内核 → boot 非 vivo 签名；而本地 1.15.1 与 7.13.15 aboot 均为新架构（验签无条件 + tampered assert）→ **零售机无法做到，工程机/放宽 aboot 可能性进一步上升**；「2016 早期 aboot 旧架构」假设仍无文件未验证。
- **来源文档**：`PD1610_案例截图判读_20261110.md`（逐张转录+时间线）、`PD1610_内存态临时Root工具链_发现记录.md`（另一位博主的内存态 root，Route 6 支持 1.15.1，可作只读采集方案）。
- 其余线索：其公开 GitHub 现无 PD1610 内核/设备树（2021 年声称开源，现已 404/不可获取）；tmproot 仓库的音频核对表（ES9038/DSD）与案例截图 DSD 演示高度吻合，两方至少共享技术圈。

---

## 2. 后面待办的事务（重启时按此清单执行）

### 2.1 第一优先级：U1 数据流（纯离线）——**主干已于 2026-11-10 午后闭合（含第二轮复核修正）**

**已完成（见 `PD1610_解锁跳过验签分支P0静态闭合_补充记录.md` §4/§5/§10）**：修正后模型——

- 验签包装 G（`0x91839B18`）**无条件**置 `is_tampered=1` 并调用 `verify_image_with_sig`（全库仅 2 调用点 /boot+/recovery）；
- **验签成功**：`[0x91B92D08]=1`、`is_tampered=0` → G 正常返回 → 调用侧 `0x9183E398`：`[0x91B944B0]≠0` 且成功标志≠0 → `0x9183E5B8`（下游跳核路径）；`[0x91B944B0]==0` → `E3B0` state 检查（state==1 → `EAC0` 警告 → `E3BC` → `0x91810E84` 按 boot_state 四路分派）；
- **验签失败**：`is_tampered` 保持 1 → **G 永不返回** → `devinfo_update` + "Device is tampered. Asserting.." + **ASSERT(0)**（aboot.c:1224）→ 关中断 → "HALT: platform_halt reboot..." → `reboot_device(0)`（PSHOLD 0x4AB000）→ **重启循环**。锁定态在此前多一道 RED 升级（Security Error + 30s + 关机尝试）；解锁态无此表现层，但**结局相同**。
- v7.4 第 3 层「调用者是否最终阻止内核装载」的答案：**失败场景根本到不了调用者；最终拦截 = tampered assert 重启，与解锁状态无关**。v7.4「不得预设 E3B0→E5DC 线性汇合」的告诫被证实。

**实验含义**：11-08「改 1 字节 → 5s 卡 logo」真归因 = aboot 内 assert 重启循环，**内核从未执行——单字节实验不能评估内核好坏**；任何被改动的 boot 都会被这条链拦截在内核跳转之前。

**剩余细化（低优先，纯离线）**：`[0x91B944B0]` 写入者与语义；`E3BC → 0x91810E84 → 下游函数 0x9183E5D4 → 候选跳核 0x9183E81C` 逐条精读（现仅验签成功路径可达）；devinfo 其余 26 个消费点（fastboot 区域）枚举。

### 2.2 需要设备在手（先备份、先确认状态，未执行）

| 事项 | 说明 |
|---|---|
| 核实设备最终状态（U6） | 开机验证，或 EDL 只读回读与 baseline 逐字节比对 |
| T3-A / T3-B | 按 5.2 拆分的两个**单变量**实验：无效 RSA 签名 / 完全缺失认证结构，各自需回读确认（U3/U4） |
| EDL 只读回读 | 读回 T1 之后 `L` 起始分区内容 → 确认「旧签名残留」不是推断（U5） |
| 临时 Root 信息采集 | 只读收集 `/proc/config.gz`、`/proc/modules`、`/proc/cmdline`、`/proc/device-tree` 或 `/sys/firmware/fdt`、`dmesg`；DTB 已离线取得，此项只补内核配置与启动日志。**已有现成方案（2026-11-10 发现）**：`xplay6-tmproot`（AlexIllinois2 GitHub）内存态临时 root，**不解 BL、不写分区**，支持 1.15.1/6.0.1 Route 6；见 `PD1610_内存态临时Root工具链_发现记录.md` |

> 评审明确要求：**不为补齐报告再刷未经验证的实验镜像**。以上均为条件登记，当前一律不执行。

### 2.3 纯离线收尾（目标 B，可与 2.1 并行）

1. ~~**原厂 DTB → mainline DTS 草稿**：装 `dtc`，反编译 `pd1610_81916_VIVO_00.dtb`~~ **已完成（2026-11-10 14:45，无需 dtc）**：自写 FDT 解析器 `C:\qfilx\exp\fdt_tool.py`，从 `firmware\81916\boot.img` 的 122 份 DTB 中定位第 79 份 PD1610 专用（409,557 B），反编译为 15,641 行 DTS（1,983 节点 / 12,829 属性），已存为 `PD1610_原厂设备树_81916.dts`/`.dtb`。**驱动量化（关键）**：292 个唯一 `compatible` 中 `vivo,`/`bbk,` 私有仅 3 个（`vivo,charger-monitor`、`vivo,hifi-codec-pd1610a`、`vivo,touchscreen-config`），252 个（86.3%）在原厂内核镜像中直接命中 ⇒ 移植工作量在**参数搬运**而非重写驱动。见 `PD1610_原厂DTS反编译与关键节点.md`。
2. **内核与设备树跨版本/跨机型对照（2026-11-10 15:05 完成）**：六份 `boot.img` 内核全部提取（PD1610 8.19.16=3.18.71 / PD1516A 3.8.5=3.18.20 / 7.7.6=3.18.31 / PD1619 与 X9s=**3.10.84** / TB8703 LOS17.1=3.18.140）。**PD1516A 7.7.6 的 boot.img 内含 PD1610 的设备树**（3 份 vivo DTB，按 `board-id` 选表：PD1516A=`0x9`、PD1610=`0xa`）⇒ 两机型共用同一内核二进制。**fstab 对照**：PD1610 原厂 `vendor` 已 `status="disabled"`（非 Treble）、`system` 为 `wait,verify`；TB8703 的 Android 10 是 `wait` + **无 vendor 节点** ⇒ 移植只需把 `fsmgr_flags` 去掉 `verify`。config 层面 Android 10 差距接近零（binder/SDCardFS/SELinux/dm-verity/dm-crypt/zram 全在；两版都无 `FS_ENCRYPTION`，均不支持 FBE）。见 `PD1610_内核与设备树_跨版本跨机型对照.md`。
2. **其它真实启动入口盘点**：Recovery / EDL / 工程固件（静态已知 Recovery 共用验签、EDL 只是写通道、PBL 认证 aboot；无机密工程固件可快速收尾）。
3. **MSM8996 Mainline 内核与驱动研究**：Tab S3 参考、pmaports、组件状态；注意 PD1610 是 UFS 而 Tab S3 是 eMMC，屏/触摸/相机/指纹/PMIC 均需适配；若最终目标仍是 LineageOS，基于原厂 3.18 内核移植通常比 mainline 更接近目标。
4. **v7.4 的 13.7 其余未闭合项**：U2（`0x91B944B0` 间接写入）、U7（两版 aboot 归一化指令比较）、U9（当前 boot ramdisk `/verity_key` 指纹）、U8/U11/U12 待条件。**U10 已于 2026-11-10 在密码学等价性层面闭合**（AOSP 标准模型 5/5 复现摘要）；aboot 内逐指令追踪 `SHA256_update` 参数仍属低优先，未执行。
   **复评任务 2 进展（2026-11-10 09:38）**：已用 X9s 官方 boot / 去加密 Magisk 修补 boot / 处理后 devinfo 做字节级对照——官方 boot 带有效 AOSP BootSignature（第 6 份哈希模型命中），修补 boot `L==size` 完全无签名尾部且能启动；**「解锁态放行无签名 boot」升为事实链已确认**，机制层面（aboot 是否真的跳过 `verify_image`）仍为推断。详见 `PD1616B_X9s_官方与修补boot字节级对照.md`（**午后已按外部复评做证据分级与归因范围修订**：4a/4b/4c 拆分、「差异最可能在 bootloader 验证策略层」放宽表述）。
   **评审重排 P 系列执行状态（2026-11-10，全部纯离线）**：**P0 完成**（unlock 日志分支定位+全链闭合+第二轮复核：解锁态抑制 RED 升级但保留 tampered 致命断言，见补充记录 §4/§5/§10）；**P1 完成**——PD1516A 385=旧架构：解锁态**结构性跳过验签**（`0x91633694` 分支），锁定+失败仅打印 "Asserting.."（无 ASSERT）继续装载，无 boot_state/RED 机制；`Skipping verification`/`Keystore failed` 串死数据。**P2-a 完成**——776 门控（恒返常数存根 `0x91831AA4`，LK app 入口 `0x91839210` 必达、与锁定状态无关）在旧/新验签实现间**选择**（=1→新实现 `0x918385F0` normal-boot，自带签名处理，返回→回退 fastboot），旧验签入口+wrapper 死代码，**新实现验签深度未逐条闭合**（§12，撤回"编译期关闭"表述）。**P2（boot 判定点）完成**——`0x91839944` 处 `cmp #0/bne`，任意非零（0x01/0xFF）判解锁。**跨机型分叉点=验签架构代际差；证书（scm 同族）与验签策略是独立两层，不能互推**。**下一优先=取得 X9s/PD1619 官方 aboot**（需用户下载）；其后 P3=`[0x91B944B0]` 写入者、P4=成功路径跳核精读。
5. **对照简报遗留**：第三方 PD1516A QFIL 3 GB 与 PD1610 三份 QFIL（1.17.5 / 1.23.4 / 7.12.35）未取得；PD1516A aboot 的 `verify_image`/`verify_sig` 反汇编未做；`Android LK` 证书是否公开测试密钥未核实；DER 之后的非零尾页数据含义未解释。
6. **新主题遗留**：每个 fastboot handler 完整函数体未反汇编；QCDT `ARMd` 表头/索引未定位（`kernel_raw.bin` 0x38 是 MZ/PE 伪命中）。~~1.15.1 / PD1516A 3.8.5 链中的 vivo 专用 DTB 未定位~~ **已解决**：PD1516A **3.8.5 的 59 份 DTB 全部是高通参考板、vivo 定制为 0**；vivo 定制 DTB 首次出现在 **7.7.6**（3 份，含 PD1610）。PD1610 **1.15.1（6.0.1）的 boot.img 本地未取得**，其 DTB 仍未定位。PD1610 现成 mainline 移植未检索到（仅本轮范围）。

### 2.4 重启「设备实验或漏洞利用研究」的四条硬条件

只有下列之一出现才值得投入（13.4，与第 10 节可证伪条件一致）；**纯离线证据收尾不在此限**：

1. 出现能通过 SBL 认证、且关闭 boot 验签的 aboot（工程机版本 / vivo 签名）；
2. 拿到与内嵌公钥匹配的 boot 签名私钥或可用签名服务；
3. 拆机引出 UART，能读 panic / 寄存器（让漏洞研究从盲狙变成工程）；
4. 命中一个已公开且确认存在于本 build 的 LK / OpenSSL-LK 内存破坏 CVE。

任何「刷机教程 / 一键工具」声称能让这台零售机跑自编译内核，都必须先解释它如何绕过上面第 2～4 层的同一组约束。将来重做的初步筛选顺序：`getvar secure` / `verifiedbootstate` / `veritymode` → `fastboot boot` 是否在命令表 → 内核 `CONFIG_KEXEC` → 才谈编译（三项只是止损筛选，不是完备判据）。

---

## 3. 证据与文件索引

| 文件 | 内容 |
|---|---|
| `Xplay6_最终报告_v7.md` | **v7.4 归档版，1046 行，封存不动**；0 节结论、4.2 控制流、13.4 重启条件、13.7 U1–U12 证伪条件表 |
| `PD1610_解锁跳过验签分支P0静态闭合_补充记录.md` | **2026-11-10 午后新增**；P0/P1/P2/P2-a/P3/P4 全链地址与闭合；§17 viQOO 反查官方签名解锁通道；§18 X9s aboot 到手；**§19 代际修正（7.x 有 tampered 断言 / 8.x 删除）+ 假设 H1**；§20-§22 H1 离线核对与隐藏拦截排查 |
| `PD1610_内核与设备树_跨版本跨机型对照.md` | **2026-11-10 15:05 新增**；六份 boot.img 内核清单、PD1516A 7.7.6 内含 PD1610 DTB、fstab 对照（非 Treble + 关 verity）、config 三方差异、驱动存在性 86.3% |
| `PD1610_原厂DTS反编译与关键节点.md` + `PD1610_原厂设备树_81916.dts/.dtb` | 15,641 行 DTS（1,983 节点）；音频 ES9038 + TFA9890 参数、充电 hybrid、面板时序；私有 compatible 仅 3 个 |
| `PD1610_H1_测试包\`（`H1_操作手册.md` + `readback_chain.xml` + `chain_manifest.txt`） | **设备到位即可用**：18 个启动链分区只读回读定义（GPT 实测扇区）、四阶段流程与判据、8.19.16 组件 sha256 基线 |
| `PD1610_案例截图判读_20261110.md`、`PD1610_内存态临时Root工具链_发现记录.md`、`TB8703_LOS171_3.18内核参考价值评估.md` | 案例博主证据链（身份闭环、时间线、信源封口、假设 B 排除）；xplay6-tmproot 工具链；TB8703 Android 10 参考实现 |
| `PD1616B_X9s_官方与修补boot字节级对照.md` | 195 行（修订后）；X9s 三文件字节级对照，已按外部复评修订证据分级 |
| `Xplay6_PD1516A_同平台固件对照.md` | 183 行；证书 / modulus / 签名结构跨机型比对 |
| `PD1610_非传统启动路径与MSM8996内核移植可行性研究.md` | 211 行；Fastboot 命令面、原厂 DTB 链、mainline 现状 |
| `PD1610_研究总报告.md`、`Xplay6_完整技术简报.md`、`Xplay6_第7轮_验签终局.md` | 早期总报告与底稿（部分结论已被 v7.4 收紧，以 v7.4 为准） |
| `C:\qfilx\aboot\`、`C:\qfilx\exp\`、`C:\qfilx\compare\` | 反汇编脚本、实验镜像、固件提取；`compare\kcfg\` = 6 份内核 + 5 份 config + 差异表；`compare\dtb\` = DTB/DTS + 节点差异清单 |
| `.workbuddy\memory\2026-11-10.md` | 当日逐轮修订日志（含 P0-P4、H1、内核/DTB 对照） |

复现前提：`capstone`（ARM A32）、Python 3、`openssl`。**`dtc` 已不需要**——自写的 `C:\qfilx\exp\fdt_tool.py` 可完成 FDT 解析与 DTS 生成。aboot 反汇编必须用 **ARM (A32)** 模式。

---

## 4. 边界与纪律

- 外部复评依据的是对话贴出的修订内容与指令摘录，**未独立读取全文**；全文一致性由本报告维护方逐处核对，不表述为「独立复核全文」。
- 推断、较强推断、已确认分开写；未执行的事项标「未执行」，不把结构发现写成「内核入口已闭合」。
- 项目暂停 = 暂停设备实验与漏洞利用研究；不排除将来做纯静态证据整理。
- 主报告不再追求版本号；只有 13.7 的证伪条件被实测满足时才重写对应结论。

---

*同步完 · 2026-11-09 22:30 · 下次重启计划从本文件第 1、2 节开始*
