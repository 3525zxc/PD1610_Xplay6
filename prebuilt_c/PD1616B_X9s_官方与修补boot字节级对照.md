# X9s（PD1616B）官方 boot / 修补 boot / 处理后 devinfo 字节级对照

> 日期：2026-11-10 09:38（**2026-11-10 午后修订**：按外部复评审见做证据分级修正与归因范围放宽，见 §0 表与 §5；新增 P0 静态闭合指向 §0 末）
> 来源：用户从酷安 `feed/68575979`、`feed/69323250` 的分享链接下载并提供的三份文件
> 范围：**纯离线只读**。只解析文件字节，未执行任何刷机工具、未解压执行文件、零设备操作、零刷写。
> 状态：主报告 `Xplay6_最终报告_v7.md` 保持 v7.4（1046 行）封存不动；本文为独立简报。

---

## 0. 结论速览

| # | 结论 | 状态 |
|---|---|---|
| 1 | X9s 官方 boot 的签名是标准 AOSP `BootSignature`，`SHA256(boot[:L] ‖ DER(attrs))` 与 RSA 恢复摘要逐字节一致 | **已确认**（第 6 份命中，跨 MSM8976 / Android 8.1） |
| 2 | X9s 官方 boot 证书与 PD1516A（Xplay5S 旗舰版 / MSM8996）**963 字节逐字节相同** | **已确认**（跨 SoC 复用同一把公钥） |
| 3 | 去加密 + Magisk 修补的 boot **完全无签名尾部**，`L == 文件大小` | **已确认**（`/boot`、OID、证书、AVB0 全 0 命中） |
| 4a | 该份修补镜像**字节上无签名**；教程把「先解 BL」列为前置；作者公开表述其解锁 X9s 并成功 root | **已确认**（各自独立：字节层 / 教程原文 / 作者公开表述） |
| 4b | 「**这一份下载到的镜像**在 X9s 实机上启动成功」 | **未验证**（无实机、无该机日志；只有公开材料旁证，不与 4a 混同） |
| 4c | 「X9s aboot 在解锁态跳过 `verify_image`」 | **未验证的机制推断**（未取得 X9s/PD1619 官方 aboot，未反汇编其解锁分支；也不排除签名缺失时走另一条装载分支） |
| 5 | X9s 与 PD1610 同样解锁、验签结果相反 → 差异**最可能**位于 bootloader 验证策略层（aboot 为首要排查对象，但上游启动阶段、硬件信任根配置、devinfo 状态编码差异均不能先验排除） | **较强推断**，直接支持 U1 |
| 6 | X9s `devinfo` 的 `0xe0–0x1ff` 含一段来源不明的 Thumb-2 代码 blob | **现象已确认，来源未定性** |

**对项目的影响**：13.4 四条重启条件一条不满足，**目标 A 仍无可行入口**。本轮没有找到绕过 PD1610 验签的方法，但把「跨机型差异」从猜测收敛到了「aboot 的解锁态判断/验签调用链」，且给了一条新的纯离线比对路径（第 6 节 P1）。项目仍暂停。

---

## 1. 输入材料与校验

| 文件 | 路径 | 大小 | SHA256 |
|---|---|---|---|
| X9s 官方 boot 8.20.30 | `D:\16\boot.img` | 36,410,602 B | `24a123c6b2b1da0765cef4bae765fa14d9d45bdff6f891b4ee12f04a5c974004` |
| 去分区加密 + Magisk 23.0 修补 boot | `C:\Users\Tse\Downloads\boot_vivo_x9s_mount_allowed-Magisk23000Patched.img` | 36,681,728 B | `23261722c1eabd2345d8d8134dd930aa6e916049f6cbc14f6b66ab48d306d666` |
| 处理后 devinfo（8.20.30） | `D:\16\devinfo.img` | 16,777,216 B | `abd363d4efe6e08e8ed1a7da2d6a7ac4d63064af9990d086dcc3fff36223f2dd` |

前两份头 8 字节均为 `ANDROID!`（真 Android boot 镜像）；第三份为 16 MB 分区 dump，头 `ANDROID-BOOT!`。

