# GitHub Release 描述：LOS16 prebuilt ROM（可直接复制）

> 用法：把下面 `--- 复制开始 ---` 到 `--- 复制结束 ---` 之间的内容整段贴进 Release 的
> 描述框。**建议勾选 `Set as a pre-release`**（理由见正文「这不是正式版」）。
> 附件：`PD1610_LOS16_20261112_UNOFFICIAL.zip` + 本目录同级的 `SHA256SUMS`。
> 建议 tag：`los16-prebuilt-sys13-20261112`，Target：`main`。

--- 复制开始 ---

## PD1610 / vivo Xplay6 · LineageOS 16.0 UNOFFICIAL（prebuilt 路线，sys13 开发快照）

**这是开发快照，不是日常可用的正式版。** 刷机脚本内的原始状态说明写着
「diagnostic code ... must be removed and retested before a public release」，
本包尚未完成这一步，因此以 Pre-release 形式发布，供研究与续修使用。

### 这是什么

vivo Xplay6（PD1610 / MSM8996）的 LineageOS 16.0（Android 9）移植包，走 **prebuilt 路线**：
vivo 未公开该机 3.18 内核源码，因此**不自己编译内核**，直接使用官方 8.19.16 `boot.img`
里的 prebuilt `Image.gz-dtb`（原厂 `3.18.71` 内核），配合从真机提取的 vendor blobs
和借用的 PD1619 设备树，编译出 `system.img`。

> ⚠️ **与本仓库另一条路线无关**：仓库里的 `ROUND*.md`、`flash_log/`、`fixtures/` 是
> **自编译 3.18.120 内核 + BLM 取证**项目。两条路线的内核与镜像不能互换、不能混刷。
> 本 Release 只包含 prebuilt 路线的产物。

### 包内容（42 个条目，解压约 2.01 GB）

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `images/boot.img` | 58,483,968 B | `929fda9985478078f0614a9c3709af69fe3b1c9c8badc50e783261f91ab241ae` |
| `images/system.img` | 1,847,857,444 B | `686de5de21ad6c8837530836ba9483bd63e69ce660d2de289c4c0a2eecb88e9a` |
| `images/recovery.img` | 64,507,904 B | `3af6463790807dfc19216a2ffbce734b328e9c24aa19d148d73b25e4bcdcf218` |
| `flash_all.bat` / `.sh` / `flash_first_time.bat` | — | 刷机脚本，见包内 `sha256sums.txt` |
| `verify.bat` | — | Windows 下用 `certutil` 校验三个 img |
| `patches/` | — | sys13 最终版 7 个源码改动、compat_libs、构建脚本 |
| `tools/` | — | 随包附带的 fastboot / adb |
| `sha256sums.txt` | — | 包内逐文件校验清单 |

**整包**：`PD1610_LOS16_20261112_UNOFFICIAL.zip`，935,087,013 B（约 892 MiB），
SHA-256 `97c3137e5498c1ac28cdde328da45c3660076b47a5e6a13846089688c2126288`。

**回滚基线已包含在包内**：`images/boot.img` 就是原厂 boot（`929fda99…`）。
只把它刷回 `boot` 分区即可回到原厂内核。

### 已验证可用

首次开机约 40 秒、开机向导、WiFi 开启并能扫描到 AP、音频、camera provider HAL、
指纹、蓝牙、传感器、keymaster/keystore、GNSS、OMX。
WiFi 修复的完整因果链与三条已纠正的误判见仓库
`prebuilt/evidence/_log_append4.md`；sys13 `system.img` 是 WiFi 修通后的已知良好基线。

### 未解决 / 已知问题

1. **相机报告 0 个设备**（camera provider HAL 在跑，但没有可用相机设备）。
2. `xtwifi-inet-agent` 缺 `libcurl.so`。
3. **发布前的诊断代码仍在**：boot init 里的 raw-block marker、kmsg markers、
   关闭的 watchdog、临时 crypto-fix action；按脚本自述，需在公开正式版前移除并
   **同时重编 boot + system 复测**。
4. SELinux 为 permissive；configstore HAL 曾出现 seccomp SIGSYS。
5. 随包的 Lineage recovery **未在 PD1610 上验证**，`--recovery` 属可选项，不建议首次刷入。
6. 无 OTA、无 TWRP 卡刷验证、无长期使用数据。

