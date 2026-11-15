# Xplay6（PD1610）vs Xplay5S（PD1516A）同平台固件信任配置对照

- 日期：2026-11-09
- 范围：**纯离线静态分析**，零设备操作、零刷写、零注入
- 主报告 `Xplay6_最终报告_v7.md` 保持 v7.4 归档版不变，本文件为独立对照简报
- **⚠ 2026-11-10 09:06 修订**：原文第 0 节第 6 点、第 5、6、7 节关于「实际 SHA‑256 输入仍未闭合」
  的结论 **已被闭合**。AOSP `BootSignature.java` 的 `generateSignableImage` 给出
  `signable = boot[:L] + DER(authenticatedAttributes)`，5/5 份镜像 `SHA256(signable)`
  与 RSA 恢复摘要逐字节一致。详见 `PD1610_哈希输入闭合与BootSignature标准格式.md`。
  旧候选全失败的原因：试的都是 `L` 起始的连续区间，而真实输入含**重新编码、非连续**的认证属性。
- **⚠ 2026-11-10 09:38 修订**：新增第 6 份镜像——X9s / PD1616B（MSM8976 / 8.20.30）
  官方 boot 的 `SHA256(boot[:L] ‖ DER(attrs))` 同样命中 AOSP 模型，且其 boot 证书
  与 **PD1516A 963 字节逐字节相同**（`4b063c75…`）。即 vivo 的 boot 签名证书**不按 SoC 划分**：
  MSM8976 的 X9s 与 MSM8996 的 PD1516A 共用 `scm`，PD1610 单独用 `scm_beta`。
  另：签名偏移不是固定 `L+0x400`（X9s 为 `L+0x3E6`，由证书长度决定），须按 DER TLV 解析。
  详见 `PD1616B_X9s_官方与修补boot字节级对照.md`。
- 触发：外部评审找到 PD1516A（Xplay5S 旗舰版 / 骁龙 820，与 PD1610 同 SoC）官方固件直链，建议比对证书 DER、RSA modulus 与签名结构；评审环境无法下载，本轮直接取包验证

---

## 0. 结论速览

1. **评审提出的关键判据被证伪**：PD1516A 与 PD1610 的 boot 签名证书 **不是同一张，RSA modulus 也不同**。
   PD1610 = `OU/CN=scm_beta`，`E1146086…`；PD1516A = `OU/CN=scm`，`A5CEEE3D…`。
   两机型同 SoC、同签名结构，但**不复用同一把 boot 签名公钥**。
2. **签名结构完全同构**：两机型 boot 尾部都是
   `SEQUENCE { INTEGER 1, X.509 cert, sha256WithRSA OID, params("/boot", INTEGER L), OCTET STRING 256B sig }`，
   签名数据在本文两机型均位于 `L+0x400`（该偏移随证书长度变化，X9s 为 `L+0x3E6`，须按 DER TLV 解析）。DER 里的 `INTEGER` 字段在 5 份镜像上**全部精确等于** `L = page_size + ALIGN(kernel) + ALIGN(ramdisk)`，跨机型、跨版本成立。
3. **PD1610 的「aboot 内嵌公钥」结论得到字节级独立复核**：1.15.1 / 8.19.16 / 16 MB 分区 dump 三份 aboot 中，都完整内嵌了与 boot 尾部**字节级相同**的 `scm_beta` 证书（985 B，SHA256 `8a1ee2d0…`）。
4. **PD1516A 的 aboot 信任配置是另一代**：内嵌 `General vivo root CA` / `attestation CA`（非 beta）与一张 `C=US, ST=CA, O=Android LK` 证书；**未发现**其 boot 尾部 `scm` 证书、序列号或 modulus 前缀，也没有 `scm_beta` 字符串。
5. **OTA 包签名证书是第三把密钥**，不能与 boot 验签混淆：两包 `META-INF/com/android/otacert` 字节相同，`OU/CN=scm`、`B96ADA8B…`，与 PD1516A boot 尾部证书同名但 modulus 不同。
6. 5/5 份镜像的签名都能用其证书公钥恢复出标准 SHA‑256 DigestInfo；`sha256(d[:L])` 等 9–10 个连续区间候选全部不匹配，但 **2026-11-10 已按 AOSP 标准模型闭合**：`SHA256(boot[:L] + DER(attrs))` 在 5/5 份镜像上与恢复摘要逐字节一致（跨两机型、跨 Android 6.0.1/7.1/8.1）。

