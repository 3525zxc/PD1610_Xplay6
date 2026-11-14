#!/bin/bash
# ============================================================================
# PD1610 —— LineageOS 16.0 编译脚本（不依赖 lunch）
#
# 为什么不用 lunch：
#   本机实测 `lunch lineage_pd1610-userdebug` 会卡死在纯 shell 状态（无子进程），
#   但用环境变量直接喂 soong_ui 就能正常解析：
#     TARGET_PRODUCT=lineage_pd1610 TARGET_BUILD_VARIANT=userdebug \
#       build/soong/soong_ui.bash --dumpvar-mode TARGET_DEVICE   → pd1610
#   所以这里直接设环境变量 + soong_ui --make-mode，绕开 lunch。
#
# 用法：
#   bash build_pd1610.sh                   # 默认 bootimage
#   bash build_pd1610.sh systemimage       # 只编 system
#   bash build_pd1610.sh bacon             # 全量（boot+system+ota）
#   JOBS=6 bash build_pd1610.sh            # 限并发（内存小时用）
# ============================================================================
set -o pipefail

SRC="${SRC:-$HOME/los16}"
TARGETS="${*:-bootimage}"
JOBS="${JOBS:-8}"

cd "$SRC" || exit 1

export TARGET_PRODUCT=lineage_pd1610
export TARGET_BUILD_VARIANT=userdebug
# LINEAGE_BUILD 必须非空：build/make/core/config.mk:1148 用 ifneq($(LINEAGE_BUILD),)
# 决定是否 include device/lineage/sepolicy/common/sepolicy.mk。
# 为空时 lineage common sepolicy（含 hal_lineage_livedisplay_* 属性/域）不参与，
# 而 device/lineage/sepolicy/qcom/vendor/hal_lineage_livedisplay_qti.te 又会被解析，
# 于是 sepolicy_neverallows 报 'attribute hal_lineage_livedisplay_server is not declared'。
export LINEAGE_BUILD=pd1610
export TARGET_BUILD_TYPE=release
export LC_ALL=C
export USE_CCACHE=1
export CCACHE_EXEC="$(command -v ccache)"
export CCACHE_DIR="${CCACHE_DIR:-$HOME/.ccache}"

command -v ccache >/dev/null && ccache -M 50G >/dev/null 2>&1

STAMP=$(date +%m%d_%H%M)
LOG="$SRC/out/build_${STAMP}.log"
mkdir -p "$SRC/out"

echo "=== 编译开始 $(date '+%F %T') ==="
echo "  产品    : $TARGET_PRODUCT-$TARGET_BUILD_VARIANT"
echo "  目标    : $TARGETS"
echo "  并发    : -j$JOBS"
echo "  日志    : $LOG"
echo "  内存    : $(free -g | awk '/Mem:/{print $2\"GB 总 / \"$7\"GB 可用\"}')"

bash build/soong/soong_ui.bash --make-mode -j"$JOBS" $TARGETS 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}

echo
echo "=== 编译结束 $(date '+%F %T') rc=$RC ==="
if [ "$RC" -ne 0 ]; then
    echo "--- 错误摘要 ---"
    grep -iE "^.*error:|FAILED:|ninja: build stopped|No rule to make target|missing file" "$LOG" | tail -30
else
    OUT="$SRC/out/target/product/pd1610"
    echo "--- 产物 ---"
    ls -lh "$OUT"/*.img 2>/dev/null | awk '{printf "  %-46s %s\n", $9, $5}'
fi
exit "$RC"
