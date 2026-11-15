# vivo Xplay6 (PD1610) 启动链完整性校验 — 完整技术简报

> 版本：2026-11-09 15:05（第 5 版）
> 本版重大变更：
> 1. **kexec 结论反转** —— 实测 `CONFIG_KEXEC=n`，二阶段加载路径关闭（详见 7.1）
> 2. **签名算法完全确认** —— raw RSA 模幂解出 PKCS#1 v1.5 + SHA-256（详见 5.3）
> 3. **签名位置修正** —— 在 1280 字节外层结构内部偏移 1024，不是其后（此错误曾导致全部离线验签失败）
> 4. **证书结构逐 TLV 解开** —— 1,280 B 外层 = version + 985 B 证书 + 算法 + params + 256 B 签名
> 用途：请独立评审。所有结论标注了证据强度（确认 / 较强 / 未定位）。
> 欢迎指出任何一条证据链的漏洞。

---

## 一、设备与目标

| 项 | 值 |
|---|---|
| 机型 | vivo Xplay6 / PD1610 / MSM8996 / UFS / 4096B 扇区 |
| 当前系统 | Android 6.0.1 / `PD1610_D_1.15.1` / `MXB48T` / `compiler12020143` |
| 内核 | Linux 3.18.20-perf-gb6998a3（2016-12-02 构建） |
| 安全补丁 | 2016-11-01 |
| 引导层 | 原厂 `PD1610_D_7.13.15`，SHA256 `b4d75a9b399a8d28...` |
| BL 状态 | devinfo `is_unlocked=1` + `is_unlock_critical=1`，`fastboot flash` 放行 |
| 其他属性 | `verifiedbootstate=green`、`veritymode=enforcing`、SELinux Enforcing、基带/IMEI 完好 |
| 目标 | 运行 LineageOS 类原生（Android 7~10），或至少取得持久 ROOT |

**实验组合说明**：分析的 aboot 是 7.13.15，测试的 boot.img 是 1.15.1。设备实际运行的就是这个组合（降级时只刷系统层，未动引导层）。**结论仅适用于此组合。**

---

## 二、核心结论

### 已确认（有实验或反汇编直接支持）

| # | 结论 | 证据 | 强度 |
|---|---|---|---|
| 1 | devinfo 解锁状态下 fastboot 写入被放行 | 实测 `fastboot flash boot` 返回 OKAY | **确认**（仅此状态、此接口） |
| 2 | 两处 header 页改动与无法正常启动**稳定相关** | 改 name 9 字节 → 启动失败；改 padding 1 字节 → 启动失败；两次刷回 baseline 均 27 秒恢复 | **确认** |
| 3 | 故障发生在 Android 正常初始化之前 | 120 秒无 USB 枚举；logo 停留约 **1 秒**即重启 | **较强**（不能排除 kernel 极早期崩溃） |
| 4 | 修改 devinfo 解锁**不等于**允许启动未签名 boot | 解锁状态下两次改动均失败；交叉引用显示验证树不读 is_unlocked | **较强** |
| 5 | **boot 尾部结构 = 证书 + 签名 + 对齐，且签名覆盖范围写在证书里** | 1,280 B 外层 SEQUENCE 逐 TLV 解析；params 声明 `/boot` + 长度；见 5.1 | **确认** |
| 6 | **签名算法 = RSA-2048 + SHA-256 + PKCS#1 v1.5** | raw RSA 模幂得到 `00 01 FF…` + 完整 DigestInfo；三份样本一致；见 5.3 | **确认** |
| 7 | **内核未编译 kexec** | `T_COUNT=19707`（符号表完整）但无 `SyS_kexec_load` / `machine_kexec`；`CONFIG_KEXEC_CORE=y` 而 `CONFIG_KEXEC=n`；见 7.1 | **确认** |
| 8 | **公钥不来自 boot 尾部证书** | `verify_image(data, len, 分区名)` 的参数中没有证书指针；第 3 参数实测为 `/boot` / `/survival`；见 5.5.1 | **确认** |
| 9 | **验签失败 → skip_flag=1 → 加载器跳失败出口** | `91839B9C: str r1,[r3]` 写入；`9183AC: bne 0x9183E5B8` 读取；见 5.5.2 | **确认** |

### 强烈支持但未完全闭合

| # | 结论 | 缺口 |
|---|---|---|
| 10 | 验签调用链（装载→取描述符→取签名→哈希→比对）函数级已定位 | **哈希输入无法用原始数据重构**（30+ 种组合，见 5.3）；`0x9186CC54` 内 `blx ip` 间接调用结构未识别（见 5.5.1） |
| 11 | aboot 内嵌的 `scm_beta` 证书就是 boot 的验证信任根 | boot 尾部证书与 aboot @0x81059 的 SHA256 完全一致；但公钥实际取自 `0x9185B080` 查表结果，该表与 @0x81059 的对应未直接建立 |
| 12 | 哈希覆盖 header 到 kernel 的连续区间 | 证书 params 声明了长度（`/boot` + 偏移），但具体字节构造未重构 |

### 未定位

| # | 问题 |
|---|---|
| 13 | 哈希输入的确切构造（aboot 是否在算哈希前规范化数据） |
| 14 | `0x9186CC54` 中 `[分区名+8]` 的解引用结构（描述符对象布局） |

