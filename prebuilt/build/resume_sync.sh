#!/bin/bash
# ============================================================================
# PD1610 —— LineageOS 16.0 续传同步
#
# 与 sync_los16.sh 的区别：**不带 --force-sync**。
# 上一轮 703 个项目中已检出 332 个，--force-sync 会把它们全部重下，纯浪费带宽。
# 不带该参数时 repo 只下载缺失的项目与缺失的 object。
# ============================================================================
set -uo pipefail

SRC="$HOME/los16"
JOBS="${JOBS:-14}"
REPO_BIN="$HOME/bin/repo"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

[ -x "$REPO_BIN" ] || REPO_BIN="$HOME/los16/../bin/repo"
[ -x "$REPO_BIN" ] || { echo "!! repo 不存在"; exit 1; }

git config --global url."https://ghfast.top/https://github.com/".insteadOf "https://github.com/"
git config --global url."https://mirrors.ustc.edu.cn/aosp/".insteadOf "https://android.googlesource.com/"

cd "$SRC" || exit 1

say "续传前状态"
echo "  已检出: $(cd "$SRC" && "$REPO_BIN" forall -c 'echo x' 2>/dev/null | wc -l)"

say "repo sync（续传，-j$JOBS，无 --force-sync）"
"$REPO_BIN" sync \
    -j"$JOBS" \
    --no-clone-bundle \
    --no-tags \
    --optimized-fetch
RC=$?

say "sync 退出码: $RC"
echo "  已检出: $(cd "$SRC" && "$REPO_BIN" forall -c 'echo x' 2>/dev/null | wc -l)"
echo "  源码占用: $(du -sh --exclude=.repo "$SRC" 2>/dev/null | cut -f1)"
echo "  .repo   : $(du -sh "$SRC/.repo" 2>/dev/null | cut -f1)"
echo "=== done $(date '+%F %T') rc=$RC ==="
exit $RC
