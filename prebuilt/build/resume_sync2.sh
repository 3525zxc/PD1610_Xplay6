#!/bin/bash
# ============================================================================
# PD1610 —— LineageOS 16.0 同步收尾（第二轮）
#
# 第一轮 rc=1 的原因：中科大 AOSP 镜像对 -j14 并发返回 HTTP 429（限流），
# 332 个项目 fetch 失败，prebuilts/go 等收不到 → soong 起不来，lunch 报
# "Device pd1610 not found"（其实是 get_build_var 调 go 失败）。
#
# 本轮改动：
#   1. AOSP remote 换清华镜像（同 commit 已验证可达）
#   2. 并发降到 4，避免再次触发限流
#   3. --retry-fetches=5 + 三轮重试
# ============================================================================
set -uo pipefail

SRC="$HOME/los16"
JOBS="${JOBS:-4}"
REPO_BIN="$HOME/bin/repo"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

[ -x "$REPO_BIN" ] || { echo "!! repo 不存在"; exit 1; }

say "切换 AOSP 镜像 → 清华"
git config --global --unset-all url."https://mirrors.ustc.edu.cn/aosp/".insteadOf 2>/dev/null || true
git config --global url."https://mirrors.tuna.tsinghua.edu.cn/git/AOSP/".insteadOf "https://android.googlesource.com/"
echo "  insteadOf: android.googlesource.com -> mirrors.tuna.tsinghua.edu.cn/git/AOSP/"
git config --global url."https://ghfast.top/https://github.com/".insteadOf "https://github.com/"

cd "$SRC" || exit 1

say "repo sync（-j$JOBS，最多 3 轮）"
RC=1
for i in 1 2 3; do
    echo "--- round $i $(date '+%T') ---"
    "$REPO_BIN" sync -j"$JOBS" --no-clone-bundle --no-tags \
        --optimized-fetch --retry-fetches=5
    RC=$?
    echo "--- round $i rc=$RC ---"
    [ "$RC" -eq 0 ] && break
    sleep 25
done

say "校验"
echo "  检出项目: $("$REPO_BIN" forall -c 'echo WT' 2>/dev/null | grep -c '^WT')"
echo "  源码占用: $(du -sh --exclude=.repo "$SRC" 2>/dev/null | cut -f1)"
echo "  .repo   : $(du -sh "$SRC/.repo" 2>/dev/null | cut -f1)"
echo "  go 工具链: $([ -x "$SRC/prebuilts/go/linux-x86/bin/go" ] && echo OK || echo MISSING)"
echo "=== done $(date '+%F %T') rc=$RC ==="
exit "$RC"
