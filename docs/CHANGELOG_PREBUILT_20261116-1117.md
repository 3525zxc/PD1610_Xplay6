# PD1610 / Xplay6 工作日志（2026-11-16 17:36 → 11-17 14:00）

> 适用范围：vivo Xplay6（PD1610 / MSM8996），LineageOS 16（Android 9）+ 原厂 prebuilt `3.18.71-perf-g8a8c60dd` 内核路线。
> 本日志是从「相机修好」到 11-17 14:00 之间**已完成工作**的整理，供更新项目文档使用。
> 关键结论均来自实机验证；每条标注状态（✅ 已完成并验证 / ⚠️ 已做但未验证 / 🗑 已废弃回滚）。

---

## 一、11-16 下午至深夜：相机 → 按键 → Recovery/TWRP → 分发包

> 两台设备：旧机 `5fccbfeb`（LOS16 日常机）、新机 `2ea753b7`（stock 8.19.16，已验证解锁链路，作参照）。
> 两台都拆过机；音量上/电源键坏，只剩音量下——进 fastboot/recovery 尽量走 adb。

### 1. 相机 0 设备 → 修复 ✅（16:5x–17:36）
- 现象：LOS16 `num_cameras=0`，桌面无相机图标。
- 排查：blobs / ELF 依赖 / DTB / 内核驱动全部正常 → 反汇编 daemon（veneer：目标 = veneer_addr + 16 + pool_value）→ strace 决定性证据：daemon 正常，provider 只枚举到 0 个 sensor subdev → 对照 stock 新机有 7 个 `/system/etc/camera/*.xml`，LOS 没有。
- **根因**：`libmmcamera2_sensor_modules.so` 硬编码读 `/system/etc/camera/msm8996_camera.xml` 加载 sensor 列表；XML 缺失 → daemon 不发探测 ioctl → 内核不注册 sensor subdev → HAL 0 相机。此前「socket 死锁」假设作废。
- 修复：7 份 XML 放进 `device/vivo/pd1610/camera/`，device.mk 加 7 行 `PRODUCT_COPY_FILES`，重编 system.img（sha `566c6b59…`）刷入。
- 验证：`num_cameras` 0→3，v4l-subdev21/22 = imx362/s5k3p3，相机 app 正常。
- 图标后续：AOSP `DisableCameraReceiver` 在 0 相机时已 `pm disable CameraLauncher`（状态存 /data，刷 system 不清）。修法 `adb root` → `pm enable com.android.camera2/com.android.camera.CameraLauncher`（必须 root）。持久。

### 2. 轻触 home 失效 → 修复 ✅（17:39–18:4x）
- 现象：stock 轻触 home 可回主页，LOS 只有按下有效。
- 排查：先误判 `vivo_virtual_key` 位图 → `getevent -t` 全设备抓包纠正：轻触来自 **`goodixfp`(指纹传感器) 的 key 253**，event4 上报 172/158/139，与 DTB 一致。
- **根因**：stock `Generic.kl` 有私有键 `key 253 FINGERPRINT_KEY`，AOSP9 的 framework 无此键 → keycode 253 被 InputReader 当 UNKNOWN 丢弃；照抄 kl 行也没用（framework 不认识 label）。
- 修复：新建 `device/vivo/pd1610/keylayout/goodixfp.kl`（设备名优先于 Generic.kl）：`key 102 HOME` / `key 139 MENU` / `key 158 BACK` / `key 253 HOME`；device.mk 注册拷贝，重编 system.img（sha `3f0f2fbf…`）。
- 坑：`adb remount`+push `/system` 的修改重启即丢，必须重编 system.img；`sendevent` 注入 253 无效，只能真人轻触验证。

### 3. 按键自定义（菜单键短按 = 多任务）✅（18:5x–19:2x）
- 决策：用 LOS16 内建 ButtonSettings，不移植社区 ROM、不做 Magisk 模块。
- 做法：lineage-sdk `config_deviceHardwareKeys` 默认 64（无 MENU 位）→ 新增 overlay `device/vivo/pd1610/overlay/lineage-sdk/.../config.xml` 设为 **7**（HOME|BACK|MENU），device.mk 注册 `DEVICE_PACKAGE_OVERLAYS`。
- 设置：`settings put system key_menu_action 2`、`key_menu_long_press_action 1`；重启后界面才刷新（曾误判不生效）。
- 验证：sendevent 注入 MENU 短按 → 焦点跳最近任务 ✅。system.img sha `8e6fb286…`。
- 配套清单：`D:/16/PD1610_81/PD1610_LOS16_按键自定义与瑕疵排查_指导清单.md`（含 15 项瑕疵排查表）。