### 刷之前必须知道

- **仅限 PD1610 / vivo Xplay6**，切勿刷到其他机型。
- 需要**已解锁的 bootloader**（本机为 `devinfo +0x10 = 0xFF`）；刷机前请自行备份。
- 从原厂 Funtouch 8.1 首次刷入**必须清除 userdata + cache**（加密 `/data` 无法被本 ROM 挂载），
  即使用 `flash_first_time.bat` 或 `flash_all.bat --wipe`。**这一步会清空手机数据。**
- 脚本只写 `boot` / `system`〔/ 可选 `recovery`〕，并按要求清 `userdata` / `cache`；
  **不碰** `aboot` / `xbl` / `modem` / `persist` / `dsp` / `devinfo` / `misc`。
- 遇到 `AdbWriteEndpointSync failed` / `no link`：保持手机在 fastboot，重新插拔 USB 后重跑脚本。

### 安装（Windows）

1. 下载并**完整解压** zip（不要在压缩包内直接刷）。
2. 运行 `verify.bat`，把输出与 `sha256sums.txt` 对照。
3. 手机进 fastboot 并连上电脑（驱动显示为 Android Bootloader Interface）。
4. 首次从原厂 8.1 刷入：双击 `flash_first_time.bat`（等价于 `flash_all.bat --wipe`）。
   已经是本 ROM、只需更新：双击 `flash_all.bat` 并按提示选择是否清除数据。
5. 首次开机约 40 秒，期间不要断电或拔线。

Linux / macOS：`./flash_all.sh --wipe`（首次）；无 `--wipe` 时脚本会交互询问。
若随包 fastboot 无法运行，安装 platform-tools 后传 `FB=/path/to/fastboot`。

### 校验下载

```bash
sha256sum -c SHA256SUMS
# 期望：PD1610_LOS16_20261112_UNOFFICIAL.zip: OK
```

或用 Git Bash / WSL：

```bash
sha256sum PD1610_LOS16_20261112_UNOFFICIAL.zip
# 97c3137e5498c1ac28cdde328da45c3660076b47a5e6a13846089688c2126288
```

### 源码、记录与冷备

- 本仓库 `prebuilt/`：1042 行移植笔记、WiFi 修复全程、sys13 最终版 `patches/`。
- `docs/RELEASE_NOTES_LOS16.md`：本描述的留档版本。
- `offline/14_prebuilt_upload_checklist.md`：续修所需文件清单与已知差异。
- 完整工程、原厂分区 dump、固件 blob 与 WSL 重建集在百度网盘冷备；
  目录结构与分享链接见 `README.md` 的「百度网盘冷备索引」。

### 免责

UNOFFICIAL 开发构建，按「现状」提供，无任何担保。刷机有变砖风险，
请先备份、确认机型与解锁状态，自行承担后果。这不是 LineageOS 官方发布。

---

## English

**This is a development snapshot, not a daily-driver release.** The bundled
flasher still contains the diagnostic code that its own header says "must be
removed and retested before a public release"; that cleanup has not been done.
Published as a pre-release for research and continuation only.

### What this is

LineageOS 16.0 (Android 9) for the **vivo Xplay6 / PD1610 (MSM8996)**, built via
the **prebuilt route**: vivo never released the 3.18 kernel source for this
device, so the kernel is **not compiled from source**. The stock 8.19.16
`Image.gz-dtb` (kernel `3.18.71`) is reused together with vendor blobs pulled
from the device and a borrowed PD1619 device tree; only `system.img` is built.

> This is unrelated to the repository's other line of work (`ROUND*.md`,
> `flash_log/`, `fixtures/`), which is a **self-compiled 3.18.120 kernel** with
> BLM bootloop forensics. Kernels and images are not interchangeable.

### Contents (42 entries, ~2.01 GB extracted)

