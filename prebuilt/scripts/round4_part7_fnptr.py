# -*- coding: utf-8 -*-
"""Round-4 part7: who uses pool@0x91D98FB4 / data table around it; 0x91D415D8 & its callers."""
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

def show(name, s, e):
    emit('=== %s  0x%08X..0x%08X ===' % (name, s, e))
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        emit('  %08X  %-8s %s' % (i.address, i.mnemonic, i.op_str))
    emit('')

# dump table region around 0x91D98FB4
emit('=== words 0x91D98F80..0x91D99020 ===')
for va in range(0x91D98F80, 0x91D99020, 4):
    v = struct.unpack_from('<I', d, O + (va - V))[0]
    tag = ' <== holds 0x91D40FCC' if v == 0x91D40FCC else ''
    note = ''
    if V <= v < V + FSZ:
        note = ' (code VA)'
    elif 0x91D80000 <= v < 0x91DA0000:
        note = ' (data/rodata VA)'
    emit('  0x%08X: 0x%08X%s%s' % (va, v, tag, note))
emit('')

# who materializes addresses near 0x91D98F.. ?
emit('=== movw/movt materializing 0x91D9xxxx (0x8F00..0x9100) ===')
for a, (mn, op) in sorted(one.items()):
    if mn == 'movw' and re.search(r'#0x8[f9][0-9a-f]{2}\b|#0x90[0-9a-f]{2}\b', op, re.I):
        nx = one.get(a + 4)
        if nx and nx[0] == 'movt' and re.search(r'#0x91d9\b', nx[1], re.I):
            lo = int(re.search(r'#(0x[0-9a-f]+)', op, re.I).group(1), 16)
            emit('  %08X movw/movt -> 0x91D9%04X' % (a, lo))
emit('')

show('0x91D415D8..0x91D41640', 0x91D415D8, 0x91D41640)
show('0x91D440C4..0x91D44100 (caller A)', 0x91D440C4, 0x91D44100)
show('0x91D440FC..0x91D44140 (caller B)', 0x91D440FC, 0x91D44140)
# context of 0x91D440C4's function - what precedes
show('0x91D44080..0x91D440C8 (before caller A)', 0x91D44080, 0x91D440C8)

# string at 0x91D85A88 region raw
seg = d[O + (0x91D85A80 - V):O + (0x91D85AD0 - V)]
emit('raw @0x91D85A80: %r' % seg)
emit('')

open(r'D:\16\PD1610_81\work\round4_part7.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part7.txt')
