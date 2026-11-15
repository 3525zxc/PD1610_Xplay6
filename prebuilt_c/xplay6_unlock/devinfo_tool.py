# -*- coding: utf-8 -*-
"""
vivo Xplay6 (PD1610 / MSM8996) devinfo 解锁标志位工具

用途:
  9008 模式下 dump 出 devinfo 分区 -> 本脚本查看/改 is_unlocked 标志 -> 写回 -> fastboot 解锁

用法:
  python devinfo_tool.py show   devinfo.bin
  python devinfo_tool.py patch  devinfo.bin [--offset 0x1F4] [--out devinfo_patched.bin]
  python devinfo_tool.py verify devinfo.bin

说明:
  - 只改 is_unlocked 一个字节, 不碰 aboot/XBL, 不动 GPT。
  - magic 不对 / 分区太小 / 目标字节非 0 时拒绝改, 避免写坏。
  - 原始 dump 永远保留, 改坏了用 9008 整包线刷即可回滚。
"""
import argparse
import os
import sys

MAGIC = b"ANDROID-BOOT!"
DEFAULT_OFFSET = 0x1F4
SCAN_START, SCAN_END = 0x1E0, 0x220


def load(path):
    if not os.path.isfile(path):
        sys.exit("[x] 文件不存在: %s" % path)
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < SCAN_END:
        sys.exit("[x] 文件只有 %d 字节, 不像 devinfo 分区 dump" % len(data))
    return data


def hexdump(data, start, end, base_off=0):
    for i in range(start, end, 16):
        chunk = data[i:i + 16]
        hexs = " ".join("%02X" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        mark = ""
        if base_off and start <= base_off < end and base_off >= i and base_off < i + 16:
            mark = "  <== 0x%03X" % base_off
        print("  %04X  %-47s  %s%s" % (i, hexs, asc, mark))


def check_magic(data):
    ok = data[:len(MAGIC)] == MAGIC
    got = data[:len(MAGIC)]
    print("  magic : %-24r %s" % (got, "[OK]" if ok else "[不匹配]"))
    return ok


def cmd_show(args):
    data = load(args.path)
    print("[*] %s  (%d 字节)" % (args.path, len(data)))
    ok = check_magic(data)
    print("\n[>] 0x%03X~0x%03X 区域:" % (SCAN_START, SCAN_END))
    hexdump(data, SCAN_START, SCAN_END, args.offset)
    b = data[args.offset]
    print("\n  0x%03X (is_unlocked) = 0x%02X  -> %s" %
          (args.offset, b, "已解锁" if b else "锁定"))
    if args.offset + 1 < len(data):
        b2 = data[args.offset + 1]
        print("  0x%03X (unlock_critical) = 0x%02X" % (args.offset + 1, b2))
    if not ok:
        print("\n[!] magic 不对, 这个 dump 很可能不是 devinfo 分区, 别往下改。")
        return 2
    return 0


def cmd_patch(args):
    data = bytearray(load(args.path))
    if not check_magic(data):
        sys.exit("[x] magic 不匹配, 拒绝修改。请先确认识别到的是 devinfo 分区。")
    off = args.offset
    cur = data[off]
    print("\n[*] 目标偏移 0x%03X: 0x%02X -> 0x%02X" % (off, cur, args.value))
    if cur == args.value:
        print("[=] 已经是目标值, 无需改动。")
        return 0
    if cur != 0:
        sys.exit("[x] 原值非 0x00 (0x%02X), 偏移可能不对。先跑 show 核对区域, 确认后再用 --value 强制。" % cur)
    if args.value not in (0, 1):
        sys.exit("[x] --value 只接受 0 或 1")
    data[off] = args.value

    out = args.out or (os.path.splitext(args.path)[0] + "_patched.bin")
    with open(out, "wb") as f:
        f.write(data)
    print("[+] 已写出: %s" % out)

    with open(args.path, "rb") as f:
        orig = f.read()
    diffs = [i for i in range(len(orig)) if orig[i] != data[i]]
    print("[*] 差异字节: %s" % (", ".join("0x%03X" % i for i in diffs) or "无"))
    if len(diffs) != 1:
        sys.exit("[x] 差异不止 1 字节, 中止 (不要刷这个文件)")

    print("\n下一步:")
    print("  edl w devinfo \"%s\"" % out)
    print("  重启后: fastboot flashing unlock")
    print("  回滚:   9008 整包线刷官方固件即可把 devinfo 写回原样")
    return 0


def cmd_verify(args):
    data = load(args.path)
    print("[*] %s  (%d 字节)" % (args.path, len(data)))
    ok = check_magic(data)
    b = data[args.offset]
    print("  is_unlocked (0x%03X) = 0x%02X  -> %s" %
          (args.offset, b, "有解锁标志" if b else "仍是锁定状态"))
    if not ok:
        print("[!] magic 异常, 结论不可信")
        return 2
    return 0


def main():
    p = argparse.ArgumentParser(description="Xplay6 devinfo is_unlocked 工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, fn, helptext in (
        ("show", cmd_show, "查看 devinfo 解锁标志与区域内容"),
        ("patch", cmd_patch, "把 is_unlocked 改成 1, 输出 _patched.bin"),
        ("verify", cmd_verify, "校验某个 dump 的解锁状态"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("path")
        sp.add_argument("--offset", type=lambda x: int(x, 0), default=DEFAULT_OFFSET,
                        help="is_unlocked 偏移, 默认 0x1F4")
        if name == "patch":
            sp.add_argument("--value", type=lambda x: int(x, 0), default=1)
            sp.add_argument("--out", default=None)
        sp.set_defaults(func=fn)

    args = p.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
