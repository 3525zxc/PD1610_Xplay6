# -*- coding: utf-8 -*-
"""Round-3 part3: writers of boot-state array 0x9200272C[0..3], pre-loop checks, G call sites, helper exits."""
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

def show(name, s, e, mark=()):
    emit('=== %s ===' % name)
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        m = ' <<<' if i.address in mark else ''
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, m))
    emit('')

# ---------- 1) contexts of the two base-pointer sites
show('site A: fn around 0x91D0B09C (base 0x92002728)', 0x91D0B060, 0x91D0B110, mark=(0x91D0B09C,))
show('site B: fn around 0x91D0B18C (base 0x92002730)', 0x91D0B150, 0x91D0B1F0, mark=(0x91D0B18C,))

# ---------- 2) all str with [rX, rY, lsl #2] where rX was materialised 0x9200272C
emit('=== str [reg, idx, lsl #2] after materialising 0x9200272C (array writes) ===')
cnt = 0
for a, (mn, op) in one.items():
    if mn.startswith('str') and 'lsl #2' in op:
        # find backwards up to 12 instructions for movw #0x272c
        va = a - 4; steps = 0; found = False
        while va >= V and steps < 12:
            m2, o2 = one.get(va, ('', ''))
            if m2 == 'movw' and '0x272c' in o2:
                found = True; break
            if m2.startswith('ldr') and '[pc' in o2:
                break
            va -= 4; steps += 1
        if found:
            cnt += 1
            emit('  %08X  %-5s %s' % (a, mn, op))
emit('  count: %d' % cnt)
emit('')

# ---------- 3) pre-loop checks & exit-path helpers
show('0x91D377A8 (pre-loop check 1)', 0x91D377A8, 0x91D37814)
show('0x91D37814 (pre-loop check 2)', 0x91D37814, 0x91D37860)
show('0x91D3D27C (exit path call)', 0x91D3D27C, 0x91D3D2B0)
show('0x91D43730 (exit path call)', 0x91D43730, 0x91D43770)

# ---------- 4) T4: G's three call sites — post-call region each (±0x50)
for name, s, e in [
    ('T4 caller1 0x91D3C84C post-region', 0x91D3C84C, 0x91D3C8F0),
    ('T4 caller2 0x91D3D764 region', 0x91D3D740, 0x91D3D810),
    ('T4 caller3 0x91D3E380 region', 0x91D3E360, 0x91D3E420),
]:
    show(name, s, e)

# check whether caller2/3 regions read flag 0x92007DAC or call helper 0x91D445E8 within ±0x200
emit('=== flag/helper proximity scan around caller2/caller3 (±0x200) ===')
for name, lo, hi in [('caller2', 0x91D3D764 - 0x200, 0x91D3D764 + 0x200),
                     ('caller3', 0x91D3E380 - 0x200, 0x91D3E380 + 0x200)]:
    fl = []; hp = []
    for a, (mn, op) in one.items():
        if lo <= a < hi:
            if mn == 'movw' and '0x7dac' in op: fl.append(a)
            if mn == 'bl' and '0x91d445e8' in op: hp.append(a)
    emit('  %s: flag-movw %s  helper-bl %s' % (name, fl, hp))
emit('')

# ---------- 5) T5: helper 0x91D445E8 full — exits, atomics, barriers
show('T5 helper 0x91D445E8 full body', 0x91D445E8, 0x91D44680)
emit('=== ldrex/strex/dmb census in helper & neighbours ===')
for a, (mn, op) in sorted(one.items()):
    if 0x91D445E8 <= a < 0x91D44780 and mn in ('ldrex', 'strex', 'dmb', 'dsb', 'isb', 'ldrexd', 'strexd'):
        emit('  %08X  %-6s %s' % (a, mn, op))
emit('(none listed = no atomics/barriers)')
emit('')

# helper -1 exit: dump the tail where mvn r0,#0 appears
emit('=== helper region containing mvn r0,#0 (fail exit) ===')
mvns = [a for a, (mn, op) in one.items() if 0x91D445E8 <= a < 0x91D44780 and mn == 'mvn' and '#0' in op]
for a in mvns:
    show('around mvn @0x%08X' % a, a - 0x30, a + 0x10, mark=(a,))

open(r'D:\16\PD1610_81\work\round3_part3.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round3_part3.txt')
