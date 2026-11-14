# PD1610（vivo Xplay6）LineageOS 16.0 设备树骨架

阶段 3 产物。**纯文本 + 一个 prebuilt 内核，尚未编译过任何 ROM。**

```
device_tree/device/vivo/pd1610/
├── AndroidProducts.mk          lunch 入口（lineage_pd1610-userdebug）
├── BoardConfig.mk              平台/内核/分区/非 Treble 结构（数值全部实测）
├── full_pd1610.mk              产品骨架（core_64_bit + full_base_telephony）
├── lineage_pd1610.mk           Lineage 产品定义
├── device.mk                   拷贝规则、硬件特性、权限 xml
├── system.prop                 640 dpi / Adreno 530 / Rome BT / dsds 等实测属性
├── manifest.xml                原厂 /vendor/manifest.xml 原件（73 个 HAL 条目）
├── proprietary-files.txt       2076 行：1838 文件 + 211 软链 + 15 私有系统库
├── extract-files.sh            adb 或「已展开 ROM 目录」两种来源
├── setup-makefiles.sh          生成 vendor/vivo/pd1610 下的 Android.mk
├── prebuilt/kernel             56,551,493 B Image.gz-dtb（含 DTB@0x8F50C1）
├── rootdir/etc/fstab.qcom      非 Treble fstab（/data 用 encryptable）
├── rootdir/init.pd1610.rc      增量 init（3 段，其余走原厂 init.qcom.rc）
├── keylayout/                  3 个 .kl，取自实机 /system/usr/keylayout
├── bluetooth/bdroid_buildcfg.h
└── sepolicy/vendor/            空目录（首版 permissive）
```

## 为什么是 prebuilt 内核

vivo 没有公开 msm8996/PD1610 的内核源码（`opensource.vivo.com` 只有 2022 年以后的新平台包），
所以内核段**一行都不编译**，直接用官方 8.19.16 boot 里的 `Image.gz-dtb`。
它自带 appended DTB（board-id 0xa 选表），因此不需要 `BOARD_DTB_*` / `TARGET_KERNEL_SOURCE`。

## 放进 LOS16 源码树

```bash
# 1. 设备树
cp -a device_tree/device/vivo/pd1610  <LOS16>/device/vivo/pd1610

# 2. blobs（D:\16\PD1610_81\blobs 已是「展开 ROM」布局：
#    vendor/ 是 /system/vendor 全量，system/lib[64] 是 15 个私有系统库）
cd <LOS16>
source build/envsetup.sh
device/vivo/pd1610/extract-files.sh /d/16/PD1610_81/blobs
#    没有本地 blobs 时直接 ./extract-files.sh 走 adb（设备需已 root）

# 3. 编译（PD1619 的经验：不要在宿主直接 make，用 Docker，python 需指向 python2）
lunch lineage_pd1610-userdebug
make -j$(nproc) bacon
```

## 改这份设备树后先跑校验

```bash
python D:/16/PD1610_81/scripts/verify_device_tree.py
```

它拿**实测数据**逐项比对（不是比对另一份手抄配置）：
boot 头的 page_size / base / 四个 offset / cmdline 原文、5 个分区实际字节数、
`prebuilt/kernel` 与官方 kernel 段的 sha256、`proprietary-files.txt` 里 1838 个文件
与 211 条软链是否都能在 blobs 里找到、fstab 引用的分区是否存在。
当前 **29/29 通过**。

## 已知未验证项（编译/首启前必须过一遍）

1. **`include device/qcom/sepolicy/sepolicy.mk`** —— 该路径取自 LOS16 的
   `xiaomi/msm8996-common`。本设备非 Treble，若该分支只有 `sepolicy-legacy*`，
   改那一行。首版 cmdline 已带 `androidboot.selinux=permissive`，policy 不全会
   打 denial 但不拦启动。
2. **`BOARD_ROOT_EXTRA_SYMLINKS := /vendor:/system/vendor`** —— Android 9 仍有该变量，
   但不同分支实现有差异。若首启 `init` 报找不到 `/vendor/etc/init/hw/init.qcom.rc`，
   说明软链没建出来，靠 `rootdir/init.pd1610.rc` 里那条 `symlink` 兜底（已写）。
3. **fstab 挂载时序** —— 我们的做法是把 fstab 同时装到 `root/fstab.qcom`（ramdisk 根）
   和 `/system/vendor/etc/fstab.qcom`，两份内容一致。原厂 `init.target.rc` 里有
   `mount_all /vendor/etc/fstab.qcom`，读的也是同一份，所以 /data 的加密标志不会打架。
   若首启卡在 `fs_mgr: Failed to mount`，先看 `dmesg | grep -i fs_mgr` 是哪个分区。
4. **原厂 vendor rc 全部保留了**（40 个 HAL service rc + 1210 行 init.qcom.rc）。
   好处是不用重编任何 HAL；代价是里面有一批指向 `/system/bin/vivo_*` 的服务会
   启动失败（只打日志，不拦启动）。等系统起来后用 `lshal` 逐个确认真正需要哪些。
5. **blobs 全量未裁剪**（491.6 MB）。首版走「能用优先」，后续要按
   `DT_NEEDED` 闭包裁掉 `vendor/lib` 里用不到的库，否则 system 镜像吃紧
   （分区 3,221,225,472 B，LOS16 本体约 1.6–1.9 GB，余量约 1.3 GB）。
6. **HAL 版本匹配** —— Pie framework 需要的版本原厂基本都有
   （composer 2.1 / allocator 2.0 / camera provider 2.4 / keymaster 3.0 /
   gatekeeper 1.0 / health 1.0 / sensors 1.0 / wifi 1.0+1.1）。
   唯一已知短板：GNSS 是 1.0 全家桶，缺 `vendor.qti.gnss@1.0-impl.so` 的
   passthrough 组合会导致 system_server abort（PD1619 踩过），blobs 里已全量保留。

## 与 PD1619 参照树的关键差异

| 项 | PD1619（X9Plus） | PD1610（Xplay6） |
|---|---|---|
| SoC | MSM8952 / Adreno 510 | **MSM8996 / Adreno 530** |
| kernel page size | 2048 | **4096** |
| boot 分区 | 64 MB | **96 MB（100,663,296 B）** |
| cmdline securebootkey | `alpha` / ver 1 | **`beta` / ver 2 / hash `da758fd5…`** |
| 触摸 | synaptics_dsx | **fts（FocalTech）** |
| 指纹 | FPC1245 | **Goodix（hbtp_vm / goodixfp）** |
| 声卡 | msm8952-cdp-snd-card | **msm8996-tasha-cdp-snd-card** |
| vendor 布局 | 非 Treble | 非 Treble（同） |
