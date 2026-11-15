# PD1610 签名哈希输入闭合与 AOSP BootSignature 标准格式确认

> 日期：2026-11-10 09:06
> 触发：外部复评（用户贴回）指出 PD1619 简报的核心结论需重大修正，并提出 AOSP `BootSignature.java` 的 `generateSignableImage` 哈希模型
> 范围：**纯离线只读**。下载 AOSP 官方源码与 GitHub release 元数据、解析本地 5+7 份镜像、运行本地 openssl/Python；零设备操作、零刷写、未执行任何刷机工具
> 主报告 `Xplay6_最终报告_v7.md` 保持 **v7.4 / 1046 行封存不动**；本文为独立简报，供转发复核

---

## 0. 结论速览

| 复评主张 | 判定 | 证据强度 |
|---|---|---|
| ① PD1610 尾部 DER 不是 vivo 私有格式，是 AOSP `AndroidVerifiedBootSignature` | **成立** | AOSP 源码 ASN.1 定义 + 5 份镜像字段逐字节对应，**已确认** |
| ② 实际哈希输入 = `SHA256(boot[0:L] ‖ DER(authenticatedAttributes))` | **成立，5/5 全部命中** | **已确认（字节级）**，长期未闭合项首次闭合 |
| ③ PD1619 无签名 boot 能启动 = 解锁态放宽验签，不是另一套架构 | **部分成立** | 「先解锁」为 release 原文；「解锁态关闭验签」仍是**较强推断**，未做 PD1619 aboot 反汇编 |
| ④ `alpha`/`beta` 只是信任根标识，不是验签策略分界 | **成立，且本轮补上硬证据** | 三份 aboot 中 `securebootkey`/`keyver` 字符串 **0 命中**，**已确认（静态范围内）** |
| ⑤ 原简报「两代机型用两套不同启动验证架构」 | **不成立，已撤销** | 封装格式同属 AOSP BootSignature 体系；差异在验证策略与证书/信任配置 |

**最重要的一句话（必须先说）**：哈希输入闭合**不是破局进展，反而把验签侧最后一点想象空间封死了**。旧报告保留「实际哈希输入未闭合」，隐含一种可能——aboot 也许在算哈希前对数据做了某种私有规范化，从而存在格式歧义可利用。现在确认：标准 AOSP 算法、标准 ASN.1 封装、标准输入拼接，**没有任何私有混淆**。缺的仍然只有与 aboot 内嵌信任根匹配的私钥，或一条免验签的可执行入口；v7.4 13.4 的四条重启条件一条都不满足。

---

## 1. AOSP 源码逐字核实

源：`https://android.googlesource.com/platform/system/extras/+/refs/heads/main/verity/BootSignature.java?format=TEXT`（HTTP 200，base64 解码后 351 行 / 13,272 B，本地存 `C:\qfilx\exp\BootSignature.java`）。
注：GitHub `aosp-mirror/platform_system_extras` 的 `master`/`main`/`android-8.1.0_r1` 三个 raw 路径均 404，改用 googlesource 官方源。

### 1.1 ASN.1 定义（源码 48–61 行，逐字）

```
AndroidVerifiedBootSignature DEFINITIONS ::=
BEGIN
    formatVersion ::= INTEGER
    certificate ::= Certificate
    algorithmIdentifier ::= SEQUENCE {
        algorithm OBJECT IDENTIFIER,
        parameters ANY DEFINED BY algorithm OPTIONAL
    }
    authenticatedAttributes ::= SEQUENCE {
        target CHARACTER STRING,
        length INTEGER
    }
    signature ::= OCTET STRING
END
```

对应 `BootSignature(byte[] signature)` 解析顺序（源码 107–128 行）：`formatVersion` → `certificate` → `algorithmIdentifier` → `authenticatedAttributes{target,length}` → `signature`。

与 5 份镜像实测 DER children 对照（`C:\qfilx\compare\final_result.txt`）：

| AOSP 字段 | PD1610 1.15.1 实测 | 标签/类型 |
|---|---|---|
| `formatVersion` | `020101` | INTEGER 1 |
| `certificate` | `308203d5…`（985 B，X.509 `OU/CN=scm_beta`） | SEQUENCE |
| `algorithmIdentifier` | `300b06092a864886f70d01010b`（11 B，sha256WithRSAEncryption OID） | SEQUENCE |
| `authenticatedAttributes` | `300d13052f626f6f74020403257000`（13 B，`"/boot"` + L） | SEQUENCE{DERPrintableString, ASN1Integer} |
| `signature` | `04820100…`（256 B） | OCTET STRING |

