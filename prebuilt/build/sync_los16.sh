#!/bin/bash
# ============================================================================
# PD1610 (vivo Xplay6) —— LineageOS 16.0 源码同步脚本
#
# 用法：
#   chmod +x sync_los16.sh
#   ./sync_los16.sh                 # 同步到 ~/los16
#   ./sync_los16.sh /srv/los16      # 指定目录
#
# 必须在 Linux 上运行（ext4/xfs/btrfs）。NTFS/exFAT 大小写不敏感，
# AOSP 源码里存在同名不同大小写的文件，checkout 会失败。
# ============================================================================
set -euo pipefail

SRC="${1:-$HOME/los16}"
BRANCH="lineage-16.0"
JOBS="${JOBS:-$(nproc)}"

# 源选择（2026-11-11 实测）
#   清华 TUNA：ls-remote 快，但 clone 走排队限流（实测 Position 1300+），
#              598 个仓库逐个排队不可行 —— 弃用。
#   GitHub   ：clone 实测 15 MB 秒级完成，走这里。
#   中科大   ：AOSP 镜像 19 MB 秒级完成，427 个 AOSP 仓库走这里。
MIRROR_LOS="https://github.com/LineageOS/android.git"
MIRROR_AOSP="https://mirrors.ustc.edu.cn/aosp/"
REPO_URL="https://mirrors.tuna.tsinghua.edu.cn/git/git-repo"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 环境自检
say "环境自检"

[ "$(uname -s)" = "Linux" ] || die "必须在 Linux 上运行（当前：$(uname -s)）"

FS_TYPE=$(stat -f -c %T "$(dirname "$SRC")" 2>/dev/null || echo unknown)
case "$FS_TYPE" in
    ext2/ext3|ext4|xfs|btrfs|zfs) : ;;
    *) die "源码目录所在文件系统是 $FS_TYPE，必须用大小写敏感的 Linux 文件系统（ext4/xfs/btrfs）。
       不要放在 /mnt/c、/mnt/d 这类 NTFS 挂载点上——AOSP 里有同名不同大小写的文件，checkout 必然失败。" ;;
esac
echo "  文件系统      : $FS_TYPE  OK"

FREE_GB=$(df -BG --output=avail "$(dirname "$SRC")" | tail -1 | tr -dc '0-9')
echo "  可用空间      : ${FREE_GB} GB"
[ "$FREE_GB" -ge 90 ] || die "可用空间不足：需要至少 90 GB（源码 ~35 GB + out ~45 GB），当前 ${FREE_GB} GB"

MEM_GB=$(awk '/MemTotal/{printf "%d", $2/1024/1024}' /proc/meminfo)
echo "  内存          : ${MEM_GB} GB"
[ "$MEM_GB" -ge 8 ] || echo "  !! 内存 < 8 GB，编译极易 OOM。建议加 swap：见脚本末尾提示"

echo "  CPU 线程      : $(nproc)"

for t in git python3 curl; do
    command -v "$t" >/dev/null || die "缺少 $t"
done
echo "  git           : $(git --version | awk '{print $3}')"
echo "  python3       : $(python3 --version 2>&1 | awk '{print $2}')"

# LOS16 的构建系统（build/make 的部分脚本）依赖 python2。
# Ubuntu 20.04+ 默认没有 python2，需要显式安装；这里只警告不阻断。
if ! command -v python2 >/dev/null && ! command -v python2.7 >/dev/null; then
    echo "  !! 未找到 python2 —— LOS16 的 repopick/findleaves 等脚本会失败"
    echo "     Ubuntu 20.04: sudo apt install python2 && sudo ln -sf /usr/bin/python2 /usr/bin/python"
    echo "     Ubuntu 22.04+: 需从 deadsnakes PPA 装 python2.7，或改用 Docker 镜像"
fi

# ---------------------------------------------------------------- 镜像配置
say "配置镜像源"

# repo 启动器：优先用 $HOME/bin/repo（已在 ext4 上，权限可靠），
# 其次用脚本同目录的副本（在 /mnt/d 的 NTFS 上，可能需要 chmod）
REPO_BIN=""
if [ -x "$HOME/bin/repo" ]; then
    REPO_BIN="$HOME/bin/repo"
    echo "  使用 $REPO_BIN"
elif [ -f "$(dirname "$0")/repo" ]; then
    mkdir -p "$HOME/bin"
    cp "$(dirname "$0")/repo" "$HOME/bin/repo"
    chmod +x "$HOME/bin/repo"
    REPO_BIN="$HOME/bin/repo"
    echo "  已复制 repo 到 $REPO_BIN ($("$REPO_BIN" --version 2>/dev/null | grep -o 'version [0-9.]*' | head -1))"
else
    mkdir -p "$HOME/bin"
    curl -fsSL "$REPO_URL" -o "$HOME/bin/repo"
    chmod +x "$HOME/bin/repo"
    REPO_BIN="$HOME/bin/repo"
    echo "  下载 repo 到: $REPO_BIN"
