# Xplay6 运行类原生的可行路径：kexec 二阶段加载

> 日期：2026-11-09
> 目标：运行 LineageOS 类原生系统（不是 root，不是改 boot）
> 前提：bootloader 已解锁、9008 可用、设备当前为 1.15.1 + 7.13.15 aboot

---

## 一、为什么只剩这条路

### 已被证伪的路径

| 路径 | 失败原因 | 证据 |
|---|---|---|
| 改 boot 分区 | aboot 对 boot 全镜像做完整性校验，改任何字节都失败 | 三次单字节实验 + 完整验签链反汇编 |
| 自签 boot | 需要 vivo 私钥，且证书是自签名 CA（`scm_beta`） | boot 尾部证书与 aboot @0x81059 哈希一致 |
| 自签 system | dm-verity 公钥非 testkey，且 `verify` 强制开启 | 1.15.1 fstab 实测 `wait,verify` |
| 换 aboot | SBL 验签，改一字节就变砖 | 11-08 实测黑屏，需拆机短接救回 |
| 工程机 aboot | 无公开渠道，案例作者拒绝提供 | — |

### 剩下的唯一结构

```
原厂 boot（签名有效，aboot 放行）
    ↓
原厂内核启动（3.18.20）
    ↓
在这个内核里做文章
    ↓
加载自编译内核 + 自定义 system
```

**关键洞察**：kexec 加载的内核是**我们自己编译的**，它的 fstab 可以不带 `verify`，因此可以挂载未经签名的 system 分区。

**这是唯一不需要破解 aboot 验签、也不需要私钥的路径。**

---

## 二、技术前提核实结果

| 前提 | 状态 | 证据 |
|---|---|---|
| 内核支持 kexec | ✅ **已确认** | `/proc/kallsyms`: `sys_kexec_load`、`compat_sys_kexec_load`、`sys_kexec_file_load` |
| `/data` 可写 | ✅ 已确认 | `touch /data/local/tmp/_t` 成功 |
| 存在 init.d | ❌ 不存在 | `/system/etc/init.d`、`/data/local/userinit.d` 均无 |
| SELinux | ⚠️ Enforcing，shell 域 `u:r:shell:s0` | `getenforce` = Enforcing |
| `/dev/binder` | ✅ `rw-rw-rw-`，类型 `binder_device` | 可用于 Dirty COW |
| 内核补丁级别 | ⚠️ 3.18.20 < Dirty COW 修复版 3.18.43 | 大概率未修复，未验证 |
| 本机 C 编译器 | ❌ 无 | gcc/clang/NDK 全无 |

---

## 三、完整技术路径

### 阶段 1：取得内核级权限

**目标**：获得 `CAP_SYS_BOOT`，以调用 `kexec_load`

**候选漏洞**：

| CVE | 适用性 | 状态 |
|---|---|---|
| CVE-2016-5195（Dirty COW） | 3.18.20 大概率未修复 | 需验证 |
| CVE-2019-2215（Binder UAF） | 3.18 受影响，2018-02 修复，本机 2016-12 构建 | 需验证 |
| CVE-2016-8655（AF_PACKET） | 2016-11-30 公开，晚于本机构建 | 需验证 |

**阻碍**：
- 本机无编译器，无法自行编译 exploit
- VIKIROOT 需要 patched sepolicy（改 boot）→ 撞死结

**必须解决**：
1. 搭建 aarch64 交叉编译环境（Linux + NDK 或 Linaro toolchain）
2. 或找到可信的 prebuilt binary
3. 验证 SELinux 是否允许 shell 域执行 kexec

### 阶段 2：SELinux 关卡（最大的不确定性）

即使拿到 uid 0，SELinux 域仍是 `u:r:shell:s0`。`kexec_load` 需要 `kernel` 类的 `kexec_load` 权限。

**三种可能**：

| 情况 | 结果 | 应对 |
|---|---|---|
| shell 域本身允许 | 直接成功 | 最好 |
| 需要切到 init 域 | 需要 exploit 支持域切换 | 类似 VIKIROOT 的做法，但需 sepolicy 配合 |
| 完全禁止 | 死路 | 需找其他加载方式 |

**目前无法判断属于哪种**——`/sys/fs/selinux/class/kernel/perms` 读不到，没有 sepolicy 源码。

**这一关可能直接终结整条路径。**

### 阶段 3：编译目标系统

如果阶段 1、2 通过，需要准备：