字段顺序、标签、类型**全部对应**，不是「长得像」。因此旧表述「vivo 自有 DER/RSA 签名格式」需要改正为：**AOSP 标准 BootSignature 封装 + vivo 自有证书/密钥材料 + vivo 自有 aboot 验证策略**。

### 1.2 关键函数（源码 131–188 行，逐字）

```java
public ASN1Object getAuthenticatedAttributes() {
    ASN1EncodableVector attrs = new ASN1EncodableVector();
    attrs.add(target);          // DERPrintableString("/boot")
    attrs.add(length);          // ASN1Integer(L)
    return new DERSequence(attrs);
}

public byte[] getEncodedAuthenticatedAttributes() throws IOException {
    return getAuthenticatedAttributes().getEncoded();     // 完整 DER，含 30 0d 头
}

public byte[] generateSignableImage(byte[] image) throws IOException {
    byte[] attrs = getEncodedAuthenticatedAttributes();
    byte[] signable = Arrays.copyOf(image, image.length + attrs.length);
    for (int i = 0; i < attrs.length; i++) {
        signable[i + image.length] = attrs[i];           // ★ 追加到镜像末尾
    }
    return signable;
}

public boolean verify(byte[] image) throws Exception {
    if (length.getValue().intValue() != image.length) {
        throw new IllegalArgumentException("Invalid image length");
    }
    byte[] signable = generateSignableImage(image);
    return Utils.verify(publicKey, signable, signature.getOctets(), algorithmIdentifier);
}
```

`getSignableImageSize`（200–249 行）给出 `image` 长度：`pageSize + ALIGN(kernel) + ALIGN(ramdisk) + ALIGN(second)`，header v1+ 再加 recovery_dtbo / v2 再加 dtb，最后整体页对齐。本项目 5 份镜像 `second_size=0`、`header_version=0`，故**精确等于既有长度模型 L**。`doSignature`（252–285 行）把 image 截断到 `signableSize` 后签名，`verifySignature`（288–315 行）再取 `Arrays.copyOf(image, signableSize)` 验签。

> 术语澄清（采纳复评）：解包工具报的 `sigtype=AVBv1` 是**旧式 Verified Boot / BootSignature footer** 的标识，不是 Android 8 引入的 AVB 2.0 `vbmeta` 体系。AOSP 自己区分二者。但 PD1619 官方 boot 未取得镜像做字节级验证，仅有 `PORTING_NOTES.md` 的工具元数据，此点仍标**未验证**。

---

## 2. 决定性实测：5/5 镜像哈希闭合

脚本 `C:\qfilx\exp\bootsig_hash_test.py`，输出 `C:\qfilx\compare\bootsig_hash_result.txt`。

方法：按 AOSP `getSignableImageSize` 精确算 L → 从 L 处解析 DER 取真实 `authenticatedAttributes` 完整字节 → `openssl pkeyutl -verifyrecover -pkeyopt rsa_padding_mode:pkcs1` 从签名恢复 DigestInfo 中的 32 字节摘要 → 计算 `sha256(boot[:L] + attrs)` 并逐字节比对。同时用独立重编码的 `DERSequence(DERPrintableString("/boot"), ASN1Integer(L))` 交叉验证。

| 镜像 | L | attrs（镜像内 / 重编码一致） | RSA 恢复摘要 = sha256(boot[:L]‖attrs) |
|---|---|---|---|
| PD1610 1.15.1 | `0x3257000` | `300d13052f626f6f74020403257000` | `1cf2d759…5da4` ✅ |
| PD1610 8.19.16 | `0x3801000` | `300d13052f626f6f74020403801000` | `3d36776e…6be4` ✅ |
| PD1610 stock 7.13.15 | `0xe30000` | `300d13052f626f6f74020400e30000` | `e1aa702e…7826` ✅ |
| PD1516A 7.7.6 | `0xdfd000` | `300d13052f626f6f74020400dfd000` | `d2d9c863…e08e3b` ✅ |
| PD1516A 3.8.5 | `0x20c2000` | `300d13052f626f6f740204020c2000` | `7f027cf7…852a` ✅ |

