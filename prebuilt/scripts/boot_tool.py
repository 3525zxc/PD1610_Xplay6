#!/usr/bin/env python3
"""PD1610 8.1 boot.img tool: unpack / patch-noverify / repack.

Key trick: the DTB-based fstab stores fsmgr_flags as a 12-byte property
"wait,verify\\0". We replace it IN PLACE with "wait\\0" + NUL padding,
keeping the property length field unchanged, so FDT structure, the 122-DTB
chain layout and the boot image size are all preserved.

Usage:
  python boot_tool.py info
  python boot_tool.py unpack
  python boot_tool.py patch-noverify
  python boot_tool.py repack
"""
import hashlib
import json
import os
import struct
import sys

sys.path.insert(0, r'C:\qfilx\exp')
from fdt_tool import FDT, enum_dtbs, be32

BOOT = r'D:\16\PD1610_81\work\boot_81_official.img'
PARTS = r'D:\16\PD1610_81\work\boot_parts'
PATCHED = r'D:\16\PD1610_81\work\boot_81_noverify.img'
TARGET_PATH = '/firmware/android/fstab/system'
TARGET_PROP = 'fsmgr_flags'
NEW_VALUE = b'wait\x00'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def header(d):
    if d[:8] != b'ANDROID!':
        raise ValueError('not an ANDROID! boot image')
    ks, ka, rs, ra, ss, sa, ta, ps = struct.unpack_from('<8I', d, 8)
    hv, osv = struct.unpack_from('<2I', d, 40)
    def al(x):
        return (x + ps - 1) // ps * ps
    L = ps + al(ks) + al(rs) + (al(ss) if ss else 0)
    return dict(kernel_size=ks, kernel_addr=ka, ramdisk_size=rs, ramdisk_addr=ra,
                second_size=ss, second_addr=sa, tags_addr=ta, page_size=ps,
                header_version=hv, os_version=osv,
                kernel_off=ps, ramdisk_off=ps + al(ks),
                second_off=ps + al(ks) + al(rs), signed_length=L, total=len(d))


def find_vivo_dtb(d):
    hits = enum_dtbs(d)
    for i, (off, tot) in enumerate(hits):
        try:
            f = FDT(d[off:off + tot])
            model = (f.root_props().get('model') or b'').split(b'\x00')[0].decode('utf-8', 'ignore')
        except Exception:
            continue
        if 'PD1610' in model:
            return i, off, tot, model, f, len(hits)
    raise RuntimeError('vivo PD1610 DTB not found')


def locate_prop(blob, fdt, path, prop):
    """Return (absolute blob offset of value, length, bytes) for a prop."""
    b = blob
    p, stack = fdt.off_struct, []
    while p + 4 <= len(b):
        tok = be32(b, p)
        p += 4
        if tok == 1:
            e = b.index(b'\x00', p)
            stack.append(b[p:e].decode('utf-8', 'ignore'))
            p = (e + 4) & ~3
        elif tok == 2:
            if stack:
                stack.pop()
        elif tok == 3:
            ln = be32(b, p)
            no = be32(b, p + 4)
            p += 8
            name = fdt.str_at(no)
            here = '/' + '/'.join(x for x in stack if x)
            if here == path and name == prop:
                return p, ln, b[p:p + ln]
            p = (p + ln + 3) & ~3
        elif tok == 9:
            break
    return None


def cmd_info():
    d = open(BOOT, 'rb').read()
    h = header(d)
    i, off, tot, model, f, n = find_vivo_dtb(d)
    print(json.dumps({'header': h, 'dtb_count': n, 'vivo_dtb_index': i,
                      'vivo_dtb_off': hex(off), 'vivo_dtb_size': tot,
                      'model': model, 'sha256': sha(d)}, indent=2))
    vo, ln, val = locate_prop(d[off:off + tot], f, TARGET_PATH, TARGET_PROP)
    print('fsmgr_flags @ boot+0x%X  len=%d  value=%r' % (off + vo, ln, val))


