#!/bin/bash
# ============================================================================
# PD1610 (vivo Xplay6) —— LineageOS 16.0 构建脚本
#
# 用法：
#   ./build_los16.sh                    # 默认 ~/los16，编译 bacon
#   ./build_los16.sh /srv/los16 boot    # 只编译 bootimage（快，用于验证内核/ramdisk）
#   ./build_los16.sh /srv/los16 systemimage
#
# 前置：sync_los16.sh 已完成；设备树已放入 device/vivo/pd1610
# ============================================================================
set -euo pipefail

SRC="${1:-$HOME/los16}"
TARGET="${2:-bacon}"
DEVICE_TREE_SRC="${DEVICE_TREE_SRC:-$(cd "$(dirname "$0")/../device_tree/device/vivo/pd1610" 2>/dev/null && pwd || true)}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$SRC/.repo" ] || die "$SRC 不是 repo 源码树，请先跑 sync_los16.sh"
[ -f "$SRC/build/envsetup.sh" ] || die "$SRC 缺少 build/envsetup.sh，同步不完整"

# ---------------------------------------------------------------- 设备树
say "安装设备树"
DEST="$SRC/device/vivo/pd1610"
if [ -d "$DEST" ] && [ "${FORCE_DEVICE_TREE:-0}" != "1" ]; then
    echo "  $DEST 已存在，跳过（FORCE_DEVICE_TREE=1 可强制覆盖）"
else
    [ -n "$DEVICE_TREE_SRC" ] && [ -d "$DEVICE_TREE_SRC" ] || \
        die "找不到设备树源目录。请用 DEVICE_TREE_SRC=/path/to/device/vivo/pd1610 指定"
    mkdir -p "$SRC/device/vivo"
    rm -rf "$DEST"
    cp -a "$DEVICE_TREE_SRC" "$DEST"
    echo "  已复制 $(find "$DEST" -type f | wc -l) 个文件到 $DEST"
fi

# 非 Treble：proprietary-files.txt 里的路径都以 vendor/ 开头，
# extract-files.sh 需要从「展开的 ROM 目录」取文件（vendor/ + system/lib*）。
BLOBS="${BLOBS_DIR:-}"
if [ -n "$BLOBS" ] && [ -d "$BLOBS/vendor" ]; then
    say "生成 vendor/vivo/pd1610（extract-files.sh）"
    cd "$DEST"
    bash ./extract-files.sh "$BLOBS" 2>&1 | tail -15
    echo "  生成文件数: $(find "$SRC/vendor/vivo/pd1610" -type f 2>/dev/null | wc -l)"
fi

# ---------------------------------------------------------------- 清理 ccache
if command -v ccache >/dev/null; then
    export USE_CCACHE=1
    export CCACHE_EXEC="$(command -v ccache)"
    export CCACHE_DIR="${CCACHE_DIR:-$HOME/.ccache}"
    ccache -M 50G >/dev/null 2>&1 || true
    echo "  ccache: $(ccache -s 2>/dev/null | awk '/cache size/{print $0}' | head -1)"
fi

# ---------------------------------------------------------------- 编译
say "编译 $TARGET（device=pd1610）"
cd "$SRC"

# shellcheck disable=SC1091
source build/envsetup.sh >/dev/null

# LOS16 有些脚本还写着 python（python2）。若系统只有 python3，先纠正。
if ! command -v python >/dev/null 2>&1; then
    if command -v python2 >/dev/null 2>&1; then
        mkdir -p "$HOME/bin"
        ln -sf "$(command -v python2)" "$HOME/bin/python"
        export PATH="$HOME/bin:$PATH"
        echo "  已注入 python -> python2 到 PATH"
    fi
fi

lunch "lineage_pd1610-userdebug" || die "lunch 失败：检查 device/vivo/pd1610/AndroidProducts.mk 与 lineage_pd1610.mk"

JOBS="${JOBS:-$(nproc)}"
echo "  开始编译：mka $TARGET -j$JOBS"
echo "  日志：$SRC/out/build_$(date +%Y%m%d_%H%M).log"
LOG="$SRC/out/build_$(date +%Y%m%d_%H%M).log"
mkdir -p "$SRC/out"

set +e
mka "$TARGET" -j"$JOBS" 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

if [ "$RC" -ne 0 ]; then
    say "编译失败（exit $RC）"
    echo "  最后 40 行错误："
    grep -iE "error:|Error [0-9]+|ninja: build stopped|FAILED:" "$LOG" | tail -40
    exit "$RC"
fi

# ---------------------------------------------------------------- 产物
say "编译成功，收集产物"
OUT="$SRC/out/target/product/pd1610"
ls -lh "$OUT"/*.img "$OUT"/*.zip 2>/dev/null | awk '{printf "  %-42s %s\n", $9, $5}'

cat <<EOF

------------------------------------------------------------------
产物目录：$OUT

关键文件：
  boot.img        自编内核 + 自编 ramdisk（含我们写的 init.pd1610.rc 与 fstab.qcom）
  system.img      类原生系统（非 Treble：vendor 在 system/vendor 内）
  recovery.img    可选

刷入前必读：
  * boot 分区 100,663,296 B，system 分区 3,221,225,472 B。
    system.img 若超出会直接刷失败，需要用 sparse 或裁剪。
  * 本机 max-download-size 只有 512 MB，system.img 必须走 EDL 或 fastboot sparse 分块；
    但实测本机 aboot 对 fastboot -S 分块会挂死 USB 端点 —— 只能用 EDL 写 system。
  * 首次启动保留 androidboot.selinux=permissive，先收集 avc denial 再收紧。
------------------------------------------------------------------
EOF
