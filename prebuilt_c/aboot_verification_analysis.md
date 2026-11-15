# vivo Xplay6 (PD1610) 启动链验证机制分析报告

> 设备：vivo Xplay6 / PD1610 / MSM8996 / UFS 6 LUN / 4096B 扇区
> 记录时间：2026-11-08 ~ 2026-11-09
> 分析对象：7.13.15（原厂 7.1.1）、1.15.1（原厂 6.0.1）、8.19.16（内测 8.1.0）三版 aboot
> 原则：全程只读分析本地镜像，不在手机上做未经验证的写入

---

## 1. 摘要

| 项目 | 结论 |
|---|---|
| BL 解锁 | 已成功（devinfo `is_unlocked=1`, `critical=1`），但只放开"写"，不放开"启动" |
| 降级 1.15.1 | **已成功**，现运行 Android 6.0.1 + 7.13.15 引导层 |
| CVE-2013-2598 | **三版全部排除**（8.19.16 含完整 `check_addr`，拒绝 aboot 区间） |
| CVE-2014-0973 | **已修复**（完整 DigestInfo + PKCS#1 结构校验） |
| CVE-2014-0974 | **不可利用**（检查可能不全，但 header 受签名保护，无法构造输入） |
| CVE-2014-4325 | **排除**（命令表无 `boot`） |
| 8.19.16 固件 | **已取得并校验**，完整启动链已提取 |
| 类原生可行性 | 公开官方固件范围内，静态层面无入口；唯一变量是"拿到不验签的 aboot" |

---

## 2. 设备现状（2026-11-09）

```
系统版本   : Android 6.0.1 / PD1610_D_1.15.1
引导层     : 7.13.15（未刷入 1.15.1 的 aboot/xbl）
BL 状态    : devinfo ULC（unlocked + critical unlocked）
data       : 1.15.1 原厂 userdata.img 重建，可正常启动
基带/NV    : persist / fsg / fsc / modemst1 / modemst2 / sec 全部保留
快照命令   : fastboot oem reboot-edl   （8.19.16 引导层可用，当前 7.13.15 不可用）
```

分区布局已验证：7.13.15 与 1.15.1 的 GPT **100% 对齐**（start_sector 与 size 全等），因此降级全程未动 GPT，可随时回退。

---

## 3. 1.15.1 降级实录

### 3.1 关键决策

| 决策 | 原因 |
|---|---|
| 只刷系统层，不动引导链 | 避免 SBL 对旧 aboot/xbl 的潜在回滚校验，杜绝黑砖 |
| 跳过 GPT | 布局零冲突，保留原分区表，可回退 |
| 跳过 `devinfo` | XML 中该条目是**擦除**操作，会抹掉 BL 解锁状态 |
| 跳过 `splash` / `cdt` | 保留开机画面与硬件配置，便于判断启动阶段 |
| 跳过 NV 六分区 | `persist/fsg/fsc/modemst1/modemst2/sec`，保护 IMEI 与传感器校准 |

### 3.2 阶段一：系统层（6 分区 / 3.1 GB）

```
LUN0 cache      <- cache.img        6.1 MB
LUN0 oem        <- oem.img         17.6 MB
LUN0 apps       <- apps.img       398.1 MB
LUN4 boot       <- boot.img        50.3 MB
LUN4 system     <- system.img    2571.9 MB
LUN4 recovery   <- recovery.img    59.1 MB
```

执行方式：`QSaharaServer` 上传 `prog_ufs_firehose_8996_ddr.elf` → `fh_loader --sendxml`。
结果：`{All Finished Successfully}`，写入速度约 37 MB/s。

**验证结果**：复位后设备进入 **6.0.1 锁屏界面**，证明 7.13.15 的 aboot **接受** 1.15.1 的 boot，引导链无需改动。

### 3.3 data 重建

问题：6.0.1 recovery 无法格式化 7.1.1 加密的 `/data`：

```
Formatting /data...
format_volume result=-1...      ← 失败
Formatting /cache...
format_volume result=0...       ← 成功
```

解决：改用 fastboot 直接写入原厂镜像

```
fastboot erase userdata / misc / cache / keystore
fastboot flash userdata userdata.img     (1.36 GB sparse，3 段全部 OKAY)
```

重启后系统正常启动，进入桌面。

### 3.4 踩坑记录

