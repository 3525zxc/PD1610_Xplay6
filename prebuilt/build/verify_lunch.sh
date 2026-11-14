#!/bin/bash
# ============================================================================
# PD1610 —— lunch 冒烟测试
#
# 目的：在真正开编之前，把 product 配置（device.mk / BoardConfig.mk /
# vendor/*.mk / 继承链）先解析一遍。lunch 阶段能暴露 90% 的设备树错误：
#   * 找不到 inherit-product 的文件
#   * PRODUCT_COPY_FILES 源文件缺失（missing file）
#   * BoardConfig 变量拼错导致空值
#   * AndroidProducts.mk / PRODUCT_MAKEFILES 不匹配
#
# 用法：bash verify_lunch.sh [源码目录]
# ============================================================================
set -o pipefail

SRC="${1:-$HOME/los16}"
cd "$SRC" || exit 1

LOG="$HOME/lunch_test.log"
: > "$LOG"

echo "=== lunch 冒烟测试 $(date '+%F %T') ===" | tee -a "$LOG"

# envsetup.sh 里有一堆 `return` 保护的代码，必须用 source
source build/envsetup.sh >> "$LOG" 2>&1
echo "envsetup RC=$?" | tee -a "$LOG"

lunch lineage_pd1610-userdebug >> "$LOG" 2>&1
RC=$?

echo "--- lunch 输出尾部 ---"
tail -n 30 "$LOG"

echo
echo "--- 关键变量 ---"
echo "TARGET_PRODUCT   = ${TARGET_PRODUCT:-<空>}"
echo "TARGET_DEVICE    = ${TARGET_DEVICE:-<空>}"
echo "TARGET_BUILD_VARIANT = ${TARGET_BUILD_VARIANT:-<空>}"
echo "OUT_DIR          = ${OUT_DIR:-<空>}"

echo
echo "--- 常见错误扫描 ---"
grep -inE "error|no such file|not found|undefined|missing" "$LOG" | grep -viE "^\s*$" | head -20

echo
if [ "$RC" -eq 0 ]; then
    echo "RESULT: PASS (lunch 成功，可以进入编译)"
else
    echo "RESULT: FAIL (exit $RC)，完整日志：$LOG"
fi
exit "$RC"
