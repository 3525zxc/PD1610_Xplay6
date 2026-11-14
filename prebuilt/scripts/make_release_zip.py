#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 PD1610 LOS16 发布目录打成单个 zip（流式，不把大文件读进内存）。"""
import os
import shutil
import stat
import sys
import time
import zipfile

SRC = r"D:\16\PD1610_81\release\PD1610_LOS16_20261112"
OUT = r"D:\16\PD1610_81\out\PD1610_LOS16_20261112_UNOFFICIAL.zip"
ROOT = os.path.basename(SRC)


def main():
    files = []
    for dirpath, _, names in os.walk(SRC):
        for n in names:
            p = os.path.join(dirpath, n)
            files.append((p, os.path.relpath(p, SRC)))
    files.sort(key=lambda x: x[1])
    print("files=%d" % len(files), flush=True)

    t0 = time.time()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as z:
        for full, rel in files:
            st = os.stat(full)
            zi = zipfile.ZipInfo(ROOT + "/" + rel.replace(os.sep, "/"),
                                 date_time=time.localtime(st.st_mtime)[:6])
            zi.compress_type = zipfile.ZIP_DEFLATED
            mode = stat.S_IMODE(st.st_mode)
            if rel.endswith(".sh") or rel.startswith("tools/") and rel.endswith("_linux"):
                mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            zi.external_attr = (0o100000 | mode) << 16
            zi.create_system = 3
            with open(full, "rb") as src, z.open(zi, "w", force_zip64=True) as dst:
                shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
            print("  + %-72s %10d B" % (rel.replace(os.sep, "/"), st.st_size), flush=True)

    size = os.path.getsize(OUT)
    print("zip written: %s (%d B, %.1f MiB) in %.1f s" %
          (OUT, size, size / 1048576.0, time.time() - t0), flush=True)

    with zipfile.ZipFile(OUT) as z:
        bad = z.testzip()
        print("testzip:", "OK" if bad is None else "CORRUPT: " + bad, flush=True)
        print("entries:", len(z.namelist()), flush=True)
    return 0 if bad is None else 1


if __name__ == "__main__":
    sys.exit(main())