| 现象 | 原因 | 解决 |
|---|---|---|
| `Sahara protocol error` / `Could not find the file` | `-s 13:"路径"` 被多包一层引号 | 改为 `13:相对文件名`，`cwd` 设为工具目录 |
| `verbose=` is not recognized | 该版 fh_loader 的 `verbose` 是开关 | 去掉 `=1` |
| `fastboot erase` 全部 `Write to device failed` | USB 链路问题（非权限拒绝） | **换 USB 口**后全部 `OKAY` |
| `fastboot oem edl` → `unknown command` | 7.13.15 的 aboot 未注册该命令 | 只能 `adb shell reboot edl` |
| recovery 反复循环 | `misc` 残留 recovery 指令 | `fastboot erase misc` |

---

## 4. 三版 aboot 对比

| 版本 | 文件大小 | entry | SHA-256 |
|---|---|---|---|
| 7.13.15（7.1.1） | 16,777,216（分区 dump） | `0x91800000` | `b4d75a9b399a8d28b8bd7ff7c68994beadab708ed3d23d4c399095788efc3c5f` |
| 1.15.1（6.0.1） | 4,015,920 | `0x91600000` | `09990c24f63c5b6fb6ab32af65ad180fce8350d640f8a67b74ef35eb0d06e3c8` |
| 8.19.16（8.1.0） | 3,173,696 | `0x91D00000` | `fe535256b3e90cb6d4c3fd2f9b7ea734d87366b5af90d22acd1befde24c15c64` |

**架构差异（决定性）**：

| 特征 | 7.13.15 | 8.19.16 |
|---|---|---|
| `ANDROID!` 代码引用 | **0 处** | **7 处** |
| 读取 `kernel_addr` (hdr+0xC) | 无 | 有 |
| 读取 `ramdisk_addr` (hdr+0x14) | 无 | 有 |
| 读取 `tags_addr` (hdr+0x20) | 无 | 有 |
| 地址检查 | overlap 检查 | 完整 `check_addr`（拒绝 `0x91D00000`–`0x922FFFFF`） |

7.13.15 走的是 **MBN hash + 证书链**，完全不解析 Android boot header；8.19.16 保留了传统 LK 的 header 解析路径。

---

## 5. CVE 排查与判定

### 5.1 CVE-2013-2598（LK 地址覆盖）

**7.13.15：排除**

- 全镜像 927,062 条指令，`ANDROID!` 常量引用 **0 处**，字符串仅用于错误提示 `image is not a boot image`
- `kernel_addr / ramdisk_addr / tags_addr` 取用 **0 处**，无攻击面
- 另有地址重叠检查（`kernel/ramdisk addresses overlap` @0x9183DAB4、`Boot image buffer address overlaps` @0x9183E5A8 等 8 处引用）

**8.19.16：同样已修复（完整区间检查）**

它保留了传统 LK 的 header 解析：

```
91D3C47C: mov  r0, #0xf000
91D3C484: movt r0, #0x91df        ; header 缓冲区 0x91DFF000
91D3C48C: mov  r2, #8
91D3C490: bl   0x91D52E68          ; memcmp(buf, "ANDROID!", 8)
91D3C498: beq  0x91D3CAE4          ; 相等 → 解析 header

91D3CB00: ldr  r7, [r4, #0xc]      ; kernel_addr
91D3CB04: ldr  r5, [r4, #0x20]     ; tags_addr
91D3CB0C: ldr  ip, [r4, #0x14]     ; ramdisk_addr
91D3CB2C: bl   0x91D3BCC0          ; 带地址进入加载
```

但它有完整的 `check_aboot_addr_range_overlap` 等价实现（`0x91D3C218`）：

```
91D3C224: mvn  ip, r0
91D3C230: cmp  ip, r1              ; 溢出检查
91D3C240: movt r2, #0x91cf         ; 0x91CFFFFF
91D3C248: bls  0x91d3c278          ; 低于 aboot → 检查 r0+r1
91D3C250: movt r2, #0x922f         ; 0x922FFFFF
91D3C258: bls  0x91d3c28c          ; 落在 aboot 区间 → 返回 -1
91D3C278: add  r0, r0, r1
91D3C280: movt r2, #0x91d0         ; 0x91D00000
91D3C284: cmp  r0, r2
91D3C288: bls  0x91d3c25c          ; 完全在下方 → 通过
```

