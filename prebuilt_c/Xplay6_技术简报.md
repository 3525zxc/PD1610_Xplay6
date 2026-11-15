# vivo Xplay6 (PD1610) 启动链分析简报

> 用于外部技术评审。所有结论均来自本地镜像静态反汇编 + 实机实验，标注"未验证"的部分请当作开放问题。

## 一、设备与现状

```
机型    vivo Xplay6 / PD1610 / MSM8996 / UFS 6 LUN / 4096B 扇区
系统    Android 6.0.1 / PD1610_D_1.15.1（已从 7.1.1 降级成功）
引导层  7.13.15 原厂（未改动）
BL      devinfo 已改：is_unlocked=1 + is_unlock_critical=1
        → fastboot flash 放行，但启动仍验签
基带    IMEI 正常，persist/fsg/modemst1/2 全部保留
恢复    adb shell reboot edl → 9008 可用；1.15.1 与 1.17.12 完整包在手
```

**目标**：刷入 LineageOS 类原生（Android 9/10）或获取 ROOT。

## 二、已确认的三层独立验证

| 层 | 保护对象 | 公钥证据 | 是否 testkey |
|---|---|---|---|
| aboot（MBN 证书链） | boot / recovery | ELF 内嵌 vivo beta CA，含 SW_ID/HW_ID/OEM_ID | 否 |
| recovery `res/keys` | update.zip | mincrypt 格式，仅 1 把，模数 `b96ada8b7d702096...` | 否 |
| boot 内 `/verity_key` | system / oem dm-verity | 模数 `a704dbb9e99cf54b...`，7.x 与 8.x 同一把 | 否 |

- dm-verity 公钥在 7.1.1 与 8.19.16 中**字节级相同**（sha256 `f16f3691ce1e667856add1ddb651b24a023de88cb75b686d45309f6dd88cad5c`）
- fstab 为 `wait,verify`，实测 `ro.boot.veritymode=enforcing` → 校验失败即中止启动，不走 EIO
- recovery 自身 `ro.secure=1` / `ro.debuggable=0` / `ro.adb.secure=1`，无 root shell

## 三、aboot 关键事实

**四版哈希**：

```
7.13.15(7.1.1)  16,777,216  b4d75a9b399a8d28b8bd7ff7c68994beadab708ed3d23d4c399095788efc3c5f
1.15.1 (6.0.1)   4,015,920  09990c24f63c5b6fb6ab32af65ad180fce8350d640f8a67b74ef35eb0d06e3c8
8.19.9 (8.1β)    3,173,696  7f21823d48ffab4aabbded6161000b8dbfd5839b5e2070446cef28fd5d0d5a0e
8.19.16(8.1.0)   3,173,696  fe535256b3e90cb6d4c3fd2f9b7ea734d87366b5af90d22acd1befde24c15c64
```

**8.19.9 与 8.19.16 代码零差异**：784 字节差异全部位于 `0x10A8–0x165A`（3×256 字节 RSA 签名块 + 25 字节版本号），代码段自 `0x8000` 起一字节未变。→ 8.19.x 全系列同一份 aboot 代码。

**架构分水岭**：

| 特征 | 7.13.15 | 8.19.16 |
|---|---|---|
| `ANDROID!` 代码引用 | 0 处 | 7 处 |
| 读 `kernel_addr`(hdr+0xC) | 无 | 有 |
| 读 `ramdisk_addr`(hdr+0x14) | 无 | 有 |
| 地址检查 | overlap 检查 | 完整 `check_addr` |

7.x 走 MBN hash + 证书链，完全不解析 Android boot header；8.x 恢复传统 LK header 解析。

## 四、已排除的路线

