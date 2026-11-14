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

$(call inherit-product, $(SRC_TARGET_DIR)/product/product_launched_with_m.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/languages_full.mk)

# 全部厂商 blobs（由 extract-files.sh 生成到 vendor/vivo/pd1610）
$(call inherit-product, vendor/vivo/pd1610/pd1610-vendor.mk)

# ---------------------------------------------------------------------------
# 屏幕：实测 ro.sf.lcd_density=640，1440x2560（5.46 英寸）
# ---------------------------------------------------------------------------
PRODUCT_AAPT_CONFIG := normal
PRODUCT_AAPT_PREF_CONFIG := xxxhdpi
TARGET_SCREEN_HEIGHT := 2560
TARGET_SCREEN_WIDTH := 1440

# ---------------------------------------------------------------------------
# Dalvik 堆：取自原厂 system/build.prop 的实测值，不是套模板
#   dalvik.vm.heapstartsize=16m / heapgrowthlimit=384m / heapsize=512m
# ---------------------------------------------------------------------------
PRODUCT_PROPERTY_OVERRIDES += \
    dalvik.vm.heapstartsize=16m \
    dalvik.vm.heapgrowthlimit=384m \
    dalvik.vm.heapsize=512m \
    dalvik.vm.heaptargetutilization=0.75 \
    dalvik.vm.heapminfree=4m \
    dalvik.vm.heapmaxfree=8m

# Bring-up：允许未授权主机连 adbd，免去每次恢复出厂都要重新点授权。
#
# 两个坑（都实测过）：
#  1. 不能用 PRODUCT_DEFAULT_PROPERTY_OVERRIDES —— Android 9 的
#     build/make/core/Makefile:152 组装 FINAL_DEFAULT_PROPERTIES 时
#     只合并 ADDITIONAL_DEFAULT_PROPERTIES 与
#     PRODUCT_SYSTEM_DEFAULT_PROPERTIES，写了不生效。
#  2. 也不能放在 BoardConfig.mk —— product_config.mk 在
#     envsetup.mk:252 就被 include，早于 BoardConfig，所以
#     common.mk 里的 ifdef 看不到它。
# 正确位置就是这里：device.mk 由 full_pd1610.mk 继承，而
# common_full_phone.mk 是在 lineage_pd1610.mk 里后继承的。
#
# 连带效果：post_process_props.py 在 ro.adb.secure != 1 时会把
# persist.sys.usb.config 自动补成 adb，USB 插上即可见 adbd。
# 本机电源键与音量上键都坏了，这是唯一可靠的调试/回刷通道。
WITH_ADB_INSECURE := true

# ---------------------------------------------------------------------------
# 分区 / 挂载
# fstab 两份内容必须一致，原因见 rootdir/etc/fstab.qcom 顶部注释
# ---------------------------------------------------------------------------
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/etc/fstab.qcom:root/fstab.qcom \
    $(LOCAL_PATH)/rootdir/etc/fstab.qcom:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qcom

# 设备侧 init 补充（不改 AOSP init.rc，只做增量）
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/init.pd1610.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/init.pd1610.rc

# ---------------------------------------------------------------------------
# 首启诊断（临时，定位卡 logo；验证完成后连同 rootdir/etc/init.qcom.rc 与
# rootdir/etc/pd1610_dumplog.sh 一起删除）
# init.qcom.rc 会被 ramdisk 根的 init.rc 用 `import /init.${ro.hardware}.rc`
# 自动导入，因此能覆盖 first stage 之后的全部 init 流程。
# ---------------------------------------------------------------------------
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/etc/init.qcom.rc:root/init.qcom.rc \
    $(LOCAL_PATH)/rootdir/etc/pd1610_dumplog.sh:root/pd1610_dumplog.sh

# 键位映射：从实机 /system/usr/keylayout 原样取出
#   gpio-keys      : 音量键/其他 GPIO 键
#   qpnp_pon       : 电源键（PM8994 PON）
#   synaptics_dsx  : 触摸控制器按键（本机触摸主控是 fts，此文件为兼容保留）
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/keylayout/gpio-keys.kl:system/usr/keylayout/gpio-keys.kl \
    $(LOCAL_PATH)/keylayout/qpnp_pon.kl:system/usr/keylayout/qpnp_pon.kl \
    $(LOCAL_PATH)/keylayout/synaptics_dsx.kl:system/usr/keylayout/synaptics_dsx.kl

