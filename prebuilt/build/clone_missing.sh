#!/bin/bash
# ============================================================================
# PD1610 —— 补齐 repo sync 漏掉的 300+ 个 AOSP/LineageOS 项目
#
# 背景：第一轮 -j14 触发中科大 429，332 个项目 fetch 失败；第二轮换清华后
# 仍因「repo sync 无 --depth」在拉全量历史而卡死。实测中科大 shallow clone
# 可达 23 MB/s，所以这里按 manifest 逐项 shallow clone 到 work tree 位置。
#
# remote 规则：
#   aosp   → https://mirrors.ustc.edu.cn/aosp/platform/<name>   tag android-9.0.0_r46
#   github → https://ghfast.top/https://github.com/<name>       branch lineage-16.0
#   裸 SHA → 先 init+fetch 该 SHA 再 checkout
#
# 跳过：cts / device/generic/* / autotest / toolchain / prebuilts/ndk
#       （模拟器、测试套件、交叉工具链，arm64 手机编译不需要）
# ============================================================================
set -uo pipefail

SRC="$HOME/los16"
MF="${MF:-/tmp/mf.xml}"
LIST=/tmp/clone_list.txt
PAR="${PAR:-4}"

[ -f "$MF" ] || { echo "!! 缺少 $MF，先跑 repo manifest -o $MF"; exit 1; }

python3 - "$MF" "$SRC" > "$LIST" <<'PYEOF'
import sys, os, xml.etree.ElementTree as ET

mf, base = sys.argv[1], sys.argv[2]
root = ET.parse(mf).getroot()

remote_rev = {}
for r in root.iter('remote'):
    remote_rev[r.get('name')] = r.get('revision') or ''

default_remote = 'github'
for d in root.iter('default'):
    default_remote = d.get('remote') or default_remote

SKIP_PREFIX = (
    'cts', 'device/generic/', 'autotest', 'toolchain/',
    'prebuilts/ndk', 'external/robolectric',
)

for p in root.iter('project'):
    path = p.get('path') or p.get('name')
    if os.path.isdir(os.path.join(base, path)):
        continue
    if any(path == s or path.startswith(s) for s in SKIP_PREFIX):
        continue

    name = p.get('name')
    remote = p.get('remote') or default_remote
    rev = p.get('revision') or remote_rev.get(remote) or ''

    # manifest 里 aosp 项目的 name 有两种前缀形态：
    #   platform/external/bzip2   （已含 platform/）
    #   kernel/configs            （不含，镜像路径要补 platform/）
    # 拼错会变成 platform/platform/xxx → 301 个项目全 404。
    if remote == 'aosp':
        if name.startswith('platform/'):
            url = 'https://mirrors.ustc.edu.cn/aosp/%s' % name
        else:
            url = 'https://mirrors.ustc.edu.cn/aosp/platform/%s' % name
    elif remote == 'github':
        url = 'https://ghfast.top/https://github.com/%s' % name
    else:
        continue

    ref = rev
    for pre in ('refs/tags/', 'refs/heads/'):
        if ref.startswith(pre):
            ref = ref[len(pre):]

    print('%s|%s|%s' % (url, ref, path))
PYEOF

TOTAL=$(wc -l < "$LIST")
echo "=== 待补齐 $TOTAL 个项目｜并发 $PAR｜$(date '+%F %T') ==="

OK=0; FAIL=0; FAILED_PATHS=""

clone_one() {
    local url="$1" ref="$2" path="$3"
    local dst="$SRC/$path"
    [ -d "$dst" ] && { echo "SKIP $path"; return 0; }
    mkdir -p "$(dirname "$dst")"

    if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
        mkdir -p "$dst"
        if ( cd "$dst" && git init -q . && git remote add origin "$url" 2>/dev/null; \
             git fetch -q --depth=1 origin "$ref" && git checkout -q FETCH_HEAD ); then
            echo "OK   $path (sha)"
            return 0
        fi
        rm -rf "$dst"; echo "FAIL $path (sha $ref)"; return 1
    fi

    local try_ref
    for try_ref in "$ref" "" lineage-16.0 master; do
        if [ -z "$try_ref" ]; then
            # 不带 --branch：拉镜像的默认 HEAD，用于 tag 不存在的项目
            if git clone -q --depth=1 "$url" "$dst" 2>/dev/null; then
                echo "OK   $path (default HEAD)"
                return 0
            fi
        elif git clone -q --depth=1 --branch "$try_ref" "$url" "$dst" 2>/dev/null; then
            echo "OK   $path ($try_ref)"
            return 0
        fi
        rm -rf "$dst"
    done
    echo "FAIL $path"
    return 1
}

while IFS='|' read -r url ref path; do
    [ -z "${url:-}" ] && continue
    clone_one "$url" "$ref" "$path" &
    while [ "$(jobs -r | wc -l)" -ge "$PAR" ]; do wait -n; done
done < "$LIST"
wait

echo "=== 完成 $(date '+%F %T') ==="