| File | Size | SHA-256 |
|---|---|---|
| `images/boot.img` | 58,483,968 B | `929fda9985478078f0614a9c3709af69fe3b1c9c8badc50e783261f91ab241ae` |
| `images/system.img` | 1,847,857,444 B | `686de5de21ad6c8837530836ba9483bd63e69ce660d2de289c4c0a2eecb88e9a` |
| `images/recovery.img` | 64,507,904 B | `3af6463790807dfc19216a2ffbce734b328e9c24aa19d148d73b25e4bcdcf218` |
| `flash_all.bat` / `.sh`, `flash_first_time.bat`, `verify.bat` | — | flashers and checksum helper |
| `patches/`, `tools/`, `sha256sums.txt` | — | final sys13 source changes, compat libs, fastboot/adb, per-file hashes |

**Archive**: `PD1610_LOS16_20261112_UNOFFICIAL.zip`, 935,087,013 B (~892 MiB),
SHA-256 `97c3137e5498c1ac28cdde328da45c3660076b47a5e6a13846089688c2126288`.

**The rollback baseline is inside the archive**: `images/boot.img` is the stock
boot (`929fda99…`). Flash only that file back to `boot` to return to stock.

### Verified working

First boot ~40 s, setup wizard, WiFi enabled with AP scan, audio, camera
provider HAL, fingerprint, Bluetooth, sensors, keymaster/keystore, GNSS, OMX.
The WiFi fix chain and three corrected misdiagnoses are in
`prebuilt/evidence/_log_append4.md`; sys13 is the known-good WiFi-fixed baseline.

### Known issues

1. Camera reports **0 devices** (provider HAL runs, no usable camera device).
2. `xtwifi-inet-agent` is missing `libcurl.so`.
3. Diagnostic code is still present (raw-block marker in boot init, kmsg
   markers, disabled watchdog, temporary crypto-fix action); must be removed
   and **both boot + system rebuilt and retested** before a public release.
4. SELinux is permissive; configstore HAL has shown seccomp SIGSYS.
5. The bundled Lineage recovery is **not validated** on PD1610; avoid
   `--recovery` on a first flash.
6. No OTA, no TWRP sideload validation, no long-term usage data.

### Before flashing

- **PD1610 / vivo Xplay6 only.** Do not flash to any other device.
- Requires an **unlocked bootloader** (`devinfo +0x10 = 0xFF` on this unit). Back up first.
- Coming from stock Funtouch 8.1 **requires erasing userdata + cache** (encrypted
  `/data` cannot be mounted): use `flash_first_time.bat` / `flash_all.bat --wipe`.
  **This wipes the phone.**
- Only `boot` / `system` [/ optional `recovery`] are written, plus the requested
  `userdata` / `cache` erase. `aboot`, `xbl`, `modem`, `persist`, `dsp`,
  `devinfo` and `misc` are untouched.
- On `AdbWriteEndpointSync failed` / `no link`: keep the phone in fastboot,
  reseat the USB cable, rerun.

### Install (Windows)

1. Download and **extract the entire zip** (do not flash from inside the archive).
2. Run `verify.bat` and compare its output with `sha256sums.txt`.
3. Put the phone in fastboot, connect USB (Android Bootloader Interface).
4. First flash from stock 8.1: double-click `flash_first_time.bat`.
   Updating an existing install: `flash_all.bat` and answer the wipe prompt.
5. First boot takes ~40 s; do not disconnect or power off.

Linux / macOS: `./flash_all.sh --wipe` for the first flash; without `--wipe` the
script asks interactively. If the bundled fastboot will not run, install
platform-tools and pass `FB=/path/to/fastboot`.

### Verify the download

```bash
sha256sum -c SHA256SUMS
# expected: PD1610_LOS16_20261112_UNOFFICIAL.zip: OK
```

### Sources, records and cold storage

`prebuilt/` (1042-line porting note, full WiFi fix log, final sys13 `patches/`),
`docs/RELEASE_NOTES_LOS16.md` (archived copy of these notes),
`offline/14_prebuilt_upload_checklist.md` (what a continuation needs).
The full project, stock partition dumps, firmware blobs and the WSL rebuild set
are in a Baidu Netdisk cold backup; see the "Baidu Netdisk cold storage" section
of `README.md` for the folder map and link.

### Disclaimer

UNOFFICIAL development build, provided as-is without warranty of any kind.
Flashing can brick a device. Back up first, confirm model and bootloader state,
and proceed at your own risk. This is not an official LineageOS release.

--- 复制结束 ---
