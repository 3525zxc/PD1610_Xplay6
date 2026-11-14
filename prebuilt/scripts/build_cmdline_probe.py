#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
判定实验：官方 boot 只改 cmdline 一个字符，签名块一字节不动。

目的：区分「aboot 是否验 RSA」。
  - L 不变（kernel/ramdisk 段未动）
  - 签名块（DER attrs 里的 INTEGER L + OCTET 256 签名）原样保留
  - 只重算 header 的 SHA1 id（AOSP boot v0 规范要求）
  - 唯一变量 = boot[:L] 的内容哈希

若设备能正常启动 => 正常启动路径不校验 RSA，改 boot 只要同步改 DER 里的 L。
若卡 logo 重启     => 验签强制，devinfo 解锁位对 flash 启动路径无效。
"""
import hashlib
import struct
import sys

SRC = 'work/boot_81_official.img'
OUT = 'work/boot_81_probe_cmdline.img'
FULL = 'work/flash_boot_probe_full.bin'
PART = 100663296  # boot 分区 96 MB

OLD = b'user_debug=31'
NEW = b'user_debug=30'


def main():
    d = bytearray(open(SRC, 'rb').read())
    if d[:8] != b'ANDROID!':
        sys.exit('not a boot image')
    page = struct.unpack_from('<I', d, 0x24)[0]
    ks, rs, ss = struct.unpack_from('<I', d, 8)[0], struct.unpack_from('<I', d, 0x10)[0], struct.unpack_from('<I', d, 0x18)[0]
    A = lambda x: (x + page - 1) // page * page
    L = page + A(ks) + A(rs) + A(ss)
    print('[0] page=%d ks=%d rs=%d ss=%d  L=0x%X (%d)  file=%d' % (page, ks, rs, ss, L, L, len(d)))

    cl = bytes(d[0x40:0x240])
    s = cl.split(b'\x00')[0]
    if OLD not in s:
        sys.exit('cmdline pattern not found')
    if len(NEW) != len(OLD):
        sys.exit('length must not change')
    s2 = s.replace(OLD, NEW, 1)
    assert len(s2) == len(s), 'cmdline 长度变化'
    d[0x40:0x40 + len(s2)] = s2
    d[0x40 + len(s2):0x240] = b'\x00' * (0x240 - 0x40 - len(s2))
    print('[1] cmdline 改动: %s -> %s  (len %d 不变)' % (OLD.decode(), NEW.decode(), len(s2)))

    # 重算 header id（AOSP: SHA1(kernel||ksize||ramdisk||rsize||second||ssize)）
    k = bytes(d[page:page + ks])
    r = bytes(d[page + A(ks):page + A(ks) + rs])
    sec = bytes(d[page + A(ks) + A(rs):page + A(ks) + A(rs) + ss])
    bid = hashlib.sha1(k + struct.pack('<I', ks) + r + struct.pack('<I', rs)
                       + sec + struct.pack('<I', ss)).digest()
    d[0x240:0x254] = bid
    print('[2] header id 重算: %s' % bid.hex())

    # 断言签名块未被触碰
    sig = bytes(d[L:])
    print('[3] 签名块 %d B 原样保留，首 8 字节 %s' % (len(sig), sig[:8].hex()))
    assert len(sig) == 5376, '签名块长度异常'
    assert sig[:4] == b'\x30\x82\x04\xfc', 'DER SEQUENCE 头异常'
    assert b'\x02\x04\x03\x80\x10\x00' in sig, 'DER 里 L 字段丢失'

    open(OUT, 'wb').write(bytes(d))
    print('[4] 写出 %s  (%d B)' % (OUT, len(d)))

    full = bytes(d) + b'\x00' * (PART - len(d))
    open(FULL, 'wb').write(full)
    print('[5] 写出 %s  (%d B = %d MB)' % (FULL, len(full), PART >> 20))
    print('[6] sha256 %s' % hashlib.sha256(full).hexdigest())


if __name__ == '__main__':
    main()
