#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把官方 boot 的签名块“原样搬回”到重建后的 boot 上，并同步修正 DER 里的 L 字段。

背景（8.19.16 aboot 实测 + 静态分析）:
  - 正常启动路径会解析 boot 尾部的签名块：SEQUENCE{INT 1, 证书,
    sha256WithRSA, SEQUENCE{IA5String "/boot", INTEGER L}, OCTET 256}
  - 签名块位置 = page + ALIGN(kernel) + ALIGN(ramdisk)
  - DER 里的 INTEGER L 必须等于该位置，aboot 用它确定签名块起点/哈希范围
  - 之前 D 类镜像把整个 DER 抹掉 → aboot 解析不出 L → 卡 logo 重启
  - 内容改动（cmdline/ramdisk）只让 RSA 摘要失配，不阻断启动

因此改 boot 的正确姿势：只替换内容，签名块整块保留，L 字段同步改写。

用法:
  python attach_sigblock.py --official work/boot_81_official.img \
      --body work/boot_81_mod_rootadb.img --out work/boot_81_mod_lfix.img
"""
import argparse
import hashlib
import struct
import sys

L_OFF_IN_SIG = 0x3F8   # 签名块内 INTEGER L 的数值偏移（big-endian 4 字节）
# 结构: 0x3E0 SEQUENCE{OID sha256WithRSA} / 0x3ED SEQUENCE{IA5String "/boot", INTEGER L}
#       / 0x3FC OCTET STRING(256) 签名，DER 总长 0x4FC+4=0x500
SIG_LEN = 5376


def layout(path):
    if isinstance(path, (bytes, bytearray)):
        d = bytes(path)
    else:
        d = open(path, 'rb').read()
    if d[:8] != b'ANDROID!':
        sys.exit('%s: not a boot image' % path)
    page = struct.unpack_from('<I', d, 0x24)[0]
    ks, rs, ss = (struct.unpack_from('<I', d, o)[0] for o in (8, 0x10, 0x18))
    A = lambda x: (x + page - 1) // page * page
    L = page + A(ks) + A(rs) + A(ss)
    return d, page, ks, rs, ss, L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--official', required=True, help='官方 boot（提供签名块与 L 基线）')
    ap.add_argument('--body', required=True, help='重建后的 boot（无签名块）')
    ap.add_argument('--out', required=True)
    ap.add_argument('--part', type=int, default=100663296, help='分区大小，用于补齐')
    args = ap.parse_args()

    od, page, oks, ors, oss, oL = layout(args.official)
    osig = od[oL:]
    if len(osig) < SIG_LEN:
        sys.exit('官方签名块长度异常: %d' % len(osig))
    osig = osig[:SIG_LEN]
    print('[0] 官方: page=%d ks=%d rs=%d L=0x%X  签名块 %d B' % (page, oks, ors, oL, len(osig)))
    if osig[:4] != b'\x30\x82\x04\xfc':
        sys.exit('官方签名块 DER 头异常: %s' % osig[:4].hex())
    old_L = struct.unpack('>I', osig[L_OFF_IN_SIG:L_OFF_IN_SIG + 4])[0]
    print('[1] DER 内 L = 0x%X (%d)  与布局 L %s' % (old_L, old_L, '一致' if old_L == oL else '不一致!'))
    if old_L != oL:
        sys.exit('官方基线自检失败')

    bd, bpage, bks, brs, bss, bL = layout(args.body)
    print('[2] 新镜像: page=%d ks=%d rs=%d L=0x%X  body len=%d' % (bpage, bks, brs, bL, len(bd)))
    if bpage != page or bks != oks:
        sys.exit('page/kernel 与官方不一致，拒绝继续')
    if len(bd) != bL:
        sys.exit('新镜像尾部有多余数据（应为纯 body）')

    # 改写 DER 里的 L（长度不变：仍为 02 04 xx xx xx xx）
    if bL >= 0x80000000:
        sys.exit('新 L 超出 4 字节正整数范围')
    if bL < 0x1000000:
        print('[!] 警告: 新 L=0x%X 最高字节为 0，DER 严格编码可能要求去掉前导 0' % bL)
    sig = bytearray(osig)
    sig[L_OFF_IN_SIG:L_OFF_IN_SIG + 4] = struct.pack('>I', bL)
    assert sig[:4] == b'\x30\x82\x04\xfc', '改 L 后 DER 头变了'
    print('[3] DER 内 L: 0x%X -> 0x%X（DER 总长不变 %d）' % (old_L, bL, 0x4fc))

    out = bd + bytes(sig)
    print('[4] 组装: body %d + sig %d = %d B' % (len(bd), len(sig), len(out)))

    # 自检
    chk, cpage, cks, crs, css, cL = layout(out)
    assert cL == bL, 'L 回读不一致'
    got = struct.unpack('>I', chk[cL + L_OFF_IN_SIG:cL + L_OFF_IN_SIG + 4])[0]
    assert got == bL, 'DER 内 L 回读不一致'
    assert chk[:page] == bd[:page], 'header 被改动'
    print('[5] 自检通过: 布局 L=0x%X，DER L=0x%X，签名块紧随其后' % (cL, got))

    open(args.out, 'wb').write(out)
    print('[6] 写出 %s (%d B)' % (args.out, len(out)))

    if args.part and len(out) <= args.part:
        full = args.out.replace('.img', '_full.bin')
        open(full, 'wb').write(out + b'\x00' * (args.part - len(out)))
        print('[7] 写出 %s (%d B = %d MB)' % (full, args.part, args.part >> 20))
        print('[8] sha256 %s' % hashlib.sha256(open(full, 'rb').read()).hexdigest())


if __name__ == '__main__':
    main()