**`ALL FIVE MATCH: True`**。

控制变体（每份镜像 8 个候选）全部**不**匹配，证明命中不是巧合：

| 变体 | 结果 |
|---|---|
| `boot[:L]`（旧基线） | 不匹配，如 1.15.1 = `3892f158…` |
| `boot[:L] + attrs 内容（去掉 30 0d 头）` | 不匹配 |
| `boot[:L] + attrs 去掉 tag` | 不匹配 |
| `attrs + boot[:L]`（顺序颠倒） | 不匹配 |
| `boot[:L±4096] + attrs` | 不匹配 |
| `boot[:L] + 独立重编码 attrs` | **匹配**（与镜像内字节逐字节相同） |

**两条附加确认**：
1. attrs 独立重编码与镜像内 DER 字节 5/5 完全相同 → 坐实 `INTEGER L` 就是 BouncyCastle `ASN1Integer` 的最小长度编码（高位补 0 规则一致）。
2. 为什么之前 30+ 组合全失败：旧脚本 `C:\qfilx\exp\verify_hash_input.py` 的 9–10 个候选**全是 `L` 起始的连续区间**（`d[:L]`、`d[:L+0x400]`、`d[:L+0x500]`…），而 AOSP 模型是「镜像前缀 + 一段**重新编码、非连续**的认证属性」。复评对失败原因的判断准确。

**边界**：本轮证明的是「用 AOSP 模型能精确复现摘要、且跨 2 机型 5 份镜像 2 个 Android 大版本一致」，属密码学等价性确认；**未**在 aboot 反汇编中逐指令追踪 `SHA256_update` 的调用参数，故 v7.4 中「aboot 内部实现」类表述仍按原文保留。DER 之后的非零尾页数据（1.15.1 为 5376 B）仍**未解释**，但它不在 `boot[:L]` 内、不参与哈希。

---

## 3. 用闭合模型重判当年实验镜像

脚本 `C:\qfilx\exp\bootsig_experiments_verify.py`，输出 `C:\qfilx\compare\bootsig_experiments_result.txt`。这把 v7.4 的「实测现象」升级为**可计算证明**。

| 镜像 | 判定 | 值 |
|---|---|---|
| `boot_00_baseline` | **SIGNATURE VALID** | 恢复摘要 = 计算摘要 = `1cf2d759…` |
| `boot_01_name`（改 name 1 字节） | **INVALID** | 计算摘要 `2909ae1e…` ≠ 恢复摘要 |
| `boot_02_cmdline`（改 cmdline 1 字节） | **INVALID** | `59ee234a…` ≠ |
| `boot_03_pad`（改 padding 1 字节） | **INVALID** | `f7f17cbe…` ≠ |
| `boot_04_nosig` | **无签名** | L 处无 DER；`L..L+0x500` 全零；size = L（52,785,152） |
| `boot_05_nosig_mod` | **无签名 + 主体被改** | L 处无 DER、全零；`sha256(boot[:L])=727f2c25…` ≠ 基线的 `3892f158…` |
| `boot_06_mykey`（自签证书重签） | **SIGNATURE VALID（但公钥不受信）** | 证书 sha `e5d91561…`、签名 sha `ba9ba594…` 均不同于基线，恢复摘要却同为 `1cf2d759…` |

三点结论：

1. **T1 三个单字节实验的「卡 logo」现在有了密码学必然解释**：任何 `boot[0:L]` 内的单字节改动都会改变 `sha256(signable)`，与不变的原签名必然不匹配。此前 v7.4 只记为「实测现象」，现可升级为**已确认**。
2. **T2 仍是双变量实验**：`nosig` 与 `nosig_mod` 都确实彻底清除了签名区（`L..L+0x500` 零非零字节），但 `nosig_mod` 同时改了镜像主体。v7.4 5.2 的「缺签名即放行不存在」仍保留为**较强推断**，未因本轮升级。
3. **`boot_06_mykey` 是最干净的一次证明**：用自有私钥对**同一个 signable** 重签，密码学完全自洽（恢复摘要与基线相同），但 aboot 内嵌的是 `scm_beta` 公钥、不信任这份证书 → 格式、算法、输入、签名生成全部闭合，**唯一障碍就是信任根/私钥**。这也独立复核了 v7.4「公钥来自 aboot 内嵌、非镜像自带证书」。