---

## 1. 样本与来源核实

两条 vivo 官方直链均可访问、返回 `Accept-Ranges: bytes`；本轮用 HTTP Range 读取 ZIP 尾部目录 + 目标条目的压缩数据，**没有下载 2 GB 整包**，逐条按 ZIP 目录 CRC32 校验通过。

| 包 | Content-Length | 条目数 | 状态 |
|---|---|---|---|
| `PD1516A_A_7.7.6-update-full_1554110230.zip`（7.1 升级包） | 2,086,404,920 | 67 | 可访问 / Range 正常 |
| `PD1516A_A_3.8.5_for7.1-wipe-update-full-2017081415.zip`（降级包） | 1,689,157,587 | 40 | 可访问 / Range 正常 |
| `Vivo_Xplay_5S_PD1516A_24052016_QFIL.zip`（第三方索引，3 GB，Drive 镜像） | — | — | **未下载**，页面未给哈希 |

提取出的文件（SHA256 为解压后实测）：

| 文件 | 大小 | SHA256 | ZIP CRC32 |
|---|---|---|---|
| `pd1516a_776/boot.img` | 14,673,130 | `7cd8c019bfe8adb5a43a89d4510ee46ef674650d06d6d5c593a8f259ab99d3d2` | `5daaf353` |
| `pd1516a_776/emmc_appsboot.mbn` | 3,579,688 | `f5cc0ee8c9c6fa9774520acafc3ef5b140b6069f41054f17ced3b09313d5305d` | `df26e8bb` |
| `pd1516a_776/otacert` | 1,367 | `74f9199965aced5f9965ad26ae7a56bb5c33e6ec05fa93775ef689b76118714a` | `de0e5a98` |
| `pd1516a_385/boot.img` | 34,354,410 | `67f3e7ec7ddb6e68b0e886872c5d2e97928de622fa765c25148f221db8adb51e` | `4b2f9f0d` |
| `pd1516a_385/emmc_appsboot.mbn` | 3,670,512 | `30ee664087dfbc25d32fbed2b5f8ba6ed8443cd1273f892926dca62a07e55a49` | `386315f3` |
| `pd1516a_385/otacert` | 1,367 | `74f91999…`（与上者字节相同） | `de0e5a98` |

PD1610 本地基线（既有样本，本轮重新计算指纹）：

| 文件 | 大小 | SHA256 |
|---|---|---|
| `aboot/RESCUE/aboot_official_1.15.1.mbn` | 4,015,920 | `09990c24f63c5b6fb6ab32af65ad180fce8350d640f8a67b74ef35eb0d06e3c8` |
| `firmware/81916/emmc_appsboot.mbn`（8.19.16） | 3,173,696 | `fe535256b3e90cb6d4c3fd2f9b7ea734d87366b5af90d22acd1befde24c15c64` |
| `firmware/8199/emmc_appsboot.mbn`（8.19.9） | 3,173,696 | `7f21823d48ffab4aabbded6161000b8dbfd5839b5e2070446cef28fd5d0d5a0e` |
| `aboot/RESCUE/aboot_full_orig.bin`（16 MB 分区 dump） | 16,777,216 | `b4d75a9b399a8d28b8bd7ff7c68994beadab708ed3d23d4c399095788efc3c5f` |
| `boottest/boot_00_baseline.img`（1.15.1） | 52,790,528 | `17b2de9f135991f606c01fe9286471e67b8014410f18a383ed5c4f318012f361` |
| `firmware/81916/boot.img`（8.19.16） | 58,729,728 | `5a03236df43fb4badeb234e6c9b2ffeead9161ca77e71115b6c923c613d48a52` |
| `exp/boot_stock.img` | 14,884,864 | `19f79da4f3544ee1c7312d068b6ff43e44120f5b86918e451a784e26973f8a41` |
| `firmware/boot115/verity_key` | 524 | `f16f3691ce1e667856add1ddb651b24a023de88cb75b686d45309f6dd88cad5c` |

两机型 aboot 文件哈希**无一相同**；PD1610 各版本 aboot 也不相同。

---

## 2. boot 尾部签名结构对照（按 Android header 定位，非文件末尾）

