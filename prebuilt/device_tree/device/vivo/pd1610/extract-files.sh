#!/bin/bash
#
# Copyright (C) 2019 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# 用法：
#   ./extract-files.sh                 # 从已连接的设备 adb pull（设备需已 root）
#   ./extract-files.sh /path/to/blobs  # 从已展开的 ROM 目录复制
#
# 本机的 blobs 目录就是第二种形态：
#   D:/16/PD1610_81/blobs/vendor/...        ← 设备 /system/vendor 全量
#   D:/16/PD1610_81/blobs/system/lib[64]/   ← 必须额外带走的私有系统库
#

set -e

export DEVICE=pd1610
export VENDOR=vivo

MY_DIR="${BASH_SOURCE%/*}"
if [[ ! -d "$MY_DIR" ]]; then MY_DIR="$PWD"; fi

LINEAGE_ROOT="$MY_DIR"/../../..

# extract_utils 的位置在 lineage-16.0 与 17.1 不同，两个都试一遍
HELPER="$LINEAGE_ROOT"/vendor/lineage/build/tools/extract_utils.sh
if [ ! -f "$HELPER" ]; then
    HELPER="$LINEAGE_ROOT"/tools/extract-utils/extract_utils.sh
fi
if [ ! -f "$HELPER" ]; then
    echo "Unable to find extract_utils.sh (looked in vendor/lineage/build/tools and tools/extract-utils)"
    echo "请在 LINEAGE_ROOT=$LINEAGE_ROOT 下先执行 'source build/envsetup.sh' 并确认分支"
    exit 1
fi
. "$HELPER"

if [ $# -eq 0 ]; then
    SRC=adb
else
    if [ $# -eq 1 ]; then
        SRC=$1
    else
        echo "$0: bad number of arguments"
        echo ""
        echo "usage: $0 [PATH_TO_EXPANDED_ROM]"
        echo ""
        echo "If PATH_TO_EXPANDED_ROM is not specified, blobs will be extracted from"
        echo "the device using adb pull."
        exit 1
    fi
fi

setup_vendor "$DEVICE" "$VENDOR" "$LINEAGE_ROOT"

# extract_utils.sh 里 write_product_copy_files / write_packages 全部用 ">>"
# 追加，没有任何清空动作。重跑若不先删，PRODUCT_COPY_FILES 会成倍累积
# （实测连跑 4 次后 mk 涨到 6310 行，混进 "system//system/..." 这类过期规则，
#  编译时直接报 missing file）。每次提取前一律重置这三份生成物。
rm -f "$PRODUCTMK" "$ANDROIDMK" "$BOARDMK"

extract "$MY_DIR"/proprietary-files.txt "$SRC"

"$MY_DIR"/setup-makefiles.sh

# 补齐跨目录符号链接。
# 原厂有 211 条软链，其中跨目录的那些写成了 /system/vendor/... 绝对路径；
# 本设备非 Treble（TREBLE_COMPAT=false），write_product_copy_files 会拼成
# "system//system/vendor/..." 导致整条规则失效——wlan.ko 就是其中之一。
# 这里改用实体副本补齐，见脚本头部说明。
if [ -f "$MY_DIR"/fix_vendor_links.py ] && [ "$SRC" != "adb" ]; then
    python3 "$MY_DIR"/fix_vendor_links.py "$SRC" "$LINEAGE_ROOT/vendor/$VENDOR/$DEVICE"
fi
