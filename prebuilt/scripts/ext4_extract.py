#!/usr/bin/env python3
"""Minimal read-only ext4 extractor for the PD1610 8.1 system image.

No external tools / libs. Handles extents (depth 0..n), fast symlinks and
linear directories. Output: D:\\16\\PD1610_81\\evidence\\system_81_extract\\
"""
import hashlib
import os
import shutil
import struct

IMG = r'D:\16\PD1610_81\backup\81_system_LUN4.bin'
OUT = r'D:\16\PD1610_81\evidence\system_81_extract'
KCFG = r'C:\qfilx\compare\kcfg\pd1610_81916_config.txt'
KDIFF = r'C:\qfilx\compare\kcfg\diff_pd1610_vs_tb8703.txt'
os.makedirs(OUT, exist_ok=True)

f = open(IMG, 'rb')
f.seek(0x400)
sb = f.read(1024)
BS = 1024 << struct.unpack_from('<I', sb, 0x18)[0]
FIRST = struct.unpack_from('<I', sb, 0x14)[0]
IPG = struct.unpack_from('<I', sb, 0x28)[0]
ISZ = struct.unpack_from('<H', sb, 0x58)[0]
GDSZ = struct.unpack_from('<H', sb, 0xFE)[0] or 32
EXTENT_FLAG = 0x80000

log = []
def emit(s=''):
    log.append(s)
    print(s)


def read_at(off, n):
    f.seek(off)
    return f.read(n)


def read_block(b):
    return read_at(b * BS, BS)


def group_desc(g):
    off = (FIRST + 1) * BS + g * GDSZ
    d = read_at(off, GDSZ)
    return struct.unpack_from('<I', d, 0x8)[0]      # bg_inode_table_lo


def inode(n):
    g, idx = divmod(n - 1, IPG)
    itab = group_desc(g)
    return read_at(itab * BS + idx * ISZ, ISZ)


def extents(raw):
    flags = struct.unpack_from('<I', raw, 0x20)[0]
    blk = raw[0x28:0x28 + 60]
    magic, n, mx, depth, gen = struct.unpack_from('<HHHHI', blk, 0)
    if not (flags & EXTENT_FLAG) or magic != 0xF30A:
        # legacy direct blocks (12) + indirect - only direct used for small files
        out = []
        for i in range(12):
            p = struct.unpack_from('<I', blk, i * 4)[0]
            if p:
                out.append((i, p, 1))
        return out
    return walk_extent_block(blk)


def walk_extent_block(data):
    magic, n, mx, depth, gen = struct.unpack_from('<HHHHI', data, 0)
    if magic != 0xF30A:
        return []
    out = []
    for i in range(min(n, mx)):
        o = 12 + i * 12
        if o + 12 > len(data):
            break
        if depth == 0:
            lb, ln, hi, lo = struct.unpack_from('<IHHI', data, o)
            phys = (hi << 32) | lo
            length = ln if ln <= 32768 else ln - 32768
            if length:
                out.append((lb, phys, length))
        else:
            _lb, lo, hi, _u = struct.unpack_from('<IIHH', data, o)
            child = read_block((hi << 32) | lo)
            out.extend(walk_extent_block(child))
    return out


def inode_data(n):
    raw = inode(n)
    size = struct.unpack_from('<I', raw, 4)[0]
    mode = struct.unpack_from('<H', raw, 0)[0]
    if (mode & 0xF000) == 0xA000:      # fast symlink
        return raw[0x28:0x28 + 60].split(b'\x00')[0]
    ex = extents(raw)
    chunks = []
    for lb, pb, ln in ex:
        chunks.append((lb, b''.join(read_block(pb + j) for j in range(ln))))
    chunks.sort()
    return b''.join(c[1] for c in chunks)[:size]


def listdir(n):
    data = inode_data(n)
    out, htree = [], False
    for base in range(0, len(data), BS):
        blk = data[base:base + BS]
        pos = 0
        while pos + 8 <= len(blk):
            ino, rl, nl, ft = struct.unpack_from('<IHBB', blk, pos)
            if rl < 8 or pos + rl > len(blk):
                htree = True
                break
            name = blk[pos + 8:pos + 8 + nl].decode('utf-8', 'ignore')
            if ino and name not in ('.', '..'):
                out.append((name, ino, ft))
            if nl == 0 and ino == 0:
                htree = True
            pos += rl
    return out, htree


emit('PD1610 8.1 system partition - offline ext4 extraction')
emit('image : %s' % IMG)
emit('geometry: block=%d first=%d inodes/group=%d inode_size=%d gd_size=%d' % (BS, FIRST, IPG, ISZ, GDSZ))

root_entries, rh = listdir(2)
emit('')
emit('=== / (%d entries, htree=%s) ===' % (len(root_entries), rh))
for name, ino, ft in root_entries:
    emit('  %-34s inode=%-6d type=%d' % (name, ino, ft))

