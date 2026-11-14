# -*- coding: utf-8 -*-
"""Round-6 part2: 拆解 'Device is unlocked! Skipping verification' 等关键字符串所在函数"""
import re, struct
from capstone import *

P = r'D:\16\PD1610_81\migrated_from_C\qfilx\firmware\81916\emmc_appsboot.mbn'
d = open(P, 'rb').read()
V, O = 0x91D00000, 0x8000
FSZ = 0x2FED40
code = d[O:O + FSZ]
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
one = {}
for o in range(0, len(code) - 3, 4):
    for i in md.disasm(code[o:o + 4], V + o):
        one[V + o] = (i.mnemonic, i.op_str)
        break

OUT = []
def emit(s=''):
    OUT.append(s); print(s)

def cstr(va, maxn=120):
    off = O + (va - V)
    if off < 0 or off >= len(d): return None
    end = d.find(b'\x00', off)
    return d[off:min(end, off + maxn)].decode('latin1', 'replace')

def xrefs(target):
    out = []
    for o in range(0, len(code) - 3, 4):
        if struct.unpack_from('<I', code, o)[0] == target:
            for va, (mn, op) in sorted(one.items()):
                if mn.startswith(('ldr', 'str')) and '[pc' in op:
                    mm = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if mm and ((va + 8) & ~3) + int(mm.group(1), 16) == o + V:
                        out.append(('pool', o + V, va))
    lo, hi = target & 0xFFFF, target >> 16
    for a, (mn, op) in sorted(one.items()):
        if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
                out.append(('movw', a, a + 4))
    return out

def fn_start(before, back=0x8000):
    cands = [va for va, (mn, op) in sorted(one.items())
             if before - back <= va < before and mn == 'push' and 'lr' in op and 'pc' not in op]
    return cands[-1] if cands else None

def dump(name, s, maxlen=0x200):
    emit('=== %s @0x%08X ===' % (name, s))
    for i in md.disasm(d[O + (s - V):O + (s - V) + maxlen], s):
        extra = ''
        if i.mnemonic == 'movw':
            nx = one.get(i.address + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', i.op_str)
            if nx and nx[0] == 'movt' and m:
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                va = (hi << 16) | lo
                sv = cstr(va)
                extra = '   ; = 0x%08X%s' % (va, (' = %r' % sv) if sv else '')
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
        if i.mnemonic == 'pop' and 'pc' in i.op_str:
            break
    emit('')

TARGETS = [
    (0x91D840C4, 'Device is unlocked! Skipping verification...'),
    (0x91D7F98C, 'ERROR: Image Invalid! signature check failed! ret %d'),
    (0x91D7F8F0, 'ERROR: VB: Image Invalid! signature check failed! ret %d'),
    (0x91D842C8, 'ERROR: Cannot read boot image signature'),
    (0x91D84EF4, ' rebooting bootloader'),
    (0x91D8393D, 'Device tampered: %s'),
    (0x91D83955, 'Device unlocked: %s'),
]

for va, label in TARGETS:
    emit('#' * 72)
    emit('# %r  (0x%08X)' % (label, va))
    xr = xrefs(va)
    emit('# refs: %s' % (', '.join('%s@0x%08X' % (k, a) for k, _, a in xr) or '(none)'))
    sites = [a for _, _, a in xr]
    for st in sites[:2]:
        fs = fn_start(st)
        emit('# 引用点 0x%08X 所在函数起点 ~0x%08X' % (st, fs if fs else 0))
        if fs:
            dump('fn@0x%08X (引用 0x%08X)' % (fs, st), fs, 0x240)
    emit('')

open(r'D:\16\PD1610_81\work\round6_verify_fns.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round6_verify_fns.txt')
