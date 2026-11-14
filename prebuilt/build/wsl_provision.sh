#!/bin/bash
# ============================================================================
# WSL 发行版内部配置（由 setup_wsl.ps1 调用，也可手动执行）
#   wsl -d PD1610 -u root -- bash /mnt/d/16/PD1610_81/build/wsl_provision.sh
# ============================================================================
set -euo pipefail

echo "==> [1/6] 配置 apt 源（清华，http —— ubuntu-base 没装 ca-certificates 时 https 会失败）"
cat > /etc/apt/sources.list <<'EOF'
deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal main restricted universe multiverse
deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal-updates main restricted universe multiverse
deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal-backports main restricted universe multiverse
deb http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ focal-security main restricted universe multiverse
EOF

echo "==> [2/6] 时区与 locale"
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
echo "Asia/Shanghai" > /etc/timezone
export DEBIAN_FRONTEND=noninteractive

echo "==> [3/6] apt update"
apt-get update -qq

echo "==> [4/6] 基础工具"
apt-get install -y -qq --no-install-recommends \
    sudo ca-certificates curl wget git nano vim-tiny less \
    python2-minimal python-is-python2 \
    rsync unzip file tzdata locales

# python 指向 python2：LOS16 的 build 系统部分脚本仍写 #!/usr/bin/env python
ln -sf /usr/bin/python2 /usr/bin/python

echo "==> [5/6] AOSP 构建依赖（LOS16 / Ubuntu 20.04 对应包名）"
dpkg --add-architecture i386
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    bc bison build-essential ccache flex g++-multilib gcc-multilib \
    gnupg gperf imagemagick lib32ncurses-dev lib32readline-dev \
    lib32z1-dev liblz4-tool libncurses-dev libsdl1.2-dev libssl-dev \
    libwxgtk3.0-gtk3-dev libxml2 libxml2-utils lzop pngcrush schedtool \
    squashfs-tools xsltproc zip zlib1g-dev openjdk-8-jdk

echo "     java: $(java -version 2>&1 | head -1)"
echo "     python: $(python --version 2>&1)"

echo "==> [6/6] 创建构建用户 builder 与 wsl.conf"
if ! id builder >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo builder
fi
echo 'builder ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/builder
chmod 440 /etc/sudoers.d/builder

cat > /etc/wsl.conf <<'EOF'
[user]
default = builder

[interop]
# 不把 Windows PATH 注入 Linux，避免 AOSP 构建时误用到 Windows 的 find/ln
appendWindowsPath = false

[automount]
enabled = true
options = "metadata,umask=22,fmask=11"

[network]
generateResolvConf = true
EOF

echo
echo "==> 配置完成，汇总："
echo "  Ubuntu     : $(. /etc/os-release; echo "$PRETTY_NAME")"
echo "  内核       : $(uname -r)"
echo "  CPU        : $(nproc) 线程"
echo "  内存       : $(free -g | awk '/^Mem:/{print $2}') GB"
echo "  python     : $(python --version 2>&1)"
echo "  java       : $(java -version 2>&1 | head -1)"
echo "  gcc        : $(gcc --version | head -1)"
echo
echo "  下一步："
echo "    wsl -d PD1610 -- bash -lc 'cd ~ && ./sync_los16.sh'"