# ---- directory listings of interest ----
dirs = {}
for name, ino, ft in root_entries:
    if name in ('etc', 'vendor') and ft == 2:
        ents, h = listdir(ino)
        dirs['/' + name] = (ents, h)
        emit('')
        emit('=== /%s (%d entries, htree=%s) ===' % (name, len(ents), h))
        for n2, i2, t2 in ents[:60]:
            emit('  %-40s inode=%-6d type=%d' % (n2, i2, t2))
        if len(ents) > 60:
            emit('  ... %d more' % (len(ents) - 60))

# ---- files to extract ----
targets = [('/build.prop', 0), ('/manifest.xml', 0), ('/compatibility_matrix.xml', 0)]
for name, ino, ft in root_entries:
    if name in ('build.prop', 'manifest.xml', 'compatibility_matrix.xml'):
        targets = [(p, i) for p, i in targets if not p.endswith('/' + name)]
        targets.append(('/' + name, ino))
for base in ('/etc', '/vendor'):
    if base not in dirs:
        continue
    for n2, i2, t2 in dirs[base][0]:
        low = n2.lower()
        if t2 == 1 and (low.startswith('fstab') or low.endswith('.rc') or
                        low.startswith('init') or 'vintf' in low or
                        low in ('manifest.xml', 'compatibility_matrix.xml', 'ueventd.rc')):
            targets.append((base + '/' + n2, i2))

# interesting subdirectories: full listing, and extract fstab/init-rc-like files
for base in ('/etc', '/vendor'):
    if base not in dirs:
        continue
    for n2, i2, t2 in dirs[base][0]:
        if t2 == 2 and n2 in ('init', 'vintf', 'permissions', 'etc'):
            sub, sh = listdir(i2)
            emit('')
            emit('=== %s/%s (%d entries, htree=%s) ===' % (base, n2, len(sub), sh))
            for n3, i3, t3 in sub[:60]:
                emit('  %-46s inode=%-6d type=%d' % (n3, i3, t3))
            if len(sub) > 60:
                emit('  ... %d more' % (len(sub) - 60))
            for n3, i3, t3 in sub:
                if t3 == 1:
                    l3 = n3.lower()
                    if (l3.startswith('fstab') or l3.endswith('.rc') or
                            l3.startswith('init') or 'vintf' in l3 or
                            n2 in ('init', 'permissions')):
                        targets.append(('%s/%s/%s' % (base, n2, n3), i3))

emit('')
emit('=== extracted files ===')
manifest = []
seen = set()
for path, ino in targets:
    if not ino or path in seen:
        continue
    seen.add(path)
    try:
        d = inode_data(ino)
    except Exception as e:
        emit('  [!] %s : %s' % (path, e))
        continue
    safe = path.lstrip('/').replace('/', '__')
    with open(os.path.join(OUT, safe), 'wb') as o:
        o.write(d)
    manifest.append((path, len(d), hashlib.sha256(d).hexdigest()[:16]))
    emit('  %-52s %8d B  sha=%s' % (path, len(d), hashlib.sha256(d).hexdigest()[:16]))

with open(os.path.join(OUT, 'MANIFEST.txt'), 'w', encoding='utf-8') as m:
    m.write('\n'.join(log) + '\n\n=== MANIFEST ===\n')
    m.write('\n'.join('%-52s %8d  %s' % r for r in manifest) + '\n')

# ---- kernel config (reuse verified historical extraction) ----
if os.path.exists(KCFG):
    shutil.copy2(KCFG, os.path.join(OUT, 'kernel_config_81916.txt'))
    cfg = open(KCFG, encoding='utf-8', errors='ignore').read().splitlines()
    enabled = [l[7:] for l in cfg if l.startswith('CONFIG_') and l.endswith('=y') and not l.startswith('#')]
    keys = ('DM_VERITY', 'EXT4_FS', 'F2FS', 'SECURITY_SELINUX', 'ANDROID', 'BINDER',
            'CRYPTO', 'KEYS', 'MODULE', 'IKCONFIG', 'PROC_CONFIG', 'ARM64', 'OF_', 'QCOM')
    summary = []
    for k in keys:
        hits = [x for x in enabled if k in x]
        summary.append('%-18s %d' % (k, len(hits)))
    with open(os.path.join(OUT, 'kconfig_summary.txt'), 'w', encoding='utf-8') as s:
        s.write('source     : %s\n' % KCFG)
        s.write('lines      : %d   CONFIG_=y : %d\n' % (len(cfg), len(enabled)))
        s.write('\n'.join(summary) + '\n\n')
        s.write('DM_VERITY / encryption related:\n')
        s.write('\n'.join('  ' + x for x in enabled if any(k in x for k in ('DM_VERITY', 'CRYPTO', 'KEYS', 'FBE'))) + '\n')
    emit('')
    emit('kernel config: %d lines, %d CONFIG_=y, copied' % (len(cfg), len(enabled)))
if os.path.exists(KDIFF):
    shutil.copy2(KDIFF, os.path.join(OUT, 'kconfig_diff_vs_TB8703.txt'))
    emit('kernel config diff vs TB8703 (LOS17.1) copied')

print('\n[written] ' + OUT)
