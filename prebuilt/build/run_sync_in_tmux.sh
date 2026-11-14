#!/bin/bash
# 在 tmux 里运行 LOS16 同步（由 setup 流程或手动调用）
LOG="$HOME/sync_los16.log"
: > "$LOG"
echo "=== start $(date '+%F %T') ===" >> "$LOG"
bash /mnt/d/16/PD1610_81/build/sync_los16.sh >> "$LOG" 2>&1
RC=$?
echo "=== EXIT=$RC  $(date '+%F %T') ===" >> "$LOG"
exit $RC