---

## 4. 逐条回应复评的其余主张

### 4.1 PD1619 为何能刷无签名 boot（复评第三节）

核实到的原文（release `lineage-16.0-20260711` 安装指南，本轮重取完整段）：

```
1. **Prerequisites:** Unlock your Bootloader first using the **viQOO Tool** provided by `@某贼` on Coolapk.
2. **Firmware Requirement:** Ensure your device is already running the **official stock Android 8.1 firmware** before flashing, or you will brick your device.
4. **Flashing via Fastboot:** ... fastboot flash boot boot.img / fastboot flash recovery TWRP-3.5.2-PD1619.img
```

- 「先解锁」是**已确认**的 release 原文；AOSP Verified Boot 文档对 UNLOCKED 状态的描述也确实允许启动未由信任根签名的系统。
- 但由此得出「PD1619 解锁态关闭/放宽了原有验签」仍是**较强推断**：本轮**未**取得 PD1619 官方 aboot 或官方 stock boot 镜像，未做反汇编，未追踪解锁状态变量；`PORTING_NOTES.md` 的 `sigtype=AVBv1` 只是第三方解包工具的元数据（原文 62–65 行：「Stock unpack metadata reports `sigtype=AVBv1`, `avbtype=boot`, `hashtype=sha1`… the AVBv1 signing/footer data is not reproduced」），**不是**对其 footer 结构的字节级验证。
- 因此原简报「两代机型用两套不同的启动验证架构（AVBv1 vs vivo 自有 DER/RSA）」**已撤销**。准确表述：**PD1610/PD1516A 的封装格式已字节级确认是 AOSP BootSignature；PD1619 官方 boot 仅有工具标注、未验证；能确认的差异是解锁态验证策略与证书/信任配置**。
- 复评点出的真问题保留并升级为第一等的跨机型课题：**同样（或同体系）的 BootSignature，为什么 PD1619 解锁后能启无签名 boot，而 PD1610 已 `is_unlocked=1`、改一个字节仍卡 logo？** 这与 v7.4 13.7 U1（上层控制流是否最终阻止内核装载）汇合，比继续找私钥更接近机制核心，但**仍不构成可执行入口**。

### 4.2 `alpha` / `beta` 降级（复评第四节）

本轮把上一轮登记的纯离线待办做掉了。三份 PD1610 aboot（1.15.1 / 8.19.16 / 16 MB 分区 dump）字符串检索：

| 关键字 | 命中 | 上下文 |
|---|---|---|
| `securebootkey` | **0** | — |
| `keyver` | **0** | — |
| `beta` | 15 | 全部是 `vivo attestation beta CA` / `vivo root beta CA` 证书主题串（0x122a 等） |
| `alpha` | 2 | 全部是 `alpha_pll` 时钟驱动日志（0x82214 等） |
| `AVBv1` / `BootSignature` | **0** | — |

→ aboot **不解析** cmdline 里的 `securebootkey` / `keyver` 字符串；这些字段是内核/系统侧信任根标识，不是 aboot 的验签策略开关。复评要求「进一步降低结论强度」成立，且现在有静态硬证据。原有判断（该 hash == aboot `@0x1A2F` 证书 SHA256，是 SBL 认证 aboot 的信任根标识）不受影响。

**边界**：字符串 0 命中排除了「按字符串解析并切换算法」这条路径，**未**排除间接形式的策略判断（如读 `devinfo` 的解锁位后走不同分支）。aboot 中 `devinfo` 3 命中、`unlocked` 5–6 命中、`verifiedbootstate` 1 命中，与 v7.4「解锁状态只放开写分区」的既有结论一致；完整控制流仍归 U1。

### 4.3 复评的任务重排

| 复评任务 | 本轮状态 |
|---|---|
| 任务 1：重建 AOSP BootSignature 哈希输入 | **已完成，5/5 闭合**（第 2 节），并加做 7 份实验镜像重判（第 3 节） |
| 任务 2：比较两机型解锁状态判断 / 追踪实际控制流 | **未执行**。需 PD1619 官方 aboot（本地无，需下载解包官方 8.1 底包）与 PD1619 官方 stock boot；PD1610 侧与 U1 重叠。项目暂停，仅登记 |
| 任务 3：确认 PD1610 是否存在独立解锁验证策略 | **部分完成（静态侧）**：第 4.2 节排除了 cmdline 标识路径；`boot_state` / `skip_flag` 的实际读取关系仍属 v7.4 U1，**未执行** |
| alpha/beta 检索待办（上一轮登记） | **已完成**，结论见 4.2 |