---

## 三、两次单字节实验 + 一次观测（全部可复现、全部可回滚）

### 实验对象结构（1.15.1 boot.img，52,790,528 B）

```
[0x00000000, 0x00000240)   boot header 前段（magic/sizes/addrs/page_size 等）
[0x00000240, 0x00000260)   id[8]（32 B）
[0x00000260, 0x00000660)   extra_cmdline[1024]
[0x00000660, 0x00001000)   对齐填充（2464 B，实测全零）
[0x00001000, 0x02B1B000)   kernel（43.10 MB）
[0x02B1B000, 0x03257000)   ramdisk（7.40 MB）
[0x03257000, 0x03258500)   尾部数据（5,376 B）
```

> 注：前半段字段（magic..os_version）占 0x00–0x2F，name 占 0x30–0x3F，cmdline 占 0x40–0x23F。因此「header 有效字段」整体是 `[0x000, 0x660)`，不是 `[0x000, 0x240)`。

Header v0 字段边界（已用 SHA1 验证）：

```
name[16]             0x030 .. 0x03F
cmdline[512]         0x040 .. 0x23F
id[8] (8×uint32=32B) 0x240 .. 0x25F
extra_cmdline[1024]  0x260 .. 0x65F
padding              0x660 .. 0xFFF    (2464 B，实测全零)
```

验证：`SHA1(kernel+ks+ramdisk+rs+second+ss)` = `87a9cbd0788ac2b764bb86373ffd6786a338d30d`，与文件 @0x240 前 20 字节**完全匹配**，`id[5..7]` 为 0。

**该匹配是格式一致性证据，不是认证证据**——无密钥的 SHA-1 任何人都能重算。另外需注意：计算用的是 header 声明的 `size` 字段（非页对齐长度），字节序为小端。

### 实验 1：改 header name

| 项 | 值 |
|---|---|
| 改动 | `0x30..0x38` 共 9 字节 → `VIVOTEST1` |
| 原值 | 16 字节全零 |
| 结果 | **卡 logo，无 USB 枚举，不掉 9008** |
| 恢复 | 刷回 baseline，27 秒进系统 |

### 实验 2：改纯填充区

| 项 | 值 |
|---|---|
| 改动 | `0x800`: `0x00 → 0xFF`，共 **1 字节** |
| 位置性质 | `0x660..0xFFF` 全零填充区正中间，不属于任何 header 字段 |
| 结果 | **卡 logo，现象与实验 1 完全一致** |
| 恢复 | 刷回 baseline，27 秒进系统 |

**实验 2 的意义**：排除“name 字段语义检查”假设。该字节不参与任何结构解析，改它仍失败，只能是完整性校验。

### 实验 3：USB 枚举 + 停留时长观测（定性实验，非新改动）

方法：刷入实验 2 的镜像 → reboot → 每 1 秒轮询 Windows PnP 设备（`VID_18D1/05C6/2D95/2717`）→ 记录时间线。

```
基线（fastboot）:  Android Bootloader Interface
刷入后 +0s      :  (无)
此后 120 秒     :  零变化
```

人工观察：屏幕反复闪 vivo logo，**每次停留约 1 秒**，设备管理器全程无反应，未掉 9008。

**能推出**：设备未进入 Android USB Gadget / ADB 可用阶段；故障在正常初始化之前。

**不能推出**：kernel 未执行（USB Gadget 需绑定才枚举；1 秒轮询也可能漏掉瞬态设备）。

**倾向性判断（非结论）**：logo 仅停留约 1 秒 → LK 读入 52 MB boot、校验、跳核通常需要 0.5–1 秒；kernel 从入口到 USB 驱动初始化一般需要数秒。1 秒的窗口更符合「LK 阶段就重启」，但缺少日志，不能定论。

---

## 四、控制流关键地址（7.13.15 aboot，基址 0x91800000）

### 启动分派

```
0x9183EC80  push {r4, lr}
0x9183ECA8  bl 0x91835454        ; 恒返回 1 的桩函数
0x9183ECAC  cmp r0, #0
0x9183ECB0  bne 0x9183ECD0       ; 永远成立
0x9183ECCC  b 0x9183D920         ; ← 不可达（含 is_unlocked 判断的路径）
0x9183ECD0  bl 0x91812608
0x9183ECEC  b 0x9183E05C         ; ← 实际执行
```

### 实际加载链

```
0x9183E05C  加载器（栈帧 0x23C）
  ├─ 0x9183D95C  memcmp(buf,"ANDROID!",8)
  ├─ 0x9183E2B8  bl 0x91839944    ; 验签封装（返回值被 0x9183E2BC 的 mvn r3,r7 覆盖）
  ├─ 0x9183E478  检查 dt magic "ARMd" (0x644D5241)
  ├─ 0x9183E898  地址范围检查 0x917FFFFF / 0x91800000
  ├─ 0x9183E81C  bl 0x9183D63C    ; 跳核
  └─ 0x9183D6C0  bl 0x9181DE78    ; dt 加载（返回值被 0x9183D6C8 检查）
```

### 已逐个定性的函数（全部与签名无关）

