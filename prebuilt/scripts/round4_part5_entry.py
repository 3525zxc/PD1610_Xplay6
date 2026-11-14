# -*- coding: utf-8 -*-
"""Round-4 part5: 0x91D01868 identity, aboot_init(0x91D40FCC) entry hunt."""
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

def cstr(va, maxn=80):
    off = O + (va - V)
    if off < 0 or off >= len(d): return None
    end = d.find(b'\x00', off)
    return d[off:min(end, off + maxn)].decode('latin1', 'replace')

def show(name, s, e):
    emit('=== %s  0x%08X..0x%08X ===' % (name, s, e))
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        extra = ''
        if i.mnemonic == 'movw':
            nx = one.get(i.address + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', i.op_str)
            if nx and nx[0] == 'movt' and m:
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                va = (hi << 16) | lo
                s2 = cstr(va)
                extra = '   ; 0x%08X%s' % (va, (' = %r' % s2) if s2 else '')
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
    emit('')

show('0x91D01868 head (tail target of fastboot gate)', 0x91D01868, 0x91D01900)

# aboot_init entry: movw/movt of 0x91D40FCC
emit('=== movw/movt of 0x91D40FCC ===')
lo, hi = 0x40FCC & 0xFFFF, 0x91D4
hits = []
for a, (mn, op) in sorted(one.items()):
    if mn == 'movw' and re.search(r'#0x0fcc\b|#0x40fcc\b', op, re.I):
        nx = one.get(a + 4)
        if nx and nx[0] == 'movt' and re.search(r'#0x91d4\b', nx[1], re.I):
            hits.append('  %08X movw/movt %s | %s' % (a, op, nx[1]))
emit('\n'.join(hits) or '  (none)')
emit('')
# pool entries holding 0x91D40FCC
refs = []
for o in range(0, len(code) - 3, 4):
    v = struct.unpack_from('<I', code, o)[0]
    if v == 0x91D40FCC:
        rr = [va for va, (mn, op) in sorted(one.items())
              if mn == 'ldr' and '[pc' in op and re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
              and ((va + 8) & ~3) + int(re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op).group(1), 16) == o + V]
        refs.append('  pool@0x%08X <- %s' % (V + o, ', '.join('0x%08X' % x for x in rr) or '(unref)'))
emit('\n'.join(refs) or '  (no pool entries)')
emit('')
# 0x91D40974 full: fastboot_init check (fastboot_register pattern)
show('0x91D40974..0x91D40B00 (fastboot_init?)', 0x91D40974, 0x91D40B00)

# does 0x91D01868 loop forever / usb? check strings it references in first 0x200 bytes
emit('=== strings referenced by 0x91D01868..0x91D01A00 ===')
for va in sorted(one):
    if 0x91D01868 <= va < 0x91D01A00:
        mn, op = one[va]
        if mn == 'movw':
            nx = one.get(va + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', op)
            if nx and nx[0] == 'movt' and m:
                lo2 = int(m.group(1), 16); hi2 = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                va2 = (hi2 << 16) | lo2
                s2 = cstr(va2)
                if s2: emit('  %08X -> %r' % (va, s2))
emit('')

open(r'D:\16\PD1610_81\work\round4_part5.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part5.txt')
