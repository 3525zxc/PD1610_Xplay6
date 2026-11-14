#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 Android boot.img 的 ramdisk 里是否带 PD1610 首启修复标记。

用法: python check_boot.py <boot.img>
"""
import gzip
import io
import struct
import sys


def align(x, p):
    return (x + p - 1) // p * p


def parse(path):
    d = open(path, "rb").read()
    assert d[:8] == b"ANDROID!", "not an Android boot image"
    (ks, ka, rs, ra, ss, sa, tags, ps) = struct.unpack_from("<8I", d, 8)
    ver = struct.unpack_from("<I", d, 36)[0] if len(d) >= 40 else 0
    ko = ps
    ro = ps + align(ks, ps)
    return d[ro:ro + rs], dict(kernel=ks, ramdisk=rs, second=ss, page=ps,
                               version=ver, ramdisk_off=ro, total=len(d))


def main():
    rd, info = parse(sys.argv[1])
    print("boot header:", info)
    try:
        cpio = gzip.decompress(rd)
    except Exception:
        # 某些 boot 用 lz4 / 未压缩，这里只做 gzip 兜底
        cpio = rd
    for marker in (b"pd1610-crypto-fix", b"ro.crypto.state", b"/dev/cpuset/top-app/cpus",
                   b"PD1610-FIX", b"class_start main"):
        print("  %-34s %s" % (marker.decode(), "FOUND" if marker in cpio else "missing"))
    # 找 init.rc 片段
    i = cpio.find(b"trigger pd1610-crypto-fix")
    if i >= 0:
        print("  init.rc context:", cpio[max(0, i - 60):i + 80].decode("ascii", "replace").replace("\n", " | "))


if __name__ == "__main__":
    main()
