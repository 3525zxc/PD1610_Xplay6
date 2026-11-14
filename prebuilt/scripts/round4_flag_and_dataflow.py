# -*- coding: utf-8 -*-
"""Round-4: (P0) BL->BEQ flag source closure, exit->fastboot string path,
G callers return-value dataflow, 0x91D3AD40 read-point adjudication."""
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

FLAGMOD = {'cmp','cmn','tst','teq','teq','adds','subs','adcs','sbcs','ands','orrs',
           'eors','bics','movs','mvns','muls','mlas','lsls','lsrs','asrs','rorrs','negs'}

def dis(s, e):
    return list(md.disasm(d[O + (s - V):O + (e - V)], s))

def show_raw(name, s, e):
    """raw words + disasm + flag-source annotation"""
    emit('=== %s  0x%08X..0x%08X (raw bytes + flag-source) ===' % (name, s, e))
    last_flag = None
    for i in dis(s, e):
        off = O + (i.address - V)
        raw = d[off:off+4].hex()
        flagnote = ''
        if i.mnemonic in FLAGMOD:
            last_flag = (i.address, '%s %s' % (i.mnemonic, i.op_str))
            flagnote = '   ; <<< sets NZCV'
        elif i.mnemonic in ('bl','blx'):
            flagnote = '   ; (BL: LR only, no NZCV)'
        elif i.mnemonic.startswith('b'):
            flagnote = '   ; branch tests: %s (set @0x%08X)' % (
                last_flag[1] if last_flag else '???STALE', last_flag[0] if last_flag else 0)
        emit('  %08X  %s  %-8s %-26s%s' % (i.address, raw, i.mnemonic, i.op_str, flagnote))
    emit('')

# ---------- 1) P0: loop core, raw-verified ----------
show_raw('loop core', 0x91D412AC, 0x91D41300)
show_raw('pre-loop entry', 0x91D41294, 0x91D412B0)

# ---------- 2) getter full function: all exits ----------
emit('=== 0x91D0AED4 full function ..0x91D0AF10, NZCV audit ===')
for i in dis(0x91D0AED4, 0x91D0AF10):
    off = O + (i.address - V)
    raw = d[off:off+4].hex()
    note = ''
    if i.mnemonic in FLAGMOD: note = '   ; <<< sets NZCV'
    if i.mnemonic in ('pop',) or 'pc}' in i.op_str: note = '   ; <<< RETURN (flag state here = caller BEQ source if no CMP follows)'
    emit('  %08X  %s  %-8s %-28s%s' % (i.address, raw, i.mnemonic, i.op_str, note))
emit('')

# support fns (flag sources after their returns)
for nm, s, e in [('0x91D0A4E4', 0x91D0A4E4, 0x91D0A540),
                 ('0x91D0AD64', 0x91D0AD64, 0x91D0AED4),
                 ('0x91D0A894', 0x91D0A894, 0x91D0A910)]:
    show_raw('support fn ' + nm, s, e)

# ---------- 3) function start of loop (prologue scan backward) ----------
emit('=== prologue scan backward from 0x91D412AC ===')
found = []
for va in sorted(one):
    if 0x91D40000 <= va < 0x91D412AC:
        mn, op = one[va]
        if mn == 'push' and 'lr' in op and ('pc' not in op):
            found.append((va, op))
if found:
    start = found[-1]
    emit('  candidate function start: 0x%08X  push %s' % (start[0], start[1]))
    # r5 initialisation inside function
    for va in sorted(one):
        if start[0] <= va <= 0x91D412B0:
            mn, op = one[va]
            if mn in ('mov','movw','ldr','eor','rsb','add','sub','and','orr','mvn') and re.match(r'^r5[,\s]', op):
                emit('    r5-def: %08X  %s %s' % (va, mn, op))
emit('')

# ---------- 4) exit path 0x91D4141C.. and "Reverting" string ----------
emit('=== exit path 0x91D4141C..0x91D41480 ===')
for i in dis(0x91D4141C, 0x91D41480):
    off = O + (i.address - V)
    raw = d[off:off+4].hex()
    emit('  %08X  %s  %-8s %s' % (i.address, raw, i.mnemonic, i.op_str))
emit('')

needle = b'Reverting to fastboot'
pos = d.find(needle)
emit('=== "Reverting to fastboot" string search ===')
while pos != -1:
    sva = V + pos - O + (0 if pos >= O else 0)
    emit('  file off 0x%06X  VA(if in PT_LOAD) 0x%08X  ctx: %r' % (pos, V + pos - O if pos >= O else -1, d[pos-16:pos+72]))
    pos = d.find(needle, pos + 1)
emit('')
# literal pools pointing at string VA
if pos is not None:
    pass
strvas = set()
pos = d.find(needle)
while pos != -1:
    if pos >= O and pos < O + FSZ:
        strvas.add(V + pos - O)
    pos = d.find(needle, pos + 1)
for sv in strvas:
    emit('  pool entries holding VA 0x%08X:' % sv)
    for o in range(0, len(code) - 3, 4):
        val = struct.unpack_from('<I', code, o)[0]
        if sv - 4 <= val <= sv + 8:
            refs = [va for va, (mn, op) in sorted(one.items())
                    if (mn.startswith('ldr')) and '[pc' in op
                    and re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    and ((va + 8) & ~3) + int(re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op).group(1), 16) == o + V]
            emit('    pool@0x%08X val=0x%08X  refs: %s' % (V + o, val,
                 ', '.join('0x%08X' % r for r in refs) or '(unreferenced)'))
emit('')

# ---------- 5) G callers: return-value dataflow ----------
show_raw('G caller1 0x91D3C84C -0x20..+0x60', 0x91D3C84C - 0x20, 0x91D3C84C + 0x60)
show_raw('G caller2 0x91D3D764 -0x20..+0x60', 0x91D3D764 - 0x20, 0x91D3D764 + 0x60)
show_raw('G caller3 0x91D3E380 -0x20..+0x60', 0x91D3E380 - 0x20, 0x91D3E380 + 0x60)

# ---------- 6) 0x91D3AD40 adjudication ----------
show_raw('round2 read point 0x91D3AD40 -0x30..+0x30', 0x91D3AD40 - 0x30, 0x91D3AD40 + 0x30)

# ---------- 7) all reads of 0x92007DAC full listing (recount) ----------
emit('=== all references to 0x92007DAC (literal pool + movw/movt) ===')
tgt = 0x92007DAC
for o in range(0, len(code) - 3, 4):
    val = struct.unpack_from('<I', code, o)[0]
    if val == tgt:
        refs = []
        for va, (mn, op) in sorted(one.items()):
            if mn.startswith(('ldr', 'str')) and '[pc' in op:
                m = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                if m and ((va + 8) & ~3) + int(m.group(1), 16) == o + V:
                    refs.append('0x%08X %s %s' % (va, mn, op))
        emit('  pool@0x%08X: %s' % (V + o, ' | '.join(refs) or '(no pc-rel ref)'))
lo, hi = tgt & 0xFFFF, tgt >> 16
for a, (mn, op) in sorted(one.items()):
    if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
        reg = op.split(',')[0].strip()
        nx = one.get(a + 4)
        if nx and nx[0] == 'movt' and nx[1].startswith(reg + ',') and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
            emit('  movw/movt @0x%08X (%s)' % (a, reg))
emit('')

open(r'D:\16\PD1610_81\work\round4_flag_dataflow.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_flag_dataflow.txt')
