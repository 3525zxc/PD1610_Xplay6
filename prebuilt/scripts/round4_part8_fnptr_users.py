# -*- coding: utf-8 -*-
"""Round-4 part8: who reads fnptr table @0x91D98FAC (aboot_init indirect call)."""
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

# 1) pool entries holding any base in [0x91D98F60..0x91D98FC8]
emit('=== pool entries with value in [0x91D98F60..0x91D98FC8] ===')
for o in range(0, len(code) - 3, 4):
    v = struct.unpack_from('<I', code, o)[0]
    if 0x91D98F60 <= v <= 0x91D98FC8:
        rr = [va for va, (mn, op) in sorted(one.items())
              if mn in ('ldr', 'str', 'add', 'sub') and '[pc' in op
              and re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
              and ((va + 8) & ~3) + int(re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op).group(1), 16) == o + V]
        emit('  pool@0x%08X = 0x%08X  <- %s' % (V + o, v, ', '.join('0x%08X(%s %s)' % (a, one[a][0], one[a][1]) for a in rr) or '(unref)'))
emit('')
# 2) movw/movt exact
emit('=== movw/movt of 0x91D98Fxx bases ===')
for a, (mn, op) in sorted(one.items()):
    if mn == 'movw' and re.search(r'#0x8(f[6-9a-c]|a[0-8])[0-9a-f]?\b|#0x8f[6-9a-c][0-9a-f]\b|#0x8fa[0-8]\b', op, re.I):
        nx = one.get(a + 4)
        if nx and nx[0] == 'movt' and re.search(r'#0x91d9\b', nx[1], re.I):
            lo = int(re.search(r'#(0x[0-9a-f]+)', op, re.I).group(1), 16)
            emit('  %08X -> 0x91D9%04X  (then: %s %s | %s %s)' % (a, lo, one.get(a+8, ('',''))[0], one.get(a+8, ('',''))[1], one.get(a+12, ('',''))[0], one.get(a+12, ('',''))[1]))
emit('')

# 3) what are 0x91D79890 and 0x91D3A938 (table siblings)?
for fn in (0x91D79890, 0x91D3A938):
    emit('=== sibling fn 0x%08X head ===' % fn)
    for i in md.disasm(d[O + (fn - V):O + (fn - V) + 0x50], fn):
        emit('  %08X  %-8s %s' % (i.address, i.mnemonic, i.op_str))
    emit('')

open(r'D:\16\PD1610_81\work\round4_part8.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part8.txt')