| 路线 | 判定 | 硬证据 |
|---|---|---|
| CVE-2013-2598（header 地址覆盖） | **排除** | 7.x 不解析 header（0 处 kernel_addr 取用）；8.x 有 `check_addr`（`0x91D3C218`），拒绝 `0x91D00000–0x922FFFFF`，调用点 `0x91D454F0` 直接校验 `[sb,#0xc]` |
| CVE-2014-0973（RSA 摘要长度） | **已修复** | 完整 19 字节 SHA-256 DigestInfo + `cmp r0,#0x33`（51=19+32）+ PKCS#1 `modlen-11` 填充校验 |
| CVE-2014-0974（FDT 地址） | **不可利用** | `Fdt addresses overlap` 字符串零引用，但控制 FDT 需改 header，header 受签名保护 |
| CVE-2014-4325（fastboot boot） | **排除** | 7.x 与 8.x 命令表均无 `boot` |
| 状态机绕过 | **死代码** | `0x9189B89C` 初值 3，状态 1 全镜像无写入源；`0x91B92D08` 恒 0 |
| 维修工具解锁 | **无增量** | `bbk unlock_vivo` handler @`0x91838894` 只读状态+复位，无网络/crypto/devinfo/fuse 调用 |
| recovery 刷未签名 OTA | **不可行** | `res/keys` 单把 vivo 公钥，非 testkey |
| 自定义 system + 官方 boot | **不可行** | verity 公钥非 testkey + `enforcing` |
| Treble / GSI | **不成立** | GPT 33 个分区，无 vendor/product/odm |
| Kexec | **闭环** | 需 root → 需改 boot → 被签名拦 |

## 五、仍存疑 / 未验证（希望重点看这里）

1. **8.19.16 的 boot 验证函数 `0x91D1F858` 只分析了入口 200 字节**。它走 MBN 头 + `+0x2800` 偏移的 hash 流程，但**签名覆盖的起始地址（0x0 还是 0x1000）尚未确认**。若为 0x1000，则 header 不在签名范围内，`kernel_addr` 可改——但仍有 `check_addr` 拦截。

2. **`0x91D3C218` 的 `check_addr` 实现**：只对 `(addr, len)` 做区间重叠判断，**是否所有调用路径都传入了正确的 len 未穷尽**。已确认 4 个调用点，其中 `0x91D454F0` 用 `kernel_addr`。

3. **8.19.16 的 `system.new.dat`（3.1 GB）尚未解包**，`/vendor` 是真实目录还是符号链接未知。若为符号链接，Treble 结论需修正。

4. **3.18 内核的 `CONFIG_KEXEC` 状态未知**（未从 `boot.img` 提取 `ikconfig`）。

5. **8.19.8 Beta 已 404**，无法确认更早版本是否更松（但 8.19.9→8.19.16 代码零差异，推测同源）。

6. **`res/keys` 只有 1 把公钥**，但未验证 recovery 的 `verify_package()` 是否还有其他旁路（如 `--just_exit`、`--wipe_data` 之外的自定义命令）。

## 六、手头材料

```
C:\qfilx\firmware\
  PD1610MD-patch_8.19.16_for_7.12.5_1108090720.zip   1.95 GB（8.1.0 全量 OTA，含完整启动链）
  PD1610MD-patch_8.19.9_Beta.zip                      106 MB（增量包，但 aboot 是全量）
  81916\   8.19.16 的 aboot/xbl/boot/tz/rpm/hyp/devcfg/keymaster/cmnlib/pmic
  8199\    8.19.9 同上
  rec115\  1.15.1 recovery 解包产物（含 res_keys.txt、default.prop）
C:\qfilx\
  dumps\   NV 分区备份 + devinfo
  exp\     boot 分区备份 + ramdisk_711.cpio（7.1.1，含 fstab.qcom / verity_key）
  gpt_lun0~5.bin
  aboot\RESCUE\  原始 aboot + 测试点照片 + 救砖脚本
```

## 七、需要你判断的问题

1. 上述三层密钥都非 testkey 的前提下，**是否存在不依赖私钥的启动路径**？
2. 第 5 节第 1 条（`0x91D1F858` 的签名覆盖范围）**是否值得继续静态分析**，还是已被 `check_addr` 完全阻断？
3. 有没有**我们没想到的验证层**（例如 TEE、QSEE、XBL 侧的额外检查）可能成为入口？
4. 如果目标降级为"仅获取 ROOT"（不刷 ROM），**是否有比改 boot 更可行的路径**？
5. `eng` + `test-keys` 的成功案例，除了工程机/换 aboot，**还有没有第三种解释**？

---

*反汇编工具：capstone 5.0.7（ARM32）。所有地址与指令均可在上述文件中复核。*
