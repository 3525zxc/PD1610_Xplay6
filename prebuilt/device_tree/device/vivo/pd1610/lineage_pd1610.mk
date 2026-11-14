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

# Inherit device configuration
$(call inherit-product, device/vivo/pd1610/full_pd1610.mk)

# Inherit some common LineageOS stuff.
$(call inherit-product, vendor/lineage/config/common_full_phone.mk)

## Device identifier. This must come after all inclusions
PRODUCT_DEVICE := pd1610
PRODUCT_NAME := lineage_pd1610
PRODUCT_BRAND := vivo
PRODUCT_MANUFACTURER := vivo
PRODUCT_MODEL := vivo Xplay6

PRODUCT_GMS_CLIENTID_BASE := android-vivo

# 原厂 ro.product.device 是 msm8996、ro.product.model 是 vivo，
# 这里统一成 pd1610 / vivo Xplay6；TARGET_OTA_ASSERT_DEVICE 仍保留
# PD1610,msm8996 两个别名，避免旧包/旧 recovery 断言失败。
PRODUCT_BUILD_PROP_OVERRIDES += \
    TARGET_DEVICE=pd1610 \
    PRODUCT_NAME=pd1610

PRODUCT_RELEASE_NAME := PD1610