def cmd_unpack():
    os.makedirs(PARTS, exist_ok=True)
    d = open(BOOT, 'rb').read()
    h = header(d)
    with open(os.path.join(PARTS, 'header.json'), 'w') as f:
        json.dump(h, f, indent=2)
    open(os.path.join(PARTS, 'kernel.bin'), 'wb').write(d[h['kernel_off']:h['kernel_off'] + h['kernel_size']])
    open(os.path.join(PARTS, 'ramdisk.gz'), 'wb').write(d[h['ramdisk_off']:h['ramdisk_off'] + h['ramdisk_size']])
    i, off, tot, model, fdt, n = find_vivo_dtb(d)
    open(os.path.join(PARTS, 'vivo_dtb_%d.dtb' % i), 'wb').write(d[off:off + tot])
    open(os.path.join(PARTS, 'signature_area.bin'), 'wb').write(d[h['signed_length']:])
    open(os.path.join(PARTS, 'boot_header.bin'), 'wb').write(d[:h['page_size']])
    print('unpacked -> %s' % PARTS)
    print('  kernel %d B, ramdisk %d B, vivo DTB idx %d (%d B), signature area %d B' %
          (h['kernel_size'], h['ramdisk_size'], i, tot, len(d) - h['signed_length']))


def cmd_patch():
    d = bytearray(open(BOOT, 'rb').read())
    h = header(bytes(d))
    i, off, tot, model, fdt, n = find_vivo_dtb(bytes(d))
    vo, ln, val = locate_prop(bytes(d[off:off + tot]), fdt, TARGET_PATH, TARGET_PROP)
    print('before: @boot+0x%X len=%d value=%r' % (off + vo, ln, val))
    if b'verify' not in val:
        raise RuntimeError('expected "wait,verify" but got %r - already patched?' % val)
    new = NEW_VALUE + b'\x00' * (ln - len(NEW_VALUE))
    assert len(new) == ln
    abs_off = off + vo
    d[abs_off:abs_off + ln] = new
    open(PATCHED, 'wb').write(d)

    out = bytes(d)
    diff = [k for k, (a, b) in enumerate(zip(open(BOOT, 'rb').read(), out)) if a != b]
    print('after : @boot+0x%X len=%d value=%r' % (abs_off, ln, new))
    print('size  : %d -> %d  (same=%s)' % (len(out), os.path.getsize(BOOT), len(out) == os.path.getsize(BOOT)))
    print('diff bytes: %d, offsets %s' % (len(diff), [hex(x) for x in diff[:16]]))
    print('sha256: %s -> %s' % (sha(open(BOOT, 'rb').read())[:16], sha(out)[:16]))

    # re-parse the DTB to prove structure is intact
    f2 = FDT(out[off:off + tot])
    vo2, ln2, val2 = locate_prop(out[off:off + tot], f2, TARGET_PATH, TARGET_PROP)
    nodes = sum(1 for dep, kind, nm, v in f2.walk() if kind == 'node')
    print('reparse: nodes=%d  %s=%r  (len=%d)' % (nodes, TARGET_PROP, val2, ln2))
    assert val2.split(b'\x00')[0] == b'wait'
    assert len(diff) <= 12
    print('OK -> %s' % PATCHED)


def cmd_repack():
    h = json.load(open(os.path.join(PARTS, 'header.json')))
    d = bytearray(open(BOOT, 'rb').read())   # start from original to keep every untouched byte
    kern = open(os.path.join(PARTS, 'kernel.bin'), 'rb').read()
    rd = open(os.path.join(PARTS, 'ramdisk.gz'), 'rb').read()
    assert len(kern) == h['kernel_size'] and len(rd) == h['ramdisk_size']
    d[h['kernel_off']:h['kernel_off'] + len(kern)] = kern
    d[h['ramdisk_off']:h['ramdisk_off'] + len(rd)] = rd
    out = r'D:\16\PD1610_81\work\boot_repacked.img'
    open(out, 'wb').write(d)
    print('repacked %d B -> %s  sha=%s' % (len(d), out, sha(bytes(d))[:16]))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'info'
    {'info': cmd_info, 'unpack': cmd_unpack,
     'patch-noverify': cmd_patch, 'repack': cmd_repack}[cmd]()
