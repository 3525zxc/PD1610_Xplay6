#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解锁生效后的验证镜像：官方 boot + 在 cmdline 末尾追加 androidboot.wbtest=<值>。

为什么用 androidboot. 前缀：
  init 会把 cmdline 里的每个 androidboot.xxx=yyy 转成 ro.boot.xxx=yyy 属性，
  普通 adb shell getprop 即可读取，无需 root，也不受 /proc/cmdline 权限限制。

同时保持:
  - kernel/ramdisk 段不动 -> L 不变 -> 签名块位置不变、DER 内 L 不变
  - 签名块 5376 B 原样保留
  - header id 重算（实际不会变，因为 id 不含 cmdline）

判据:
  启动后 getprop ro.boot.wbtest == 期望值  => 这个 boot 真的在跑，aboot 没走备份/官方镜像
"""
import argparse
import hashlib
import struct
import sys

SRC = 'work/boot_81_official.img'
PART = 100663296


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--out', default='work/boot_81_probe_wbtest.img')
    ap.add_argument('--tag', default='androidboot.wbtest=PD1610A')
    args = ap.parse_args()

    d = bytearray(open(args.src, 'rb').read())
    if d[:8] != b'ANDROID!':
        sys.exit('not a boot image')
    page = struct.unpack_from('<I', d, 0x24)[0]
    ks, rs, ss = (struct.unpack_from('<I', d, o)[0] for o in (8, 0x10, 0x18))
    A = lambda x: (x + page - 1) // page * page
    L = page + A(ks) + A(rs) + A(ss)

    cl = bytes(d[0x40:0x240])
    s = cl.split(b'\x00')[0]
    tag = args.tag.encode()
    if tag in s:
        sys.exit('cmdline 里已存在该 tag')
    s2 = s + b' ' + tag
    if len(s2) > 512:
        sys.exit('cmdline 溢出: %d > 512' % len(s2))
    d[0x40:0x240] = s2 + b'\x00' * (512 - len(s2))
    print('[0] cmdline %d -> %d B (上限 512)' % (len(s), len(s2)))
    print('    追加: %s' % tag.decode())

    k = bytes(d[page:page + ks])
    r = bytes(d[page + A(ks):page + A(ks) + rs])
    sec = bytes(d[page + A(ks) + A(rs):page + A(ks) + A(rs) + ss])
    bid = hashlib.sha1(k + struct.pack('<I', ks) + r + struct.pack('<I', rs)
                       + sec + struct.pack('<I', ss)).digest()
    d[0x240:0x254] = bid
    print('[1] header id: %s' % bid.hex())

    sig = bytes(d[L:])
    assert len(sig) == 5376 and sig[:4] == b'\x30\x82\x04\xfc', '签名块异常'
    assert struct.unpack('>I', sig[0x3F8:0x3FC])[0] == L, 'DER 内 L 与布局不符'
    print('[2] 签名块 5376 B 原样保留，DER 内 L=0x%X 与布局一致' % L)

    out = bytes(d)
    open(args.out, 'wb').write(out)
    print('[3] 写出 %s (%d B)  sha256 %s' % (args.out, len(out), hashlib.sha256(out).hexdigest()[:32]))

    full = args.out.replace('.img', '_full.bin')
    open(full, 'wb').write(out + b'\x00' * (PART - len(out)))
    print('[4] 写出 %s (%d B = %d MB)' % (full, PART, PART >> 20))
    print('    sha256 %s' % hashlib.sha256(open(full, 'rb').read()).hexdigest())


if __name__ == '__main__':
    main()