`L` 由 header 独立算出：`page_size + ALIGN(kernel_size) + ALIGN(ramdisk_size)`（second/dt 均为 0）。DER 起点正是 `L`，**不在镜像最后 4 KB**（那里是填充区）。

| 项 | PD1610 1.15.1 | PD1610 8.19.16 | PD1610 stock | PD1516A 7.7.6 | PD1516A 3.8.5 |
|---|---|---|---|---|---|
| L | `0x3257000` | `0x3801000` | `0xe30000` | `0xdfd000` | `0x20c2000` |
| params 内 INTEGER | `03 25 70 00` | `03 80 10 00` | `00 e3 00 00` | `00 df d0 00` | `02 0c 20 00` |
| 外层 SEQUENCE 长度 | 1276 | 1276 | 1276 | **1254** | **1254** |
| 证书长度 | 985 | 985 | 985 | **963** | **963** |
| 算法 OID | `sha256WithRSA` | 同左 | 同左 | 同左 | 同左 |
| OCTET STRING 偏移 | `L+0x3FC`（数据 `L+0x400`） | 同左 | 同左 | 同左 | 同左 |
| 签名长度 | 256 | 256 | 256 | 256 | 256 |
| `L` 之后剩余字节 | 5376 | 5376 | 8192 | 5354 | 5354 |

- 一级子元素实测（PD1610 1.15.1）：`INTEGER 1` / `cert(981)` / `SEQUENCE(11)=300b06092a864886f70d01010b` / `SEQUENCE(13)=300d13052f626f6f74020403257000` / `OCTET STRING(256)`。
- PD1516A 对应位置为 `300d13052f626f6f74020400dfd000` 与 `…02040 20c2000`，即 `PrintableString "/boot"` + `INTEGER L`。
- **5 份镜像的 INTEGER 全部 == L**，这是既有报告「长度模型」的跨机型、跨版本加强证据；但它只说明**签名结构里声明的长度**，不等于 RSA 实际哈希的输入范围（见第 6 节）。
- DER 之后仍有非零数据 + 零填充；4 份 OTA/基线镜像的最后 4 KB 呈「前 256 B 非零 + 3840 B 零」，`boot_stock.img` 例外（多一页、末字节非零）。该差异未解释。

---

## 3. 证书与 RSA modulus 对照

| 机型 / 版本 | boot 尾部证书 SHA256 | Subject / Issuer | Serial | Modulus 前 32 hex | 公钥 PEM SHA256 |
|---|---|---|---|---|---|
| PD1610 1.15.1 / 8.19.16 / stock（三份**完全相同**） | `8a1ee2d0b1ea378d43e27e20e9ec0b34986c9693a16973e3260f1652d2559e3a` | `O=vivo, OU=scm_beta, CN=scm_beta`（自签） | `F2EC2903803243F0` | `E1146086D08BE59EEF00E460C311BFEE` | `617ddc249d3a29accc877d45ec7e513dcb87b3401031e194750a7ec3e37218c8` |
| PD1516A 7.7.6 / 3.8.5（两份**完全相同**） | `4b063c75a854b75db5975608407996db9e79fe493678319e24be109725fbbf9f` | `O=vivo, OU=scm, CN=scm`（自签） | `D13D9D1EDA09F4BD` | `A5CEEE3D7AA078514AF946405CAF0CBF` | `d78b147c7e8a8def8cfff552db9ee6aeefcfb8d2541c93408b512ddd37e16e80` |
| PD1516A 两包 `otacert`（OTA 签名，非 boot 验签） | `973e2e8ca844249ea94cda3015397547cdf41924b1fdec1690b3ee907ca23958`（DER） | `O=vivo, OU=scm, CN=scm, email=vivo@vivo.com.cn` | `B886FE8126CD2DFE` | `B96ADA8B7D702096BEF6E03D7B2EAE6B` | — |

交叉搜索（在全部 5 份 boot + 5 份 aboot 中查证书全字节 / 序列号 / modulus 前 16 B）：

- PD1610 证书 → 只出现在 PD1610 自己的 3 份 boot 与 3 份 aboot 中；PD1516A 任何文件 **0 命中**。
- PD1516A 证书 → 只出现在 PD1516A 自己的 2 份 boot 中；PD1610 任何文件 **0 命中**，PD1516A 两份 aboot 也 **0 命中**。
- 结论：**两机型不共用 boot 签名公钥**；各自跨版本复用自己的那一张证书。
- 证书自身的签名算法是 `sha1WithRSAEncryption`（`2a864886f70d010105`），与外层 boot 签名机制的 `sha256WithRSA` 是两件事。

