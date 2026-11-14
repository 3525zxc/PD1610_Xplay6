#!/bin/bash
# ============================================================================
# PD1610 —— 绕开 repo，直接用 shallow clone 补齐编译必需的 prebuilts
#
# 为什么不用 repo sync：
#   repo 2.73 的 sync **没有 --depth 选项**（实测报 no such option），
#   manifest 里的 project 也没写 clone-depth，于是它给每个项目做全量 fetch。
#   prebuilts/gcc 全量历史 >5 GB，prebuilts/clang >3 GB，几个仓库并发就把
#   带宽和镜像连接全占死，实测 10 分钟 0 字节。
#
#   实测对照：中科大镜像上
#     repo sync 全量          → 10 分钟无进展
#     git clone --depth=1 tag → 207 MB / 9 秒（23 MB/s）
#   所以这里直接 shallow clone 到 work tree 位置。make 只按路径取文件，
#   是不是 repo 管的仓库无关紧要。
# ============================================================================
set -uo pipefail

SRC="$HOME/los16"
MIRROR="https://mirrors.ustc.edu.cn/aosp/platform"
TAG="android-9.0.0_r46"
PAR="${PAR:-3}"

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

clone_one() {
    local p="$1"
    local dst="$SRC/$p"
    if [ -d "$dst/.git" ] || [ -d "$dst/bin" ]; then
        echo "SKIP  $p（已存在）"
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    local ref
    for ref in "$TAG" master; do
        if git clone --depth=1 --branch "$ref" "$MIRROR/$p" "$dst" >/dev/null 2>&1; then
            printf 'OK    %-58s %-20s %s\n' "$p" "$ref" "$(du -sh "$dst" 2>/dev/null | cut -f1)"
            return 0
        fi
        rm -rf "$dst"
    done
    echo "FAIL  $p"
    return 1
}
export -f clone_one
export SRC MIRROR TAG

echo "=== 开始 $(date '+%F %T')｜${#PROJECTS[@]} 个项目｜并发 $PAR ==="
printf '%s\n' "${PROJECTS[@]}" | xargs -P"$PAR" -I{} bash -c 'clone_one "$@"' _ {}

echo
echo "=== 校验 $(date '+%F %T') ==="
for d in prebuilts/clang/host/linux-x86 prebuilts/gcc prebuilts/go prebuilts/jdk \
         prebuilts/misc prebuilts/r8 prebuilts/python prebuilts/tools; do
    printf '  %-44s ' "$d"
    if [ -d "$SRC/$d" ]; then du -sh "$SRC/$d" 2>/dev/null | cut -f1; else echo MISSING; fi
done
echo "  go:    $([ -x "$SRC/prebuilts/go/linux-x86/bin/go" ] && echo OK || echo MISSING)"
echo "  clang: $(ls "$SRC"/prebuilts/clang/host/linux-x86/*/bin/clang 2>/dev/null | head -1 || echo MISSING)"
echo "  javac: $(ls "$SRC"/prebuilts/jdk/jdk8/*/bin/javac 2>/dev/null | head -1 || echo MISSING)"
echo "=== done $(date '+%F %T') ==="