### 4. 基线采集 ✅ 只读（19:2x）
- 证据 `evidence/baseline_1116_1930/`（logcat 1.1M / dmesg 488K 等 1.7M）。
- 结论：崩溃 0；传感器全在线；基带 OUT_OF_SERVICE 待插卡验证（`*#06#` 是占位不可信）；SELinux 133 条 avc denied（permissive 放行，收敛 Enforcing 前需补规则——未做）；背光节点 `/sys/devices/soc/leds-qpnp-24/leds/button-backlight`。

### 5. Magisk 安装（旧机）✅（19:3x–20:1x）
- 前置：旧机 out/boot.img 内核段与 stock 逐字节同（sha `085a53e2…`）→ 新机验证过的内核补丁可直接复用。
- **内核 su 拦截补丁**（vivo 在 `prepare_bprm_creds` 检查 basename `su`）：只打分支不动函数入口（入口改 mov/ret 会内核崩溃）：`0xFFFFFFC0001B1F24 tbnz→nop(1f2003d5)`、`0xFFFFFFC0001B2090 tbz→b(04000014)`；字节序陷阱：hex 是机器码值，写入要小端；裸内核偏移 `0x131F24`/`0x132090`。
- 流程：dd dump boot → magiskboot 改两处内核补丁 → Magisk app 注入 ramdisk → `fix_boot_sig.py` 补签名块 → fastboot flash boot。
- **卡 logo 真根因**（推翻多轮错误假设）：任何 repack 都会丢 vivo DER 签名块 → bootloader 解析不出 L → 卡 logo。纯 repack 对照实验是定位关键。
- 成品：`release/los_boot_magisk_final_signed.img`（sha `5de27cc…`），`su -v` = `23.0:MAGISKSU`，system 未动。
- 开发者选项闪退（新机问题，旧 LOS 无）：sepolicy 拦 `persist.logd.logpersistd*`，修法 `/data/adb/service.d/pd1610_permissive.sh`（setenforce 0）。

### 6. LOS recovery ✅（20:15）
- 关键发现：recovery 签名块与 boot **不同**（DER `30820500`、L@+0x3FC、块内含 `/recovery` 分区名）→ 新工具 `fix_recovery_sig.py`。
- 成品 `release/recovery_los_signed.img`（sha `dec1d17d…`）已刷入验证（后被 TWRP 替换，留作回退）。

### 7. TWRP：5 版自编全闪屏 → 混合方案成功 ✅（20:2x–21:45）
- 自编尝试（全失败）：omnirom 3.3.1、官方 TeamWin 3.7.0、TW_FBIOPAN、关 crypto、强制单缓冲——5 版全部 0.5s 循环闪屏（进程级崩溃，pid 递增，崩溃点随机）。
- 对照决定性：同内核/DTB/fstab/像素格式下 LOS recovery 稳定 → 问题在自编 ramdisk 某组件（具体未深挖）。
- **最终方案（成品在用）**：PD1610 kernel+DTB + 官方小米5 gemini TWRP 3.7.0 ramdisk（官方 md5 `a79f6e3a…`）+ magiskboot cpio 注入 `zh_CN/zh_TW.xml`。
- 验证：GUI 稳定（首次完整到 `Set page: main2`+MTP）、触摸 fts 正常、shell 即 root、挂载正常、中文切换成功。
- gemini 原生 img 不能直接 fastboot boot（bootloader 拒 `dtb not found`）；omnirom 源码备份 `/home/builder/recovery_omnirom_backup`。

### 8. vendor 挂载失败 → 修复 ✅（21:48）
- gemini fstab 把 vendor 指向小米5 `cust` 分区，PD1610 没有 → 块设备空报 Invalid argument。PD1610 非 Treble，vendor 在 system 内，本不需要挂。
- 修复：删 fstab 的 `/vendor`、`/vendor_image` 两行 → cpio 注入 → repack → 签名 → dd 刷入。`vendor` 报错 0。
- **最终 TWRP 成品**：`release/twrp_pd1610_final_signed.img`（md5 `c184d6a6…`，sha256 `d626bff7…`）；旧 md5 `b10bf890` 作废。

