#!/usr/bin/env python3
"""把 ELF .so 的 DT_NEEDED 里某个 soname 原地改成另一个（更短的）名字。

用途：vivo 8.1 的 android.hardware.audio@2.0-impl.so / audio.effect@2.0-impl.so
依赖 8.1 版 android.hardware.audio.common@2.0-util.so 里的
  android::HidlUtils::audioConfigToHal(...)
而 LOS16 的同名库把 HidlUtils 挪进了新命名空间，符号不再存在。

做法：把 8.1 的 util 库以新名字 libaucommonutil81.so 装进 /vendor/lib，
再把 impl 里的 DT_NEEDED 字符串原地改短（NUL 补齐）。因为 dynstr 用的是
偏移，改短不会破坏其它字符串的位置。
"""
import sys


def patch(path, old, new, dry=False):
    old_b = old.encode() + b"\0"
    new_b = new.encode() + b"\0"
    if len(new_b) > len(old_b):
        raise SystemExit("new name too long: %d > %d" % (len(new_b), len(old_b)))
    d = open(path, "rb").read()
    cnt = d.count(old_b)
    if cnt == 0:
        print("  %-60s : no occurrence of %s" % (path.split("/")[-1], old))
        return 0
    if dry:
        print("  %-60s : would patch %d occurrence(s)" % (path.split("/")[-1], cnt))
        return cnt
    d = d.replace(old_b, new_b + b"\0" * (len(old_b) - len(new_b)))
    open(path, "wb").write(d)
    print("  %-60s : patched %d occurrence(s) -> %s" % (path.split("/")[-1], cnt, new))
    return cnt


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit("usage: patch_needed_soname.py <old> <new> <file> [file...]")
    old, new = sys.argv[1], sys.argv[2]
    total = 0
    for f in sys.argv[3:]:
        total += patch(f, old, new)
    print("total patched files ok, occurrences=%d" % total)
