#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建 PD1610 8.19.16 boot.img：保留官方内核/头部/cmdline，仅替换 ramdisk 内容。

ramdisk 修改项（可通过 --props 覆盖）：
  默认把 default.prop 里的 ro.secure / ro.adb.secure 置 0、ro.debuggable 置 1，
  并追加 ro.wb.marker=<值> 作为"我们改的 ramdisk 真的跑了"的判据。

用法:
  python build_boot_mod.py --src boot_81_official.img --out boot_81_mod.img \
      --marker PD1610WB1 [--fstab-encryptable]
"""
import argparse
import gzip
import hashlib
import io
import os
import struct
import sys

PAGE = 4096


def align(x, a=PAGE):
    return (x + a - 1) // a * a


def parse_boot(path):
    d = open(path, 'rb').read()
    if d[:8] != b'ANDROID!':
        raise SystemExit('not an android boot image: %r' % d[:8])
    page = struct.unpack_from('<I', d, 0x24)[0]
    ks, rs, ss = [struct.unpack_from('<I', d, o)[0] for o in (8, 0x10, 0x18)]
    k_off = page
    r_off = page + align(ks, page)
    s_off = r_off + align(rs, page)
    return {
        'raw': d, 'page': page, 'ks': ks, 'rs': rs, 'ss': ss,
        'kernel': d[k_off:k_off + ks],
        'ramdisk': d[r_off:r_off + rs],
        'second': d[s_off:s_off + ss],
        'header': bytearray(d[:page]),
    }


def cpio_parse(b):
    out = []
    p = 0
    while p + 110 <= len(b) and b[p:p + 6] in (b'070701', b'070702'):
        f = [int(b[p + 6 + i * 8: p + 6 + (i + 1) * 8], 16) for i in range(13)]
        ns, fs = f[11], f[6]
        name = b[p + 110: p + 110 + ns - 1].decode('utf-8', 'replace')
        ds = (p + 110 + ns + 3) & ~3
        out.append({'fields': f, 'name': name, 'data': b[ds:ds + fs], 'off': p})
        p = (ds + fs + 3) & ~3
        if name == 'TRAILER!!!':
            break
    return out


def cpio_build(ents):
    out = io.BytesIO()
    for e in ents:
        f = list(e['fields'])
        f[6] = len(e['data'])                    # filesize
        name = e['name'].encode('utf-8') + b'\x00'
        f[11] = len(name)                        # namesize
        hdr = b'070701' + b''.join(b'%08X' % (x & 0xFFFFFFFF) for x in f)
        assert len(hdr) == 110, len(hdr)
        out.write(hdr)
        out.write(name)
        pad = (-(110 + len(name))) % 4
        out.write(b'\x00' * pad)
        out.write(e['data'])
        out.write(b'\x00' * ((-len(e['data'])) % 4))
    # 对齐到 512（cpio 结尾惯例，非必须）
    tail = (-out.tell()) % 512
    out.write(b'\x00' * tail)
    return out.getvalue()


def patch_default_prop(text, marker, root_adb):
    lines = text.split('\n')
    out = []
    seen = set()
    for ln in lines:
        s = ln.strip()
        if s.startswith('ro.secure=') and root_adb:
            out.append('ro.secure=0'); seen.add('secure'); continue
        if s.startswith('ro.adb.secure=') and root_adb:
            out.append('ro.adb.secure=0'); seen.add('adb'); continue
        if s.startswith('ro.debuggable=') and root_adb:
            out.append('ro.debuggable=1'); seen.add('dbg'); continue
        out.append(ln)
    if root_adb:
        if 'secure' not in seen:
            out.append('ro.secure=0')
        if 'adb' not in seen:
            out.append('ro.adb.secure=0')
        if 'dbg' not in seen:
            out.append('ro.debuggable=1')
    txt = '\n'.join(out)
    if not txt.endswith('\n'):
        txt += '\n'
    txt += 'ro.wb.marker=%s\n' % marker
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--marker', default='PD1610WB1')
    ap.add_argument('--no-root-adb', action='store_true')
    args = ap.parse_args()

    bi = parse_boot(args.src)
    rd = bi['ramdisk']
    if rd[:2] != b'\x1f\x8b':
        raise SystemExit('ramdisk is not gzip (magic %r)' % rd[:2])
    raw = gzip.decompress(rd)
    print('[1] 官方 ramdisk: 压缩 %d -> 解压 %d' % (len(rd), len(raw)))

    ents = cpio_parse(raw)
    print('[2] cpio 条目 %d，最后一条 %r' % (len(ents), ents[-1]['name']))

    target = None
    for e in ents:
        if e['name'] == 'default.prop':
            target = e
            break
    if target is None:
        raise SystemExit('default.prop 不在 ramdisk 里')

    old = target['data'].decode('utf-8', 'replace')
    new = patch_default_prop(old, args.marker, not args.no_root_adb)
    target['data'] = new.encode('utf-8')
    print('[3] default.prop: %d -> %d 字节' % (len(old), len(new)))
    for ln in new.split('\n'):
        if any(k in ln for k in ('ro.secure', 'ro.adb.secure', 'ro.debuggable', 'ro.wb.marker')):
            print('      %s' % ln)

    raw2 = cpio_build(ents)
    gz = gzip.compress(raw2, 9, mtime=0)
    print('[4] 新 ramdisk: 解压 %d -> 压缩 %d' % (len(raw2), len(gz)))

    # 自检：重新解析新 cpio
    ents2 = cpio_parse(raw2)
    assert len(ents2) == len(ents), 'cpio 条目数变化'
    assert [e['name'] for e in ents2] == [e['name'] for e in ents], 'cpio 条目名变化'
    dp = [e for e in ents2 if e['name'] == 'default.prop'][0]['data'].decode('utf-8')
    assert 'ro.wb.marker=%s' % args.marker in dp
    print('[5] 自检通过：条目与顺序一致，marker 已写入')

    # 组新 boot.img
    hdr = bytearray(bi['header'])
    k, r = bi['kernel'], gz
    struct.pack_into('<I', hdr, 8, len(k))
    struct.pack_into('<I', hdr, 0x10, len(r))
    struct.pack_into('<I', hdr, 0x18, 0)
    bid = hashlib.sha1(k + struct.pack('<I', len(k)) + r + struct.pack('<I', len(r))
                       + struct.pack('<I', 0)).digest()
    hdr[0x240:0x240 + 20] = bid

    body = bytes(hdr).ljust(PAGE, b'\x00') + k + b'\x00' * (align(len(k)) - len(k)) \
        + r + b'\x00' * (align(len(r)) - len(r))
    open(args.out, 'wb').write(body)
    print('[6] 写出 %s  (%d 字节)' % (args.out, len(body)))

    # 复核
    chk = parse_boot(args.out)
    assert chk['kernel'] == bi['kernel'], '内核被改动'
    assert chk['rs'] == len(r), 'ramdisk_size 字段错误'
    assert gzip.decompress(chk['ramdisk']) == raw2, 'ramdisk 回读不一致'
    assert bytes(chk['header'][0x40:0x240]) == bytes(bi['header'][0x40:0x240]), 'cmdline 被改动'
    print('[7] 复核通过：内核逐字节相同、cmdline 相同、ramdisk 可解压')
    print('    cmdline: %s' % bytes(chk['header'][0x40:0x240]).split(b'\x00')[0].decode('ascii', 'replace'))
    print('    sha256 : %s' % hashlib.sha256(body).hexdigest())


if __name__ == '__main__':
    main()