**它确实被用于 kernel_addr**（调用点 `0x91D454F0`）：

```
91D454E4: ldr  r0, [sb, #0xc]      ; kernel_addr
91D454EC: add  r0, r0, r3          ; kernel_addr + len
91D454F0: bl   0x91D3C218          ; 区间校验
```

任何落在 `0x91D00000`–`0x922FFFFF`（aboot 自身）的地址都会被拒绝。**8.19.16 同样不可利用。**

### 5.2 CVE-2014-0973（RSA 摘要长度）

**已修复**

DigestInfo 由 19 条 `strb` 逐字节构造（7.13.15 @ `0x91810CF8`–`0x91810D88`）：

```
sp[0x00..0x12] = 30 31 30 0d 06 09 60 86 48 01 65 03 04 02 01 05 00 04 20
```

（SHA-256 完整 DER：SEQUENCE → OID 2.16.840.1.101.3.4.2.1 → NULL → OCTET STRING len 0x20）

长度校验：

```
91810DBC: bl  #0x9182154c
91810DC0: cmp r0, #0x33        ; 51 = 19 + 32，必须完整匹配
91810DC4: beq 0x91810e0c       ; 否则走错误分支
```

PKCS#1 v1.5 结构校验（`0x9186CDD4`）：

```
9186CDE0: sub  lr, r1, #0xb    ; modlen - 11（规范最小填充）
9186CDE8: cmp  lr, r3
9186CE00: blt  0x9186ce64      ; 填充空间不足 → 拒绝
9186CE18: mov  r1, #0xff
9186CE1C: strb sb, [r5], #2    ; 00
9186CE24: strb r8, [r3, #1]    ; 01
9186CE2C: bl   memset          ; FF 填充
9186CE34: strb sb, [r5, r7]    ; 00 分隔符
```

无长度截断，无尾随数据可利用空间。

### 5.3 CVE-2014-0974（FDT 地址校验）

**不可利用**

- `Fdt addresses overlap`（0x9187B993）**全镜像零引用**，仅 `Tags addresses overlap`（0x9181D6AC）被使用 → 检查可能不全
- 但控制 FDT 地址必须修改 boot header，而 header 在签名覆盖范围内 → **无法构造输入**

### 5.4 CVE-2014-4325（fastboot boot 绕过）

**排除**

7.13.15 命令表无 `boot`；8.19.16 命令表（字符串区 `0x08D300`–`0x08D460`）为：

```
flash:  erase:  continue  reboot  reboot-bootloader
bbk lock_vivo  oem device-info  preflash
oem enable-charger-screen  oem disable-charger-screen
product  kernel  serialno  oem update- app  bbk unlock_vivo
partition-size:  partition-type:
oem reboot-edl          ← 实用：可从 fastboot 直进 9008
```

同样 **没有 `boot`**。`boot:`（0x07F2F1）是消息文本，不是命令。

---

## 6. 7.13.15 验证链完整还原

### 6.1 三个启动验证入口

| 入口 | 指令 | 说明 |
|---|---|---|
| `0x91839974` | `bl 0x91810E40` | 某启动路径 |
| `0x918399C8` | `b 0x91810E40` | **解锁/锁定分支汇合点** |
| `0x9183E3C8` | `bl 0x91810E84` | 常规启动路径 |

三处全部汇入 `0x91810E40`（tail-call）→ `0x91810E84`（主体），**没有旁路**。

### 6.2 状态机：为什么解锁无效

```
9189B89C  静态初值 = 0x00000003   （锁定态）
91B92D08  静态初值 = 0x00000000   （标志恒 0）
```

两条"跳过验证"分支均为死路：

```
91839C: ldr r3, [0x91B92D08]
9183A8: cmp r3, #0
9183AC: bne 0x9183e5b8       ; 恒不成立

9183B0: bl  0x91811ab0       ; 返回 0x9189B89C 的值
9183B4: cmp r0, #1
9183B8: beq 0x9183eac0       ; 状态 1 无任何写入源
```

状态升级逻辑双重封死：

```
91810C84: bics ip, r0, #2    ; state ∈ {0,2} → 改成 3
918115F0: sub  r1, r1, #1
918115F4: cmp  r1, #1
918115F8: movls r1, #3       ; state ∈ {1,2} → 改成 3
```

全镜像 10 个引用点中，**没有任何一处写入 1**。