### 9. 分发包 ✅（21:55）
- 目录 `D:\16\PD1610_81\dist\PD1610_Xplay6_LOS16_Pack_20261116\`（11 文件）+ 整包 zip（1.4G，md5 `4ee2b276…`）。
- 结构：00_解锁工具 / 01_Recovery(twrp+los rec+原厂回退) / 02_ROM(LOS16 zip + magisk boot + 回退 boot) / 03_Magisk / 04_教程 + README_必读.md + CHECKSUMS.txt。
- 关键校验：TWRP `c184d6a6` / ROM zip `b325e8a1`（935,087,013 B）/ Magisk boot `0aebb0a1`（sha `5de27cc…`）。
- 未分发：新机 stock 套件、NV 备份、内部脚本；README 已警告勿刷 modemst/persist。

---

## 二、11-17 凌晨至白天：浏览器 → 音频 → HIFI APP → 校时 → UI → 分发模块

### 10. 系统浏览器黑屏 → 修复（真因是 /data 脏数据）✅
- 症状：系统浏览器 Jelly + 第三方（Via/X浏览器）全部黑屏/闪退。
- 弯路：报 `ClassNotFoundException: androidx.window.extensions` 就判定「WebView 与 Android9 不兼容」，试 Bromite108/96、AOSP92、打内核 do_mount_check 补丁刷 boot、补 .so——全是被 `/data` 残留误导，每换一版报不同错。
- **真相**：反复覆盖安装各种 WebView 后，`/data/user/0/com.android.webview/` 与 odex 缓存堆了与新 apk 不匹配的编译产物，新旧 dex 混用才崩溃。**TWRP 双清 + 重刷包后，同一个 WebView 138 立刻正常**。
- 教训：系统组件黑屏/闪退、尤其反复装过多版本后，先清该 app 数据或双清 /data 再判断版本。
- 副产物（保留可复用）：内核 do_mount_check 补丁（解 vivo 反 /system 挂载），特征串 `0092CF C2C9CDDDDA00`→`0092CF C2C9CEC0DB00`，3.18.71 内核偏移 `0x116E723` 唯一命中；补丁版 boot `D:/xplay6/webview_fix/boot_build/boot_mountfix_signed.img`（sha `169ad246…`）已刷入。参考来源：酷安 ShionKanagawa 的 PD1619 LOS16、wuxianlin/build_magisk_vivo。

### 11. 音频全部修好（三重根因，11:00 闭环）✅
> 推翻此前「软件层穷尽、tfa98xx 功放 DAPM 不上电、修不好」的结论。真因全在配置/供电层，**没动内核**。
- **根因1 HAL 缺库**：`audio.primary.msm8996.so` 依赖 `libaudioroute.so`，ROM 没有 → `loadHwModule() error -19` → HAL 起不来 → 所有设备 unreachable。补原厂 8.19.16 的 `libaudioroute.so`（20348 B，md5 `bae1a7b6…`）即修。
- **根因2 mixer 读错文件（关键）**：HAL 按 `qcom,model=msm8996-tasha-cdp-snd-card` 拼文件名，**实际读 `/vendor/etc/mixer_paths_tasha.xml`**，不是 `mixer_paths.xml`。LOS16 自带的是精简版（96188 B），缺 `low-latency-playback speaker` 等组合路由 → 日志 `unable to find path 'low-latency-playback speaker'` + `Couldn't get the backend index for ret=-14` → 路由中断。用板级完整版（119329 B，md5 `b9edc980…`）覆盖即修。验证判据：`audio_route` 出现 `Apply path: low-latency-playback speaker`。
- **根因3 HIFI 电路没供电**：DT 里 `hifi_3v3@0`/`hifi_4v8@0` 是 `regulator-fixed`（GPIO82/GPIO84，3.3V/4.8V），供 ES9038 DAC 的 `ext-dac-va` 和功放；两者 `state=disabled, num_users=0`（驱动是空壳不主动使能，GPIO 已被 claim）。修复：写 debugfs 可写接口 `echo 1 > /sys/kernel/debug/regulator/hifi_3v3/enable`（4v8 同理）。
- **耳机检测（MBHC 能测到但不上报）**：硬件层正常（`HPH Type`>0、`HPHL/HPHR Impedance`=21、中断有计数），但 `/sys/class/switch/h2w` 不存在、`/dev/input/event7 (Headset Jack)` 驱动不发 switch 事件。绕过：轮询 `tinymix 19`(HPH Type)，变化时用 Java 工具调 `AudioSystem.setDeviceConnectionState()` + 发 `ACTION_HEADSET_PLUG` sticky broadcast。
- **状态栏图标关键坑**：`HEADSET_PLUG` 是 protected broadcast，`am broadcast`（shell uid 2000）被 SecurityException 拒；必须 root + 自建 Context（`ActivityThread.systemMain()`→`getSystemContext()`），app_process 里先 `Looper.prepareMainLooper()`，并等 `sys.boot_completed=1`。
- 验证结果：✅ 外放有声、✅ 耳机有声且状态栏图标正常、✅ 拔插可切换（用户确认）。用户明确「不是带麦耳机，只有耳机」→ 统一按 `headphone` 上报。
- 诊断报告：`D:/xplay6/hifi_port/无声根因诊断与修复.md`。