两个 boot 的 cmdline 均含 `product.version=PD1616B_A_8.20.30`、`fingerprint.abbr=8.1.0/OPM1.171019.019`、`androidboot.securebootkey=alpha`。

---

## 2. 官方 boot：AOSP BootSignature 第 6 份命中

按 `BootSignature.getSignableImageSize()` 计算：

```
page=2048, kernel=33,299,470, ramdisk=3,106,401, second=0, header_ver=0
L = align(page + align(kernel) + align(ramdisk)) = 0x22B9000 (36,409,344)
file_size - L = 1258                        ← 尾部正好是签名块
```

`L` 处 DER 外 `30 82 04 E6`（长度 1254，含头共 1258 B），`DER end == file_size`，**签名块精确占满文件尾**，没有多余填充。子节点：

| 偏移 | 标签 | 长度 | 内容 |
|---|---|---|---|
| `L+0x004` | INTEGER | 1 | `01`（formatVersion） |
| `L+0x007` | SEQUENCE | 959 | X.509 证书 |
| `L+0x3CA` | SEQUENCE | 11 | `sha256WithRSAEncryption` OID |
| `L+0x3D7` | SEQUENCE | 13 | `300d13052f626f6f740204022b9000` = `SEQUENCE{PrintableString "/boot", INTEGER 0x22B9000}` |
| `L+0x3E6` | OCTET STRING | 256 | RSA-2048 签名 |

> **修正一处旧表述**：签名偏移不是固定 `L+0x400`。PD1610 观测到 `L+0x400` 是因为其证书长度不同；X9s 为 `L+0x3E6`。签名位置由 DER 内证书长度决定，应按 TLV 解析，不能硬编码偏移。主报告 v7.4 封存不动，此处只作适用范围说明。

独立重编码 `DER(SEQUENCE{"/boot", L})` 与镜像内字节**逐字节相同**。

```
RSA verifyrecover → SHA-256 DigestInfo
target digest      = 062b260d5346706b818762bccf1a413c50c46fd78664a1eb95aee7f1a19bb619
SHA256(boot[:L] ‖ DER(attrs)) = 062b260d5346706b818762bccf1a413c50c46fd78664a1eb95aee7f1a19bb619  ** MATCH **
```

控制变体全部不匹配：`boot[:L]` 单独、`attrs‖boot[:L]`、只拼 attrs 内容、去 SEQUENCE 头、`L±2048`。

**意义**：AOSP BootSignature 哈希模型在 **6/6 份镜像**上成立，覆盖 MSM8996 与 MSM8976 两个平台、Android 6.0.1 / 7.1 / 8.1 三个代际、两把不同证书。此前 5/5 的结论是跨机型一致的，不是巧合；vivo 没有在哈希输入里加私有混淆。

---

## 3. 证书：X9s 与 PD1516A 逐字节相同

| | X9s 官方 boot 8.20.30 | PD1516A 7.7.6 |
|---|---|---|
| 证书 SHA256 | `4b063c75a854b75db5975608407996db9e79fe493678319e24be109725fbbf9f` | 同左 |
| 证书长度 | 963 B | 963 B |
| 字节级相同 | ✅ | — |
| subject | `C=CN, ST=GD, L=SHENZHEN, O=vivo, OU=scm, CN=scm` | 同左 |
| serial | `D13D9D1EDA09F4BD` | 同左 |
| RSA modulus | `A5CEEE3D7AA07851…` | 同左 |

对照 PD1610：证书 SHA256 `8a1ee2d0…`、`OU/CN=scm_beta`、serial `F2EC2903803243F0`、modulus `E1146086…`，**另一把密钥**。

**新事实**：vivo 的 boot 签名证书不是按 SoC 平台划分的——MSM8976 的 X9s 与 MSM8996 的 PD1516A 共用同一张 `scm` 证书，而同为 MSM8996 的 PD1610 用 `scm_beta`。因此 X9s 与 PD1610 的验签结果差异**不能归因于证书或信任根标识**，差异最可能位于 bootloader 的验签策略层；aboot 是首要排查对象，但上游启动阶段 / 硬件信任根配置 / devinfo 状态编码差异不能先验排除（与第 5 节结论一致）。

