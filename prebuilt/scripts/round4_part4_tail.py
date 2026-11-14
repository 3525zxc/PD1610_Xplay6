# -*- coding: utf-8 -*-
"""Round-4 part4: tail full disasm, 0x91D48E70 identity, jump table, loop-fn entry hunt."""
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
        m = re.search(r'#(0x[0-9a-f]+)\s*$', i.op_str)
        if i.mnemonic == 'movw':
            nx = one.get(i.address + 4)
            if nx and nx[0] == 'movt':
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                va = (hi << 16) | lo
                s2 = cstr(va)
                extra = '   ; 0x%08X%s' % (va, (' = %r' % s2) if s2 else '')
        if i.mnemonic == 'ldr' and '[pc' in i.op_str:
            mm = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', i.op_str)
            pa = ((i.address + 8) & ~3) + int(mm.group(1), 16)
            if O + (pa - V) + 4 <= len(d):
                val = struct.unpack_from('<I', d, O + (pa - V))[0]
                s2 = cstr(val) if V <= val < V + FSZ else None
                extra = '   ; pool@0x%08X=0x%08X%s' % (pa, val, (' = %r' % s2) if s2 else '')
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
    emit('')

show('tail FULL 0x91D411B8..0x91D412A0', 0x91D411B8, 0x91D412A0)
show('0x91D48E70 head (fastboot entry candidate)', 0x91D48E70, 0x91D48F00)

# xrefs to 0x91D48E70
srcs = [va for va, (mn, op) in sorted(one.items()) if mn in ('bl', 'b') and '0x91d48e70' in op]
emit('  xrefs to 0x91D48E70: %s' % ', '.join('0x%08X(%s)' % (s, one[s][0]) for s in srcs))
emit('')

# pool value at 0x91D415D0
val = struct.unpack_from('<I', d, O + (0x91D415D0 - V))[0]
emit('pool@0x91D415D0 = 0x%08X  str=%r' % (val, cstr(val) if V <= val < V + FSZ else None))
emit('')

# switch jump table at 0x91D3AD5C, 12 entries (ldrls pc,[pc,r0,lsl#2] @0x91D3AD54, pc=0x91D3AD5C)
emit('=== switch table @0x91D3AD5C (12 entries) ===')
for k in range(12):
    va = 0x91D3AD5C + 4 * k
    t = struct.unpack_from('<I', d, O + (va - V))[0]
    emit('  [%d] 0x%08X -> 0x%08X' % (k, va, t))
emit('')

# loop function entry hunt: b/bl to anything in 0x91D40FCC..0x91D41000
emit('=== branches into 0x91D40FCC..0x91D41000 ===')
hits = [va for va, (mn, op) in sorted(one.items()) if mn in ('bl', 'b') and '0x91d40f' in op]
for h in hits: emit('  %08X %s %s' % (h, one[h][0], one[h][1]))
emit('(end)')
emit('')

# what does 0x91D1D770 do (tail call)? and 0x91D47590?
show('0x91D1D770 head', 0x91D1D770, 0x91D1D7B0)
show('0x91D47590 head', 0x91D47590, 0x91D475D0)
# strings 0x91D85288 (in 0x91D40974) and 0x91D775CC/D4 (0x91D0206C)
for va in (0x91D85288, 0x91D775CC, 0x91D775D4, 0x91D85664):
    emit('str 0x%08X: %r' % (va, cstr(va)))
emit('')

# 0x91D377E0 / 0x91D42C2C context: what is stored where
emit('=== who references 0x91D85A88 "fastboot" ===')
refs = []
for o in range(0, len(code) - 3, 4):
    v = struct.unpack_from('<I', code, o)[0]
    if v == 0x91D85A88:
        for va, (mn, op) in sorted(one.items()):
            if mn == 'ldr' and '[pc' in op and re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op):
                if ((va + 8) & ~3) + int(re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op).group(1), 16) == o + V:
                    refs.append('  %08X %s %s' % (va, mn, op))
    lo, hi = 0x5A88, 0x91D8
    # movw/movt
emit('\n'.join(refs) or '  (no pool refs)')
mv = []
for a, (mn, op) in sorted(one.items()):
    if mn == 'movw' and re.search(r'#0x5a88\b', op, re.I):
        nx = one.get(a + 4)
        if nx and nx[0] == 'movt' and re.search(r'#0x91d8\b', nx[1], re.I):
            mv.append('  %08X movw/movt' % a)
emit('\n'.join(mv) or '  (no movw/movt refs)')
emit('')

open(r'D:\16\PD1610_81\work\round4_part4.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part4.txt')
