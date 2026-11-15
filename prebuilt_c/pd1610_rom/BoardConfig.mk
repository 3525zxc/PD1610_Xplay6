# vivo Xplay6 (PD1610 / MSM8996)
# All values below were measured on the actual device (9008 GPT, boot header,
# /system/build.prop, /proc/cmdline, fstab.qcom). Nothing here is guessed.
# Target tree: device/vivo/pd1610

DEVICE_PATH := device/vivo/pd1610

# ---- Architecture (MSM8996: Kryo 2+2, arm64 with 32-bit userspace) ----
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := kryo
TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv7-a-neon
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_VARIANT := cortex-a53

TARGET_BOARD_PLATFORM := msm8996
TARGET_BOARD_PLATFORM_GPU := qcom-adreno530
TARGET_BOOTLOADER_BOARD_NAME := QC_Reference_Phone   # ro.product.board
TARGET_NO_BOOTLOADER := true
TARGET_NO_RADIOIMAGE := true
TARGET_USES_QCOM_BSP := true
BOARD_USES_QCOM_HARDWARE := true

# ---- boot.img header (parsed from the device's own boot partition) ----
BOARD_BOOTIMG_HEADER_VERSION := 0
BOARD_KERNEL_PAGESIZE := 4096
BOARD_KERNEL_BASE := 0x80000000
BOARD_KERNEL_OFFSET := 0x00008000       # kernel_addr 0x80008000
BOARD_RAMDISK_OFFSET := 0x01000000      # ramdisk_addr 0x81000000
BOARD_TAGS_OFFSET := 0x00000100         # tags_addr 0x80000100
BOARD_MKBOOTIMG_ARGS := --kernel_offset 0x00008000 --ramdisk_offset 0x01000000 --tags_offset 0x00000100
BOARD_KERNEL_CMDLINE := console=ttyHSL0,115200,n8 androidboot.console=null androidboot.hardware=qcom user_debug=31 msm_rtb.filter=0x237 ehci-hcd.park=3 lpm_levels.sleep_disabled=1 cma=32M@0-0xffffffff
BOARD_KERNEL_BASE_ADDRESS := 0x80000000

# ---- Partition sizes (from the real LUN0/LUN4 GPT, 4096-byte sectors) ----
BOARD_BOOTIMAGE_PARTITION_SIZE := 100663296      # boot   LUN4 start 47370
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 100663296  # recovery LUN4 start 858378
BOARD_SYSTEMIMAGE_PARTITION_SIZE := 3221225472   # system  LUN4 start 71946
BOARD_USERDATAIMAGE_PARTITION_SIZE := 120980189184
BOARD_CACHEIMAGE_PARTITION_SIZE := 268435456
BOARD_PERSISTIMAGE_PARTITION_SIZE := 33554432
BOARD_FLASH_BLOCK_SIZE := 262144
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4       # NOTE: no vendor partition exists

# ---- Display / input ----
TARGET_SCREEN_DENSITY := 640
TARGET_RECOVERY_PIXEL_FORMAT := RGBA_8888
BOARD_HAS_NO_SELECT_BUTTON := false
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/rootdir/fstab.qcom

# ---- Verified boot / dm-verity: READ THIS ----
# This device has NO vbmeta partition and NO AVB footer on boot/recovery.
# Stock boot carries a vivo DER/X.509 signature chain at 0xE30000.
# Any byte change inside [0x00000000, 0x00E30000) of boot makes the device
# loop at the logo (verified experimentally on this exact unit).
BOARD_AVB_ENABLE := false
# The STOCK boot's fstab.qcom is:
#   /dev/block/bootdevice/by-name/system /system ext4 ro,barrier=1,discard wait,verify
#   /dev/block/bootdevice/by-name/oem    /oem    ext4 ro,barrier=1,discard wait,verify
# So even if we build a system without verity, the stock boot will refuse it.
# A matching (engineering / re-signed) boot is REQUIRED before flashing.
# We do NOT have vivo's verity private key: the key in the ramdisk
# (/verity_key, 524 B) does not match the AOSP testkey in vivo_tools.zip.

# ---- Kernel source: NOT AVAILABLE ----
# No public android_kernel_vivo_msm8996 was found. This line is a placeholder;
# you must supply vivo's GPL kernel release for LA.HB.1.3.2-09200-8x96.0
# and generate a defconfig (start from the device's /proc/config.gz).
# TARGET_KERNEL_SOURCE := kernel/vivo/msm8996
# TARGET_KERNEL_CONFIG := pd1610_defconfig
# TARGET_KERNEL_CROSS_COMPILE_PREFIX := aarch64-linux-android-

# ---- Recovery / selinux ----
BOARD_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_SPARSE_EXT_DISABLED := false