| 地址 | 功能 | 证据 |
|---|---|---|
| `0x91850854` | dt 格式识别 | `cmp ip,#0xD00DFEED`（FDT magic）→ `cmp r3,#0x02FF2112`（QCDT magic） |
| `0x91851560` | FDT 节点路径查找 | `cmp r3,#0x2f` 判 `/`、递归、字符串 `/memory` `/chosen` |
| `0x918010E0` | dt 条目遍历 | `cmp r3,#0xe` 属性类型、`cmp r3,#1` 值 |
| `0x9181CC64` | MBN 字段解析 | `ubfx` 重组 + `+0x2800`，无模幂 |
| `0x9181DE78` | dt 加载 | 失败打印 `"Invalid device tree header"`（`0x9187BB10`），被 `0x9183D6C8` 检查 |
| `0x9183D82C` | dt 失败分支 | 打印 `"ERROR: Updating Device Tree Failed"`（`0x91881E38`）后 `b 0x9183D6CC` **继续** |

### 状态变量

| 地址 | 用途 | 初值 | 读取点 |
|---|---|---|---|
| `0x9192BBDC + 0x10` | devinfo is_unlocked | 由 devinfo 决定 | 11 处，**0 处在验证树内** |
| `0x9189B89C` | boot state（0/1/2/3） | **静态初值 3** | 7 处，全在状态机 `0x91810C80–0x91811B08` |
| `0x91B92D08` | skip flag | 0（无写入点） | 3 处，均在加载器外围 |

### 已知字符串

```
0x91880B68  "Device is unlocked! Skipping verification..."
0x91880B98  "Keystore verification failed! Continuing anyways..."
0x91881E38  "ERROR: Updating Device Tree Failed"
0x9187BB10  "Invalid device tree header"
```

**注意**：上述“Continuing anyways”属于独立的 Keystore 状态处理逻辑，**不能**解释为“启动镜像验证被跳过”。

---

## 五、密钥体系与信任链（2026-11-09 14:15 实证更新）

### 5.1 boot 尾部 5,376 字节的完整结构（2026-11-09 14:55 完整解开）

```
0x3257000 .. 0x3257500   1,280 B   外层 SEQUENCE（30 82 04 FC）
0x3257500 .. 0x3257600     256 B   非零数据
0x3257600 .. 0x3258500   3,840 B   全零（页对齐）
```

**外层 1,280 字节的 TLV 逐项解析**（这是本次的关键修正）：

```
@0     SEQUENCE  len=1276 (总 1280)      ← 外层容器
  @4   INTEGER   len=1   = 01            version
  @7   SEQUENCE  len=981 (总 985)        ← X.509 证书本体
  @992 SEQUENCE  len=11                  AlgorithmIdentifier: sha256WithRSA (OID 1.2.840.113549.1.1.11)
  @1005 SEQUENCE len=13                  SignatureParameters（见下）
  @1020 OCTET STRING len=256             ← RSA-2048 签名（在 1280 内部！）
```

字节校验：4 + 3 + 985 + 13 + 15 + 260 = 1,280 ✓

**签名参数（@1005）解出的内容极为关键**：

```
30 0d 13 05 "2f 62 6f 6f 74" 02 04 "03 25 70 00"
        └ PrintableString "/boot" ┘ └ INTEGER 0x03257000 ┘
```

即：**分区名 = `/boot`，签名覆盖长度 = 0x03257000**。

**重要修正**：此前记录为「签名在 1,280 字节之后」，实际在**外层 SEQUENCE 内部偏移 1,020 处**。这个错误导致之前所有离线验签取错数据，全部返回 `invalid padding`。

三份样本的 params 对照（每个数字恰好等于块自身偏移）：

| 版本 | 块偏移 | params 声明长度 | 块数 |
|---|---|---|---|
| 7.13.15 | @0x00E30000 | 0x00E30000 | 2 块（同一密钥） |
| 7.13.15 | @0x032A7000 | 0x032A7000 | |
| 1.15.1 | @0x03257000 | 0x03257000 | 1 块 |
| 8.19.16 | @0x03801000 | 0x03801000 | 1 块 |

**这是分段签名**：每一段覆盖 `[0, 本块偏移)`，7.13.15 有两段，后两版各一段。

证书本体（@7，985 B）解析结果：

```
Version      v3
Serial       f2:ec:29:03:80:32:43:f0
Signature    sha1WithRSAEncryption（证书自身的签名算法）
Issuer       C=CN, ST=GD, L=SHENZHEN, O=vivo, OU=scm_beta, CN=scm_beta, emailAddress=vivo@vivo.com
Subject      同上 —— 自签名 CA
Validity     2016-10-20 .. 2044-03-07
Public Key   RSA-2048
  Modulus    00:e1:14:60:86:d0:8b:e5:9e:ef:00:e4:60:c3:11:bf:ee...
Basic Constraints  CA:TRUE
SHA256       8a1ee2d0b1ea378d43e27e20e9ec0b34...
```

### 5.2 aboot 内嵌证书（关键证据）

在 aboot 中搜索带 `vivo` / `scm_beta` 的 DER 对象，找到 6 个候选，其中：

