#
# Copyright (C) 2019 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

DEVICE_PATH := device/vivo/pd1610

# ---------------------------------------------------------------------------
# 本文件所有硬件数值均来自实机实测，不是抄来的估值：
#   boot 头   : work/boot_81_official.img（kernel 56,551,493 B / ramdisk 2,162,779 B）
#   分区大小  : work/part_sizes.txt（55 个 by-name 分区的 blockdev --getsize64）
#   cmdline   : 官方 8.19.16 boot 镜像内的 413 字节原文
#   校验工具  : scripts/verify_device_tree.py（会逐项比对，改错立刻报出来）
# ---------------------------------------------------------------------------

# Platform
TARGET_BOARD_PLATFORM := msm8996
TARGET_BOARD_PLATFORM_GPU := qcom-adreno530
QCOM_HARDWARE_VARIANT := msm8996

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_ABI2 :=
TARGET_CPU_VARIANT := kryo
TARGET_CPU_VARIANT_RUNTIME := kryo

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := kryo
TARGET_2ND_CPU_VARIANT_RUNTIME := kryo

TARGET_USES_64_BIT_BINDER := true
ENABLE_CPUSETS := true

# Bootloader
TARGET_NO_BOOTLOADER := true
TARGET_BOOTLOADER_BOARD_NAME := msm8996
# aboot 会用这个串做 OTA 包断言；ro.product.device 官方值是 msm8996
TARGET_OTA_ASSERT_DEVICE := PD1610,msm8996

# ---------------------------------------------------------------------------
# Kernel —— 完全走 prebuilt 路线
#
# vivo 未公开 PD1610 内核源码（opensource.vivo.com 只有 2022+ 新平台），
# 所以不编译内核，直接用官方 8.19.16 boot 里的 Image.gz-dtb：
#   prebuilt/kernel = boot.img 偏移 4096 起 56,551,493 字节，gzip 头 1f 8b，
#   内部偏移 0x8F50C1 处是 appended DTB（totalsize 372,497 B，board-id 0xa）。
# 自带 DTB ⇒ 不需要 BOARD_DTB_* / TARGET_KERNEL_SOURCE。
#
# cmdline 与官方逐字节一致（只追加 androidboot.selinux=permissive 便于首启调试），
# 其中 androidboot.securebootkey / securebootkeyhash / securebootkeyver 三个
# 私有参数必须原样保留：aboot 的 TZ 通道按它们选密钥槽，删掉会启动失败。
# ---------------------------------------------------------------------------
BOARD_KERNEL_CMDLINE := console=null androidboot.console=ttyHSL0 androidboot.hardware=qcom user_debug=31 msm_rtb.filter=0x237 ehci-hcd.park=3 lpm_levels.sleep_disabled=1 cma=32M@0-0xffffffff product.version=PD1610_D_8.19.16 fingerprint.abbr=8.1.0/OPM1.171019.026 buildvariant=user androidboot.securebootkey=beta androidboot.securebootkeyhash=da758fd52632ba6649d61830a88bbe76a616e4b083b9358b3e98e13772dc139d androidboot.securebootkeyver=2 androidboot.selinux=permissive

BOARD_KERNEL_BASE := 0x80000000
# 官方 boot header 实测 page_size=4096（PD1619 的 2048 不能照抄）
BOARD_KERNEL_PAGESIZE := 4096
BOARD_MKBOOTIMG_ARGS := --kernel_offset 0x00008000 --ramdisk_offset 0x01000000 --second_offset 0x00f00000 --tags_offset 0x00000100
BOARD_KERNEL_IMAGE_NAME := Image.gz-dtb

TARGET_KERNEL_ARCH := arm64
TARGET_KERNEL_HEADER_ARCH := arm64
TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel

# ---------------------------------------------------------------------------
# 文件系统 / 分区（字节数取自 blockdev --getsize64，不是 MiB 近似值）
#
# 非 Treble：没有 vendor 分区，blobs 全部落进 /system/vendor。
# 这是本设备与绝大多数 LOS16 设备树最大的结构性差异。
# ---------------------------------------------------------------------------
TARGET_COPY_OUT_VENDOR := system/vendor
# Android 9 仍支持该变量：在 system 镜像根建 /vendor -> /system/vendor 软链，
# 让 init 能按 /vendor/etc/init/*.rc 找到厂商 rc。LOS16 之后被移除。
BOARD_ROOT_EXTRA_SYMLINKS := /vendor:/system/vendor

BOARD_FLASH_BLOCK_SIZE := 131072

BOARD_BOOTIMAGE_PARTITION_SIZE := 100663296
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 100663296
BOARD_SYSTEMIMAGE_PARTITION_SIZE := 3221225472
BOARD_USERDATAIMAGE_PARTITION_SIZE := 120980189184
BOARD_CACHEIMAGE_PARTITION_SIZE := 268435456
BOARD_CACHEIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_PERSISTIMAGE_PARTITION_SIZE := 33554432

TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USES_MKE2FS := true
BOARD_SUPPRESS_SECURE_ERASE := true

# ---------------------------------------------------------------------------
# 加密 —— 首启关闭
#
# 原厂是 FDE（vendor/etc/fstab.qcom 里 /data 带 forceencrypt=footer,quota），
# 但 TARGET_HW_DISK_ENCRYPTION 需要 libcryptfs_hw + keymaster 头文件，
# prebuilt 内核不生成这些头，首启一律先关。等系统能起来再打开。
# ---------------------------------------------------------------------------
TARGET_HW_DISK_ENCRYPTION := false

# Recovery
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/rootdir/etc/fstab.qcom
TARGET_RECOVERY_PIXEL_FORMAT := "RGBX_8888"
TARGET_RECOVERY_DEVICE_MODULES :=
BOARD_USES_FULL_RECOVERY_IMAGE := false

# Audio（msm8996 + TASHA codec，实机声卡名 msm8996-tasha-cdp-snd-card）
AUDIO_FEATURE_ENABLED_ACDB_LICENSE := true
AUDIO_FEATURE_ENABLED_ANC_HEADSET := true
AUDIO_FEATURE_ENABLED_COMPRESS_CAPTURE := true
AUDIO_FEATURE_ENABLED_COMPRESS_VOIP := true
AUDIO_FEATURE_ENABLED_CUSTOMSTEREO := true
AUDIO_FEATURE_ENABLED_DEV_ARBI := true
AUDIO_FEATURE_ENABLED_EXTENDED_COMPRESS_FORMAT := true
AUDIO_FEATURE_ENABLED_FLAC_OFFLOAD := true
AUDIO_FEATURE_ENABLED_FLUENCE := true
AUDIO_FEATURE_ENABLED_HFP := true
AUDIO_FEATURE_ENABLED_KPI_OPTIMIZE := true
AUDIO_FEATURE_ENABLED_MULTI_VOICE_SESSIONS := true
AUDIO_FEATURE_ENABLED_PCM_OFFLOAD := true
AUDIO_FEATURE_ENABLED_PCM_OFFLOAD_24 := true
AUDIO_FEATURE_ENABLED_PROXY_DEVICE := true
AUDIO_FEATURE_ENABLED_SOURCE_TRACKING := true
AUDIO_FEATURE_ENABLED_VBAT_MONITOR := true
AUDIO_USE_LL_AS_PRIMARY_OUTPUT := true
BOARD_USES_ALSA_AUDIO := true
TARGET_USES_QCOM_MM_AUDIO := true
USE_CUSTOM_AUDIO_POLICY := 1
USE_XML_AUDIO_POLICY_CONF := 1