# ---------------------------------------------------------------------------
# 硬件特性声明
# 依据：原厂 /vendor/manifest.xml 的 73 个 HAL 条目 + /proc/bus/input/devices
# 实测输入设备（qpnp_pon / gpio-keys / goodixfp / fts / vivo_virtual_key）
# ---------------------------------------------------------------------------
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.audio.low_latency.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.audio.low_latency.xml \
    frameworks/native/data/etc/android.hardware.audio.pro.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.audio.pro.xml \
    frameworks/native/data/etc/android.hardware.bluetooth.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.bluetooth.xml \
    frameworks/native/data/etc/android.hardware.bluetooth_le.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.bluetooth_le.xml \
    frameworks/native/data/etc/android.hardware.camera.flash-autofocus.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.camera.flash-autofocus.xml \
    frameworks/native/data/etc/android.hardware.camera.front.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.camera.front.xml \
    frameworks/native/data/etc/android.hardware.camera.full.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.camera.full.xml \
    frameworks/native/data/etc/android.hardware.camera.raw.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.camera.raw.xml \
    frameworks/native/data/etc/android.hardware.fingerprint.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.fingerprint.xml \
    frameworks/native/data/etc/android.hardware.location.gps.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.location.gps.xml \
    frameworks/native/data/etc/android.hardware.opengles.aep.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.opengles.aep.xml \
    frameworks/native/data/etc/android.hardware.sensor.accelerometer.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.accelerometer.xml \
    frameworks/native/data/etc/android.hardware.sensor.compass.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.compass.xml \
    frameworks/native/data/etc/android.hardware.sensor.gyroscope.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.gyroscope.xml \
    frameworks/native/data/etc/android.hardware.sensor.light.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.light.xml \
    frameworks/native/data/etc/android.hardware.sensor.proximity.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.proximity.xml \
    frameworks/native/data/etc/android.hardware.sensor.stepcounter.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.stepcounter.xml \
    frameworks/native/data/etc/android.hardware.sensor.stepdetector.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.stepdetector.xml \
    frameworks/native/data/etc/android.hardware.telephony.cdma.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.cdma.xml \
    frameworks/native/data/etc/android.hardware.telephony.gsm.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.gsm.xml \
    frameworks/native/data/etc/android.hardware.touchscreen.multitouch.jazzhand.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.touchscreen.multitouch.jazzhand.xml \
    frameworks/native/data/etc/android.hardware.usb.accessory.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.usb.accessory.xml \
    frameworks/native/data/etc/android.hardware.usb.host.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.usb.host.xml \
    frameworks/native/data/etc/android.hardware.vulkan.compute-0.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.vulkan.compute.xml \
    frameworks/native/data/etc/android.hardware.vulkan.level-0.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.vulkan.level.xml \
    frameworks/native/data/etc/android.hardware.vulkan.version-1_0_3.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.vulkan.version.xml \
    frameworks/native/data/etc/android.hardware.wifi.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.wifi.xml \
    frameworks/native/data/etc/android.hardware.wifi.direct.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.wifi.direct.xml \
    frameworks/native/data/etc/android.software.midi.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.midi.xml \
    frameworks/native/data/etc/android.software.sip.voip.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.sip.voip.xml

# ---------------------------------------------------------------------------
# PRODUCT_PACKAGES
#
# 首版刻意留空：所有 HAL 服务都用原厂 blob（/system/vendor/bin/hw 下 40 个 rc
# 已经随 blobs 一起装机），不从源码重编，避免版本/签名不匹配。
# 阶段 4 若某个服务在 lshal 里缺版本，再按需加：
#   android.hardware.gnss@1.0-service       —— 原厂 GNSS 依赖 passthrough impl
#   android.hardware.light@2.0-service      —— 原厂 light 由 vivo 私有 HAL 提供
#   android.hardware.vibrator@1.0-service
# 注意：加了源码 HAL 就会和原厂同路径 blob 打架，必须先把对应 blob 从
# proprietary-files.txt 里删掉。
# ---------------------------------------------------------------------------
PRODUCT_PACKAGES += \
    android.hardware.wifi@1.0-service \
    android.hardware.keymaster@3.0-impl \
    android.hardware.biometrics.fingerprint@2.1 \
    android.hardware.media.omx@1.0-service

# WiFi HAL 用 AOSP9 源码版（hardware/interfaces/wifi/1.2/default）：
#  1) 它的 rc 带 capabilities SYS_MODULE，WifiModeController 会调
#     DriverTool::LoadDriver() → wifi_load_driver() insmod
#     WIFI_DRIVER_MODULE_PATH=/system/vendor/lib/modules/wlan.ko（BoardConfig 已设）。
#     原厂 8.1 HAL 不含这套逻辑，也无权 insmod，所以 wlan0 永远不出现。
#  2) 关键：必须从 pd1610-vendor.mk 删掉 vivo 的 libwifi-hal.so 拷贝规则。
#     AOSP9 会编出自己的 libwifi-hal.so（1,385,824 B，内含 qcwcn 实现），
#     同名 blob（328,736 B, 8.1）会覆盖它，导致 P 的 WifiLegacyHal 用
#     8.1 的 wifi_hal_fn 布局 → wifi_cleanup+28 SIGSEGV。
# libwifi10_81.so / libwifi11_81.so 仍保留，供 vendor.qti.hardware.wifi@1.0_vendor.so 用。