### 6.3 参数真相

`androidboot.authorized_kernel=true` 位于 cmdline 模板（与 `veritymode`、`keymaster`、`baseband` 并列），是**验证通过后追加给内核的输出标志**，不是 aboot 的判断开关。

---

## 7. 8.19.16 固件归档

```
C:\qfilx\firmware\PD1610MD-patch_8.19.16_for_7.12.5_1108090720.zip
  2,095,790,333 字节
  MD5    7B71B9C91A1BE011F40BE6935B92AFC9   ✅ 与 4PDA 记录一致
  来源   https://sysuptxdl.vivo.com.cn/upgrade/upload/UpdateFiles/
  Last-Modified  2018-11-08

C:\qfilx\firmware\81916\
  emmc_appsboot.mbn   3,173,696   fe535256b3e90cb6d4c3fd2f9b7ea734d87366b5af90d22acd1befde24c15c64
  boot.img           58,729,728   5a03236df43fb4badeb234e6c9b2ffeead9161ca77e71115b6c923c613d48a52
  xbl.elf             1,830,152   8f6d322a715c37334439229a762e1288feefe28baed775e96eed9cb8e208ded8
  tz.mbn / rpm.mbn / hyp.mbn / devcfg.mbn / keymaster.mbn / cmnlib*.mbn / pmic.elf
  updater-script
```

`updater-script` 关键行：

```
Target: vivo/PD1610/PD1610:8.1.0/OPM1.171019.026/compil11071557:user/release-keys
package_extract_file("boot.img",        "/dev/block/bootdevice/by-name/boot")
assert(package_extract_file("xbl.elf",  "/dev/block/bootdevice/by-name/xbl"))
assert(package_extract_file("emmc_appsboot.mbn", "/dev/block/bootdevice/by-name/aboot"))
...
```

boot.img 头（标准 Android boot header v0）：

```
magic         ANDROID!
kernel_size   0x035EE845  (53.9 MB)
kernel_addr   0x80008000
ramdisk_addr  0x81000000
tags_addr     0x80000100
page_size     0x00001000
os_version    0x10040129  (Android 8.1.0)
```

---

## 8. 待验证项

| 项 | 方法 | 风险 |
|---|---|---|
| 8.19.16 aboot 能否被 SBL 接受 | 需要实机刷写 | **高**（可能需短接） |
| 8.19.16 完整包是否可用于升级 | 卡刷（官方 recovery 验签） | 中（会改变系统版本） |
| 成功案例的 aboot/boot | 需联系原分享者，索取哈希 | 无 |

---

## 9. 后续路线

**推荐**

1. 8.19.16 的地址检查已确认完整，静态路线至此全部封闭
2. 唯一剩余变量：取得一份不验签的 aboot（工程机 dump / 内测泄露）
3. 若无材料来源，维持当前 6.0.1 + 解锁 BL 状态即可

**不建议**

- 修改 `sec.dat`（可能烧不可逆 eFuse）
- patch aboot（SBL 验签，一字节即黑砖）
- 继续在 7.13.15 上找通用 CVE（已逐条证实封闭）

---

## 10. 附：工具与产物

| 文件 | 用途 |
|---|---|
| `C:\qfilx\downgrade\gpt_compare.py` | 当前 GPT 与刷写表坐标比对 |
| `C:\qfilx\downgrade\make_downgrade_xml.py` | 生成保基带/保解锁的刷写清单 |
| `C:\qfilx\downgrade\make_stages.py` | 三阶段清单裁剪 |
| `C:\qfilx\downgrade\flash_exec.py` | Sahara + fh_loader 命令行刷写 |
| `C:\qfilx\downgrade\cve2598_scan.py` | ANDROID! magic 与 header 字段扫描 |
| `C:\qfilx\downgrade\cve0973_audit.py` | 签名验证字符串与函数定位 |
| `C:\qfilx\downgrade\verifier_paths.py` | 验证器入口与地址检查覆盖枚举 |
| `C:\qfilx\downgrade\verifier_body.txt` | 7.13.15 验证器完整反汇编（1152 行） |
| `C:\qfilx\firmware\` | 8.19.16 原始包与提取产物 |

---

*本报告所有地址、指令、字节序列均来自本地镜像的静态反汇编（capstone 5.0.7, ARM32），未经实机验证的部分已明确标注。*
