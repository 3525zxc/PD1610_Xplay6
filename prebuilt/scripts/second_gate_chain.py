"""Close the chain 0x91D445E8 -> 0x92013AC0 -> 0x91D3C58C (8.19.16 aboot).

Pure static analysis, no device operation.
Decode one instruction at every aligned word to avoid linear-sweep desync.
"""
import re, json, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

P = r'D:\16\PD1610_81\migrated_from_C\qfilx\firmware\81916\emmc_appsboot.mbn'
OUT = r'D:\16\PD1610_81\evidence\second_gate_chain_1111.txt'

V, O, FSZ, MSZ = 0x91D00000, 0x8000, 0x2FED40, 0x331814
d = open(P, 'rb').read()
code = d[O:O + FSZ]
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

one = {}
for off in range(0, len(code) - 3, 4):
    for i in md.disasm(code[off:off + 4], V + off):
        one[V + off] = (i.mnemonic, i.op_str)
        break

L = []
def emit(s=''):
    L.append(s); print(s)

def dis(s, e, mark=()):
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        m = ' <<<' if i.address in mark else ''
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, m))

def find_bl(target):
    out = []
    for va, (mn, op) in one.items():
        if mn in ('bl', 'blx'):
            m = re.search(r'#0x([0-9a-fA-F]+)', op)
            if m and int(m.group(1), 16) == target:
                out.append(va)
    return sorted(out)

def func_entry(addr, maxback=0x3000):
    """Nearest preceding push{...,lr} / stmfd sp!,{...,lr}."""
    cands = []
    for va in sorted(one, reverse=True):
        if va > addr: continue
        if addr - va > maxback: break
        mn, op = one[va]
        if (mn.startswith('push') or mn.startswith('stm')) and 'lr' in op:
            cands.append(va)
    return cands[:6]

emit('=== 8.19.16 aboot: second-gate chain closure ===')
emit('binary %s (%d B)  PT_LOAD vaddr=0x%08X off=0x%X filesz=0x%X memsz=0x%X' %
     (P, len(d), V, O, FSZ, MSZ))
emit('')

# ---- 1. all callers of the helper ----
emit('--- 1. callers of 0x91D445E8 (helper) ---')
for va in find_bl(0x91D445E8):
    emit('  bl @0x%08X' % va)
emit('  total = %d' % len(find_bl(0x91D445E8)))
emit('')

# ---- 2. all callers of G ----
emit('--- 2. callers of G = 0x91D39CB4 (verify wrapper) ---')
gcall = find_bl(0x91D39CB4)
for va in gcall:
    emit('  bl @0x%08X' % va)
emit('  total = %d' % len(gcall))
emit('')

# ---- 3. helper full body: exits and r0 values ----
emit('--- 3. helper 0x91D445E8 full body 0x91D445E8..0x91D44768 ---')
dis(0x91D445E8, 0x91D44768,
    mark=(0x91D44608, 0x91D44618, 0x91D44620, 0x91D446F4, 0x91D44704, 0x91D44708))
emit('')

# ---- 4. [0x92013AC0] references (direct + nearby base+offset) ----
emit('--- 4. variable A [0x92013AC0] direct references ---')
lo, hi = 0x3AC0, 0x9201
mat = []
for va, (mn, op) in one.items():
    if mn == 'movw' and re.search(r'#0x%04x' % lo, op, re.I):
        reg = op.split(',')[0].strip()
        nx = one.get(va + 4)
        if nx and nx[0] == 'movt' and nx[1].startswith(reg + ',') and \
                re.search(r'#0x%04x' % hi, nx[1], re.I):
            mat.append((va, reg))
for va, reg in mat:
    emit('  materialise @0x%08X reg %s' % (va, reg))
    s, e = max(V, va - 8), va + 32
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        if re.search(r'\[' + reg + r'(?:\s*,|\])', i.op_str):
            emit('     %08X %-6s %s' % (i.address, i.mnemonic, i.op_str))
emit('  direct materialisations = %d' % len(mat))
emit('')

# ---- 5. [0x920157DC] writers (guard variable) ----
emit('--- 5. variable B [0x920157DC] direct writes ---')
lo2, hi2 = 0x57DC, 0x9201
mat2 = []
for va, (mn, op) in one.items():
    if mn == 'movw' and re.search(r'#0x%04x' % lo2, op, re.I):
        reg = op.split(',')[0].strip()
        nx = one.get(va + 4)
        if nx and nx[0] == 'movt' and nx[1].startswith(reg + ',') and \
                re.search(r'#0x%04x' % hi2, nx[1], re.I):
            mat2.append((va, reg))
writes = 0
for va, reg in mat2:
    s, e = max(V, va - 8), va + 24
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        if re.search(r'\[' + reg + r'(?:\s*,|\])', i.op_str) and i.mnemonic.startswith('str'):
            emit('  WRITE @0x%08X %-6s %s  (base @0x%08X)' % (i.address, i.mnemonic, i.op_str, va))
            writes += 1
emit('  materialisations = %d, direct writes = %d' % (len(mat2), writes))
emit('')

# ---- 6. function containing 0x91D3C58C, its entry and callers ----
emit('--- 6. function containing early-return 0x91D3C58C ---')
ents = func_entry(0x91D3C58C)
emit('  candidate entries (nearest push{...,lr}): %s' %
     ', '.join('0x%08X' % x for x in ents))
for e0 in ents[:3]:
    bls = find_bl(e0)
    emit('  entry 0x%08X -> bl callers = %d %s' %
         (e0, len(bls), ', '.join('0x%08X' % x for x in bls[:10])))
emit('')
emit('  --- disassembly 0x91D3C570..0x91D3C5B0 (return value setup) ---')
dis(0x91D3C570, 0x91D3C5B0, mark=(0x91D3C588, 0x91D3C590, 0x91D3C5A4))
emit('')

# ---- 7. what consumes the return value 4: look at callers' next insns ----
emit('--- 7. consumers of the enclosing function return value ---')
for e0 in ents[:3]:
    for c in find_bl(e0)[:6]:
        emit('  caller bl @0x%08X, following 8 insns:' % c)
        dis(c, c + 36)
emit('')

# ---- 8. .bss classification ----
emit('--- 8. .bss classification ---')
bss0, bss1 = V + FSZ, V + MSZ
emit('  .bss 0x%08X .. 0x%08X' % (bss0, bss1))
for a in (0x92007DAC, 0x92013AC0, 0x920157DC):
    emit('  0x%08X in .bss: %s' % (a, bss0 <= a < bss1))
emit('')

emit('=== Boundary ===')
emit('Direct movw/movt + aligned-word decoding only. Indirect writes through')
emit('computed pointers / bulk memset / other segments are NOT fully excluded.')
emit('Static analysis only; no device operation, no flashing.')

open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\nwrote', OUT)