| 位置 | 大小 | SHA256 前缀 | 说明 |
|---|---|---|---|
| **@0x81059** | 985 | **8a1ee2d0b1ea378d...** | **与 boot 尾部证书完全相同** |
| @0x1A2F | 945 | da758fd52632ba66... | 与 boot cmdline 的 securebootkeyhash 匹配 |

**两项交叉验证**：

1. **boot 尾部证书 == aboot @0x81059 证书**（SHA256 完全一致）
   → 证明 aboot 内嵌了验证 boot 所需的公钥，boot 尾部携带同一份用于告知验证者
2. **aboot @0x1A2F 证书的 SHA256 == boot cmdline 的 `androidboot.securebootkeyhash`**
   ```
   cmdline: androidboot.securebootkey=beta
            androidboot.securebootkeyhash=da758fd52632ba6649d61830a88bbe76a616e4b083b9358b3e98e13772dc139d
            androidboot.securebootkeyver=2
   aboot @0x1A2F 证书 sha256 = da758fd52632ba6649d61830a88bbe76...
   ```
   → 这张是 **aboot 自身被 SBL 认证所用的证书**，其 hash 在启动时被写入 cmdline 传给内核

**因此可以确认存在两层独立的信任链**：

```
SBL  →  验证 aboot      （根：da758fd5... 证书，hash 写入 cmdline）
aboot →  验证 boot      （根：8a1ee2d0... scm_beta 自签名 CA）
```

这回答了此前评审提出的质疑：**aboot 内的证书链确实就是 boot 的验证信任根，不是仅用于自身认证**。

### 5.3 签名算法已完全确认，但哈希输入未能重构（2026-11-09 14:55 更新）

**已确认的部分**（用正确的签名偏移 `tail[1024:1280]` 重做）：

对 256 字节签名做 raw RSA 模幂（`pow(sig, 65537, n)`），三份样本结果一致：

```
EM: 00 01 ff ff ff ... ff 00
    └─ 204 字节 PKCS#1 v1.5 padding ─┘

DigestInfo (51 B):
  30 31 30 0d 06 09 60 86 48 01 65 03 04 02 01 05 00 04 20 | <32 B>
  └ SEQUENCE(49) ┘└ SEQ(13) ┘└ OID 2.16.840.1.101.3.4.2.1 ┘ NULL └len=32┘
                              = SHA-256
```

**结论：签名 = RSA-2048 + SHA-256 + PKCS#1 v1.5，教科书式实现，无任何结构缺陷。**

这与 aboot 里 `verify_sig`（`0x91810CB0`）手工拼出的 19 字节 DigestInfo **逐字节一致**：

```
91810CF8: strb lr, [sp]        ; 0x30
91810D00: strb lr, [sp, #2]    ; 0x30
91810D1C: mov r3, #9  → sp[5]  ; 0x09
91810D34: strb ip, [sp, #6]    ; 0x60
91810D38: strb lr, [sp, #7]    ; mvn #0x79 → 0x86
91810D44: strb sl, [sp, #0xa]  ; 0x65
91810D48: strb r3, [sp, #0xc]  ; 0x04
91810D50: strb r3, [sp, #0x11] ; 0x04
91810D88: strb ip, [sp, #0xf]  ; 0x05
91810D8C: strb lr, [sp, #0x12] ; 0x20
```

**未闭合的部分**：**哈希输入无法用原始文件数据重构。**

已穷举 30+ 种组合，全部不匹配（目标摘要取自 DigestInfo）：

| 类别 | 尝试过的构造 |
|---|---|
| 边界 | `[0, 块偏移)`、`[0, EOF)`、`[0, 96MB 分区)`、`[0x1000, …)`、`[0x800, …)`、`[0x240, …)` |
| 分区填充 | 文件 + 零填充至 96 MB、区间 + 尾部块 |
| 前缀/后缀 | `/boot` + data、data + `/boot`、le32/le64 长度前后缀 |
| 二次处理 | `sha256(sha256(data))`、按 2K/4K/64K 分块后整体哈希 |
| header 规范化 | id 清零、name 清零、id+name 清零、id+name+cmdline 清零 |

**注意**：`boot_full.bin`（7.13.15 的 96 MB 真实分区 dump）同样不匹配，因此不是"文件 vs 分区"的问题。

**可能的解释**（均未验证）：

1. aboot 在计算哈希前对缓冲区做了规范化处理（例如清零某些字段、重建 MBN 头）
2. 签名由 vivo 的签名服务在另一份数据上生成，而刷入的镜像与该数据存在差异
3. 哈希覆盖的是「哈希表」而非原始数据（尽管 DigestInfo 只有一个摘要，此解释较弱）

**这不影响"boot 内容受完整性保护"的行为结论**——三份样本的 PKCS#1 结构都正确，说明签名真实有效；改任何受覆盖字节都会破坏摘要，与三次实验现象一致。

### 5.4 其他两层（证据强度维持原判）

| 层 | 观察到的公钥 | 与 AOSP testkey 关系 | 能证明什么 |
|---|---|---|---|
| recovery `res/keys` | 1 把，模数 `b96ada8b7d702096...` | **不匹配** | 该 recovery 不接受 testkey 签名的 OTA |
| dm-verity `/verity_key` | 模数 `a704dbb9e99cf54b...`（7.1.1 与 8.1.0 字节级相同） | **不匹配** | testkey 签不出可通过校验的 verity 元数据 |

