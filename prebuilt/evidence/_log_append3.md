
### 23:5x–00:0x 续记（sys10 实测 + sys11 待刷）
- **sys10（只保留 -iwlan0）已刷入并实测**：编译/刷写/首启都正常（40 s），但点 WiFi 开关后
  `dumpsys wifi` 回到 disabled、`init.svc.wpa_supplicant=stopped`，且**设备随后整体掉线**。
- 实测日志给出两个新事实：
  1. **init 的 `write` 不解释 `\n`**：`wpa_supplicant` 报
     `Line 1: invalid number "1\neapol_version=1\n..."`、`Invalid configuration line ...`，
     整个 conf 被当成一行。sys11 已把两个 conf 改成单行合法内容
     （`update_config=1` / `ctrl_interface=/data/misc/wifi/sockets`）。
  2. **wlan 内核模块在开关 WiFi 后整个消失**：`lsmod | grep wlan` 为空，`ip link` 只剩
     lo/bond0/dummy0/sit0/rmnet*（22 个），**wlan0 和 p2p0 都不存在**；
     supplicant 因此报 `Could not read interface wlan0 flags: No such device` →
     `nl80211: Failed to set interface 0 to mode 2: -19` → 退出 →
     `found dead hwbinder service for ISupplicant/default` → `ClientMode failed`。
     开机早期（未点 WiFi）`lsmod` 是 `wlan 5866783 0`、ip link 有 wlan0(23)/p2p0(24)，
     所以是「点开关后驱动被卸载/崩溃」。
- **设备行为模式**：每次点 WiFi 开关 → 十几秒后 adb/fastboot 同时消失，
  Windows PnP 保留 `Android Composite ADB Interface` (VID_2D95&PID_6001) 且 Status OK、
  无重枚举 → 不是 bootloop，推测 wlan 驱动/固件崩溃导致整机 hang 或 panic；
  需要物理断电才能恢复（有一次它自行回到 fastboot，`getvar` 在挂起 15 min 后
  终于返回 `0x20000000`，说明设备最终重启进了 fastboot）。
- **源码线索**：`libwifi-hal.so` 字符串含 `wifi_load_driver enter` /
  `wifi_load_driver skip for driver already loaded` / `wlan.driver.status` /
  `/proc/modules` / `/system/vendor/lib/modules/wlan.ko`；wlan.ko 在本机由
  `cnss-daemon` 开机加载（原厂 rc 只有 `on property:wifi.ftmd.load=true` 时
  insmod 另一个 `pronto_wlan.ko`），**全树 rc 没有任何地方设置 `wlan.driver.status`**。
  怀疑 8.1 libwifi-hal 认为驱动未加载而重复 insmod/卸载重载，触发崩溃。
- **sys11（已编译，待刷）**：`init.pd1610.rc` 增加 `on boot / setprop wlan.driver.status ok`，
  让 `wifi_load_driver()` 跳过重载；同时修掉 conf 换行。镜像尚未验证。
- **另一条排查路线（未执行）**：AOSP9 源码版 wifi HAL 与 8.1 `libwifi-hal.so` 是
  `wifi_hal_fn` 结构体布局不匹配（`start()` 里实际调到 `wifi_cleanup+28` 并 SIGSEGV），
  要修需要写结构体转换 shim，工作量大于改 8.1 HAL。当前优先走 8.1 HAL + 属性法。
- **接手建议**：设备恢复后先抓 panic 证据（`adb shell cat /proc/last_kmsg | tail -100`
  或 `/sys/fs/pstore/console-ramoops*`），再决定是继续属性法还是改 HAL；
  每次点开关前先 `lsmod | grep wlan` + `ip link | grep wlan` 做基线。