仍未发现任何私钥；证书可公开提取，与私钥泄露无关。

---

## 4. 修补 boot：无签名，改动全在内容层

```
size = 36,681,728 = 0x22FB800
L    = 0x22FB800   →  L == file_size，L 之后 0 字节
/boot 0 命中 | sha256WithRSA OID 0 | 证书 0 | AVB0 0
（全文件 `30 82` 123 处均为压缩内核/ramdisk 数据中的伪命中；官方 boot 的 `/boot` 在 0x22B93DB 仅 1 处）
```

ramdisk 为 gzip，解压后逐项对照：

| 检查项 | 官方 | 修补后 | 说明 |
|---|---|---|---|
| 解压后大小 | 8,320,000 B | 8,730,884 B | Magisk 注入 |
| `forceencrypt=footer` | **1** | **0** | `fstab.qcom` 的 `/data` 行已删 → 去 FDE 坐实 |
| `forceencrypt`（总） | 3 | 2 | 剩下的是属性名，非挂载标志 |
| `magisk` | 0 | 55 | Magisk 23.0 修补 |
| `suu` | 0 | 1 | vivo 内核拦截 `su` → 改名 `suu` |
| `skip_initramfs` | 0 | 2 | system-as-root 相关 |
| kernel / ramdisk 长度 | 33,299,470 / 3,106,401 | 33,279,353 / 3,399,663 | 均被改动 |

**未验证项**：教程给的 `magiskboot hexpatch kernel 0092CFC2C9CDDDDA00 → 0092CFC2C9CEC0DB00`，这两个字节串在两份 kernel 区里**都 0 命中**。可能是针对不同内核版本 / `kernel_dtb` 区，或该成品用了别的绕挂载方式；此处标**未执行/未验证**，不据此否定教程，也不把它写成本镜像的改动证据。

---

## 5. 核心判定：解锁态验签策略差异已做成字节级证据链

| 环节 | 证据 |
|---|---|
| 官方 boot 需要签名 | 第 2 节：完整 DER + RSA 签名，密码学验证通过 |
| 修补 boot 没有签名 | 第 4 节：`L == size`，签名结构 0 命中 |
| 修补 boot 被修改的是内容 | 第 4 节：fstab / kernel / ramdisk / Magisk |
| 该无签名镜像被启动 | 教程与 release 公开说明；PD1619 release 安装指南第 1 条即 `Unlock your Bootloader first`，X9s 教程先解 BL 再刷此 boot |
| PD1610 的反例 | `is_unlocked=1`、`oem device-info` 两项 true、`fastboot flash` 放行；改 boot 一字节即 5s 卡 logo，且 `bootsig_experiments_verify.py` 已证明三个单字节实验镜像签名 **INVALID** |

**证据分级**（修正表述：镜像存在 ≠ 该镜像被证明实机启动）：

| 命题 | 证据等级 |
|---|---|
| 修补镜像无签名（字节层） | **已确认**（本文件第 4 节） |
| 教程把「先解 BL」列为前置条件 | **已确认**（教程原文） |
| 作者公开表述其解锁 X9s 并 root 成功 | **已确认**（公开表述） |
| **这份下载到的镜像**在 X9s 实机上启动 | **未验证**（无实机、无该机启动日志） |
| X9s aboot 解锁态跳过 `verify_image`（机制） | **未验证**（无 X9s/PD1619 官方 aboot；亦不排除签名缺失走另一装载分支） |

**对 PD1610 的价值**：两款机型签名格式相同（都是 AOSP BootSignature）、哈希算法相同、X9s 甚至与 PD1516A 共用证书。差异**最可能**位于 bootloader 验证策略层——aboot 的解锁态控制流是首要排查对象，但上游启动阶段 / 硬件信任根配置 / devinfo 状态编码差异不能先验排除。这把 U1（`0x9183E398` 两分支 → 最终内核入口）和 11-08 日志里 `0x91839958` `"Device is unlocked! Skipping verification..."` 分支的优先级抬到最高：**要解释的差异不在密码学，在控制流**。

