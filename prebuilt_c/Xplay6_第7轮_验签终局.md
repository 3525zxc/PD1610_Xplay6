# Xplay6 启动链：本轮证据与终局判定

> 设备：vivo Xplay6 / PD1610 / MSM8996，当前 Android 6.0.1 (1.15.1) + aboot 7.13.15
> 时间：2026-11-09 17:20–17:50
> 目标：让设备运行类原生（LineageOS 系），**不是 root**

---

## 一、本轮六条新证据（全部可复现）

### 1. `fastboot boot` 被拒（不是我们没用对）

```
Sending 'boot.img' (51553 KB)   OKAY [1.374s]
Booting  FAILED (remote: 'unknown command or device is lock')
```

### 2. `fastboot oem` 命令表被完全裁掉

`oem help` / `oem ?` / `oem peek` / `oem read` / `oem info` 全部返回同一句
`FAILED (remote: 'unknown command or device is lock')`
→ 不是权限问题，是 vivo 在 LK 里根本没注册这些命令。

### 3. 安全启动熔丝已烧

```
(bootloader) secure:yes
(bootloader) kernel:lk
(bootloader) variant:Surf eMMC
(bootloader) product:QC_REFERENCE_PHONE
```

`secure:yes` = QFPROM 里 SECURE_BOOT 熔丝已烧 → **PBL/SBL 会认证 aboot**。
推论：把 aboot 改成"验签恒真"是死路——改了 SBL 不认，设备停在 SBL，只能 9008 救回。

### 4. 签名 DER 里挖出「被签数据的精确长度」

`params` 里除字符串 `/<分区名>` 外还有一段 `INTEGER`，它与数据区长度**逐字节吻合**：

| 镜像 | 分区名 | params INTEGER | 签名块起始偏移 | 页+对齐kernel+对齐ramdisk |
|---|---|---|---|---|
| 1.15.1 boot（14.9 MB） | `/boot` | `0x0E30000` | `0x0E30000` | `0x0E30000` ✓ |
| 1.15.1 boot（52.8 MB） | `/boot` | `0x3257000` | `0x3257000` | `0x3257000` ✓ |
| 1.15.1 recovery | `/recovery` | `0x3B10000` | `0x3B10000` | `0x3B10000` ✓ |
| 8.19.16 boot | `/boot` | `0x3801000` | `0x3801000` | `0x3801000` ✓ |

→ **长度模型完全正确**：`len = page_size + ALIGN(kernel) + ALIGN(ramdisk)`，签名块紧跟在数据区之后。
此前"len 算成 0x3258000 / 0x3257000 差一页"的争论到此终结。

### 5. 五份镜像的摘要 vs 前缀 SHA-256 —— 全部不匹配

用**各镜像自带证书里的公钥**做 raw RSA 解签（PKCS#1 v1.5，DigestInfo `30 31 30 0d 06 09 60 86 48 01 65 03 04 02 01 05 00 04 20`），拿到摘要后与"数据区"的 SHA-256 对比：

| 镜像 | 摘要(前16) | SHA256(数据区)(前16) | 结果 |
|---|---|---|---|
| 1.15.1 boot 14.9 MB | `e1aa702eca8ec163` | `20b9f66dd1a618ea` | ✗ |
| 1.15.1 boot 52.8 MB | `1cf2d759c00f4761` | `3892f158c791be66` | ✗ |
| 1.15.1 recovery | `fd0c8e3dd6af6ddd` | `b7c037b2216f5260` | ✗ |
| 8.19.16 boot | `3d36776e08863ac1` | `dc11a0d278776ede` | ✗ |
| 96 MB 分区 dump 首镜像 | `e1aa702eca8ec163` | `20b9f66dd1a618ea` | ✗ |

排除性结论（本轮已穷举过的不再重复）：

- 不是取错签名段（三个版本、5 个签名各自摘要不同，说明都是"各签各的"）
- 不是长度算错（见第 4 条）
- 不是简单切片（起点 0/0x200/0x400/0x800/0x1000 × 终点 0xE30000±0x2000，512 步长全扫）
- 不是分块哈希 / 双哈希 / 页旋转 / 页 0 清零
- 不是单个 header 字段清零（name / cmdline / id / extra_cmdline 及其 **全部 16 种组合**，含尾填充清零）
- 不是"紧凑拼接"（去掉页对齐填充）或"紧凑+补零"

→ **aboot 在算哈希前确实对缓冲区做了改写**（或哈希的不是这段连续数据）。
由于改写方式未知且没有私钥，这条路对"刷自编译内核"没有任何产出。

### 6. `/boot`、`/recovery`、`/survival` 三条启动路径全部验签

静态确认两个 `verify_image` 调用点，函数同一（`0x9181167C`）：

```asm
91839B60  ldr  r3, [r3]        ; 全局 0x91B933A8
91839B68  movwne r2, #0xc08    ; 非0 → "/survival"
91839B6C  movweq r2, #0xc14    ; ==0 → "/boot"
91839B78  bl   0x9181167c      ; verify_image(data, len, name)
...
91839C44  movw r2, #0xbfc      ; "/recovery"
91839C4C  bl   0x9181167c      ; 第二条路径，同样验签
```

且失败分支 `0x91839B9C: str r1,[r3]` 会把 `[r4+0x14]` 清 0（不再装载内核）→ 与"卡 logo 反复闪"现象一致。

### 附带修正：96 MB boot 分区里的第二个签名不是 recovery

```
0x0000000  boot.img（14.9 MB，ANDROID! 头）
0x0E32000  FDT / dt 镜像（38 MB，字符串 p_ahb_clk …）
0x32A7000  第二份签名（DER 1280 B + 256 B 签名）
0x32A8500  之后全零至 96 MB
```

