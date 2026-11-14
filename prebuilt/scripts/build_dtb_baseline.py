#!/usr/bin/env python3
"""Build a self-contained device-tree baseline for PD1610 from the REAL 8.1
boot partition readback (D:\\16\\PD1610_81\\backup\\81_boot_LUN4.bin).

Output: D:\\16\\PD1610_81\\evidence\\dtb_81_baseline\\
"""
import collections
import hashlib
import os
import sys

sys.path.insert(0, r'C:\qfilx\exp')
from fdt_tool import FDT, enum_dtbs, fmt_val

BOOT = r'D:\16\PD1610_81\backup\81_boot_LUN4.bin'
IMG = 58729728
REF_VIVO = r'C:\qfilx\compare\dtb\pd1610_81916_79.dtb'
REF_776 = r'C:\qfilx\compare\dtb\pd1610_776.dtb'
OUT = r'D:\16\PD1610_81\evidence\dtb_81_baseline'
os.makedirs(OUT, exist_ok=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def node_paths(fdt):
    stack, out = [], []
    for depth, kind, name, val in fdt.walk():
        if kind == 'node':
            stack.append(name)
            p = '/' + '/'.join(x for x in stack if x)
            out.append(p if p != '/' else '/')
        elif kind == 'end':
            if stack:
                stack.pop()
    return out


def compat_values(fdt):
    c = collections.Counter()
    for depth, kind, name, val in fdt.walk():
        if kind == 'prop' and name == 'compatible':
            for s in val.split(b'\x00'):
                if s:
                    c[s.decode('utf-8', 'ignore')] += 1
    return c


def fmt_prop(name, val):
    """fmt_val, but keep NUL-separated string lists as quoted strings (dtc-safe)."""
    parts = [p.decode('ascii', 'ignore') for p in val.split(b'\x00') if p]
    if len(parts) > 1 and all(parts) and all(32 <= ord(c) < 127 for p in parts for c in p):
        return ', '.join('"%s"' % p for p in parts)
    return fmt_val(val)


def to_dts_full(fdt):
    """Like fdt_tool.to_dts but KEEPS phandle/linux,phandle (needed to compile)."""
    lines = ['/dts-v1/;', '']
    for depth, kind, name, val in fdt.walk():
        if kind == 'node':
            lines.append('\t' * depth + ('/ {' if depth == 0 else (name or '?') + ' {'))
        elif kind == 'end':
            lines.append('\t' * depth + '};' if depth >= 0 else '};')
        elif kind == 'prop':
            lines.append('\t' * (depth + 1) + name + ' = ' + fmt_prop(name, val) + ';')
    return '\n'.join(lines) + '\n'


def subtree_props(fdt, prefix):
    """Flat dump of every property of nodes whose path starts with prefix."""
    stack, lines = [], []
    for depth, kind, name, val in fdt.walk():
        if kind == 'node':
            stack.append(name)
            path = '/' + '/'.join(x for x in stack if x)
            if path.startswith(prefix):
                lines.append('')
                lines.append('%s {' % path)
        elif kind == 'end':
            if stack:
                stack.pop()
        elif kind == 'prop':
            path = '/' + '/'.join(x for x in stack if x)
            if path.startswith(prefix):
                lines.append('    %s = %s;' % (name, fmt_prop(name, val)))
    return lines


def write(fn, text):
    with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
        f.write(text)


log = []
def emit(s=''):
    log.append(s)
    print(s)


buf = open(BOOT, 'rb').read(IMG)
emit('source      : %s (first %d bytes = official boot.img)' % (BOOT, IMG))
emit('boot sha256 : %s' % sha(buf))
hits = enum_dtbs(buf)
emit('DTB count   : %d' % len(hits))

vivo = []
for i, (off, tot) in enumerate(hits):
    try:
        f = FDT(buf[off:off + tot])
        rp = f.root_props()
    except Exception:
        continue
    model = (rp.get('model') or b'').split(b'\x00')[0].decode('utf-8', 'ignore')
    if 'PD1610' in model:
        vivo.append((i, off, tot, model, f, rp))

emit('vivo PD1610 DTBs: %d' % len(vivo))
for i, off, tot, model, f, rp in vivo:
    emit('  idx=%d off=0x%08X size=%d model=%s' % (i, off, tot, model))

if not vivo:
    raise SystemExit('[X] no vivo PD1610 DTB found')

idx, off, tot, model, fdt, rp = vivo[0]
blob = buf[off:off + tot]
ref = open(REF_VIVO, 'rb').read() if os.path.exists(REF_VIVO) else b''
emit('')
emit('vivo DTB sha256      : %s' % sha(blob))
emit('historical extract   : %s  %d B  %s' % (sha(ref)[:32], len(ref), 'MATCH' if ref == blob else 'DIFFER'))
open(os.path.join(OUT, 'pd1610_81916_vivo.dtb'), 'wb').write(blob)

# --- root identity (what mainline porting needs) ---
ids = []
ids.append('model        = %s' % model)
for key in ('compatible', 'qcom,msm-id', 'qcom,board-id', 'qcom,pmic-id',
            'qcom,msm-name', 'qcom,board-name', 'interrupt-parent', '#address-cells',
            '#size-cells'):
    if key in rp:
        ids.append('%-13s = %s' % (key, fmt_prop(key, rp[key])))
write('board_ids.txt', '\n'.join(ids) + '\n')
emit('')
emit('--- root identity ---')
for l in ids:
    emit('  ' + l)

paths = node_paths(fdt)
props = sum(1 for d, k, n, v in fdt.walk() if k == 'prop')
write('node_inventory.txt', '\n'.join(paths) + '\n')
emit('')
emit('nodes=%d  props=%d  dts_lines=%d' % (len(paths), props, len(to_dts_full(fdt).splitlines())))

comp = compat_values(fdt)
priv = {k: v for k, v in comp.items() if 'vivo' in k.lower() or 'bbk' in k.lower()}
write('compatible_inventory.txt',
      '# %d distinct compatible strings, %d occurrences\n' % (len(comp), sum(comp.values())) +
      '# vivo-private: %s\n' % (', '.join(sorted(priv)) or 'none') +
      '\n'.join('%4d  %s' % (v, k) for k, v in sorted(comp.items())) + '\n')
emit('compatible distinct=%d occurrences=%d vivo-private=%s' %
     (len(comp), sum(comp.values()), sorted(priv)))

dts = to_dts_full(fdt)
write('pd1610_81916_vivo.dts', dts)
emit('DTS written  : %d lines, phandle preserved, string-lists readable' % len(dts.splitlines()))

fstab = subtree_props(fdt, '/firmware/android/fstab')
write('fstab_nodes.txt',
      '# /firmware/android/fstab subtree from the REAL 8.1 DTB (vivo idx 79)\n' +
      '\n'.join(fstab) + '\n')
emit('fstab nodes  : %d property lines written' % len(fstab))

# --- diff vs 7.7.6 PD1610 DTB ---
if os.path.exists(REF_776):
    b776 = open(REF_776, 'rb').read()
    p776 = set(node_paths(FDT(b776)))
    p819 = set(paths)
    add = sorted(p819 - p776)
    rem = sorted(p776 - p819)
    write('diff_776_to_81916.txt',
          '# node paths: 7.7.6=%d  8.19.16=%d  +%d / -%d\n' %
          (len(p776), len(p819), len(add), len(rem)) +
          '\n=== ADDED in 8.19.16 ===\n' + '\n'.join(add) +
          '\n\n=== REMOVED in 8.19.16 ===\n' + '\n'.join(rem) + '\n')
    emit('')
    emit('diff 7.7.6 -> 8.19.16 : +%d / -%d nodes' % (len(add), len(rem)))
    emit('  added sample: %s' % (', '.join(add[:6]) or 'none'))
    emit('  removed sample: %s' % (', '.join(rem[:6]) or 'none'))
else:
    emit('[!] 7.7.6 reference missing, diff skipped')

write('BASELINE.txt', '\n'.join(log) + '\n\n'
      'USAGE\n'
      '  pd1610_81916_vivo.dtb  - exact DTB selected by aboot for this board\n'
      '  pd1610_81916_vivo.dts  - decompiled source (phandle preserved)\n'
      '  board_ids.txt          - qcom,msm-id / board-id / pmic-id / compatible\n'
      '  node_inventory.txt     - all node paths\n'
      '  compatible_inventory.txt - all compatible strings + vivo-private ones\n'
      '  fstab_nodes.txt        - fstab lives IN the DTB: system=wait,verify / vendor=disabled\n'
      '                           -> for a custom ROM, edit the DTB (drop "verify") and repack boot\n'
      '  diff_776_to_81916.txt  - node-level delta vs 7.7.6\n'
      '  reproduce: python D:\\16\\PD1610_81\\scripts\\build_dtb_baseline.py\n')
print('\n[written] ' + OUT)
