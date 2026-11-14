#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 newc 格式（魔数 070701）cpio，列出条目 / 软链目标 / 可选解包。
不依赖系统 cpio 包。

用法：
    python3 cpio_list.py <archive.cpio>            # 列表（含软链目标）
    python3 cpio_list.py <archive.cpio> --extract DIR
    python3 cpio_list.py <archive.cpio> --grep "^(init|fstab)"
"""
import os
import re
import sys

HEADER = 110  # newc 头固定长度


def entries(buf):
    off = 0
    n = len(buf)
    while off + HEADER <= n:
        magic = buf[off:off + 6]
        if magic not in (b"070701", b"070702"):
            break
        f = [int(buf[off + 6 + i * 8: off + 6 + (i + 1) * 8], 16) for i in range(13)]
        # 0 ino,1 mode,2 uid,3 gid,4 nlink,5 mtime,6 filesize,7 devmajor,
        # 8 devminor,9 rdevmajor,10 rdevminor,11 namesize,12 check
        mode, filesize, namesize = f[1], f[6], f[11]
        name = buf[off + HEADER: off + HEADER + namesize - 1].decode("utf-8", "replace")
        data_off = off + HEADER + namesize
        data = buf[data_off:data_off + filesize]
        if name == "TRAILER!!!":
            break
        yield name, mode, filesize, data
        off = data_off + filesize
        off = (off + 3) & ~3


def fmt_mode(mode):
    t = mode & 0o170000
    kind = {0o100000: "-", 0o120000: "l", 0o040000: "d", 0o020000: "c",
            0o060000: "b", 0o010000: "p", 0o140000: "s"}.get(t, "?")
    perm = "".join(c if mode & (1 << i) else "-" for i, c in
                   zip(range(8, -1, -1), "rwxrwxrwx"))
    return kind + perm


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    buf = open(sys.argv[1], "rb").read()
    args = sys.argv[2:]

    if "--extract" in args:
        out = args[args.index("--extract") + 1]
        os.makedirs(out, exist_ok=True)
        cnt = 0
        for name, mode, size, data in entries(buf):
            dst = os.path.join(out, name)
            t = mode & 0o170000
            if t == 0o040000:
                os.makedirs(dst, exist_ok=True)
            elif t == 0o120000:
                os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
                if os.path.lexists(dst):
                    os.unlink(dst)
                os.symlink(data.decode("utf-8", "replace"), dst)
            elif t == 0o100000:
                os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(data)
                os.chmod(dst, mode & 0o7777)
            cnt += 1
        print("已解包 %d 个条目到 %s" % (cnt, out))
        return

    pat = None
    if "--grep" in args:
        pat = re.compile(args[args.index("--grep") + 1])

    total = 0
    for name, mode, size, data in entries(buf):
        total += 1
        if pat and not pat.search(name):
            continue
        if mode & 0o170000 == 0o120000:
            print("%s %8s %s -> %s" % (fmt_mode(mode), "-", name, data.decode("utf-8", "replace")))
        else:
            print("%s %8d %s" % (fmt_mode(mode), size, name))
    if not pat:
        print("--- 共 %d 条 ---" % total)


if __name__ == "__main__":
    main()
