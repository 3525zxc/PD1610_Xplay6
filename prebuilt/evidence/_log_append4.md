
## 00:0x–00:4x（11-12）WiFi 彻底修通 ✅ —— 最终可复现方案

**结果：`Wi-Fi is enabled`，`wpa_supplicant=running`，wlan0/p2p0 都在，
设置页能列出 9 个 AP（ZTE-fReXGK / ZTE-fReXGK-5G / 10319 / 10319_5G /
6A604 / 10219 / CMCC-dRX9 / Xiaomi_B8F2 / 1）。截图 `evidence\wifi_working.png`。**
`WifiClientModeManager: Wifi is ready to use for client mode`、
`WifiStateMachinePrime: client mode active`、
`WifiScanningService: wifi driver loaded with scan capabilities: max buckets=6`、
`Driver: 4.0.11.213S Firmware: 4:3:3:54`、LOWI 扫描收到 7–10 个 AP。

### 之前几次判断的修正（重要，别再走回头路）
- 「设备卡死/内核 panic」是**误判**：带 `logcat -v time -b all` 流式抓包 +
  每 2 s 采 dmesg（产物 `work/wifi_logcat_stream.txt`、`work/wifi_dmesg_seq.txt`）证明
  设备一直活着（`uptime` 连续增长、`sys.boot_completed=1`），只是点开关后 **USB/adbd 断开一阵**，
  `/proc/last_kmsg` 是 DBGC 二进制缓冲不是 panic，pstore 为空。不必每次断电。
- `WifiScanningService: wifi driver unloaded` 是 WiFi 关闭状态的正常
  `CMD_DRIVER_UNLOADED` 消息（`WifiScanningServiceImpl.java:1108`），不是缺驱动的证据。
- 真正的因果链是下面 4 条，缺一不可。

### WiFi 最终 4 条修复（全部在 sys13 镜像里）
1. **用 AOSP9 源码版 wifi HAL**：`PRODUCT_PACKAGES += android.hardware.wifi@1.0-service`
   （`hardware/interfaces/wifi/1.2/default`），删掉 vivo 的
   `/vendor/bin/hw/android.hardware.wifi@1.0-service` 与其 rc 的拷贝规则。
   它的 rc 带 `capabilities NET_ADMIN NET_RAW SYS_MODULE`，`WifiModeController` 会调
   `DriverTool::LoadDriver()` → `wifi_load_driver()` insmod
   `WIFI_DRIVER_MODULE_PATH=/system/vendor/lib/modules/wlan.ko`（BoardConfig 已设），
   成功后自动 `setprop wlan.driver.status ok`。8.1 原厂 HAL 没有这套逻辑、也无权 insmod，
   所以 wlan0 永远不出现。
2. **删掉 `pd1610-vendor.mk` 里 vivo `libwifi-hal.so` 的拷贝规则**（最关键的一条）：
   AOSP9 会自己编 `libwifi-hal.so`（未 strip 1,385,824 B / 安装后 369,776 B，
   内含 `hardware/qcom/wlan*/qcwcn/wifi_hal` 实现 + `libcld80211.so`）。
   同名 8.1 blob 只有 328,736 B，会**覆盖**它，导致 P 的 `WifiLegacyHal` 用
   8.1 的 `wifi_hal_fn` 布局 → tombstone `libwifi-hal.so wifi_cleanup+28` SIGSEGV。
   之前误以为「P 源码 HAL 与 8.1 libwifi-hal ABI 不兼容」其实是这个覆盖造成的。
   `libwifi10_81.so`/`libwifi11_81.so` 保留给 `vendor.qti.hardware.wifi@1.0_vendor.so`。
3. **BoardConfig.mk 注释掉 `WIFI_DRIVER_FW_PATH_AP/STA`**：定义了它们，
   P 的 `DriverTool` 就会在 createStaIface 时 `wifi_change_fw_path()` 写
   `/sys/module/wlan/parameters/fwpath`（root:root），而 HAL 以 `user wifi` 运行 →
   `Failed to open wlan fw path param: Permission denied` → `Failed to change firmware mode`
   → `WifiVendorHal: Failed to create STA iface`。去掉宏后 `wifi_get_fw_path()` 兜底为 NULL，
   HAL 跳过固件模式切换（与 8.1 原厂行为一致）。
4. **`init.pd1610.rc` 的 `post-fs-data` 补两个 supplicant conf（单行！）**：
   init 的 `write` **不解释 `\n`**，多行字面量会被 wpa_supplicant 当成一行并报
   `Line 1: invalid number "1\neapol_version=1\n..."`。最终用
   `write /data/misc/wifi/wpa_supplicant.conf "update_config=1"` 和
   `write /data/misc/wifi/p2p_supplicant.conf "ctrl_interface=/data/misc/wifi/sockets"`，
   各跟 `chown wifi wifi` + `chmod 0660`。
   另外把 `/vendor/etc/init/hw/init.qcom.rc` 的 `service wpa_supplicant` 里
   `-ip2p0 ... -N` 那段删掉，只保留 `-iwlan0`（p2p0 在驱动重载后可能晚于 supplicant 出现，
   而任一接口初始化失败会让整个 wpa_supplicant 退出；原厂 overlay 本来就有 `p2p_disabled=1`）。

### 最终镜像
- `D:\16\PD1610_81\out\system.img` = **sys13**，sha256
  `686de5de21ad6c8837530836ba9483bd63e69ce660d2de289c4c0a2eecb88e9a`，已刷入并验证。
- 编译 `bash ~/build_pd1610.sh systemimage`（约 75 s）；刷写 60 s；首启 40 s。
- 源码改动文件：`device/vivo/pd1610/{device.mk,BoardConfig.mk,rootdir/init.pd1610.rc}`、
  `vendor/vivo/pd1610/{pd1610-vendor.mk,proprietary/vendor/etc/init/hw/init.qcom.rc}`、
  以及前几轮的 `system/core/rootdir/init.rc` 与 `system/core/init/init.cpp`。

### 当前剩余 TODO（按优先级）
1. 相机 `Number of camera devices: 0`（116 chromatix / 136 mmcamera 库都在镜像里，
   provider 已注册，属运行时 sensor 枚举；查 mm-qcamera-daemon 日志/权限）。
2. `xtwifi-inet-agent` 缺 `libcurl.so`（XTRA 辅助下载，非致命；可从 8.1 抽）。
3. **发布前清理诊断代码**：`init.cpp` PD1610 DIAG、`rootdir/etc/init.qcom.rc` 的 kmsg 标记、
   看门狗 `PD_WD_SECONDS 100000`、AOSP `init.rc` 的 `pd1610-crypto-fix` 临时动作、
   `init.pd1610.rc` 的 `write /proc/sys/kernel/printk "7 7 7 7"`。清理后必须重编 boot+system 并复测首启。
4. sepolicy 仍 permissive，需收集 avc denial 收敛；`configstore-hal-1-0` 因 seccomp
   拦截 `getdents64` 每 5 s 被 SIGSYS 杀掉重启（噪音，可修 seccomp policy）。
5. 未产出可刷 ROM zip / TWRP 包。