AOSP testkey 模数 `e8eb784d2f4d5491...`。

**说明**：「不匹配 testkey」≠「证明归属 vivo」，只能说明不是公开 testkey。

---

## 5.5 完整验签调用链（2026-11-09 15:10 修正第三个参数含义）

### 调用层级

```
boot 分区
  ↓
0x9180FF90   镜像读取/对齐处理
  内部调用 0x91873D04 / 0x91873234 / 0x91834538 / 0x9187318C
  返回 (buffer, size)
  ↓
0x9181167C   verify_image(data, len, 分区名)      ← 第 3 参数是名字，不是公钥
  9181168C: add r8, r0, r1        ; r8 = data_end（连续区间）
  91811690: mov r7, r1            ; len
  91811698: mov sb, r2            ; sb = 分区名字符串
  918116A0: mov r6, r0            ; data
  918116AC: bl 0x918107C4
  918116B0: bl 0x9184FB9C         ; malloc
  91811734: bl 0x9185B080         ; 取得验证描述符（见 5.5.1）
  918118D8: ldr r2, [sl, #0x10]   ; 描述符里的签名容器
  918118E8: ldr r2, [r2, #8]      ; 签名
  918118E4: mov r3, sb            ; 第 4 参数 = 分区名
  918118EC: bl 0x91810CB0
  ↓
0x91810CB0   verify_sig
  91810CC4: mov sb, r0            ; data
  91810CD0: mov r8, r1            ; ★ r8 = len（函数原参数，非 end）
  91810D04: mov r7, r2            ; sig
  91810D14: mov r6, r3            ; 分区名
  91810CD4: mov r1, #0x100        ; RSA-2048 模数 256 B
  91810CF8: strb lr, [sp]         ; lr = 0x30
  91810CEC: mov sl, #0xd
  91810CE4: mov fp, #0x31
  91810CFC: mov ip, #0x60
  → 逐字节拼出 30 31 30 0d 06 09 60 86 48 01 65 03 04 02 01 05 00 04 20
  91810D9C: mov r0, sb            ; hash 输入 = data
  91810DA0: mov r1, r8            ; hash 长度 = len
  91810DA4: mov r2, #2            ; 算法类型
  91810DAC: bl 0x918215B4
  91810DB0: mov r0, r7            ; sig
  91810DB4: mov r1, sl            ; hash 输出
  91810DB8: mov r2, r6            ; 分区名
  91810DBC: bl 0x9182154C         ; → 0x9186CC54（PKCS#1 结构校验）
  ↓
0x918215B4 → 0x9182193C（算法分派）
  91821964: bl 0x91800BD0         ; 检测类型
  91821978: beq 0x918219C8        ; type 2
  918219E0: b 0x9186E294          ; type 1
  ↓
0x9186E294   hash 实现
  9186E2CC: bl 0x9186E008         ; init
  9186E2E4: bl 0x9186DEC8         ; update(data, len)
  9186E2F0: bl 0x9186E0B8         ; final
  9186E2F8: mov r1, #0x70         ; 上下文 112 B
```

### 5.5.1 信任根来源：公钥不来自 boot 尾部（2026-11-09 15:10 新增）

`0x91839B78` 调用 `verify_image` 之前的参数准备：

```
91839B58: movw r3, #0x33a8
91839B5C: movt r3, #0x91b9
91839B60: ldr  r3, [r3]          ; 读全局标志 0x91B933A8（静态初值 0）
91839B64: cmp  r3, #0
91839B68: movwne r2, #0xc08      ; 非0 → r2 = 0x91880C08
91839B6C: movweq r2, #0xc14      ; ==0 → r2 = 0x91880C14
91839B70: movtne r2, #0x9188
91839B74: movteq r2, #0x9188
91839B78: bl   0x9181167C        ; verify_image(data=r0, len=r1, name=r2)
```

两个候选地址的实际内容：

```
0x91880C08: "/survival"
0x91880C14: "/boot"
```

**结论：`verify_image` 的第三个参数是分区名字符串，不是公钥，也不是证书指针。**

`verify_image` 的完整参数表是 `(data, len, 分区名)`——**它从未接收过任何证书指针**。

因此可以排除「aboot 从 boot 尾部读取证书并无条件信任」这种模式（此前评审提出的“情况 B”）。公钥必然来自 aboot 自身的数据结构，经 `0x9185B080` 按名字查找获得。

**仍未闭合**：`0x9186CC54` 内出现 `ldr ip,[r3,#8]` → `ldr ip,[ip,#8]` → `blx ip` 的间接调用，若 `r3` 是裸字符串则解引用会失败，说明此处还有一层未识别的结构（描述符对象或参数重排）。这一点尚未解释。

### 5.5.2 验签失败 → 阻断启动的因果链已闭合（2026-11-09 15:10 新增）