---

## 4. aboot 内嵌证书清单（openssl 逐张解析）

| 文件 | 内嵌证书（文件偏移 / Subject / Serial / Modulus 前缀） |
|---|---|
| PD1610 aboot 1.15.1 | `0x165B` General vivo attestation **beta** CA (`C04BDB0E…`)；`0x1A3F` General vivo root **beta** CA (`AD8A2398…`)；`0x80FE5` **scm_beta** (`E1146086…`, `F2EC2903803243F0`) |
| PD1610 aboot 8.19.16 | 同上三张，位置 `0x165B` / `0x1A3F` / `0x83F15` |
| PD1610 aboot dump 16 MB | 同上三张，位置 `0x164B` / `0x1A2F` / `0x81059` |
| PD1516A aboot 7.7.6 | `0x164C` General vivo attestation CA (`D08F1FE7…`)；`0x1A1C` General vivo root CA (`DE29D9E8…`)；`0x78334` **`C=US, ST=CA, O=Android LK`** (`C8820943…`, serial `05`) |
| PD1516A aboot 3.8.5 | 同上三张，位置 `0x164C` / `0x1A1C` / `0x72758` |

附加事实：

- PD1610 aboot 中 `scm_beta` 证书（985 B）与 boot 尾部证书**字节级完全相同**，SHA256 同为 `8a1ee2d0…`。→ 独立复核了「验签公钥内嵌于 aboot」。
- PD1516A aboot 中：`scm_beta` 字符串 0 命中；其 boot 尾部 `scm` 证书、序列号、`A5CEEE3D…` 模数前缀均 0 命中。→ **PD1516A 的验签公钥来源与 PD1610 不同**，本轮未继续追其来源。
- `C=US, ST=CA, O=Android LK` 这张证书是否为 LK/AOSP 自带公开测试密钥，**未核实**；此处只记录 subject 与指纹，不推断私钥可得性。
- 未对 PD1516A aboot 做 `verify_sig` 反汇编（本轮未执行）。

---

## 5. 签名可验证性（离线 RSA 恢复，不涉及设备）

对 5 份镜像各自用「boot 尾部证书 → 公钥」对 256 B 签名做 `openssl pkeyutl -verifyrecover -pkeyopt rsa_padding_mode:pkcs1`：

| 镜像 | 恢复结果 | 目标摘要（前 16 hex） | `sha256(d[:L])` 是否命中 |
|---|---|---|---|
| PD1610 1.15.1 | 51 B `3031300d…0420` + 32 B | `1cf2d759c00f4761…` | 否 |
| PD1610 8.19.16 | 同上 | `3d36776e08863ac1…` | 否 |
| PD1610 stock | 同上 | `e1aa702eca8ec163…` | 否 |
| PD1516A 7.7.6 | 同上 | `d2d9c86360c8c182…` | 否 |
| PD1516A 3.8.5 | 同上 | `7f027cf7b0589afd…` | 否 |

- **5/5 恢复成功**：证明证书内公钥确为对应签名的验签公钥，且两机型都用 PKCS#1 v1.5 + SHA‑256 DigestInfo。
- 测试的哈希输入候选（9–10 个）：`d[:L]`、`d[:L+0x3FC]`、`d[:L+0x400]`、`d[:L+DER长度]`、`d[:L+0x500]`、`d[:L+0x600]`、`d[0x100:L]`、`d[0x240:L]`、header 尺寸字段清零变体 —— **全部不匹配**。
- **2026-11-10 闭合**：这些全是「`L` 起始的连续区间」，而 AOSP `BootSignature.java` 的 `generateSignableImage` 追加的是**重新编码的认证属性** `DER(SEQUENCE{PrintableString "/boot", INTEGER L})`（PD1610 1.15.1 = `300d13052f626f6f74020403257000`，15 B）。`SHA256(boot[:L] ‖ attrs)` 在 5/5 份镜像上命中；去掉 SEQUENCE 头、顺序颠倒、`L±page`、单独 `boot[:L]` 等 8 个控制变体全不匹配。长度模型仍只是 DER 声明的长度，但**哈希输入已确认**。

---

## 6. 对原项目的影响

