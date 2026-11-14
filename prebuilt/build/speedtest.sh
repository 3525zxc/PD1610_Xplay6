#!/bin/bash
# 对比不同源的真实 clone 速度（WSL 内部运行）
REPO="android_external_icu"
BRANCH="lineage-16.0"

try() {
    local url="$1"
    rm -rf /tmp/_sp
    local s e ms rc sz
    s=$(date +%s%N)
    timeout 60 git clone --quiet --depth=1 --single-branch -b "$BRANCH" "$url" /tmp/_sp >/dev/null 2>&1
    rc=$?
    e=$(date +%s%N)
    ms=$(( (e - s) / 1000000 ))
    sz=$(du -sm /tmp/_sp 2>/dev/null | cut -f1)
    printf '  %-58s RC=%-3s %6sms %5sMB\n' "$url" "$rc" "$ms" "${sz:-0}"
}

echo "=== 单仓库 clone 对比：$REPO ($BRANCH) ==="
try "https://github.com/LineageOS/$REPO.git"
try "https://gitclone.com/github.com/LineageOS/$REPO.git"
try "https://hub.gitmirror.com/https://github.com/LineageOS/$REPO.git"
try "https://ghfast.top/https://github.com/LineageOS/$REPO.git"
rm -rf /tmp/_sp

echo
echo "=== codeload tar.gz 直下（同一仓库）==="
for u in \
  "https://codeload.github.com/LineageOS/$REPO/tar.gz/refs/heads/$BRANCH" \
  "https://ghfast.top/https://github.com/LineageOS/$REPO/archive/refs/heads/$BRANCH.tar.gz" ; do
    printf '  %-58s ' "$(echo "$u" | cut -c1-56)"
    timeout 30 curl -sL -o /dev/null -w '%{speed_download} B/s  %{size_download} B\n' "$u" 2>&1 | tail -1
done
