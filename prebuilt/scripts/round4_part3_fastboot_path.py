# -*- coding: utf-8 -*-
"""Round-4 part3: fastboot path closure + loop fn caller + G write semantics."""
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

def cstr(va, maxn=96):
    off = O + (va - V)
    end = d.find(b'\x00', off)
    return d[off:min(end, off + maxn)].decode('latin1', 'replace')

def show(name, s, e):
    emit('=== %s  0x%08X..0x%08X ===' % (name, s, e))
    for i in md.disasm(d[O + (s - V):O + (e - V)], s):
        extra = ''
        if i.mnemonic in ('movw',) and 'r0' in i.op_str.split(',')[0]:
            m = re.search(r'#(0x[0-9a-f]+)', i.op_str)
            nx = one.get(i.address + 4)
            if nx and nx[0] == 'movt':
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                extra = '   ; r0 -> 0x%08X = %r' % ((hi << 16) | lo, cstr((hi << 16) | lo, 48))
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
    emit('')

# strings referenced in flag-read#1 context
for va in (0x91D83E90, 0x91D83EC8, 0x91D83D08, 0x91D85778, 0x91D856B8, 0x91D856D0):
    emit('str 0x%08X: %r' % (va, cstr(va)))
emit('')

# pool at 0x91D415CC (arg of ldr r0,[pc,#0x3fc] @0x91D411CC)
val = struct.unpack_from('<I', d, O + (0x91D415CC - V))[0]
emit('pool@0x91D415CC = 0x%08X' % val)
try:
    emit('  as VA string: %r' % cstr(val))
except Exception:
    pass
emit('')

# identities
show('0x91D40974 (called first in tail)', 0x91D40974, 0x91D409B0)
show('0x91D0A010 (tail 2nd call)', 0x91D0A010, 0x91D0A070)
show('0x91D0206C (tail 3rd call, pooled arg)', 0x91D0206C, 0x91D020D0)

# loop fn entry: search b/movw refs to 0x91D40FCC
emit('=== refs to 0x91D40FCC ===')
refs = []
for va, (mn, op) in sorted(one.items()):
    if '0x91d40fcc' in op:
        refs.append('  %08X %s %s' % (va, mn, op))
emit('\n'.join(refs) or '  (none)')
emit('')
# maybe function starts earlier; scan pushes before 0x91D40FCC in 0x91D40800..0x91D40FCC
cands = [va for va, (mn, op) in sorted(one.items()) if 0x91D40800 <= va < 0x91D40FCC and mn == 'push' and 'pc' not in op and 'lr' in op]
emit('  push{..lr} candidates in 0x91D40800..FCC: %s' % ', '.join('0x%08X' % x for x in cands[-5:]))
emit('')

# G write branch fuller context
show('G 0x91D39D40..0x91D39E14 (write flag branch)', 0x91D39D40, 0x91D39E14)

# who calls G's containing region 0x91D39CB4 done before; check "boot into fastboot" strings
emit('=== fastboot-related strings & their code refs ===')
for needle in (b'fastboot\x00', b'FastBoot\x00', b'enter fastboot', b'fb_init'):
    pos = 0
    while True:
        pos = d.find(needle, pos)
        if pos == -1: break
        if O <= pos < O + FSZ:
            va = V + pos - O
            emit('  str VA 0x%08X: %r' % (va, cstr(va, 60)))
        pos += 1
emit('')

# 0x91D42C2C (called in tail with two args from 0x91D012E4/0x91D01320)
show('0x91D42C2C head', 0x91D42C2C, 0x91D42C70)
show('0x91D012E4 head', 0x91D012E4, 0x91D01310)
show('0x91D01320 head', 0x91D01320, 0x91D01350)

open(r'D:\16\PD1610_81\work\round4_part3.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round4_part3.txt')