### 12. 单一 Magisk 模块整合 ✅
- 只保留一个模块 `audio_pd1610`（删除旧的 audio_hal_fix / audio_route_fix），作者 `Amino`，中文描述。
- 内容：`module.prop` / `service.sh`（开机开两路 regulator）/ `jackd.sh`（轮询 HPH Type 桥接，含 boot_completed 等待、单实例保护、失败重试）/ `audiotools.dex`（JackCtl + HiFiCtl）/ `tinymix` / `system/vendor/lib/libaudioroute.so` / `system/vendor/etc/{mixer_paths_tasha.xml,mixer_paths.xml,audio_platform_info.xml}`。
- 重启后模块自启动验证通过。

### 13. HIFI 参数可调 APP ✅
- 包名 `com.pd1610.hifictl`；源码 `D:/xplay6/hifi_port/app_src/`（纯 Java 代码 UI + 反射调 @hide 的 `AudioManager.setParameters`）。
- **实测纠错（关键）**：真正生效的 HAL 参数是 **`enable_hifi=1/0`**，不是早期以为的 `hifi-playback`（后者 HAL 只收下不处理）。`enable_hifi=1` 有 `hifi state change from 0 to 1` 日志。
- **改参数后必须重建输出流**（停播再播）才应用 `headphone-hifi` path（`TERT_MI2S mode=Slave` + `S24_LE`）。
- 三页 UI：状态（只读 DT）/ 调节（模式+音量+时钟+持久化）/ 关于（参数对比 + DSD 结论）。
- **DSD 实测结论**：`DSDEnable=1` 无效；Java AudioTrack 拒绝 DSD（`AUDIO_FORMAT_DSD=0x1A000000`）；DSD 由「输出流本身是 DSD 格式」触发，非参数开关。结论已写入关于页。
- APK：`D:/xplay6/hifi_port/deliver/HifiCtl-v1.0.apk`；结论文档 `HIFI_APP_实测结论.md`。

### 14. 自动网络校时 ✅
- **根因不是 NTP 服务器不通**：实测 UDP 123 —— `ntp.aliyun.com` 101ms/偏差19ms、`cn.pool.ntp.org` 49ms/31ms、`time.windows.com` 203ms/-4ms；`time.google.com` 超时（被墙）。`auto_time=1` 生效、Wi-Fi VALIDATED，但 `dumpsys network_time_update_service` 轮询 24h、缓存 2.9h，系统时间慢 16h40m。
- **真因**：改 `ntp_server` 只写配置、不触发立即同步；time_daemon/modem 又把时间改回。切 `auto_time 0→1` 立刻同步成功。
- 修复：设 `ntp_server=ntp.aliyun.com`；在 `audio_pd1610` 模块里加自动校时守护 `timed.sh` + `NtpProbe.dex`（等 boot_completed → 每 **9 小时**用 UDP 123 测偏差，|offset|>5s 就切 auto_time 0→1 强制同步，日志 `/data/local/tmp/time_pd1610.log`）；`service.sh` 增加启动。重启后常驻。

