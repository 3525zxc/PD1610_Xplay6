"""Trace every read/write of the global flag at VA 0x92007DAC in 8.19.16 aboot.

Robust against linear-sweep desync: decode each 4-byte aligned word
individually, locate all movw #0x7DAC / movt #0x9200 pairs and all
pc-relative literal loads pointing at the raw address, then disassemble
a window around each site to find the actual load/store.
"""
import os, struct, re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

P = r'D:\16\PD1610_81\migrated_from_C\qfilx\firmware\81916\emmc_appsboot.mbn'
OUT = r'D:\16\PD1610_81\evidence\flag_92007dac_trace.txt'
TARGET = 0x92007DAC
LOW, HIGH = TARGET & 0xFFFF, TARGET >> 16

d = open(P, 'rb').read()
e_phoff = struct.unpack_from('<I', d, 28)[0]
e_phentsize = struct.unpack_from('<H', d, 42)[0]
e_phnum = struct.unpack_from('<H', d, 44)[0]
segs = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    t, off, va, pa, fsz, msz = struct.unpack_from('<IIIIII', d, o)
    if t == 1:
        segs.append((va, off, fsz, msz))
VADDR, FOFF, FSZ, MSZ = segs[0]

def va2off(va):
    return va - VADDR + FOFF

def off2va(off):
    return off - FOFF + VADDR

md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
lines = []
def emit(s=''):
    lines.append(s)
    print(s)

emit('=== 8.19.16 aboot: global flag 0x%08X access trace ===' % TARGET)
emit('binary: %s (%d bytes)' % (P, len(d)))
emit('PT_LOAD vaddr=0x%08X off=0x%X filesz=0x%X memsz=0x%X' % (VADDR, FOFF, FSZ, MSZ))
emit('')

# Decode one instruction at every aligned word (no desync)
code = d[FOFF:FOFF + FSZ]
one = {}
for off in range(0, len(code) - 3, 4):
    for ins in md.disasm(code[off:off + 4], off2va(FOFF + off)):
        one[ins.address] = (ins.mnemonic, ins.op_str)
        break

# --- 1. movw/movt pairs materialising the address ---
pairs = []
for va, (mn, op) in one.items():
    if mn == 'movw' and re.search(r'#0x%04x' % LOW, op, re.I):
        reg = op.split(',')[0].strip()
        nxt = one.get(va + 4)
        if nxt and nxt[0] == 'movt' and nxt[1].startswith(reg + ',') \
                and re.search(r'#0x%04x' % HIGH, nxt[1], re.I):
            pairs.append((va, reg))
emit('--- 1. movw/movt pairs materialising 0x%08X ---' % TARGET)
emit('count = %d' % len(pairs))
for va, reg in pairs:
    emit('  VA 0x%08X  %s' % (va, reg))
emit('')

# --- 2. raw literal-pool occurrences ---
pat = struct.pack('<I', TARGET)
lits = [m.start() for m in re.finditer(re.escape(pat), d)]
emit('--- 2. raw 32-bit literal occurrences ---')
emit('count = %d  %s' % (len(lits), [hex(off2va(x)) for x in lits[:10]]))
emit('')

# --- 3. access sites: window disassembly around each pair ---
emit('--- 3. reads/writes through the materialised register ---')
accesses = []
for va, reg in pairs:
    s = max(VADDR, va - 8)
    e = min(VADDR + FSZ, va + 48)
    for ins in md.disasm(d[va2off(s):va2off(e)], s):
        if re.search(r'\[' + re.escape(reg) + r'(?:\s*,|\])', ins.op_str):
            kind = 'WRITE' if ins.mnemonic.startswith('str') else 'READ'
            accesses.append((ins.address, kind, ins.mnemonic, ins.op_str, va))
for addr, kind, mn, op, mat in sorted(accesses):
    emit('  VA 0x%08X  %-5s %-8s %-30s  (materialised @0x%08X)' %
         (addr, kind, mn, op, mat))
emit('')

# --- 4. all pc-relative literal loads pointing at the raw value ---
emit('--- 4. pc-relative literal loads of the address ---')
con = []
litvas = {off2va(x) for x in lits}
for va, (mn, op) in one.items():
    if mn.startswith('ldr') and '[pc' in op:
        m = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
        if not m:
            continue
        try:
            disp = int(m.group(1), 16)
        except ValueError:
            continue
        tgt = (va + 8 + disp) & ~3
        if tgt in litvas:
            con.append((va, mn, op, tgt))
for va, mn, op, tgt in sorted(con):
    emit('  VA 0x%08X  %-8s %-34s -> 0x%08X' % (va, mn, op, tgt))
emit('consumers = %d' % len(con))
emit('')

# --- 5. full context of the known G-function site ---
emit('--- 5. G function region 0x91D39D78..0x91D39DD4 ---')
s, e = 0x91D39D78, 0x91D39DD4
for ins in md.disasm(d[va2off(s):va2off(e)], s):
    emit('  %08X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
emit('')

# --- 6. Is the flag inside .bss? (memsz > filesz) ---
bss_start, bss_end = VADDR + FSZ, VADDR + MSZ
emit('--- 6. address space classification ---')
emit('  .bss range: 0x%08X .. 0x%08X' % (bss_start, bss_end))
emit('  target 0x%08X in .bss: %s' % (TARGET, bss_start <= TARGET < bss_end))
emit('  => value initialised to 0 by crt0; any non-zero value comes from a store.')
emit('')
emit('=== Boundary ===')
emit('Covers direct movw/movt materialisation and pc-relative literals in the')
emit('single PT_LOAD segment. Indirect pointer tables / computed registers /')
emit('other segments are not covered. Static analysis only, no device operation.')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print('\nwrote', OUT)
