#!/bin/bash
# ============================================================================
# PD1610 —— 只同步「编译必需」的 prebuilts
#
# 背景：第一轮 -j14 触发中科大 429，626/707 项目失败；缺失的恰是编译核心
# 依赖（clang/gcc/go/jdk/misc/r8）。而 repo sync 全量又会先拉 cts(3GB+)、
# goldfish、emulator 这些和 arm64 手机编译无关的大项目，把时间全吃掉。
#
# 这里用 repo sync 的项目过滤参数，只拉编译链路必需的 prebuilts。
# cts / goldfish / emulator 不拉：本设备编译完全不需要。
# ============================================================================
set -uo pipefail

SRC="$HOME/los16"
JOBS="${JOBS:-6}"
REPO_BIN="$HOME/bin/repo"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

cd "$SRC" || exit 1

PROJECTS=(
    prebuilts/clang/host/linux-x86
    prebuilts/clang-tools
    prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9
    prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9
    prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.15-4.8
    prebuilts/gcc/linux-x86/x86/x86_64-linux-android-4.9
    prebuilts/go/linux-x86
    prebuilts/jdk/jdk8
    prebuilts/jdk/jdk9
    prebuilts/misc
    prebuilts/python/linux-x86/2.7.5
    prebuilts/r8
    prebuilts/tools
    prebuilts/vndk/v27
)

say "定向同步 ${#PROJECTS[@]} 个 prebuilts（-j$JOBS，清华源）"
RC=1
for i in 1 2 3; do
    echo "--- round $i $(date '+%T') ---"
    "$REPO_BIN" sync -j"$JOBS" --no-clone-bundle --no-tags \
        --optimized-fetch --retry-fetches=5 "${PROJECTS[@]}"
    RC=$?
    echo "--- round $i rc=$RC ---"
    [ "$RC" -eq 0 ] && break
    sleep 20
done

say "校验"
for d in prebuilts/clang/host/linux-x86 prebuilts/gcc prebuilts/go prebuilts/jdk \
         prebuilts/misc prebuilts/r8 prebuilts/python prebuilts/tools; do
    printf '  %-42s ' "$d"
    if [ -d "$SRC/$d" ]; then du -sh "$SRC/$d" 2>/dev/null | cut -f1; else echo MISSING; fi
done
echo "  go 可执行: $([ -x "$SRC/prebuilts/go/linux-x86/bin/go" ] && echo OK || echo MISSING)"
echo "  clang 可执行: $(ls "$SRC"/prebuilts/clang/host/linux-x86/*/bin/clang 2>/dev/null | head -1 || echo MISSING)"
echo "=== done $(date '+%F %T') rc=$RC ==="
exit "$RC"
