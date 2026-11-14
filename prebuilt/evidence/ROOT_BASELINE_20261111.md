# PD1610 8.1 · root 通道全分区基线备份

- 时间：2026-11-11 14:49–15:00
- 设备状态：Android 8.1.0 / PD1610_D_8.19.16，`ro.boot.flash.locked=0`、`verifiedbootstate=orange`、`adb root` 可用
- 产物目录：`D:\16\PD1610_81\backup\root_20261111\`（4.79 GB，55 个分区）
- 清单：`_manifest.json`（含每个分区的完整 sha256、落盘字节数、耗时）
- 工具：`scripts\dump_partitions_root.py`（备份）、`scripts\restore_partition_root.py`（校验/回写）

## 1. 方法

不再使用 EDL：解锁生效后 adb 直接以 root 运行，可读全部块设备。

| 环节 | 做法 |
|---|---|
| 枚举 | `blockdev --getsize64 /dev/block/bootdevice/by-name/*`，取真实字节数（非 GPT 名义长度） |
| 读取 | `adb pull /dev/block/bootdevice/by-name/<p>`，实测 9.5–17 MB/s，比 `exec-out dd`（2.9 MB/s）快约 3 倍 |
| 完整性 | 本地流式 sha256 **+** 设备端 `sha256sum`，两侧逐一比对；长度必须等于分区字节数 |
| 大分区 | `userdata` 112.7 GB 超过 D 盘余量，只采样头部 16 MB（ext4 超级块 / 加密元数据） |

坑：toybox `dd` 把统计行写进 **stdout**，会污染落盘镜像（首次测试多出 88 B）。已改为客户端精确截取 N 字节。三条独立通道（pull / `dd bs=4M` / `dd bs=1M`）取到的 boot 分区 sha256 完全相同（`02010ab6…`），确认 pull 通道字节精确。

## 2. 结果

**55/55 分区全部 `size_ok=True sha_ok=True`，0 失败。**

| 分区 | 大小 | sha256(前 16) |
|---|---|---|
| userdata（仅采样 16 MB） | 120980.2 MB | `f539fabf6bb06929` |
| system | 3221.2 MB | `cafc66c1f5fbd2b1` |
| apps | 536.9 MB | `43ca5a1c508acf35` |
| cache | 268.4 MB | `7c745dc4cc97601a` |
| boot | 100.7 MB | `02010ab600d542db` |
| recovery | 100.7 MB | `c6362174255e94d3` |
| survival | 100.7 MB | `4dd55ab9171ae873` |
| modem | 99.6 MB | `1ab898dacb703f3e` |
| bluetooth | 67.1 MB | `1a219b261798769c` |
| oem | 67.1 MB | `e8acf5dd6c78b517` |
| splash | 34.2 MB | `efd199079045b4ba` |
| mdtp | 33.6 MB | `c47821e639220f11` |
| persist | 33.6 MB | `6c020c7b34766a9d` |
| aboot / abootbak | 16.8 MB | `3ce25555e4390bc1` / `75112250abbe060c` |
| dsp | 16.8 MB | `8e04b46338134e81` |
| apanic / backup / reserved | 10.5 MB | `a876752081bca960` / `acb190257813d527` / `e5b844cc57f57094` |
| xbl / xblbak | 4.1 MB | `c5a0dc961fd6f411` / `3a48fc0524432adc` |
| tz / tzbak | 2.1 MB | `3c5ab97cf71339fd` / `81a2d0fd9b44f7cd` |
| modemst1 / modemst2 / fsg / sti | 2.1 MB | 见 manifest |
| ddr / dip / misc | 1.0 MB | 见 manifest |

其余 25 个分区均 < 1 MB（cdt、devinfo、frp、fsc、sec、ssd、pmic、hyp、keymaster、cmnlib、devcfg、rpm、tz 备份组等），完整清单与 sha256 见 `_manifest.json`。

## 3. 与 EDL 基线的交叉校验

| 分区 | 对比对象 | 结果 |
|---|---|---|
| aboot | `backup\81_aboot_LUN4.bin`（EDL 读回） | **逐字节一致** |
| xbl | `backup\81_xbl_LUN1.bin`（EDL 读回） | **逐字节一致** |
| system | `backup\81_system_LUN4.bin`（做包权威基线） | **逐字节一致**（3 GB） |
| boot | `work\boot_81_mod_lfix.img` | 前 58,705,152 B 一致，其余为分区补零 |

→ root 通道与 EDL 通道在大分区、小分区、带签名镜像三类样本上都取到同一份数据，通道可信。

## 4. devinfo 的变化（非备份损坏）

当前 `devinfo.bin` 与解锁前 EDL 基线 `81_devinfo_LUN4.bin` 相差 2820 B，集中在 0xE4 之后；零字节占比由约 1% 升至 47.5%。

结论：**解锁真正生效后，aboot 往 devinfo 追加了记录表**（`ff ff 03 00 | xx 93 00 00 | 00 00 00 00` 周期结构）。解锁位本身未变：

```
+0x10 = FF   (unlocked)
+0x14 = 00   (tampered)
+0x18 = FF
```

对应用户可见结果：`oem device-info` → `unlocked:true / critical unlocked:true`，系统侧 `flash.locked=0 / verifiedbootstate=orange`。

因此：**当前 `devinfo.bin` 是唯一正确的"已解锁态"备份**；旧 EDL 文件只作历史对照。恢复它不会影响解锁，换成旧文件则会退回锁定态。

## 5. 恢复方式

```bat
:: 只读校验（不写设备）
python scripts\restore_partition_root.py verify boot

:: 回写（先 dry-run，再 --yes 真写）
python scripts\restore_partition_root.py restore boot backup\root_20261111\boot.bin --yes
```

约束：
- 文件长度必须严格等于分区字节数，脚本会拒绝；`boot`/`recovery` 这类镜像需先补齐到 100,663,296 B（或直接用 `fastboot flash boot <img>`，无需补齐）
- `userdata` 只有 16 MB 采样，脚本禁止回写
- 回写后自动回读校验 sha256
- 若 `adb` 不可用（系统起不来），仍走 EDL：`C:\qfilx\backup\restore_601.bat` 或 `scripts\restore_81_all.xml`

## 6. 局限

- `userdata` 未全量备份（112.7 GB，D 盘余 91 GB）。用户已确认数据可丢，且每次改 boot 后如触发解密失败可恢复出厂
- 采样 16 MB 仅够判断文件系统类型与加密头，不能做数据恢复
- 备份是"分区镜像"，不含 GPT 表本身；GPT 可用 `sgdisk --backup` 另行取（现有 `restore_81_all.xml` 已含分区布局）

## 7. 下一步（阶段 2）

1. 从 `system.bin` 与 `oem.bin` 提取 vendor blobs：按 `DT_NEEDED` 闭包抽 `lib*.so`、`bin/hw`、`etc/permissions`、firmware
2. 用 `system.bin` 的 `build.prop` / `vendor` 布局确认非 Treble 挂载方式（PD1610 `vendor` 为 `disabled`、`system` 为 `wait,verify`）
3. 以 msm8996 LOS 树 + prebuilt kernel（`boot.bin` 里的 3.18.71-perf）搭设备树
4. 打包自编 ramdisk（`init.rc` / `fstab.qcom` 必须落 ramdisk 根，`/system` 标 `recoveryonly`）
