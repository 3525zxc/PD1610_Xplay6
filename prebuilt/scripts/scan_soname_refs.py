#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 soname 字面量扫描 vendor blob，列出可能引用它的 ELF（候选，再用 readelf 确认）。"""
import os
import sys

BASE = r"D:\16\PD1610_81\blobs\vendor"


def scan(root, needle):
    nb = needle.encode()
    hits = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > 200 * 1024 * 1024:
                    continue
                with open(p, "rb") as f:
                    head = f.read(4)
                    if head != b"\x7fELF":
                        continue
                    f.seek(0)
                    data = f.read()
            except OSError:
                continue
            if nb in data:
                hits.append((p, data.count(nb)))
    return hits


if __name__ == "__main__":
    needle = sys.argv[1] if len(sys.argv) > 1 else "android.hardware.gnss@1.0.so"
    for p, c in scan(BASE, needle):
        print("%-90s x%d" % (p[len(BASE) + 1:], c))
