
### 23:45–23:5x 续记（接力）
- **日志补齐完成**：本文件上一段「续（23:0x–23:4x）」+ `MEMORY.md` 已更新为「首启已打通 / WiFi 待修」。
- **sys10 已编译但未刷入**：把 `vendor/vivo/pd1610/proprietary/vendor/etc/init/hw/init.qcom.rc` 的
  `service wpa_supplicant` 改成只保留 `-iwlan0`（删掉 `-ip2p0 ... -N` 那段），
  理由见上文「当前卡点 p2p0 No such device」。产物 `D:\16\PD1610_81\out\system.img`
  sha256 `ac01ca5f363e6e880e98a04db30fb48288cdc22366a503afbe25662e1c3bd852`，
  镜像内 `system/vendor/etc/init/hw/init.qcom.rc` 已确认是新版。**未执行：刷入与验证**。
- **设备此时不在线**：点过 WiFi 开关后设备掉线，Windows PnP 稳定保留
  `Android Composite ADB Interface` (USB\VID_2D95&PID_6001\5FCCBFEB, Status OK)，
  连续 30 s 采样无重枚举 → 不是 bootloop；但 `adb devices` 空 / 曾短暂显示 `offline`，
  `fastboot devices` 空，`getvar` 等待设备。`adb kill-server/start-server`、`adb reconnect offline`、
  PnP Disable/Enable（Disable 返回「常规故障」，Enable 成功）都无法恢复。
  判断为**设备侧 userspace 卡死或 USB 端点再次挂住**，需要物理断电/拔插 USB。
- **接手第一步**：确认设备在线（adb 或 fastboot）。若仍无 adb：
  请用户断电重启（拔电池排线）或重新拔插 USB；设备进系统后用
  `adb reboot bootloader` → 刷 sys10 → `fastboot reboot` →
  `am start -a android.settings.WIFI_SETTINGS` + `input tap 1302 434` 实测 WiFi。
  若只能进 EDL(9008)：用 `simg2img` 把 sys10 sparse 展开成 raw(3.2 GB)，
  走 `QSaharaServer` + `fh_loader`，LUN4 / start_sector=71946 / 786432 扇区 / 4096 B。
- 备用定位手段：若 sys10 仍不行，检查 `p2p0` 是否在 wifi HAL configureChip 之后出现
  （`ip link`），以及 `wpa_supplicant` 是否还需要 `-g@android:wpa_wlan0` 那个 init socket。
