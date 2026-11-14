# ③ 固件 blob 依赖清单（完成度 gate `firmware_inventory`）

产物：`offline/03_firmware_inventory.csv`（332 行），原始采集 `flash_log/stock_firmware_full.txt`。

## [O] 观察

| 指标 | 值 |
|---|---|
| 文件总数 | **332** |
| 总字节 | **82,957,648 B（约 79.1 MiB）** |
| `/firmware` | 256 个（modem / DSP / TEE 分段 blob 为主） |
| `/vendor/firmware` | 73 个（GPU、WLAN、指纹、TEE 应用） |
| `/bt_firmware` | 3 个 |
| 自编译 `#9` dmesg 中 `ueventd: firmware: loading` | 54 次（a530 GPU、adsp、modem、mba、cpp_firmware_v1_10_0 等） |

按文件名前缀归类（启发式，非精确归属）：`other/unsigned-blob` 177（多为 `.b00`–`.bxx` 分段）、TEE 系列 50、Modem 21、WLAN 20、SLPI/Sensors 16、GPU Adreno 13+9(legacy)、ADSP 10、Fingerprint 10、Venus/VPU 6。

**关键缺口**：`st_fts.bin`、`fts_threshold.bin`、`CYFW_PD1602.bin` 这三个由我们启用的开源 `fts.c` / `cyttsp_button.c` 请求的固件，**均不在清单里**。这直接解释了 dmesg 里的 `firmware update failed` / `fw_name is empty, don't update!`；芯片靠内置固件工作，所以用户实测「等几秒 + 锁屏唤醒后触摸可用」。

## [H] 判定

- 第 3 档允许「保留固件 blob」，但要求**显式清单化**：本文件 + CSV 已满足 `firmware_inventory` gate（权重 5）。
- 补全 332 个 blob 的精确归属（哪个驱动/哪个子系统加载）需要逐项对照 dmesg 与驱动 `request_firmware` 调用，属于后续可增量工作；当前清单是「存在性 + 大小 + 启发式子系统的」基线，不冒充完整依赖图。
- 要真正到「尽量无闭源 blob」（第 4 档），这 332 个文件就是硬边界：modem / DSP / GPU / TEE 固件无签名、无数据手册，公开案例里也基本都保留（见 `06_prior_art.md`）。

## 可复现

```bash
adb shell 'for d in /vendor/firmware /system/etc/firmware /firmware /bt_firmware; do
  [ -d $d ] && find $d -type f | while read f; do
    echo "$d|$f|$(stat -c %s $f)"; done; done' > flash_log/stock_firmware_full.txt
# 再由 offline/03 的生成脚本产出 CSV（含 likely_subsystem 列）
```
