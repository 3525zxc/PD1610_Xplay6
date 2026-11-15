# LineageOS 14.1 product for vivo Xplay6 (PD1610)
# Branch must match the device: cm-14.1 / lineage-14.1 (Android 7.1, SDK 25).
# Newer branches (15.1+, Android 9/10) are NOT viable with the stock 3.18
# kernel and the pre-Treble partition layout of this device.

$(call inherit-product, device/vivo/pd1610/device.mk)
$(call inherit-product, vendor/lineage/config/common_full_phone.mk)

PRODUCT_NAME := lineage_pd1610
PRODUCT_DEVICE := pd1610
PRODUCT_BRAND := vivo
PRODUCT_MODEL := vivo Xplay6
PRODUCT_MANUFACTURER := vivo

PRODUCT_GMS_CLIENTID_BASE := android-vivo
PRODUCT_DEFAULT_PROPERTY_OVERRIDES += ro.build.description=PD1610-user 7.1.1 NMF26F release-keys
