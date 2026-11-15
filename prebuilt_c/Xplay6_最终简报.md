# vivo Xplay6 (PD1610) 启动链研究报告 — 最终简报

> 目的：请独立评审是否还有未被排除的技术路径。
> 所有结论均附可复核的地址或哈希，欢迎指出哪一条证据有误。

---

## 一、设备与目标

| 项 | 值 |
|---|---|
| 机型 | vivo Xplay6 / PD1610 / MSM8996 / UFS / 4096B 扇区 |
| 当前系统 | Android 6.0.1 / `PD1610_D_1.15.1` / `MXB48T` |
| 引导层 | 原厂 `PD1610_D_7.13.15`（aboot SHA256 `b4d75a9b399a8d28...`） |
| BL 状态 | devinfo 已改 `is_unlocked=1` + `is_unlock_critical=1`，`fastboot flash` 放行 |
| 其他 | `verifiedbootstate=green`、`veritymode=enforcing`、基带/IMEI 完好、9008 可用 |
| 目标 | 运行 LineageOS 类原生（Android 7~10）/ 或至少取得 ROOT |

---

## 二、三层密钥体系（全部为 vivo 自有，无一为 AOSP testkey）

| 层 | 保护对象 | 公钥指纹 | 能否自签 |
|---|---|---|---|
| aboot MBN 证书链 | boot / recovery 镜像 | vivo root beta CA（`OU=DEBUG=2`），三版 aboot 同一信任根 | 否 |
| recovery `res/keys` | OTA `update.zip` | 1 把，模数 `b96ada8b7d702096...` | 否 |
| dm-verity `/verity_key` | system 分区 | 模数 `a704dbb9e99cf54b...`（7.1.1 与 8.1.0 **字节级相同**） | 否 |

AOSP 公开 testkey 模数为 `e8eb784d2f4d5491...`，与上述任意一把均不匹配。

---

## 三、决定性实验（2026-11-09，单变量）

**方法**：取原厂 1.15.1 `boot.img`（52,790,528 B），只改 header 的 `name` 字段（偏移 `0x30..0x38`，9 字节 → `VIVOTEST1`），其余字节完全不动，`fastboot flash boot` 写入。

**结构基准**：
```
header      0x00000000 .. 0x00000240
kernel      0x00001000 .. 0x02B1B000   (43.10 MB)
ramdisk     0x02B1B000 .. 0x03257000   ( 7.40 MB)
签名块      0x03257000 .. 0x03258500   ( 5,376 B, DER 30 82 04 FC)
cmdline     @0x40，实际 365 字节
```

**结果**：`fastboot flash` 返回 `OKAY`，重启后**卡在 vivo logo**，adb / fastboot / 9008 全部不可见。

**恢复**：进 fastboot 刷回原镜像 → 28 秒进系统，属性全部恢复正常。

**结论**：`name` 字段不参与 kernel 加载、ramdisk 解压、dt 匹配中的任何一项。它一改就失败，只能解释为**覆盖整个 boot 分区的完整性校验**。任何未签名 boot 都无法启动。

---

## 四、真实阻断点（7.13.15 aboot 反汇编）

启动主线：`0x9183D63C`（跳核函数）→ `bl 0x9181DE78`，返回值被逐项检查：

```
9183D6C0: bl  0x9181DE78      ; 加载 + 校验
9183D6C4: cmp r0, #0
9183D6C8: bne 0x9183D82C      ; 失败 → 错误处理
```

`0x9181DE78` 内部：

```
9181DEA0: bl 0x91850854        → 失败即 return 1
9181DEDC: bl 0x9181CC64        → 失败即 return 1
9181DF10: bl 0x918398C4        → 地址范围检查（0x917FFFFF / 0x91DFFFFF）
9181DF48: bl 0x91852270        → dt.img 解析，失败即跳错
9181DF60: bl 0x91851560        → blt 错误分支
9181DF70: bl 0x918010E0        → bne 错误分支
```

配套字符串：`0x9187BB10 = "Invalid device tree header"`。

**每个返回值都被 `cmp` + 条件跳转检查，没有旁路。**

---

## 五、已排除的路线（每条都有证据）