fi
export REPO_URL="$REPO_URL"

# GitHub remote 重定向到 ghfast.top 代理。
# 实测（2026-11-11，WSL2）：
#   https://github.com/LineageOS/...         clone 60 秒超时，0 字节 —— 直连不通
#   https://gitclone.com/...                 git 报错 RC=128
#   https://hub.gitmirror.com/...            git 报错 RC=128
#   https://ghfast.top/https://github.com/   373 MB / 20.5 秒 ≈ 18 MB/s —— 可用
# insteadOf 会把 https://github.com/LineageOS/xxx 改写成
# https://ghfast.top/https://github.com/LineageOS/xxx，正好是代理的 URL 格式。
git config --global --unset-all url."https://ghfast.top/https://github.com/".insteadOf 2>/dev/null || true
git config --global url."https://ghfast.top/https://github.com/".insteadOf "https://github.com/"
echo "  insteadOf: github.com -> ghfast.top 代理"

# AOSP remote 指向 android.googlesource.com，重定向到中科大镜像。
# 先清掉可能存在的旧 insteadOf（例如之前指向清华的），避免叠加或冲突。
git config --global --unset-all url."https://mirrors.tuna.tsinghua.edu.cn/git/AOSP/".insteadOf 2>/dev/null || true
git config --global --unset-all url."$MIRROR_AOSP".insteadOf 2>/dev/null || true
git config --global url."$MIRROR_AOSP".insteadOf "https://android.googlesource.com/"
echo "  insteadOf: android.googlesource.com -> $MIRROR_AOSP"

# ---------------------------------------------------------------- repo init
say "repo init（$BRANCH）"
mkdir -p "$SRC"
cd "$SRC"

if [ -f .repo/manifest.xml ] || [ -d .repo/manifests/.git ]; then
    echo "  .repo 已初始化，跳过 init（如需重置请先删除 .repo）"
else
    # repo 启动器每次 init 都会把自身仓库重新 clone 到 .repo/repo。
    # 清华镜像的 git-repo 仓库有 11939 个 refs，全量 fetch 会卡死（实测 5 分钟无进展）。
    # 因此预置一份浅克隆副本，用本地路径当 --repo-url（实测 0.06 秒完成）。
    REPO_SRC="${REPO_SRC:-$HOME/repo-src}"
    if [ -d "$REPO_SRC/.git" ]; then
        echo "  repo 源: 本地 $REPO_SRC（REPO_URL 环境变量）"
        REPO_URL="$REPO_SRC" REPO_REV=master "$REPO_BIN" init \
            -u "$MIRROR_LOS" \
            -b "$BRANCH" \
            --depth=1 \
            --no-clone-bundle
    else
        echo "  !! 未找到 $REPO_SRC，回落到网络拉取（可能很慢）"
        REPO_URL="$REPO_URL" "$REPO_BIN" init \
            -u "$MIRROR_LOS" \
            -b "$BRANCH" \
            --depth=1 \
            --no-clone-bundle
    fi
    echo "  init 完成"
fi

# ---------------------------------------------------------------- repo sync
say "repo sync（598 个项目，-j$JOBS）"
echo "  预计：千兆带宽 40-90 分钟，百兆 3-5 小时。中断后重跑本脚本可续传。"

# repo 2.71 的选项集：--force-sync / --no-clone-bundle / --no-tags /
# --optimized-fetch 都支持；重试参数名是 --retry-fetches（不是 --retry-fetcher）。
"$REPO_BIN" sync \
    -j"$JOBS" \
    --force-sync \
    --no-clone-bundle \
    --no-tags \
    --optimized-fetch

say "同步完成，校验"
cd "$SRC"
echo "  已同步项目数: $(find .repo/projects -maxdepth 3 -name '*.git' 2>/dev/null | wc -l)"
echo "  源码占用    : $(du -sh --exclude=.repo . 2>/dev/null | cut -f1)"
echo "  .repo 占用  : $(du -sh .repo 2>/dev/null | cut -f1)"
echo "  HEAD        : $(git -C .repo/manifests rev-parse --short HEAD 2>/dev/null)"

cat <<'EOF'

------------------------------------------------------------------
下一步：
  1. 安装构建依赖（Ubuntu 18.04/20.04）：
       sudo apt install -y bc bison build-essential ccache curl flex \
         g++-multilib gcc-multilib git gnupg gperf imagemagick \
         lib32ncurses5-dev lib32readline-dev lib32z1-dev libelf-dev \
         liblz4-tool libncurses5 libncurses5-dev libsdl1.2-dev \
         libssl-dev libxml2 libxml2-utils lzop pngcrush rsync \
         schedtool squashfs-tools xsltproc zip zlib1g-dev openjdk-8-jdk \
         python-is-python2

  2. 放入设备树：
       cp -r /path/to/device_tree/device/vivo/pd1610  <源码根>/device/vivo/pd1610

  3. 跑 build_los16.sh
------------------------------------------------------------------
EOF