### 15. HIFI APP 玻璃态 UI（v1.1-glass）✅ / GLES 版 🗑
- 评估 Kyant0/AndroidLiquidGlass：库 minSdk21，但 blur 需 API31、RuntimeShader(lens) 需 API33 → Android9 上效果被库自身跳过，100% 还原不可行；技术栈是 Compose Multiplatform，现有 APP 是纯 Java View。
- **v1.1-glass（已交付并实机验证三页）**：`Glass.java` 用原生 Drawable 做半透明渐变 + 高光 + 亮边 + 投影胶囊/卡片，背景动态蓝紫光晕，顶部玻璃胶囊 tab。APK `D:/xplay6/hifi_port/deliver/HifiCtl-v1.1-glass.apk`（24935 B，classes.dex sha `d8813d6c…`）。
- **v1.2-glassgl（GLES 底部导航折射版）**：用户实测闪退 → 已废弃回滚（删 GlassGLView.java，源码树精确还原 v1.1，dex 哈希与留档一致）。**当前设备 = v1.1-glass**。

### 16. 两版分发用 Magisk 模块 ✅（13:43）
- 用户要分发给他人安装，产出两个 zip（放 `D:/xplay6/hifi_port/deliver/`）：
  - `audio_pd1610_校时版.zip`（53 KB / 12 文件，v1.0-校时版 code101）：完整模块，含校时守护，sha256 `4c53c2819431570c6b7c18c0e80bc0667db65e7649bb8bc306cdc36a2739cc57`。
  - `audio_pd1610_纯音频版.zip`（51 KB / 10 文件，v1.0-音频版 code100）：只做音频修复，无校时文件与启动逻辑，sha256 `2b7debbd2432c2f8838c2e0dfb3c1db3807c8299cd5bc1fe38b6e269120a3b2b`。
- 两版文件在 zip 根目录（Magisk 格式），CRC 校验 OK；两版模块 id 相同，同一设备二选一安装。

---

## 三、设备与产物状态（截至 11-17 14:00）

- **旧机 `5fccbfeb`**：LOS16 + 原厂 prebuilt 内核，Magisk23 root 正常；外放/耳机/状态栏图标全好，HIFI 可用 `com.pd1610.hifictl` v1.1-glass 调节；浏览器正常；boot = do_mount_check 补丁版（`169ad246…`）；SELinux Permissive。
- **新机 `2ea753b7`**：stock 8.19.16，已验证解锁链路（参照机），本轮未动。
- **单模块**：`audio_pd1610`（作者 Amino），两版分发 zip 见 §16。
- **APP**：`com.pd1610.hifictl` v1.1-glass（当前设备所装）。
- **未做/遗留**：SELinux 收敛（133 条 denied 补规则后切 Enforcing）、基带插卡实测、GPS 实测、自编 TWRP ramdisk 问题组件深挖（均不影响使用）。

---

## 四、可复用铁律（本批工作踩坑沉淀）

| 场景 | 要点 |
|---|---|
| repoack boot/recovery | 必须补 vivo DER 签名块，否则卡 logo；boot `308204fc` L@+0x3F8，recovery `30820500` L@+0x3FC |
| `/system` 改文件 | adb remount+push 重启即丢；固化必须重编 system.img |
| WSL 命令 | `bash -lc` 内 `$VAR`/`$(…)` 被 Windows 层展开成空 → 写独立 .sh 到 /mnt/d 执行 |
| Git Bash 路径 | adb push/shell 必加 `MSYS_NO_PATHCONV=1`，否则远程路径被转成 PortableGit 目录 |
| 装 APP 降级 | versionCode 高→低需 `adb install -r -d` |
| 系统组件黑屏 | 反复装过多版本后先清 app 数据/双清 /data，别急判"不兼容" |
| 系统时间不准 | 改 ntp_server 不触发同步；切 auto_time 0→1 才立即同步（已做 9h 守护） |
| 状态栏耳机图标 | HEADSET_PLUG 是 protected broadcast，须 root+自建 Context+先 prepareMainLooper+等 boot_completed |
| 全刷机包 | 必须排除 modemst1/2/fsg/fsc/persist（modemst.mbn 全零，刷入丢 IMEI） |