即 boot 分区 = boot.img + dt 镜像，recovery 是独立分区（1.15.1 recovery.img 61.9 MB，自带 `/recovery` 签名）。

---

## 二、路线清算（本轮之后）

| 路线 | 状态 | 依据 |
|---|---|---|
| 改 boot 任意字节加载自编译内核 | **死** | 两次单字节实验 + 5 镜像摘要不匹配 |
| 自签 boot / 用别的证书 | **死** | 公钥来自 aboot 内部，非镜像内证书 |
| 改 aboot 让验签恒真 | **死** | `secure:yes`，SBL 认证 aboot |
| `fastboot boot` 免刷启动 | **死** | 命令表无 boot；老版 1.15.1 aboot 同样无 boot 串 |
| `fastboot oem` 内存读写 | **死** | OEM 命令表被裁 |
| 换更老官方 aboot（官方签名，SBL 会认） | **无收益** | 1.15.1 aboot 与现用 aboot 同为 vivo 裁过的 LK，命令面一致 |
| recovery 分区免验签 | **死** | `0x91839C44` 明确对 `/recovery` 验签 |
| kexec 二阶段 | **死** | `CONFIG_KEXEC=n` |
| devinfo 解锁 → 关验签 | **死** | 实测两次；vivo 的验签不读解锁态 |

---

## 三、还剩什么

按可行性排序：

1. **aboot 解析漏洞**（唯一还有理论空间的方向）
   `verify_image` 用手写代码解析镜像尾部这段 **完全由我们控制的 ASN.1**。这是 bootloader 里最典型的可攻击面：长度字段、嵌套 SEQUENCE、证书 TLV 都可能是栈溢出/越界点。
   可做的最小验证：构造异常 DER（超大 length、深度嵌套、截断）刷入，观察是"正常拒绝"还是"复位/9008"——后者说明踩到了内存破坏，值得继续。
   代价：没有 UART、没有调试器，只能靠"能否启动"做 1 bit 预言机；成功率和周期都不乐观。

2. **工程机 aboot / 泄露私钥**：能一次性解决，但公开渠道没有。截图里那台 `lineage_pd1610-eng` 大概率是工程机（熔丝未烧）或换过引导层。

3. **放弃该机的类原生移植**：就目前证据，零售版 Xplay6 在"熔丝已烧 + 全路径验签 + 无 fastboot 后门 + 无 kexec"下，自编译内核无法被引导。

---

## 四、复现命令

```bash
# 1) 读 bootloader 状态
fastboot getvar all

# 2) 解出某镜像的签名参数与摘要（需 openssl）
#    DER 偏移 = 数据区长度 = params INTEGER
openssl asn1parse -inform DER -in <der_1280B> -i | tail -6
openssl pkeyutl -verifyrecover -pubin -inkey <cert_pub.pem> -in <sig_256B> \
        -pkeyopt rsa_padding_mode:pkcs1

# 3) 对照前缀哈希
python -c "import hashlib,sys;d=open('<img>','rb').read();\
print(hashlib.sha256(d[:<L>]).hexdigest())"
```

---

## 五、补测（17:47–17:55）：无签名分支 + 解析器实现

### 5.1 「没有签名块就放行」——证伪

| 测试 | 镜像 | 结果 |
|---|---|---|
| T1 | `baseline[:0x3257000]`（截掉签名块，但分区里旧签名仍在原位） | 进系统 |
| T2 | `baseline` 改 `0x800: 00→FF` **且** 签名区 0x1500 清零 | **卡 logo** |

T1 之所以能启动，是因为 `fastboot flash` 只写了 52.8 MB，`0x3257000` 起的旧签名**原封不动**，而数据一个字节没改 → 验签照样通过。
T2 把「数据变了 + 签名没了」两个条件同时给上 → 失败。
结论：**aboot 无条件是"必须验"，不存在"缺签名即跳过"的分支**。

### 5.2 解析器实现：OpenSSL-LK 移植

aboot 里引用了 `lib/openssl/crypto/asn1/tasn_utl.c`、`rsa_eay.c`、`rsa_pk1.c`、`b_print.c`，以及定制日志：

```
Openssl LK: Removed qsort dependency in ameth_lib.c
Openssl LK: removing qsort dependency in tasn_enc
Openssl LK: Removed rand dependency in rsa_eay.c
Openssl LK: Removing rand dependency in rsa_pk1.c
```

即：DER/X.509 解析走的是 **LK 版 OpenSSL 1.0.1 移植**（Qualcomm aboot 常见做法），不是 vivo 手写解析。

外层长度解析（`0x91810B74`）的边界处理是完整的：

```asm
91810b90  tst  r3, #0x80        ; 短/长格式判断
91810bbc  cmp  r7, r4 / bls     ; 越界→报错
91810bd8  cmp  r3, #0x1000000 / bhs  ; 长度上限 16 MB
91810c40  mvn  r2, r4 / cmp r2, r3 / bhi ; 加法溢出检查
```

→ 想在这条链上找"一个 length 字段就砸穿栈"的低成本漏洞，概率很低。

### 5.3 顺带取到的运行时状态（对判断"还有没有别的路"很关键）

```
ro.boot.verifiedbootstate   = green
ro.boot.veritymode          = enforcing
ro.boot.securebootkey       = beta      (keyver 2)
ro.boot.securebootkeyhash   = da758fd5…139d
/system                     = /dev/block/dm-0  (dm-verity 容器)
/oem                        = /dev/block/dm-1
fstab: /system  ... wait,verify ;  /oem ... wait,verify
```

即：**引导层不仅验 boot，还通过 cmdline 把 `veritymode=enforcing` 传给内核**，/system 与 /oem 都挂 dm-verity。换 system 也同样被 vivo 的 verity 密钥锁住。