**2026-11-10 午后更新**：P0 已纯离线完成静态闭合——`0x91839958` 所在函数在盘上 7.13.15 build 定位为 `0x91839944`（xref `0x918399A4/A8`），解锁态语义为「设 boot_state=1 + 打日志」，验签调用本身不被跳过；解锁态绕过的是 RED 升级的表现层（无 Security Error 屏、无 30s、无关机尝试）。**但第二轮复核发现：验签失败的最终拦截是 tampered assert 重启循环（`is_tampered=1` → ASSERT(0) → platform_halt(reboot)），锁定/解锁一视同仁**——「解锁+验签失败=继续启动」在 PD1610 7.13.15 上**不成立**。X9s 能启动无签名 boot 说明其 aboot 必然缺少/改写这条链，P3 价值升级为定位真正的行为分叉点。详见独立补充记录《PD1610_解锁跳过验签分支P0静态闭合_补充记录.md》（§10）。

---

## 6. devinfo 字段对照与一段未解释的代码

```
X9s 处理后   414e44524f49442d424f4f5421 000000 ff000000 00000000 ff000000 00000000
PD1610 UL    414e44524f49442d424f4f5421 000000 01000000 00000000 00000000 00000000
PD1610 ULC   414e44524f49442d424f4f5421 000000 01000000 00000000 01000000 00000000
PD1610 orig  414e44524f49442d424f4f5421 000000 00000000 00000000 00000000 00000000
```

- magic 相同（`ANDROID-BOOT!`）→ 结构同源。
- X9s 的 `0x10 = 0xff`、`0x18 = 0xff`；PD1610 的 `UL`/`ULC` 实验用 `0x01`。aboot 通常按「非零即真」判断，且 PD1610 写 1 后 `oem device-info` 已返回 true；但**不能排除某些实现严格判 `==1`**，这是 PD1610 上没测过的变量，登记为线索，不写成差异原因。
- **2026-11-10 午后更新（P2 静态闭合）**：PD1610 boot 路径上的解锁判定点（7.13.15 build `0x91839944` 函数）反汇编为 `ldr r0,[devinfo+0x10]; cmp r0,#0; bne 解锁分支` —— **任何非零值（0x01 或 0xFF）都会被判定为已解锁**。devinfo 缓存指针全局 `0x9192BBDC` 共 27 处使用点（集中在 fastboot 区域），未逐一枚举完；`0x01` 与 `0xFF` 在 boot 判定上等价这一点已按指令级确认，其余消费点留作余量。
- X9s devinfo 只有前 0x200 字节有数据（279 个非零字节），其后全零；本地 PD1610 样本只有 4096 B 回读，因此**不能断言 PD1610 devinfo 后段为空**。

**未解释部分**：`0xE0` 起是 `01 00 00 00` + 13 个 u32（`0x23CB3`…`0x69678`），`0x118` 起是典型 Thumb-2 函数入口：

```
2de9f04f   push.w {r4,r5,r6,r7,r8,sb,sl,fp,lr}
03af       add    r7, sp, #0xc
a7b0       sub    sp, #0x9c
dff888a9   ldr.w  sl, [pc, #0x988]
...
```

按 Thumb-2 解码连续 48 条均为合法指令（`push.w` / `ldr.w` / `it` / `cmphs` / `blx` / 栈帧操作），按 A32 解码全是无意义指令 → 不是随机数据。用 16 / 32 / 64 B 探针在本地 5 份 aboot（PD1610 三份、PD1516A 两份）中检索**全部 0 命中**，来源不明。

**不写成「漏洞利用 payload」**：也可能是该机 devinfo 分区里的校验数据恰好含代码片段、工具写入的额外数据、或 dump 时混入相邻分区内容。需要 X9s 官方 aboot 才能定性。本轮标**现象已确认、来源未定性**。

---

## 7. 待办（评审重排后；均标注执行状态）