```
91839B7C: mov  r6, r0            ; 保存 verify_image 返回值
91839B80: bl   0x91811AF0        ; 状态检查
91839B84: cmp  r6, #0
91839B88: beq  0x91839BA4        ; 返回 0（成功）→ 继续
; 返回非 0（失败）：
91839B8C: movw r3, #0x2d08
91839B90: movt r3, #0x91b9       ; r3 = 0x91B92D08
91839B94: mov  r1, #1
91839B98: mov  r2, #0
91839B9C: str  r1, [r3]          ; ★ skip_flag = 1
91839BA0: str  r2, [r4, #0x14]   ; devinfo+0x14 = 0
```

**这是一处重要修正**：此前记录为「`0x91B92D08` 恒为 0，4 处引用全是读，是死分支」——错误。该地址是 BSS（静态初值 0），但此处就是写入点；之前的匹配脚本只认 `movw/movt` 紧邻 `ldr/str` 的形式，漏掉了中间隔开几条指令的写法。

加载器 `0x9183E05C` 读取该标志并跳转：

```
91839C: ldr r3, [0x91B92D08]
9183A8: cmp r3, #0
9183AC: bne 0x9183E5B8           ; 标志非 0 → 失败出口
```

**完整因果**：

```
verify_image 返回非 0
   → skip_flag[0x91B92D08] = 1
   → 加载器检查该标志
   → bne 0x9183E5B8（失败出口，return -1）
```

这使「验签函数存在」与「验签失败阻止启动」两个命题合为一个有代码依据的链条。

### 两处误判修正

| 地址 | 此前判断 | 实际 |
|---|---|---|
| `0x91810AF4` | 核心验签函数 | 仅 60 字节的懒初始化包装（读全局指针，为空则 `bl 0x9185B080`） |
| `0x91862A48` | SHA-256 | 长度计算：`ldr r0,[r0,#4]` 取元素数，`add r0,r0,r5,lsl#5` = `(n-1)*32` |

### 完整因果链

```
boot 分区 → 读入内存 (buffer, size) → verify_image
         ├─ pubkey ← 尾部 1,280 B 证书（与 aboot @0x81059 完全相同）
         ├─ sig    ← 尾部 +0x500 起 256 B
         ├─ hash(data, len) → SHA-256
         └─ 比对（DigestInfo 19 B + 摘要 32 B = 51 B）
              ↓
         不匹配 → 写状态 3 → 启动不通过
```

**这是代码级因果，每一环都有具体地址与指令。**

---

## 5.6 哈希覆盖范围的实验反推

`len` 的精确值需运行时确认，但三次实验已把边界约束死：

| 改动位置 | 结果 | 推论 |
|---|---|---|
| `0x30`（name，header 最前段） | 启动失败 | `len` 起点 ≤ 0x30 |
| `0x800`（padding，header 中段） | 启动失败 | `len` 覆盖 0x800 之后 |
| kernel 段字节（11-08 E 组） | 启动失败 | `len` 延伸到 kernel 区 |

**三点合并 → `len` 覆盖 header→kernel 连续区间，与「整个 boot.img 参与哈希」一致。**

唯一未确认：尾部 3,840 字节对齐区是否在内（不影响结论）。

---

## 六、已排除路线（附证据强度）

| 路线 | 结论 | 证据强度 |
|---|---|---|
| 改 devinfo 解锁 → 启动未签名 boot | 无效 | **确认**（两次实测 + 解锁分支不可达） |
| `fastboot boot` 绕过 | 无效 | **确认**（命令表无 boot，实测被拒；仅限该组合与该接口） |
| 改原厂 boot 的字节加载自定义内核 | 无效 | **确认**（两次单字节实验） |
| **kexec 二阶段加载自编译内核** | **不可用** | **确认**（`CONFIG_KEXEC=n`，无 `SyS_kexec_load`/`machine_kexec`，见 7.1） |
| 用 AOSP testkey 签 system | 无效 | **较强**（模数不匹配；未确认实际加载的 key 与 verity 执行路径） |
| 原厂 recovery 刷 unsigned OTA | 无效 | **较强**（res/keys 非 testkey、ro.secure=1；TWRP 写入后能否启动未单独测） |
| CVE-2013-2598 | 排除 | **中等**（三版均有 check_addr；未逐条验证所有调用路径） |
| CVE-2014-0973 | 已修复 | **中等**（完整 DigestInfo + PKCS#1；未确认在实际验证路径） |
| CVE-2014-0974 | 存疑 | **弱**（FDT 检查字符串零引用，但执行顺序未确认） |
| CVE-2014-4325 | 排除 | **确认**（无命令入口） |
| Treble / GSI | 常规方式不可行 | **较强**（无 vendor/product/odm 分区；非 Treble 移植理论可行但工作量极大） |
| `bbk unlock_vivo` / 维修工具 | 无增量 | **确认**（handler 只读状态 + 复位） |
| firehose peek/poke 注入 | 未验证 | **未验证**（存在 peek/poke，但 ROP、重启失效均为推断） |
| 8.19.x 内测固件更松 | 未见更松版本 | **中等**（8.19.9 与 8.19.16 某代码段字节级相同；配置/其他组件未比对） |

---

## 七、仍未排除的方向（可能值得继续）

### 7.1 二阶段加载：kexec 路径（2026-11-09 15:01 实测否定）

**内核版本对比**（从各 boot.img 解包 kernel 段、zlib 解压、正则提取）：

