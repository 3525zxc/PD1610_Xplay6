# -*- coding: utf-8 -*-
"""Round-4 part2: 0x91D37814 identity, string @0x91D856E4 pool refs, 0x91D411B8 tail,
caller of loop function 0x91D40FCC, 0x91D41414, flag-read#1 context fn & target 0x91D3B710."""
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

# 1) 0x91D37814: helper before flag-read#1 (and used at 0x91D412A0)
show('helper candidate 0x91D37814', 0x91D37814, 0x91D37860)
# who writes [0x92013AC0]-like vars? find its read var first: done in prior rounds
# also check callers of 0x91D37814
srcs = [va for va, (mn, op) in sorted(one.items()) if mn == 'bl' and '0x91d37814' in op]
emit('  callers of 0x91D37814: %s' % ', '.join('0x%08X' % x for x in srcs))
emit('')

# 2) string around 0x91D856E4 and pool refs
emit('=== strings near 0x91D856E4 ===')
seg = d[O + (0x91D856C0 - V):O + (0x91D85760 - V)]
emit('  raw: %r' % seg)
for cand in (0x91D856E4, 0x91D856F4, 0x91D85705 - 17, 0x91D856D0):
    val = cand
    refs = []
    for o in range(0, len(code) - 3, 4):
        v = struct.unpack_from('<I', code, o)[0]
        if v == val:
            rr = [va for va, (mn, op) in sorted(one.items())
                  if mn.startswith('ldr') and '[pc' in op
                  and re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                  and ((va + 8) & ~3) + int(re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op).group(1), 16) == o + V]
            refs.append((V + o, rr))
    emit('  VA 0x%08X pool hits: %s' % (cand, '; '.join('pool@0x%08X<-%s' % (p, ','.join('0x%08X' % r for r in rr) or '?') for p, rr in refs) or '(none)'))
emit('')

# 3) tail 0x91D411B8 region
show('tail 0x91D411B8..0x91D41200', 0x91D411B8, 0x91D41200)

# 4) 0x91D41414 (beq target from 0x91D4129C)
show('0x91D41414..0x91D4141C', 0x91D41414, 0x91D4141C)

# 5) who calls loop function 0x91D40FCC?
srcs = [va for va, (mn, op) in sorted(one.items()) if mn == 'bl' and '0x91d40fcc' in op]
emit('  callers of 0x91D40FCC: %s' % ', '.join('0x%08X' % x for x in srcs))
emit('')

# 6) flag-read#1 context: what function contains 0x91D3AD40? prologue scan
found = []
for va in sorted(one):
    if 0x91D38000 <= va < 0x91D3AD40:
        mn, op = one[va]
        if mn == 'push' and 'lr' in op and 'pc' not in op:
            found.append(va)
if found:
    st = found[-1]
    emit('  function containing flag-read#1 starts ~0x%08X' % st)
# 7) 0x91D3B710 (flag!=0 target)
show('flag-read#1 nonzero target 0x91D3B710..0x91D3B780', 0x91D3B710, 0x91D3B780)

# 8) where does G write flag: 0x91D39DA0 context (inside G)
show('G write site 0x91D39D80..0x91D39DC0', 0x91D39D80, 0x91D39DC0)

# 9) 0x91D51508 identity check (print fn?) - first 12 instrs
show('0x91D51508 (print fn?) head', 0x91D51508, 0x91D51530)

open(r'D:\16\PD1610_81\work\round4_part2.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part2.txt')