| 评审设想 / 路线 | 本轮判定 |
|---|---|
| 「若 PD1516A 与 PD1610 boot 尾部 modulus 相同 → 两机型复用同一签名公钥」 | **证伪**：`E1146086…` ≠ `A5CEEE3D…`，证书 SHA256 也不同 |
| 「同平台机型的证书 / 私钥可借来签 PD1610 的 boot」 | 对 PD1516A 这一样本**关闭**；未发现任何私钥 |
| 「PD1610 aboot 内嵌公钥验签」 | **加强**：aboot 与 boot 尾部证书字节级一致，且给出精确文件偏移 |
| 「长度模型 `L = page_size + ALIGN(kernel)+ALIGN(ramdisk)`」 | **加强**：DER params INTEGER 在 5 份镜像上全部精确等于 L（跨 2 机型 / 5 版本） |
| 「实际 SHA‑256 输入」 | **2026-11-10 已闭合**：`SHA256(boot[:L] ‖ DER(attrs))`，5/5 命中；确实不是简单前缀 |
| 主报告 v7.4 的核心结论 | **不变**：设备解锁状态 ≠ 启动信任状态；内嵌公钥验签机制仍成立 |

边界：本轮只否定了 PD1516A 这一个对照样本，**不排除**其他机型、工程固件或调试镜像共用密钥；也不构成「私钥已泄露」或「未泄露」的证明。OTA 签名证书与 boot 验签证书是不同实体，不能互相替代。

---

## 7. 未执行 / 未闭合

1. 第三方 `Vivo_Xplay_5S_PD1516A_24052016_QFIL.zip`（3 GB、Drive 镜像）**未下载**，页面无哈希可核；本轮用 vivo 官方 OTA 包内的 `emmc_appsboot.mbn` / `boot.img` 已足够回答证书与公钥问题。
2. 评审提到的 PD1610 三份 QFIL 固件（`1.17.5` / `1.23.4` / `7.12.35`，onfix.cn）**未取得、页面未核实**。
3. PD1516A aboot 的 `verify_image` / `verify_sig` 反汇编 **未执行**；其验签公钥来源（为何不在 aboot 中找到 boot 证书）**未查明**。
4. `C=US, ST=CA, O=Android LK` 证书是否为公开测试密钥 **未核实**。
5. 实际 SHA‑256 哈希输入 **2026-11-10 已闭合**；DER 之后的非零尾页数据（不在 `boot[:L]` 内、不参与哈希）含义 **仍未解释**。
6. 全程零设备操作、零刷写；主报告 `Xplay6_最终报告_v7.md` v7.4 归档版未改动。

---

## 8. 证据文件与可复现命令

产物目录 `C:\qfilx\compare\`：`probe_result.txt`、`der_result.txt`（一次 TLV 解析脚本崩溃已记录，结论以 `final_result.txt` 为准）、`final_result.txt`、`aboot_certs_result.txt`、`hash_input_result.txt`，以及提取的镜像与各 `cert_*.der`。

```
python C:\qfilx\exp\remote_zip.py list    <官方ZIP直链> 2086404920 "aboot|boot|mbn|\.img"
python C:\qfilx\exp\remote_zip.py extract <官方ZIP直链> 2086404920 C:\qfilx\compare\pd1516a_776 "boot\.img$|emmc_appsboot\.mbn$|otacert$"
python C:\qfilx\exp\remote_zip.py extract <降级ZIP直链> 1689157587 C:\qfilx\compare\pd1516a_385 "boot\.img$|emmc_appsboot\.mbn$|otacert$"
python C:\qfilx\exp\compare_final.py      # L 定位 / DER 结构 / 证书与 modulus
python C:\qfilx\exp\aboot_certs.py        # aboot 内嵌证书枚举
python C:\qfilx\exp\verify_hash_input.py  # RSA 恢复 DigestInfo 与哈希输入候选
```

官方直链：
- `https://sysupwrdl.vivo.com.cn/upgrade/official/officialFiles/PD1516A_A_7.7.6-update-full_1554110230.zip`
- `https://sysupwsdl.vivo.com.cn/upgrade/upload/UpdateFiles/PD1516A_A_3.8.5_for7.1-wipe-update-full-2017081415.zip`

说明：本简报只依据本地实际取到的二进制与 openssl 输出；未把固件索引页列出的文件名、大小或「含某证书」的说法冒充成已验证结果。