**未执行**（项目暂停，均需明确重启）：PD1619 官方固件/aboot 下载与反汇编、v7.4 13.7 U1 数据流追踪、任何设备操作。`dtc` 仍未安装，DTB→DTS 未做。

---

## 5. 对主报告与重启条件的影响

| v7.4 中的条目 | 本轮后状态 |
|---|---|
| 3.3 / 3.5 / 6 节「实际哈希输入未确认」「30+ 组合全不匹配」 | **已闭合**（标准 AOSP 模型，5/5 字节级）。v7.4 按封存约定不改动，以本文为准 |
| 13.7 U10「追 SHA-256 update 的地址/长度参数复现摘要」 | **密码学等价性已闭合**；aboot 内部逐指令实现仍未追踪，保留为低优先 |
| 2 节第 10 条、13.1「签名算法与结构」 | **加强**：由「vivo 私有格式」更正为「AOSP 标准 BootSignature + vivo 证书」 |
| 5.2 T1 单字节实验「卡 logo」 | 现象升级为**可计算证明**（签名 INVALID） |
| 5.2 T2「缺签名」双变量 | **不变**，仍为较强推断 |
| 13.1 层 2「自编译 boot 无可行路径」、13.4 四条重启条件 | **不变，且被加强**：验签侧无私有格式歧义可利用 |
| 4.2 / 13.7 U1「调用者是否最终阻止内核装载」 | **不变，仍是第一优先未闭合项** |

**判定：不构成新破局方向，不重启项目。** 这次收获是把「验签到底验什么」从黑盒变成白盒，把跨机型对比从「两套架构」的猜测变成「同一套标准格式、不同的解锁态策略」的可验证命题。

---

## 6. 产物与可复现命令

```bash
# AOSP 源码（GitHub mirror 的 master/main 路径均 404，用 googlesource 官方源）
curl -sS -L "https://android.googlesource.com/platform/system/extras/+/refs/heads/main/verity/BootSignature.java?format=TEXT" \
  | python3 -c "import sys,base64;open('BootSignature.java','w').write(base64.b64decode(sys.stdin.read()).decode())"

# 5 份镜像哈希模型验证（含 8 个控制变体）
python C:\qfilx\exp\bootsig_hash_test.py                 # -> C:\qfilx\compare\bootsig_hash_result.txt

# 7 份实验镜像事后判定
python C:\qfilx\exp\bootsig_experiments_verify.py        # -> C:\qfilx\compare\bootsig_experiments_result.txt

# 旧候选（对照，均 FAIL）
python C:\qfilx\exp\verify_hash_input.py                 # -> C:\qfilx\compare\hash_input_result.txt
```

| 文件 | 说明 |
|---|---|
| `C:\qfilx\exp\BootSignature.java` | AOSP 官方源码本地副本（351 行） |
| `C:\qfilx\exp\bootsig_hash_test.py` | 哈希模型 + 控制变体 + 独立重编码 |
| `C:\qfilx\exp\bootsig_experiments_verify.py` | 7 份实验镜像事后判定 |
| `C:\qfilx\compare\bootsig_hash_result.txt` | 5/5 命中原始输出 |
| `C:\qfilx\compare\bootsig_experiments_result.txt` | 实验镜像判定原始输出 |
| `C:\qfilx\compare\pd1619\PORTING_NOTES.md` / `release.json` | PD1619 原文证据 |

**取证边界**：AOSP `Utils.java` 一次拉取遇 CONNECT tunnel 502，未取到；签名算法不依赖该文件——已由 DER 内 `sha256WithRSAEncryption` OID 与 5/5 恢复出的标准 SHA-256 DigestInfo（51 B，`3031300d…0420`）独立坐实。外部复评依据的是简报与公开 AOSP 源码，本文的实测部分（第 2、3、4.2 节）为本轮本地独立执行，两者不混为一谈。