# Bluetooth
BOARD_BLUETOOTH_BDROID_BUILDCFG_INCLUDE_DIR := $(DEVICE_PATH)/bluetooth
BOARD_HAVE_BLUETOOTH := true
# 用原厂 android.hardware.bluetooth@1.0-service-qti + 原厂 libbt-vendor 闭包。
# bt-caf 源码版 libbt-vendor 会编进同路径把原厂 blob 覆盖掉，而且它需要内核
# uapi 里的 TIOCPMGET/TIOCPMPUT/TIOCPMACT（bionic 没有、也拿不到 msm-3.18
# 头文件）→ 编译必挂。这里必须为 false，blobs 里 libbt-vendor.so 已收录。
BOARD_HAVE_BLUETOOTH_QCOM := false
BLUETOOTH_HCI_USE_MCT := true
# ANT+：Xplay6 无 ANT 硬件，且 "qualcomm-hidl" 变体要求 QCPATH 非空（qcomm-hidl/Android.mk
# 第 17 行 ifneq ($(QCPATH),)），本构建 QCPATH 为空 → libantradio 无人定义，
# antradio_app 报 missing libantradio 直接中断解析。留空则 ant 三个 mk 全部跳过。
# BOARD_ANT_WIRELESS_DEVICE := "qualcomm-hidl"

# Camera（原厂 cameraprovider 2.4 + vivo 私有 vif/vivodevice，全是 32 位 blob）
USE_DEVICE_SPECIFIC_CAMERA := true
USE_PROPRIETARY_CAMERA := true
BOARD_QTI_CAMERA_32BIT_ONLY := true
TARGET_USES_QTI_CAMERA_DEVICE := true
TARGET_PROCESS_SDK_VERSION_OVERRIDE := \
    /system/vendor/bin/mm-qcamera-daemon=23

# Display
MAX_VIRTUAL_DISPLAY_DIMENSION := 2048
NUM_FRAMEBUFFER_SURFACE_BUFFERS := 3
TARGET_CONTINUOUS_SPLASH_ENABLED := true
TARGET_FORCE_HWC_FOR_VIRTUAL_DISPLAYS := true
TARGET_USES_C2D_COMPOSITION := true
TARGET_USES_GRALLOC1 := true
TARGET_USES_ION := true
TARGET_USES_NEW_ION_API := true
TARGET_USES_OVERLAY := true
TARGET_USES_HWC2 := true
MAX_EGL_CACHE_KEY_SIZE := 12*1024
MAX_EGL_CACHE_SIZE := 2048*1024
OVERRIDE_RS_DRIVER := libRSDriver_adreno.so
USE_OPENGL_RENDERER := true

# GPS
USE_DEVICE_SPECIFIC_GPS := true
USE_DEVICE_SPECIFIC_LOC_API := true
TARGET_NO_RPC := true
BOARD_VENDOR_QCOM_GPS_LOC_API_HARDWARE := $(TARGET_BOARD_PLATFORM)

# HIDL —— 直接沿用原厂 8.1 的 /vendor/manifest.xml（非 Treble 布局：
# 原厂就是 /vendor/manifest.xml 而不是 /vendor/etc/vintf/manifest.xml）。
DEVICE_MANIFEST_FILE := $(DEVICE_PATH)/manifest.xml

# Init
# msm8996 的设备节点挂在 /devices/soc/ 下；原厂 cmdline 的 hardware=qcom
# 决定了 ramdisk 侧读的是 fstab.qcom / init.qcom.rc。
TARGET_PLATFORM_DEVICE_BASE := /devices/soc/
# 首版不写 libinit_pd1610（还没有源码模块）。等需要改 ro.product.model、
# 按 SKU 切属性时再加回来，并同步在 device.mk 里加 libinit 模块。
# TARGET_INIT_VENDOR_LIB := libinit_pd1610

# Lights
TARGET_PROVIDES_LIBLIGHT := true

# Media
TARGET_USES_MEDIA_EXTENSIONS := true
TARGET_ENABLE_MEDIADRM_64 := true

# Power
TARGET_HAS_NO_WLAN_STATS := true
TARGET_RPM_SYSTEM_STAT := /d/rpm_stats
TARGET_USES_INTERACTION_BOOST := true

