#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PD1610 —— 补齐 vendor 树里丢失的符号链接（以实体副本方式）

背景
----
原厂 /system/vendor 下有 211 条符号链接。Windows 侧解包时无法创建 Unix
软链，只能记录到 blobs/vendor_links.json。extract_utils.sh 的 `src:dst`
语法虽然能表达软链，但本设备（非 Treble，TREBLE_COMPAT=false）有两个坑：

  1. dst 若写成 /system/vendor/... 绝对路径，mk 会拼成
     "system//system/vendor/..."，整条规则失效（含 wlan.ko 这条关键链接）；
  2. dst 写成相对路径时，跨目录软链在 vendor 仓里会解析错误，且
     PRODUCT_COPY_FILES 复制时会 cp -f 解引用，断链直接导致复制失败。

所以采用「实体副本」：把链接目标的内容复制到链接所在路径，再补一条
普通 PRODUCT_COPY_FILES。代价是 system.img 增大（toybox 150 条 × 499 KB
≈ 75 MB），换来的是不依赖软链语义、绝对不会有断链。

用法
----
  python3 fix_vendor_links.py <blobs_dir> <vendor_repo_dir>

    blobs_dir       含 vendor_links.json / vendor/ / system/ 的目录
    vendor_repo_dir 形如 ~/los16/vendor/vivo/pd1610（内含 proprietary/）

幂等：已存在的文件不覆盖；每次 extract 之后跑一次即可。
"""

import json
import os
import shutil
import stat
import sys

MARK_BEGIN = "# --- 软链补齐（fix_vendor_links.py 生成，勿手改）---"
MARK_END = "# --- 软链补齐结束 ---"


def resolve_target(blobs, path, linkname):
    """把 vendor_links.json 的一条记录解析成 blobs 里的真实文件路径。

    linkname 可能是：
      * 绝对路径 /system/vendor/...  → 去掉 /system 前缀后落在 blobs 根
      * 相对名 toybox_vendor        → 相对 path 所在目录
    """
    if linkname.startswith("/"):
        tgt = linkname
        if tgt.startswith("/system/"):
            tgt = tgt[len("/system/"):]
        return os.path.join(blobs, tgt.lstrip("/"))
    return os.path.join(blobs, os.path.dirname(path), linkname)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    blobs = os.path.abspath(sys.argv[1])
    vendor = os.path.abspath(sys.argv[2])

    link_json = os.path.join(blobs, "vendor_links.json")
    if not os.path.isfile(link_json):
        print("!! 找不到 %s" % link_json)
        return 1

    with open(link_json, "r", encoding="utf-8") as f:
        links = json.load(f)

    prop_dir = os.path.join(vendor, "proprietary")
    product_mk = os.path.join(vendor, "pd1610-vendor.mk")
    if not os.path.isdir(prop_dir):
        print("!! %s 不存在，先跑 extract-files.sh" % prop_dir)
        return 1

    added, skipped, existed = [], [], 0
    present = []          # 文件已就位（本次复制或原本就在），必须保证 mk 里有打包规则

    for e in links:
        path, linkname = e["path"], e["linkname"]
        dst = os.path.join(prop_dir, path)
        src = resolve_target(blobs, path, linkname)

        if os.path.exists(dst):
            existed += 1
            present.append(path)
            continue

        if not os.path.isfile(src):
            skipped.append((path, linkname))
            continue

        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        # /vendor/bin 下的命令保持可执行
        if "/bin/" in path:
            os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        added.append(path)
        present.append(path)

    # 读 mk 并剔除上一次生成的补齐段（保证幂等）
    if os.path.isfile(product_mk):
        with open(product_mk, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        out, in_block = [], False
        for ln in lines:
            if ln.strip() == MARK_BEGIN.strip():
                in_block = True
                continue
            if ln.strip() == MARK_END.strip():
                in_block = False
                continue
            if not in_block:
                out.append(ln)
        lines = out
    else:
        lines = []

    # 普通段已覆盖的目标。重复的 PRODUCT_COPY_FILES 会触发 build 的 dup 报错，
    # 所以只补普通段里没有的目标。
    covered = set()
    for ln in lines:
        s = ln.strip()
        if s.endswith("\\"):
            s = s[:-1].strip()
        if not s or s.startswith("#") or s.startswith("PRODUCT_COPY_FILES"):
            continue
        if ":" in s:
            covered.add(s.split(":", 1)[1].strip())

    need = [p for p in present if ("system/" + p) not in covered]

    if need:
        lines.append("")
        lines.append(MARK_BEGIN)
        lines.append("PRODUCT_COPY_FILES += \\")
        for i, p in enumerate(need):
            end = "" if i == len(need) - 1 else " \\"
            lines.append("    vendor/vivo/pd1610/proprietary/%s:system/%s%s" % (p, p, end))
        lines.append(MARK_END)

    with open(product_mk, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("软链总条数  : %d" % len(links))
    print("  文件已在位: %d（本次新复制 %d）" % (existed, len(added)))
    print("  需补规则  : %d" % len(need))
    print("  目标缺失  : %d（原厂断链，忽略）" % len(skipped))
    if added:
        print("  新增示例  :")
        for p in added[:5]:
            print("    + %s" % p)
    if skipped:
        print("  缺失示例  :")
        for p, ln in skipped[:5]:
            print("    - %s -> %s" % (p, ln))
    return 0


if __name__ == "__main__":
    sys.exit(main())
