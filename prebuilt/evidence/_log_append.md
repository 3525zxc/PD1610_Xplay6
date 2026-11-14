
## 续（23:0x–23:4x）sys8 / sys9 与 WiFi 全链路（给后续模型接力）

### 环境与固定命令（切换模型必读）
- WSL 发行版 `PD1610`，源码 `~/los16`（Windows UNC `\\wsl$\PD1610\home\builder\los16`）。
- 编译（**绕开 lunch，本机 lunch 会卡死**）：
  `wsl.exe -d PD1610 -- bash -lc "cd ~/los16 && bash ~/build_pd1610.sh systemimage > ~/build_sysN.log 2>&1"`
  产物 `~/los16/out/target/product/pd1610/system.img`（Android sparse，magic 0x3AFF26ED），
  拷到 `D:\16\PD1610_81\out\system.img` 再刷。增量编译 30–80 s。
- adb/fastboot：`D:\16\PD1610_81\migrated_from_C\qfilx\platform-tools\platform-tools\`（不在 PATH）；
  另有 `/d/16/viqoo_extract/bin/`。
- 刷机三步：`adb reboot bootloader` → `fastboot flash system <img>`（sparse 自动 4×512 MB，约 60 s）
  → `fastboot reboot` → 轮询 `sys.boot_completed`（约 40 s 变 1）。
- `getvar max-download-size` 正常应回 `0x20000000`(512 MB)。若返回
  `AdbWriteEndpointSync failed (121)` 或 `Write to device failed (no link)` = **USB 端点死锁**，
  三个版本的 fastboot 都一样、Windows `pnputil /restart-device` 需管理员会被拒，
  **唯一解法是拔插 USB 线**（手机留在 fastboot，无需断电）。
- 8.1 备份镜像 `backup/81_system_LUN4.bin` 是 system-as-root：debugfs 路径为 `/lib`、`/lib64`、`/vendor/lib*`，
  **不是** `/system/lib*`。抽库：`debugfs -R 'dump /lib64/xxx.so /mnt/d/.../out.so' ...`。
- ELF 工具：`scripts/patch_needed_soname.py <old> <new> <files...>`（原地改 DT_NEEDED/SONAME，
  新名必须更短，剩余补 NUL）、`scripts/scan_soname_refs.py <soname>`（扫 blobs/vendor 里引用它的 ELF）。
- 禁用 `adb root`（会让 adbd 永久 offline）；`cmd wifi set-wifi-enabled` 需 root（uid 2000 拒绝）。
  实测开关用：`am start -a android.settings.WIFI_SETTINGS` + `input tap 1302 434`（屏幕 1440×2560，
  预览图 608×1080 上的开关 (550,183) 换算而来）。

### 本轮改动过的文件（全在 WSL 源码树 `los16/`）
| 文件 | 改动 |
|---|---|
| `system/core/rootdir/init.rc` | `trigger pd1610-crypto-fix`（zygote-start 前）+ 文件末尾动作块：`setprop ro.crypto.state unencrypted`、写 6 组 `/dev/cpuset/*/{cpus,mems}=0-3/0`、`class_start main/late_start` |
| `system/core/init/init.cpp` | 诊断代码 PD1610 DIAG 保留；看门狗 `PD_WD_SECONDS 100000`（不再 120 s 自动回 fastboot） |
| `device/vivo/pd1610/device.mk` | `PRODUCT_PACKAGES += android.hardware.keymaster@3.0-impl`、`android.hardware.biometrics.fingerprint@2.1`、`android.hardware.media.omx@1.0-service`；**wifi HAL 已从 PRODUCT_PACKAGES 删除**（改回原厂 blob） |
| `device/vivo/pd1610/rootdir/init.pd1610.rc` | `on post-fs-data` 增加 `/data/misc/wifi` 三个 mkdir + `write` 两个 supplicant conf + chown/chmod |
| `vendor/vivo/pd1610/pd1610-vendor.mk` | 删：keymaster@3.0-impl.so(32/64)、media.omx service 二进制+rc；wifi HAL 二进制+rc 删后又加回；增：`libaucommonutil81.so`、`libgnss10_81.so`(32/64)、`libwifi10_81.so`/`libwifi11_81.so`、相机 `vif@1.0-impl.so`/`vivodevice@1.0-impl.so` 从 `hw/` 拷一份到 `lib{,64}/` 根 |
| `vendor/vivo/pd1610/proprietary/vendor/**` | 8.1 库改名+DT_NEEDED 补丁：`libaucommonutil81.so`(32/64)、`libgnss10_81.so`(32/64)、`libwifi10_81.so`/`libwifi11_81.so`(64)；4 个 audio impl、9 个 gnss 模块、wifi HAL 二进制和 `vendor.qti.hardware.wifi@1.0_vendor.so` 均已改 NEEDED；原文件留 `.orig` |

### 各版 system.img 与实测结果
| 版 | 内容 | 结果 |
|---|---|---|
| sys5 | keymaster 源码 impl + fingerprint@2.1 | 首启成功 40 s，`android.security.keystore` 注册(svc 120)，但 system_server 卡 phase 600 → ANR 弹窗「System UI isn't responding」 |
| sys6 | + gnss 8.1 库改名（9 处 NEEDED） | **`sys.boot_completed=1`**、`bootanim=stopped`、无 ANR、前台 SetupWizard WelcomeActivity |
| sys7 | + 相机 vif/vivodevice 搜索路径 + AOSP9 OMX 服务 | `ICameraProvider/legacy/0`、`IVivoCameraProvider/default`、`IOmxStore/default`、`IOmx/default` 全注册；指纹/蓝牙/传感器全表正常；相机仍 `Number of camera devices: 0`（116 chromatix/136 mmcamera 库都在镜像里，属运行时枚举） |
| sys8 | + `init.pd1610.rc` 补 supplicant conf | `wpa_supplicant=running`、`ISupplicant/default` 注册；但点开关后 `ClientMode failed` |
| sys9（当前已刷入） | 改回**原厂 wifi HAL** + 8.1 `libwifi10_81/11_81.so` | `init.svc.wifi_hal_legacy=running`（不再 restarting）、`IWifi/default` + `IWifi@1.1/default` 注册；WiFi 状态变成 enabling（不再秒退），**但 supplicant 启动后退出，WiFi 仍未真正打开** |

### WiFi 诊断链（务必按此顺序理解）
1. `service wpa_supplicant` 定义在 `/vendor/etc/init/hw/init.qcom.rc`（**原厂 blob，不是设备树里的
   `root/init.qcom.rc`**，后者只有 14 行 DIAG 标记）。命令行：
   `-ip2p0 -Dnl80211 -c/data/misc/wifi/p2p_supplicant.conf -I.../p2p_supplicant_overlay.conf -N`
   `-iwlan0 -Dnl80211 -c/data/misc/wifi/wpa_supplicant.conf -I.../wpa_supplicant_overlay.conf`
   `-O/data/misc/wifi/sockets -puse_p2p_group_interface=1 -dd -e/data/misc/wifi/entropy.bin -g@android:wpa_wlan0`，
   `class main / socket wpa_wlan0 dgram 660 wifi wifi / disabled / oneshot`，由 wificond 用 ctl.start 拉起。
2. 第一层：擦过 data 后两个 conf 不存在 → `Failed to open config file ... p2p_supplicant.conf` → 退出。
   sys8 补 conf 后解决（supplicant 自己会 `Initing hidl control` / `hidl_register service name default`，
   **8.1 blob 已自带 ISupplicant HIDL，不需要编树内 supplicant 服务**；
   树里 `hardware/interfaces/wifi/supplicant/1.0/default/` 缺失，只有 .hal 和 vts）。
3. 第二层：树内源码 wifi HAL 与 8.1 `libwifi-hal.so` ABI 冲突 →
   tombstone `SIGSEGV fault addr 0x2a`，`libwifi-hal.so (wifi_cleanup+28)` ←
   `V1_2::legacy_hal::WifiLegacyHal::start()` ← `WifiChip::handleChipConfiguration`。
   sys9 改回原厂 blob 后消失。
4. **当前卡点（sys9）**：supplicant 起来了又退出，日志
   `E/wpa_supplicant: Could not read interface p2p0 flags: No such device` →
   `p2p0: Failed to initialize driver interface` → `Deiniting hidl control`；
   接着 framework 报 `found dead hwbinder service for ISupplicant/default`、
   `Failed to get ISupplicant / NoSuchElementException`、`Got null ISupplicant service`。
   `dumpsys wifi` 停在 `Wi-Fi is enabling`，`init.svc.wpa_supplicant=stopped`。
   即：**conf 已通、HAL 已通，只差 p2p0 接口在 supplicant 启动时不存在**（开机早期 ip link 曾同时有 wlan0(23)/p2p0(24)，
   但 enable 之后 wifi HAL 重载驱动，可能只剩 wlan0）。
5. **下一步修法（未执行）**：编辑 `/vendor/etc/init/hw/init.qcom.rc` 的 `service wpa_supplicant`，
   把 `-ip2p0 ... -N` 这段去掉或挪到 wlan0 之后，让 supplicant 只以 `-iwlan0` 启动
   （P 的 `SupplicantStaIfaceHal` 只要 `ISupplicant.getInterface({STA,"wlan0"})`）；
   或先确认 p2p0 是否真不存在再决定是否动态建接口。代价：WiFi Direct 可能不可用，普通 WiFi 能通。
   改完按三步重编/刷/测；实测开关用 `input tap 1302 434`。

### 其它未解决（非致命，按优先级）
- 相机 `Number of camera devices: 0`：库齐全，需查 mm-qcamera-daemon 的 sensor 探测日志/权限。
- `xtwifi-inet-agent` 启动失败：`library "libcurl.so" not found`（XTRA 辅助下载，非致命；可从 8.1 抽 libcurl）。
- 诊断代码仍在：`init.cpp` PD1610 DIAG、`rootdir/etc/init.qcom.rc` 的 kmsg 标记、看门狗、
  AOSP `init.rc` 的 `pd1610-crypto-fix` 临时动作。**发布前要清理并复测**。
- sepolicy 仍 `androidboot.selinux=permissive`，大量 avc denial 待收敛。
- 未产出可刷 ROM zip / TWRP 包；`build\flash_los.ps1` 与 EDL 脚本是更早写的，未在本轮验证。

### 23:40 现场状态（重要）
- 点过一次 WiFi 开关后设备 **自行掉线并重启**：Windows PnP 从 `Android Bootloader Interface`
  变成 `Android Composite ADB Interface` (VID_2D95&PID_6001 / 5FCCBFEB)，
  `adb kill-server && start-server` 后 `adb devices` 显示 `5fccbfeb offline`，随后轮询又变空。
  尚不确定是 WiFi HAL 重启、内核 panic 还是 USB 重枚举；**接手第一步先重新确认设备在线状态**。
- 当前 `D:\16\PD1610_81\out\system.img` = sys9，sha256 `c03e62efda481003fc939e7ff761eb104fd26319b6eef1449c12cbfac0954a8b`，
  已成功刷入（59.9 s，4/4 稀疏块）。
- 截图证据：`evidence\boot_ok_raw.png`（SetupWizard 语言页）、`evidence\wifi_page.png` / `wifi_page2.png`（WiFi 设置页）。
