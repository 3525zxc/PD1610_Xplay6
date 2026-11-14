#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 Android boot image v0 头，打印关键字段并与参照镜像逐项比对。

用法：
    python3 boot_info.py <boot.img> [参照 boot.img]

字段布局（AOSP mkbootimg, header v0，小端）：
    0x000 magic        "ANDROID!" (8B)
    0x008 kernel_size  u32
    0x00C kernel_addr  u32
    0x010 ramdisk_size u32
    0x014 ramdisk_addr u32
    0x018 second_size  u32
    0x01C second_addr  u32
    0x020 tags_addr    u32
    0x024 page_size    u32
    0x028 header_version u32（8.0+ 复用该位置；v0 时为 0）
    0x02C os_version   u32
    0x030 name         16B
    0x040 cmdline      512B
    0x240 id           32B (sha1)
    0x260 extra_cmdline 1024B
"""
import hashlib
import os
import struct
import sys


def align(n, page):
    return (n + page - 1) // page * page


def parse(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"ANDROID!":
        raise SystemExit("%s: magic 不是 ANDROID!" % path)
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
     second_size, second_addr, tags_addr, page_size,
     header_version, os_version) = struct.unpack_from("<10I", data, 8)
    name = data[0x30:0x40].split(b"\0")[0].decode("ascii", "replace")
    cmdline = data[0x40:0x240].split(b"\0")[0].decode("ascii", "replace")
    img_id = data[0x240:0x260]
    extra = data[0x260:0x660].split(b"\0")[0].decode("ascii", "replace")

    kernel_off = page_size
    ramdisk_off = kernel_off + align(kernel_size, page_size)
    second_off = ramdisk_off + align(ramdisk_size, page_size)

    kernel = data[kernel_off:kernel_off + kernel_size]
    ramdisk = data[ramdisk_off:ramdisk_off + ramdisk_size]

    return {
        "path": path,
        "total": len(data),
        "page_size": page_size,
        "kernel_size": kernel_size,
        "kernel_addr": kernel_addr,
        "ramdisk_size": ramdisk_size,
        "ramdisk_addr": ramdisk_addr,
        "second_size": second_size,
        "tags_addr": tags_addr,
        "header_version": header_version,
        "os_version": os_version,
        "name": name,
        "cmdline": cmdline,
        "extra_cmdline": extra,
        # boot 头里的 id 是 kernel+ramdisk+second 的 sha1，mkbootimg 会写；
        # 部分厂商镜像该字段留空，因此只作为参考值打印。
        "id_field": img_id.hex(),
        "computed_id": hashlib.sha1(
            kernel + ramdisk + data[second_off:second_off + second_size]
        ).hexdigest(),
        "kernel_sha256": hashlib.sha256(kernel).hexdigest(),
        "ramdisk_sha256": hashlib.sha256(ramdisk).hexdigest(),
    }


def show(info):
    print("文件            : %s (%d B / %.1f MB)" % (info["path"], info["total"], info["total"] / 1048576.0))
    print("page_size       : %d" % info["page_size"])
    print("kernel_size     : %d" % info["kernel_size"])
    print("kernel_addr     : 0x%08X" % info["kernel_addr"])
    print("ramdisk_size    : %d" % info["ramdisk_size"])
    print("ramdisk_addr    : 0x%08X" % info["ramdisk_addr"])
    print("second_size     : %d" % info["second_size"])
    print("tags_addr       : 0x%08X" % info["tags_addr"])
    print("header_version  : %d" % info["header_version"])
    print("name            : %r" % info["name"])
    print("cmdline (%d B)  : %s" % (len(info["cmdline"]), info["cmdline"]))
    print("extra_cmdline   : %r" % info["extra_cmdline"])
    print("id 字段         : %s" % info["id_field"])
    print("id 实算         : %s" % info["computed_id"])
    print("kernel sha256   : %s" % info["kernel_sha256"])
    print("ramdisk sha256  : %s" % info["ramdisk_sha256"])


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    new = parse(sys.argv[1])
    show(new)

    if len(sys.argv) >= 3:
        ref = parse(sys.argv[2])
        print("\n=== 与参照镜像比对 ===")
        show(ref)
        print("\n=== 逐项差异 ===")
        keys = ["page_size", "kernel_size", "kernel_addr", "ramdisk_size",
                "ramdisk_addr", "second_size", "tags_addr", "name"]
        same = True
        for k in keys:
            a, b = new[k], ref[k]
            flag = "OK  " if a == b else "DIFF"
            if a != b:
                same = False
            print("  %-4s %-14s new=%-12s ref=%s" % (flag, k, a, b))
        print("  %-4s %-14s %s" % ("OK  " if new["kernel_sha256"] == ref["kernel_sha256"] else "DIFF",
                                   "kernel    内容", "逐字节一致" if new["kernel_sha256"] == ref["kernel_sha256"] else "不一致"))
        print("  %-4s %-14s %s" % ("OK  " if same else "DIFF", "头部其余字段", "全部一致" if same else "存在差异（见上）"))
        print("\n  cmdline 差异：")
        print("    new: %s" % new["cmdline"])
        print("    ref: %s" % ref["cmdline"])


if __name__ == "__main__":
    main()
