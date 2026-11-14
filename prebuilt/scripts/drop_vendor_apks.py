#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 proprietary-files.txt 中剔除 vivo 预装 APK 及其配套 odex/vdex。

原因：AOSP 9 的 build/make/core/Makefile:28 有硬性检查
    error: Prebuilt apk found in PRODUCT_COPY_FILES: ... use BUILD_PREBUILT instead!
extract_utils.sh 的 write_product_copy_files 对 .apk 一视同仁写进
PRODUCT_COPY_FILES，所以只要清单里有 apk，kati 解析阶段就必挂。

启动阶段这些 vendor 应用（CABLService / QFingerprintService / 各运营商
overlay 等）不参与 boot，先整体剔除。后续要恢复时，正确做法是为每个 apk
生成 BUILD_PREBUILT 模块（LOCAL_MODULE_CLASS := APPS,
LOCAL_CERTIFICATE := PRESIGNED），而不是塞回 PRODUCT_COPY_FILES。

同时剔除 vendor/app/*/oat/ 下的 odex/vdex：原厂 odex 绑定的是 vivo 的
/system/framework，换 ROM 后 ART 校验不过会重新编译，留着只是白占空间。

用法：python3 drop_vendor_apks.py <proprietary-files.txt>
"""
import re
import sys

def main(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    kept, dropped = [], []
    apk_re = re.compile(r"\.apk(\s*$|:)")
    oat_re = re.compile(r"/oat/|\.(odex|vdex|oat)(\s*$|:)")

    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#") and (apk_re.search(s) or oat_re.search(s)):
            dropped.append(s)
            continue
        kept.append(ln)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")

    apks = sum(1 for d in dropped if d.endswith(".apk"))
    print("剔除 apk      : %d" % apks)
    print("剔除 odex/vdex: %d" % (len(dropped) - apks))
    print("剩余条目      : %d" % len([l for l in kept if l.strip() and not l.strip().startswith("#")]))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "proprietary-files.txt")