| 固件 | 内核版本 | 构建时间 |
|---|---|---|
| 1.15.1（当前系统） | `3.18.20-perf-gb6998a3` | 2016-12-02 |
| 7.13.15（当前 aboot） | `3.18.31-perf-g53ef513f7` | **2022-02-22** |
| 8.19.16（最后官方固件） | `3.18.71-perf-g8a8c60dd` | 2018-11-07 |
| **成功案例截图** | **`3.18.124-perf-g2363427e-dirty`** | — |

**没有任何官方固件是 3.18.124**。这说明成功者使用的是 CAF 或自编译内核，不是保留原厂内核。

#### 曾经以为 kexec 可用，但实测否定了（重要修正）

最初只看到 `W sys_kexec_load` 就判断「kexec 已启用」。**这个判断是错的**——`W` 是弱符号，在 ARM64 3.18 上恰好是未编译时的 `sys_ni_syscall` 桩。

完整实测（`/proc/kallsyms`，`T_COUNT = 19707` 证明符号表完整）：

```
对照组（证明 grep 正常）：
  T SyS_reboot
  T SyS_openat
  T sys_ni_syscall

kexec 相关全部符号：
  W compat_sys_kexec_load
  W sys_kexec_file_load
  W sys_kexec_load
  t setup_crash_kexec_post_notifiers
  t __setup_str_setup_crash_kexec_post_notifiers
  b crash_kexec_post_notifiers

缺失的关键符号：
  SyS_kexec_load        ← 不存在（syscall 实现）
  machine_kexec         ← 不存在（重定位执行）
  kexec_mutex / kimage  ← 不存在
  kernel_kexec          ← 不存在
```

#### 精确解释：`CONFIG_KEXEC_CORE=y` 但 `CONFIG_KEXEC=n`

3.18 的 Kconfig 把 kexec 拆成两个开关，对应的编译单元不同：

```
kernel/kexec_core.o                  ← obj-$(CONFIG_KEXEC_CORE)
kernel/kexec.o                       ← obj-$(CONFIG_KEXEC)     提供 SYSCALL_DEFINE4(kexec_load)
arch/arm64/kernel/machine_kexec.o    ← obj-$(CONFIG_KEXEC)
arch/arm64/kernel/relocate_kernel.S  ← obj-$(CONFIG_KEXEC)
```

实测符号分布与此完全吻合：

- `crash_kexec_post_notifiers`（BSS）、`setup_crash_kexec_post_notifiers`（`t`）存在 → **core 编译了**
- `SyS_kexec_load`、`machine_kexec` 不存在 → **syscall 与重定位未编译**

离线证据一致：内核镜像里 `kexec_load:`、`Kexec image is too large`、`Unsupported kexec segments` 全部 0 次。

**这是 Android 厂商的常见配置**：保留 crash dump 基础设施，关闭 kexec 系统调用（防止 root 后换内核）。

#### 结论：这条路径关闭

```
原厂 boot → 验签通过 → 原厂内核（3.18.20）
                            ↓
                   即使拿到 root
                            ↓
              ✗ 无法 kexec 加载自编译内核
```

**没有 kexec，就无法在运行时换内核**；而换内核是运行类原生的必要条件之一（至少需要自定义内核的 fstab 去掉 `verify`，否则无法挂载未签名的 system）。

**连带影响**：即使 Dirty COW / Binder UAF 成功拿到临时 root，也只能在当前内核里做事，**无法启动类原生**。因此运行时提权对「跑类原生」这个目标的价值大幅下降（对「只要 root」仍有价值）。

### 7.3 验证 Dirty COW 的阻碍（2026-11-09 14:28 实测）

**首先修正一个关键事实**：设备当前运行的内核是 **3.18.20**（`1.15.1` 的 boot），不是 `7.13.15` 的 3.18.31。因为降级时只刷了系统层，boot 也是 1.15.1 的。

```
Linux version 3.18.20-perf-gb6998a3
#1 SMP PREEMPT Fri Dec 2 01:50:48 CST 2016
```

3.18.20 属于 2016 年 5 月左右的源码分支，**远早于 Dirty COW 修复（3.18.43，2016-10-20）**。虽然构建时间（2016-12-02）晚于修复发布，但版本号未跟进，说明 vivo 用的是旧分支源码，**大概率未合入修复**。

**但静态验证走不通**：

| 障碍 | 具体情况 |
|---|---|
| 内核 stripped | 无符号表，`/proc/kallsyms` 所有地址均为 `0`（kptr_restrict 生效） |
| 无 `config.gz` | `/proc/config.gz`、`/boot/config` 均不存在 |
| 本机无 C 编译器 | `gcc`/`clang`/`cc`/`tcc` 全部不存在，也无 Android NDK |
| `vmlinux-to-elf` 安装失败 | pip 调用被中断（SIGTERM），未能装成 |
| VIKIROOT 原始仓库无 release | `niejuhu/VIKIROOT` releases 页面为 0 条目 |
| fork 有 release 但未取到 | `hyln9/VIKIROOT` v0.1.1（含 debug 版），asset 文件名未确认，GitHub API 访问不到 |

**更关键的限制**：VIKIROOT 的 README 明确说明——