# Properties
TARGET_SYSTEM_PROP += $(DEVICE_PATH)/system.prop

# Qualcomm support
BOARD_USES_QCOM_HARDWARE := true
TARGET_USE_SDCLANG := true

# RIL
TARGET_RIL_VARIANT := caf
TARGET_PROVIDES_QTI_TELEPHONY_JAR := true
TARGET_USES_OLD_MNC_FORMAT := true

# Sepolicy
# LOS16 的 msm8996 树（xiaomi/msm8996-common）用的是 device/qcom/sepolicy。
# 本设备非 Treble，首启已加 androidboot.selinux=permissive，denial 不会拦启动。
# 若分支里没有该目录，依次替换为 sepolicy-legacy-um / sepolicy-legacy。
include device/qcom/sepolicy/sepolicy.mk
BOARD_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/vendor

# Shims
# 首版不启用：libshims_camera / libshims_rild_socket 需要自写源码，
# 没有它们只会让相机/rild 在 Pie 上缺符号，不会阻止开机。
# 等 `/system/vendor/lib64/libril-qc-qmi-1.so` 报 undefined symbol 再补。
# TARGET_LD_SHIM_LIBS := \
#     /system/vendor/bin/mm-qcamera-daemon|libshims_camera.so \
#     /system/vendor/lib64/libril-qc-qmi-1.so|libshims_rild_socket.so

# Vibrator（原厂的 android.hardware.vibrator@1.0-service + vivo 私有 light HAL 都在 blobs 里）
TARGET_USES_QCOM_VIBRATOR := true

# WiFi（wlan.ko 在 /system/vendor/lib/modules/wlan.ko，非 Treble 路径）
BOARD_HAS_QCOM_WLAN := true
BOARD_HAS_QCOM_WLAN_SDK := true
BOARD_WLAN_DEVICE := qcwcn
BOARD_HOSTAPD_DRIVER := NL80211
BOARD_HOSTAPD_PRIVATE_LIB := lib_driver_cmd_$(BOARD_WLAN_DEVICE)
BOARD_WPA_SUPPLICANT_DRIVER := NL80211
BOARD_WPA_SUPPLICANT_PRIVATE_LIB := lib_driver_cmd_$(BOARD_WLAN_DEVICE)
# 不要定义 WIFI_DRIVER_FW_PATH_STA/AP/P2P：
# AOSP9 的 DriverTool 只要 wifi_get_fw_path() 非空，就会在 createStaIface 时
# 调 wifi_change_fw_path() 写 /sys/module/wlan/parameters/fwpath。
# 该节点属 root:root，而 wifi HAL 以 user wifi 运行 → "Failed to open wlan fw
# path param: Permission denied" → "Failed to change firmware mode" →
# WifiVendorHal: Failed to create STA iface。vivo 8.1 原厂 HAL 从不做固件模式切换，
# 去掉这两个宏后 libwifi-hal 里的兜底是 NULL，HAL 直接跳过该步骤。
# WIFI_DRIVER_FW_PATH_AP := "ap"
# WIFI_DRIVER_FW_PATH_STA := "sta"
WIFI_DRIVER_MODULE_ARG := ""
WIFI_DRIVER_MODULE_NAME := "wlan"
WIFI_DRIVER_MODULE_PATH := "/system/vendor/lib/modules/wlan.ko"
WPA_SUPPLICANT_VERSION := VER_0_8_X
TARGET_USES_WCNSS_MAC_ADDR_REV := true

# 关闭 adbd 授权校验的开关放在 device.mk 的 WITH_ADB_INSECURE，
# 不能放这里：product_config.mk 在 envsetup.mk:252 就被 include，
# 早于 BoardConfig，common.mk 的 ifdef 看不到本文件里的变量（实测无效）。

# 继承 blobs 侧生成的 BoardConfigVendor.mk（由 extract-files.sh 产出）
-include vendor/vivo/pd1610/BoardConfigVendor.mk
