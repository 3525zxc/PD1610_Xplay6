# -*- coding: utf-8 -*-
"""Round-4 part6: aboot_init true entry (min bl-target before 0x91D40FCC) + fastboot_register check."""
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

# all bl targets in 0x91D3F000..0x91D40FCC
tgts = set()
for va, (mn, op) in one.items():
    if mn == 'bl':
        m = re.search(r'#0x([0-9a-f]+)', op)
        if m:
            t = int(m.group(1), 16)
            if 0x91D3F000 <= t <= 0x91D40FCC:
                tgts.add(t)
emit('bl targets in 0x91D3F000..0x91D40FCC: %s' % ', '.join('0x%08X' % t for t in sorted(tgts)))
# callers of the minimum
if tgts:
    start = min(t for t in tgts if t < 0x91D40974) if any(t < 0x91D40974 for t in tgts) else min(tgts)
    emit('candidate aboot_init start: 0x%08X' % start)
    srcs = [(va, one[va][0]) for va, (mn, op) in sorted(one.items())
            if mn in ('bl', 'b') and ('0x%08x' % start) in op]
    emit('  callers/branches: %s' % ', '.join('0x%08X(%s)' % c for c in srcs))
    show('head', start, start + 0x40)
emit('')

show('0x91D41D3C head (fastboot_register?)', 0x91D41D3C, 0x91D41D70)

# confirm: does anything bl INTO the middle of aboot_init region besides known blocks?
emit('=== all bl targets inside 0x91D40FCC..0x91D41600 (block entries) ===')
inside = set()
for va, (mn, op) in one.items():
    if mn == 'bl':
        m = re.search(r'#0x([0-9a-f]+)', op)
        if m:
            t = int(m.group(1), 16)
            if 0x91D40FCC <= t <= 0x91D41600:
                inside.add(t)
for t in sorted(inside):
    srcs = [va for va, (mn, op) in one.items() if mn == 'bl' and ('0x%08x' % t) in op]
    emit('  0x%08X <- %s' % (t, ', '.join('0x%08X' % s for s in sorted(srcs)[:6])))
emit('')

open(r'D:\16\PD1610_81\work\round4_part6.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part6.txt')