| 组件 | 内容 | 难度 |
|---|---|---|
| 内核 | CAF msm8996 3.18 分支（对应成功案例的 3.18.124） | 高（需源码 + 交叉编译） |
| initramfs | 最小 rootfs，含 init、busybox、kexec 工具 | 中 |
| system | LineageOS 14.1（Android 7.1，与内核匹配）+ 原厂 vendor blobs | 极高（需完整设备树） |
| 设备树 | Xplay6 的 DTS（屏幕、触摸、传感器、摄像头） | 极高（需逆向原厂 dt.img） |

**这部分是整个方案里工作量最大的，也是成功案例作者说"自己编译的，逆向一下内核驱动自己做个 dt"对应的部分。**

### 阶段 4：自动化（每次开机都要重做）

因为 boot 分区没变，每次冷启动都会进入原厂系统。要让它"看起来像类原生"，需要：

```
原厂系统启动 → 自动执行 exploit → 提权 → kexec → 进入 LineageOS
```

**自启动方案**：

| 方案 | 可行性 |
|---|---|
| init.d 脚本 | ❌ 不存在该目录 |
| 修改 init.rc | ❌ 在 boot ramdisk 里，改不了 |
| 安装自启 app（开机广播） | ✅ 可行，但需用户手动装一次 |
| Xposed / 框架 | 需 root，循环 |

**结论**：只能靠 app 自启，且每次开机有 10-30 秒的原厂系统过渡期。

---

## 四、现实评估

### 每一步的成功率（主观估计，非精确）

| 阶段 | 成功率 | 依据 |
|---|---|---|
| 1. 提权（Dirty COW） | 60% | 版本号支持未修复，但需编译 + 可能有 SELinux 阻碍 |
| 2. SELinux 允许 kexec | **30%** | 完全未知，可能直接死 |
| 3. 编译完整系统 | 20% | 需要设备树、vendor blobs、大量调试 |
| 4. 自动化 | 80% | app 自启是成熟方案 |
| **全链条** | **约 3%** | 各阶段相乘 |

### 这条路能带来什么

**如果全部成功**：
- 开机后能进入 LineageOS
- 但底层仍是"原厂 boot → 原厂内核 → exploit → kexec"的链
- 每次冷启动需 10-30 秒过渡
- exploit 失败就回到原厂系统

**它不是真正的"刷机"，是"运行时切换"。**

### 与"工程机 aboot"的对比

| 项 | kexec 方案 | 工程机 aboot |
|---|---|---|
| 需要私钥 | 否 | 否 |
| 需要额外硬件 | 否 | 是（工程机或内部 aboot） |
| 每次开机需重做 | **是** | 否 |
| 稳定性 | 低（依赖 exploit） | 高 |
| 工作量 | 极大 | 极小（如果有文件） |
| 公开可行性 | 理论可行 | 无渠道 |

---

## 五、建议的最小验证顺序

在投入大量工作前，先做三个低成本验证：

### 验证 1：Dirty COW 是否存在（最关键）

**方法**：编译一个最小 PoC，只做检测不利用

```c
// 伪代码
void *map = mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, fd_ro, 0);
// 两线程：一个 madvise(MADV_DONTNEED)，一个 memcpy 写入
// 检查是否写入成功
```

**需要**：aarch64 编译环境

**输出**：能写 → 漏洞存在；不能写 → 已修复

### 验证 2：SELinux 是否允许 kexec

**方法**：需要先有 root（循环依赖）

**替代**：分析 sepolicy（需要 `sepolicy-inject` 或 `sesearch` 工具，以及 `sepolicy` 文件）

**当前状态**：无法读取

### 验证 3：kexec 的具体接口

**方法**：`sys_kexec_load` 存在，但需要确认：
- 是否支持 ARM64 的 kexec（有些平台只支持 crash dump）
- 是否需要 `kexec_file_load`（更严格）

**方法**：反汇编内核的 `sys_kexec_load`，看是否有完整实现

---

## 六、结论

**kexec 路径在架构上成立，是从"改 boot"这条死路之外唯一不需要私钥的方案。**

**但它的瓶颈不在 aboot，在三个地方**：

1. **没有编译器**——本机无法产出任何 ARM64 二进制
2. **SELinux 未知**——可能直接禁止 shell 域调 kexec
3. **设备树/vendor 工作量**——即使跑通 kexec，做一个能用的 LineageOS 仍是数十小时的工作

**如果要做，最小启动动作是**：先搭一台 Linux 编译环境，编译 Dirty COW 检测程序，在设备上跑一次。**这一步的结论决定后面全部是否值得投入。**

**如果不做，设备维持现状**：1.15.1 音质版 + BL 解锁 + 基带完好 + 9008 可恢复，这是公开条件下的最优状态。
