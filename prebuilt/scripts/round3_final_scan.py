# -*- coding: utf-8 -*-
"""Round-3 final: full-file scans for writers of the four key globals; helper caller census."""
import re, struct
from capstone import *

P = r'D:\16\PD1610_81\migrated_from_C\qfilx\firmware\81916\emmc_appsboot.mbn'
d = open(P, 'rb').read()
V, O, FSZ = 0x91D00000, 0x8000, 0x2FED40
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

def full_scan(target, label):
    emit('=== %s 0x%08X (full PT_LOAD scan) ===' % (label, target))
    lo, hi = target & 0xFFFF, target >> 16
    mm = []
    for a, (mn, op) in one.items():
        if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
            reg = op.split(',')[0].strip()
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and nx[1].startswith(reg + ',') and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
                mm.append((a, reg))
    emit('  movw/movt: %d' % len(mm))
    for a, reg in sorted(mm):
        # classify usage: find str/ldr via reg within 8 instrs
        uses = []
        va = a
        for _ in range(8):
            va += 4
            m2, o2 = one.get(va, ('', ''))
            if (m2.startswith('str') or m2.startswith('ldr')) and ('[%s' % reg) in o2.replace(' ', ''):
                uses.append('%08X %s %s' % (va, m2, o2))
            if m2.startswith('pop'):
                break
        kind = 'WRITE' if any(u.split(None, 2)[1].startswith('str') for u in uses) else 'read'
        emit('    @0x%08X (%s) %s' % (a, reg, kind))
        for u in uses:
            emit('        ' + u)
    # literal pools
    ph = []
    for o in range(0, len(code) - 3, 4):
        val = struct.unpack_from('<I', code, o)[0]
        if val == target:
            pa = V + o
            refs = []
            for va in sorted(one):
                mn, op = one[va]
                if (mn.startswith('ldr') or mn.startswith('str')) and '[pc' in op:
                    m = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if m and ((va + 8) & 0xFFFFFFFC) + int(m.group(1), 16) == pa:
                        refs.append((va, mn, op))
            ph.append((pa, refs))
    emit('  literal pools: %d' % len(ph))
    for pa, refs in ph:
        emit('    pool@0x%08X refs=%d' % (pa, len(refs)))
        for va, mn, op in refs[:6]:
            emit('        %08X %s %s' % (va, mn, op))
    emit('')

full_scan(0x92013AC0, 'gate-selector [0x92013AC0]')
full_scan(0x92002738, 'boot-state [0x92002738]')
full_scan(0x92002734, 'boot-state-1 [0x92002734]')
full_scan(0x9200273C, 'boot-state-4 [0x9200273C]')

# guard writes: str to 0x920157DC (canary init)
emit('=== writes to guard 0x920157DC (canary init) ===')
lo, hi = 0x57DC, 0x9201
n = 0
for a, (mn, op) in one.items():
    if mn == 'movw' and re.search(r'#0x57dc\b', op, re.I):
        reg = op.split(',')[0].strip()
        nx = one.get(a + 4)
        if nx and nx[0] == 'movt' and nx[1].startswith(reg + ',') and re.search(r'#0x9201\b', nx[1], re.I):
            va = a
            for _ in range(8):
                va += 4
                m2, o2 = one.get(va, ('', ''))
                if m2.startswith('str') and ('[%s' % reg) in o2.replace(' ', ''):
                    n += 1
                    emit('  %08X %s %s' % (va, m2, o2))
                if m2.startswith('pop'):
                    break
emit('  guard stores: %d' % n)
emit('')

# helper caller census
emit('=== callers of getter 0x91D445E8 ===')
srcs = [va for va, (mn, op) in one.items() if mn == 'bl' and re.search(r'#0x91d445e8\b', op, re.I)]
emit('  ' + ', '.join('0x%08X' % s for s in sorted(srcs)))
emit('')

# verify function boundary: is 0x91D44628 a separate function (reached only via its own entry)?
emit('=== who branches into 0x91D44628..0x91D44640 (the -1 fn) ===')
for tgt in (0x91D44628, 0x91D44624, 0x91D4463C, 0x91D4464C, 0x91D44650):
    srcs = [va for va, (mn, op) in one.items() if mn.startswith('b') and mn != 'bl' and
            re.search(r'#0x%x\b' % tgt, op, re.I)]
    emit('  0x%08X <- %s' % (tgt, ', '.join('0x%08X' % s for s in sorted(srcs)) or '(none)'))
emit('')

# what calls the -1 function? find its entry and callers. Entry = 0x91D44628.
emit('=== callers of 0x91D44628 (-1 fn) ===')
srcs = [va for va, (mn, op) in one.items() if mn == 'bl' and re.search(r'#0x91d44628\b', op, re.I)]
emit('  ' + (', '.join('0x%08X' % s for s in sorted(srcs)) or '(none)'))
emit('')

# image re-read check: does boot-main 0x91D3C3F0 reload image each iteration?
# G internally reads partition each call -> check G calls partition read (0x91d1d830 seen before G in caller2).
emit('=== G body: flash/partition read calls inside 0x91D39CB4..0x91D39E30 ===')
for a, (mn, op) in sorted(one.items()):
    if 0x91D39CB4 <= a < 0x91D39E30 and mn == 'bl':
        emit('  %08X bl %s' % (a, op))

open(r'D:\16\PD1610_81\work\round3_final_scan.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round3_final_scan.txt')
