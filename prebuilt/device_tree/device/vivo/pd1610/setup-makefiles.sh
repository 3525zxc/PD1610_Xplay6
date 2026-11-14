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
# 只生成 vendor/ 侧的 Android.mk / BoardConfigVendor.mk / <device>-vendor.mk，
# 不重新抓取文件。extract-files.sh 结束时会自动调用它。
#

set -e

export DEVICE=pd1610
export VENDOR=vivo

MY_DIR="${BASH_SOURCE%/*}"
if [[ ! -d "$MY_DIR" ]]; then MY_DIR="$PWD"; fi

LINEAGE_ROOT="$MY_DIR"/../../..

HELPER="$LINEAGE_ROOT"/vendor/lineage/build/tools/extract_utils.sh
if [ ! -f "$HELPER" ]; then
    HELPER="$LINEAGE_ROOT"/tools/extract-utils/extract_utils.sh
fi
if [ ! -f "$HELPER" ]; then
    echo "Unable to find extract_utils.sh"
    exit 1
fi
. "$HELPER"

setup_vendor "$DEVICE" "$VENDOR" "$LINEAGE_ROOT"

write_makefiles "$MY_DIR"/proprietary-files.txt
