#!/bin/bash
# PD1610：从 LineageOS msm8996 内核源码生成 KERNEL_OBJ 里的内核头
# 目的：audio-caf / media-caf 源码 HAL 依赖 linux/msm_audio*.h、sound/voice_params.h、
#       media/msm_media_info.h 等 uapi 头，这些只在真实内核树里存在。
# 用法：bash install_kernel_headers.sh
set -e

KS="$HOME/ksrc"
TAR="$KS/msm8996-lineage-16.0.tar.gz"
SRC="$KS/msm8996-lineage-16.0"
KOUT="$KS/kout"
OBJ="$HOME/los16/out/target/product/pd1610/obj/KERNEL_OBJ"

echo "=== 1. 解压 ==="
cd "$KS"
if [ ! -d "$SRC" ]; then
    tar xzf "$TAR"
    if [ -d android_kernel_xiaomi_msm8996-lineage-16.0 ]; then
        mv android_kernel_xiaomi_msm8996-lineage-16.0 "$SRC"
    fi
fi
echo "源码树: $(du -sh "$SRC" | cut -f1)"

echo "=== 2. 关键头文件是否存在 ==="
for h in include/uapi/sound/voice_params.h \
         include/uapi/linux/msm_audio.h \
         include/uapi/linux/msm_audio_calibration.h \
         include/uapi/media/msm_media_info.h \
         include/uapi/linux/msm_ipa.h \
         include/uapi/linux/rmnet_data.h; do
    if [ -f "$SRC/$h" ]; then echo "  OK   $h"; else echo "  MISS $h"; fi
done
echo "--- techpack/audio/include ---"
ls "$SRC/techpack/audio/include" 2>/dev/null | head -5 || echo "  无 techpack/audio"

echo "=== 3. headers_install ==="
mkdir -p "$KOUT" "$OBJ/usr/include"
cd "$SRC"
# 3.18 的 headers_install 只依赖 host 侧脚本，不需要交叉编译器；
# 但需要先 prepare 出 include/generated。失败不致命，后面有手工兜底。
make ARCH=arm O="$KOUT" prepare >/tmp/kprep.log 2>&1 || echo "  prepare 有告警（继续）"
if make ARCH=arm O="$KOUT" INSTALL_HDR_PATH="$OBJ/usr" headers_install >/tmp/khdr.log 2>&1; then
    echo "  headers_install 成功"
else
    echo "  headers_install 失败，见 /tmp/khdr.log 尾部："
    tail -15 /tmp/khdr.log
fi
echo "已安装头数量: $(find "$OBJ/usr/include" -name '*.h' 2>/dev/null | wc -l)"

echo "=== 4. 手工兜底：直接铺 uapi ==="
if [ ! -f "$OBJ/usr/include/sound/voice_params.h" ]; then
    echo "  按目录直拷 include/uapi + arch/arm/include/uapi"
    cp -a "$SRC/include/uapi/." "$OBJ/usr/include/"
    cp -a "$SRC/arch/arm/include/uapi/." "$OBJ/usr/include/" 2>/dev/null || true
fi

echo "=== 5. techpack/audio 头（msm8996 的音频 uapi 实际在这里）==="
if [ -d "$SRC/techpack/audio/include" ]; then
    mkdir -p "$OBJ/usr/techpack/audio"
    cp -a "$SRC/techpack/audio/include" "$OBJ/usr/techpack/audio/include"
    echo "  已复制到 $OBJ/usr/techpack/audio/include"
    # 同时把 techpack 里的 sound/ 头并进主 include，简化 -I
    if [ -d "$SRC/techpack/audio/include/sound" ]; then
        mkdir -p "$OBJ/usr/include/sound"
        cp -an "$SRC/techpack/audio/include/sound/." "$OBJ/usr/include/sound/" 2>/dev/null || true
    fi
fi

echo "=== 6. 校验关键头 ==="
for h in sound/voice_params.h sound/msm_audio.h linux/msm_audio.h \
         linux/msm_audio_calibration.h linux/msm_ipa.h linux/rmnet_data.h \
         media/msm_media_info.h; do
    if [ -f "$OBJ/usr/include/$h" ]; then echo "  OK   $h"; else echo "  MISS $h"; fi
done
echo "=== 完成：$OBJ/usr/include 共 $(find "$OBJ/usr/include" -type f | wc -l) 个文件 ==="
