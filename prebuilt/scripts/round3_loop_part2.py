# -*- coding: utf-8 -*-
"""Round-3 P0 part2: writers of 0x92002738, loop support fns, xrefs into loop blocks."""
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

def dis(s, e):
    return list(md.disasm(d[O + (s - V):O + (e - V)], s))

def show(name, s, e, mark=()):
    emit('=== %s ===' % name)
    for i in dis(s, e):
        m = ' <<<' if i.address in mark else ''
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, m))
    emit('')

def access_report(target, label, neighborhood=0x40):
    """Find all references to target: literal pools + movw/movt + pc-rel ldr/str onto pools."""
    emit('=== %s 0x%08X ===' % (label, target))
    # 1) literal pool entries holding target or target-nearby (struct base usage)
    pool_hits = []
    lo_v, hi_v = target - neighborhood, target + neighborhood
    for o in range(0, len(code) - 3, 4):
        val = struct.unpack_from('<I', code, o)[0]
        if lo_v <= val <= hi_v:
            pool_hits.append((V + o, val))
    emit('  literal pool entries (val in [0x%X..0x%X]): %d' % (lo_v, hi_v, len(pool_hits)))
    # map pool addr -> accesses
    used = 0
    for pa, val in pool_hits:
        refs = []
        for va in sorted(one):
            mn, op = one[va]
            if mn.startswith('ldr') or mn.startswith('str'):
                if '[pc' in op:
                    m = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if m:
                        # pc-rel base = (va+8)&~3 for ARM
                        base = (va + 8) & 0xFFFFFFFC
                        tgt = base + int(m.group(1), 16)
                        if tgt == pa:
                            refs.append((va, mn, op, val))
        for va, mn, op, val in refs:
            used += 1
            off = target - val
            note = ''
            if off:
                note = '  ; +0x%x -> reaches 0x%08X? (offset %d)' % (val and (target-val), target, off)
            emit('    %08X %-6s %-24s pool@0x%08X val=0x%08X%s' % (va, mn, op, pa, val, note))
    emit('  pool-referenced: %d' % used)
    # 2) movw/movt materialisation
    lo, hi = target & 0xFFFF, target >> 16
    hits = []
    for a, (mn, op) in one.items():
        if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
            reg = op.split(',')[0].strip()
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and nx[1].startswith(reg + ',') and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
                hits.append((a, reg))
    emit('  movw/movt materialisations: %d' % len(hits))
    for a, reg in sorted(hits):
        # find nearest str/ldr via reg within +/- 0x20 bytes
        ctx = []
        for va in sorted(one):
            if a <= va <= a + 0x20:
                mn, op = one[va]
                if (mn.startswith('str') or mn.startswith('ldr')) and ('[%s]' % reg) in op.replace(' ',''):
                    ctx.append('    %08X %-6s %s' % (va, mn, op))
        emit('    @0x%08X (%s)' % (a, reg))
        for c in ctx: emit(c)
    emit('')

# ---- state writers
access_report(0x92002738, 'loop state [0x92002738]')
# ---- canary global lifecycle (for T7 evidence)
access_report(0x920157DC, 'canary global [0x920157DC]')

# ---- helper/loop support functions
show('0x91D0A4E4 (called with r4 mid-loop)', 0x91D0A4E4, 0x91D0A540)
show('0x91D0A894 (called before cmn r4,#1)', 0x91D0A894, 0x91D0A910)
show('0x91D0AD64 (r4 = its ret)', 0x91D0AD64, 0x91D0AED4)
show('0x91D0AF10 (canary-mismatch path of 0x91D0AED4)', 0x91D0AF10, 0x91D0AF50)
show('loop exits region 0x91D41414..0x91D41440', 0x91D41414, 0x91D41440, mark=(0x91D4141C,))

# ---- xrefs INTO loop blocks: who branches to 0x91D412AC / 0x91D412C8 / 0x91D4141C
emit('=== xrefs into key loop addresses ===')
for tgt in (0x91D412AC, 0x91D412C8, 0x91D4141C, 0x91D41414, 0x91D411B8):
    srcs = [va for va, (mn, op) in one.items()
            if mn.startswith('b') and re.search(r'#0x%x\b' % tgt, op, re.I)]
    emit('  target 0x%08X <- %s' % (tgt, ', '.join('0x%08X' % s for s in sorted(srcs)) or '(fallthrough only)'))
emit('')

# what is 0x91D0AED4's callers (is the canary-read also used elsewhere?)
emit('=== callers of 0x91D0AED4 / 0x91D0A894 / 0x91D0AD64 / 0x91D0A4E4 ===')
for fn in (0x91D0AED4, 0x91D0A894, 0x91D0AD64, 0x91D0A4E4):
    srcs = [va for va, (mn, op) in one.items() if mn == 'bl' and re.search(r'#0x%x\b' % fn, op, re.I)]
    emit('  0x%08X <- %s' % (fn, ', '.join('0x%08X' % s for s in sorted(srcs)) or '(none)'))

open(r'D:\16\PD1610_81\work\round3_loop_part2.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round3_loop_part2.txt')