| 优先 | 事项 | 状态（2026-11-10 午后） |
|---|---|---|
| **P0** | 定位 `Device is unlocked! Skipping verification...` 交叉引用，追踪前置判断、被跳过的函数与后续目标；确认是否在实际 boot 装载路径、是否跳过 BootSignature 验签 | **纯离线完成静态闭合（含第二轮复核）**：xref=`0x918399A4/A8`（7.13.15），函数=`0x91839944`，调用者=`0x9183E2B8`（boot 装载主函数内）；解锁态=设 `boot_state=1`+打日志，**不跳过验签调用本身**；解锁只绕过 RED 升级的表现层，**验签失败的最终拦截是 tampered assert 重启循环（`is_tampered=1`→ASSERT(0)→关中断→reboot），与解锁状态无关**；G 在失败时永不返回，调用侧分支仅验签成功可达。详见补充记录 §10 |
| **P1** | PD1516A 两份 aboot 反汇编，检查 `verify_image` 调用者是否读 `is_unlocked` | **纯离线完成（2026-11-10 11:20，函数级判据）**：两份 build 均为**旧架构**——385 解锁态**结构性跳过验签**（`0x91633694` 解锁≠0 直接走装载，G-385 `0x916305D8` 仅锁定分支可达）；776 验签门存根 `0x91831AA4` 恒返 1、验签调用点不可达；锁定+失败仅打印 "Device is tampered. Asserting.."（**无 ASSERT**，尾调 dprintf `0x91640D80` 返回继续装载）；无 boot_state/RED 机制（`boot_verifier.c`/`KEYSTORE`/QSEE 字符串全缺）。跨机型分叉点=验签架构代际差，详见补充记录 §11 |
| **P2** | PD1610 devinfo 字段精确比较逻辑（0x01/0xFF/0x18） | **boot 判定点已闭合**：`cmp #0/bne`，任意非零=解锁（见第 6 节更新）；fastboot 侧 27 个 devinfo 使用点未逐一枚举 |
| **P3** | 取得 X9s / PD1619 官方 aboot | **未执行**（需外部资源） |
| **P4** | 定性 X9s devinfo `0xE0–0x1FF` Thumb-2 数据段 | **保持中性**（现象已确认、来源未定性，不写成利用 payload） |
| 保留 | U1 尾段：`0x9183E398` 两分支 → 验签成功 `E5B8` 返回 / 失败+解锁 `EAC0` 警告后回 `E3BC` → `0x91810E84(is_unlocked)` 按 boot_state 四路分派 → 下游函数（`0x9183E5D4` 起，含候选跳核 `0x9183E81C`） | **主干已通**，剩余仅下游函数内部细节 |

**13.4 四条重启条件**（认证通过的免验签 aboot / 匹配的签名私钥 / UART / 已确认存在于本 build 的 LK 内存破坏 CVE）**一条都不满足**。

---

## 8. 边界、产物与复现

**未执行**：任何设备操作、刷写、刷机工具；X9s / PD1619 官方 aboot 与 stock boot 未取得；kernel hexpatch pattern 未命中故未验证；devinfo 代码段未定性；「无签名 boot 能启动」依据教程与 release 公开说明，本机未实机验证 X9s。

**主报告** `Xplay6_最终报告_v7.md` 仍为 1046 行 v7.4 归档版，一字未改。

| 产物 | 路径 |
|---|---|
| 文件清点 / 结构解析 | `C:\qfilx\exp\x9s_probe.py` → `C:\qfilx\compare\pd1616b\x9s_probe_result.txt` |
| BootSignature 验签、证书比对、devinfo 框架 | `C:\qfilx\exp\x9s_bootsig_verify.py` → `x9s_bootsig_verify_result.txt` |
| fstab / Magisk / kernel 改动核实 | `C:\qfilx\exp\x9s_patch_verify.py` → `x9s_patch_verify_result.txt` |
| devinfo 代码段反汇编 | `C:\qfilx\exp\x9s_devinfo_code.py` → `x9s_devinfo_code_result.txt` |
| 上一轮下载受阻的证据 | `C:\qfilx\compare\pd1616b\download_blocked_page.html`、`lz_file_page.html`、`lz_api.json` |

复现：`cd C:\qfilx\exp && python3 x9s_bootsig_verify.py`（依赖 `openssl`、Python 3）；devinfo 反汇编另需 `capstone`。
