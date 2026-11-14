# -*- coding: utf-8 -*-
"""Round-3 P0: close the retry loop 0x91D412AC and the condition fn 0x91D0AED4."""
import re, struct, sys
from capstone import *

P = r'D:\16\PD1610_81\migrated_from_C\qfilx\firmware\81916\emmc_appsboot.mbn'
d = open(P, 'rb').read()
V, O = 0x91D00000, 0x8000
FSZ = 0x2FED40
code = d[O:O + FSZ]
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

OUT = []


def emit(s=''):
    OUT.append(s)
    print(s)


def dis(s, e):
    return list(md.disasm(d[O + (s - V):O + (e - V)], s))


def show(name, s, e, mark=()):
    emit('=== %s ===' % name)
    for i in dis(s, e):
        m = ' <<<' if i.address in mark else ''
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, m))
    emit('')


# aligned single-instruction map (for cross references)
one = {}
for o in range(0, len(code) - 3, 4):
    for i in md.disasm(code[o:o + 4], V + o):
        one[V + o] = (i.mnemonic, i.op_str)
        break

emit('# Round-3 P0: retry loop 0x91D412AC closure')
emit('# PT_LOAD vaddr=0x%08X off=0x%x, aboot=%s' % (V, O, P))
emit('')

# ---------------------------------------------------------------- T1: loop
# The loop: 0x91D412AC bl 0x91D3C3F0 ; ... 0x91D412DC bl 0x91D0AED4 ; beq 0x91D412AC
# Dump the WHOLE enclosing region to find: loop entry, all back edges, exits, counters.
show('T1 region 0x91D411C0..0x91D41360 (loop core)',
     0x91D411C0, 0x91D41360,
     mark=(0x91D412AC, 0x91D412B0, 0x91D412B4, 0x91D412B8, 0x91D412BC, 0x91D412DC, 0x91D412E0))

# find every branch whose target is inside the loop core -> back edges
LO, HI = 0x91D411C0, 0x91D41400
emit('T1 branch census in [0x91D411C0,0x91D41400):')
for va in sorted(one):
    if not (LO <= va < HI):
        continue
    mn, op = one[va]
    if mn in ('b', 'bl', 'beq', 'bne', 'blt', 'ble', 'bgt', 'bge', 'bls', 'bhi', 'bcc', 'bcs', 'bvc', 'bvs', 'bmi', 'bpl'):
        m = re.search(r'#0x([0-9a-fA-F]+)', op)
        if m:
            tgt = int(m.group(1), 16)
            tag = ''
            if tgt == 0x91D412AC:
                tag = '  <<< BACK-EDGE to loop head'
            elif tgt < LO or tgt >= HI:
                tag = '  (exit)'
            emit('  %08X  %-5s -> 0x%08X%s' % (va, mn, tgt, tag))
emit('')

# counters: look for str to a global right before/inside loop, or cmp with growing value
emit('T1 memory-write census inside loop core:')
for va in sorted(one):
    if not (0x91D412A0 <= va < 0x91D412E0):
        continue
    mn, op = one[va]
    if mn.startswith('str') or mn.startswith('sub') or mn.startswith('add'):
        emit('  %08X  %-5s %s' % (va, mn, op))
emit('')

# ---------------------------------------------------------------- T2: 0x91D0AED4
# find function end (pop {..., pc})
end = None
for i in dis(0x91D0AED4, 0x91D0AED4 + 0x400):
    if i.mnemonic == 'pop' and 'pc' in i.op_str:
        end = i.address + 4
        break
emit('T2 0x91D0AED4 function end = 0x%08X' % (end or 0))
show('T2 full function 0x91D0AED4..end', 0x91D0AED4, end or 0x91D0B000)

# what globals does it read? materialised addresses
emit('T2 globals materialised inside 0x91D0AED4:')
s = 0x91D0AED4
e = end or 0x91D0B000
for va in sorted(one):
    if not (s <= va < e):
        continue
    mn, op = one[va]
    if mn == 'movw':
        reg = op.split(',')[0].strip()
        nx = one.get(va + 4)
        if nx and nx[0] == 'movt' and nx[1].startswith(reg + ','):
            lo = int(re.search(r'#0x([0-9a-fA-F]+)', op).group(1), 16)
            hi = int(re.search(r'#0x([0-9a-fA-F]+)', nx[1]).group(1), 16)
            emit('  @0x%08X  %s = 0x%08X' % (va, reg, (hi << 16) | lo))
emit('')

open(r'D:\16\PD1610_81\work\round3_loop_analysis.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round3_loop_analysis.txt')