> "SELinux bypass" 指 payload 会运行在 init 域，**但仍需要 patched sepolicy 才能让 init 域 unconfined。通常这意味着需要修改 boot image。**

**这正好撞上我们已经确认的死结**：boot 有全镜像完整性校验，改 boot 就会启动失败。

所以即使 Dirty COW 未修复，**"用 VIKIROOT 一键 root"这条路在本机走不通**。

### 7.4 对 kexec 路径的工程评估（2026-11-09 15:01 结论反转）

| 环节 | 状态 | 难度 |
|---|---|---|
| 内核支持 kexec | ❌ **确认不支持**（`CONFIG_KEXEC=n`，无 `SyS_kexec_load` / `machine_kexec`） | **不可逾越** |
| Dirty COW 未修复 | ⚠️ 大概率（补丁级别 2016-11-01 < 修复级别 2016-11-06），未实测 | 中 |
| 编译 ARM64 exploit | ✅ 已解决（zig 交叉编译，v2 检测程序已部署运行） | — |
| SELinux 允许调 kexec | — | 无关（kexec 本身不存在） |
| 持久化 | — | 无关 |

**结论：kexec 路径在架构上不成立**，不是工程难度问题，是内核根本没这个功能。评审 M6 的判断正确。

若仍要走「运行时换内核」，理论上只剩**自研内核接管**（自己实现停核、重定位、跳转，相当于手写 `machine_kexec`），工程量与风险都远超本项目目标。

**它是一条约有希望但成本很高的路，不是"找到了答案"。**

### 7.5 其他方向

| 方向 | 理由 | 前置条件 | 对「跑类原生」的价值 |
|---|---|---|---|
| **运行时提权（临时 root）** | 补丁 2016-11-01，`/dev/binder` `rw-rw-rw-`；检测程序已编译部署 | 待实测 | **低**（kexec 不可用，root 换不了内核） |
| 自研内核接管 | kexec 不存在，只能自己实现停核/重定位/跳转 | 需 root + 大量开发 | 高，但工程量极大 |
| **哈希输入构造** | 唯一未闭合的技术环节（见 5.3） | 需运行时观测或更深的静态追踪 | 中（理解机制，不直接解决问题） |
| **UART 日志** | 可在校验失败瞬间看到 LK 打印 | 需拆机接串口 | 低（只解决归因） |
| **工程机 aboot / 泄露私钥** | 唯一能直接解决问题的材料 | 无公开渠道 | **最高，但不可得** |

---

## 八、想请评审回答的问题

1. **kexec 已确认不可用**（`CONFIG_KEXEC=n`）、**boot 全镜像验签已确认**、**devinfo 解锁只给写权限已确认**。在这三条同时成立的前提下，是否还存在不依赖私钥、也不依赖工程机的冷启动路径？
2. 第二节哪一条的“证据强度”标注仍然过高？请指出具体条目与理由。
3. **哈希输入无法用原始数据重构**（30+ 种组合全部不匹配，包括 96 MB 真实分区 dump）。已知签名是 PKCS#1 v1.5 + SHA-256、公钥正确、params 声明 `/boot` + 长度。可能的解释是 aboot 在算哈希前对缓冲区做了规范化（如重建 MBN 头、清零某些字段）。有没有比继续穷举更高效的验证手段？（本机 `/sys/fs/pstore` 不存在，`/proc/last_kmsg` 仅 76 字节非零，UART 需拆机）
4. 关于运行时提权：本机 Android 6.0.1 / 3.18.20 / 补丁 2016-11-01 / SELinux Enforcing / `/dev/binder` `rw-rw-rw-`。**但 kexec 不可用，所以即使拿到 root 也无法换内核**。在这种情况下，运行时提权对「运行类原生」还有没有其他利用方式？
5. `lineage_pd1610-eng 10` / `eng.root` / `test-keys` / 内核 `3.18.124-perf-g2363427e-dirty`（比所有官方固件都新）的截图案例，除「工程机」「换过 aboot」「运行时换内核」之外，还有哪些**可通过公开材料验证**的解释？如果只能拿到截图，需要补充什么材料才能定性？

---

## 九、可复核材料

```
aboot 原件      C:\qfilx\probe\aboot.bin              (7.13.15, 16 MB)
8.19.16 启动链  C:\qfilx\firmware\81916\              (emmc_appsboot.mbn / boot.img / ramdisk)
实验镜像        C:\qfilx\boottest\boot_00_baseline.img
                C:\qfilx\boottest\boot_01_name.img
                C:\qfilx\boottest\boot_03_pad.img
执行器          C:\qfilx\boottest\boottest.py           (--flash baseline|name|pad)
USB 观测        C:\qfilx\boottest\usb_watch.py
详细分析        C:\Users\Tse\WorkBuddy\寒霜刷机\boot_state_machine_analysis.md
```

三版 aboot SHA256：

```
7.13.15  b4d75a9b399a8d28b8bd7ff7c68994beadab708ed3d23d4c399095788efc3c5f
1.15.1   09990c24f63c5b6fb6ab32af65ad180fce8350d640f8a67b74ef35eb0d06e3c8
8.19.16  fe535256b3e90cb6d4c3fd2f9b7ea734d87366b5af90d22acd1befde24c15c64
```