| 路线 | 结论 | 关键证据 |
|---|---|---|
| 改 devinfo 解锁 → 启动未签名 boot | 无效 | 解锁只放开 `fastboot flash` 写权限；`verifiedbootstate` 仍 green、`veritymode` 仍 enforcing |
| `fastboot boot` 绕过 | 无效 | 命令表无 `boot` 项，实测返回 `unknown command or device is lock` |
| CVE-2013-2598（header 地址覆盖 LK） | 排除 | 三版 aboot 均有 `check_aboot_addr_range_overlap`（7.1.1 @`0x918398C4`/`0x9183E898`，8.19.16 @`0x91D3C218`），双边界拦截 `kernel_addr` |
| CVE-2014-0973（RSA 摘要长度） | 已修复 | 完整 19 字节 SHA-256 DigestInfo（`30 31 30 0d 06 09 60 86 48 01 65 03 04 02 01 05 00 04 20`）+ `cmp r0,#0x33`（51）+ PKCS#1 v1.5 结构校验 |
| CVE-2014-0974（FDT 地址） | 排除 | `Fdt addresses overlap` 字符串零引用，但 header 受签名保护，无法构造输入 |
| 自签 system（recovery `res/keys`） | 无效 | 公钥非 testkey；recovery 为 `ro.secure=1` / `ro.debuggable=0` |
| 自签 system（dm-verity） | 无效 | `verity_key` 非 testkey，且 7.1.1 与 8.1.0 同一把 |
| 原厂 recovery 刷 unsigned TWRP | 无效 | `update.zip` 验签用 vivo 公钥，改名为 `update.zip` 必然 `signature verification failed` |
| Treble / GSI | 硬件不支持 | GPT 33 个分区，**无 vendor / product / odm** |
| Kexec | 闭环 | 需 root；root 需改 boot 或刷 Magisk；改 boot 被完整性校验拦 |
| `bbk unlock_vivo` / 维修工具 | 无增量 | handler `0x91838894` 只读状态 + 复位，无网络/crypto/fuse 调用 |
| firehose peek/poke 注入 | 工程上不可行 | Xplay6 firehose **确实支持** peek/poke，但需 ROP 链跨 EDL→aboot 时间窗，且重启失效 |
| 8.19.x 内测固件 | 不比 7.1.1 松 | 8.19.9 与 8.19.16 的 aboot **代码段字节级相同**（784 字节差异全在 3×256B RSA 签名块 + 版本号）；8.19.16 反而恢复 header 解析但带完整 `check_addr` |

---

## 六、唯一自洽的解释

网上流传的 `lineage_pd1610-eng 10` / `eng.root.20261014.103120 test-keys` / `3.18.124-perf-g2363427e-dirty` 截图：

- `eng` + `test-keys` 是本地 `lunch lineage_pd1610-eng` 的默认产物，**零售机官方系统不可能出现**
- 作者原话「解 BL 跟 9008 实际作用范围一样，实际无意义」「自己编译的，逆向一下内核驱动自己做个 dt 就可以搞了」
- 该开发者**拒绝提供** boot / aboot / 设备树文件

在「boot 必须通过完整性校验」这一实测事实下，只有两种可能：**工程机（bootloader 不验签）**，或**内部流出的放宽验签 aboot**。两者都无法通过公开渠道复现。

---

## 七、当前设备状态

```
系统      Android 6.0.1 / 1.15.1 / MXB48T
引导层    原厂 7.13.15，未被修改
BL        devinfo ULC，fastboot 可写
基带/IMEI 完好
boot      原厂镜像，已验证可正常启动
恢复      fastboot 可用 / 9008 可用 / 1.15.1 + 1.17.12 完整包在手
```

---

## 八、想请你判断的问题

1. 在「boot 分区完整性校验覆盖全镜像、且无任何私钥」的前提下，是否存在**不依赖私钥、也不依赖工程机**的启动路径？
2. 上面第五节有没有哪条结论的证据链不成立？如果有，请指出具体是哪一条、错在哪。
3. 如果目标降级为「仅 ROOT、不换 ROM」，在 Android 6.0.1 + 已解锁 BL + 9008 可用的组合下，有没有比改 boot 更可行的路径？
4. `eng` + `test-keys` 案例，除了「工程机 / 换过 aboot」，还有没有第三种能通过公开材料复现的解释？

---

## 九、分析产物（可复核）

```
aboot 原件      C:\qfilx\probe\aboot.bin              (7.13.15, 16 MB)
8.19.16 启动链  C:\qfilx\firmware\81916\              (emmc_appsboot.mbn / boot.img / ramdisk)
实验镜像        C:\qfilx\boottest\boot_00_baseline.img
                C:\qfilx\boottest\boot_01_name.img    (本次实验用，已证否)
执行器          C:\qfilx\boottest\boottest.py
详细分析        C:\Users\Tse\WorkBuddy\寒霜刷机\boot_state_machine_analysis.md
```

三版 aboot SHA256：
```
7.13.15  b4d75a9b399a8d28b8bd7ff7c68994beadab708ed3d23d4c399095788efc3c5f
1.15.1   09990c24f63c5b6fb6ab32af65ad180fce8350d640f8a67b74ef35eb0d06e3c8
8.19.16  fe535256b3e90cb6d4c3fd2f9b7ea734d87366b5af90d22acd1befde24c15c64
```
