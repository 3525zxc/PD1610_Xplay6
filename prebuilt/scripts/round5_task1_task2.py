# -*- coding: utf-8 -*-
"""Round-5: (1) 自动校验返回码分类  (2) 状态非零路径三函数全量  (3) flag 写读与状态数组写入者穷举"""
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

def cstr(va, maxn=80):
    off = O + (va - V)
    if off < 0 or off >= len(d): return None
    end = d.find(b'\x00', off)
    return d[off:min(end, off + maxn)].decode('latin1', 'replace')

# ============ 任务一：返回码分类自动校验 ============
emit('=' * 72)
emit('TASK1  自动校验：bl 0x91D3C3F0 返回值 ret 的分类')
emit('  指令：sub r0,r0,#4 | cmp r0,#5 | bhi EXIT | lsl r3,r5(=1),r0 | tst r3,#0x27 | beq EXIT')
emit('=' * 72)
emit('  ret | ret-4 | >5? | 1<<(ret-4) | &0x27 | Z | 路径')
rows = []
for ret in range(0, 13):
    r0 = (ret - 4) & 0xFFFFFFFF
    bhi = (r0 > 5)
    if bhi:
        path = 'EXIT(0x91D4141C) via BHI'
        z = '-'; mask = '-'; sh = '-'
    else:
        sh = (1 << r0) & 0xFFFFFFFF
        mask = sh & 0x27
        z = 1 if mask == 0 else 0
        path = ('EXIT(0x91D4141C) via TST;BEQ' if z else 'CONTINUE -> 状态检查 [0x92002738]')
    emit('  %3d | %6d | %-4s | %-9s | %-4s | %-1s | %s' % (
        ret, r0, bhi,
        hex(sh) if sh != '-' else '-',
        hex(mask) if mask != '-' else '-',
        z, path))
    rows.append((ret, path))
CONT = sorted(r for r, p in rows if p.startswith('CONTINUE'))
EXIT_TST = sorted(r for r, p in rows if p.startswith('EXIT') and 'TST' in p)
EXIT_BHI = sorted(r for r, p in rows if p.startswith('EXIT') and 'BHI' in p)
emit('')
emit('  ⇒ 进入状态检查的 ret : %s' % CONT)
emit('  ⇒ TST;BEQ 退出的 ret  : %s' % EXIT_TST)
emit('  ⇒ BHI 直接退出的 ret  : %s' % EXIT_BHI)
assert CONT == [4, 5, 6, 9], CONT
assert EXIT_TST == [7, 8], EXIT_TST
assert EXIT_BHI == [0, 1, 2, 3, 10, 11, 12], EXIT_BHI
emit('  ASSERT PASS ✓  ret∈{4,5,6,9}→状态检查；ret∈{7,8}→EXIT；ret<4 或 ret>9→BHI EXIT')
emit('')

# ============ 任务二：状态非零路径三函数全量 ============
def func_dump(name, s, maxlen=0x900):
    """dump until pop{..pc} ; collect str/ldr targets"""
    emit('=== %s @0x%08X ===' % (name, s))
    writes, reads, calls = [], [], []
    regs = {}
    for i in dis(s, s + maxlen):
        extra = ''
        mn, op = i.mnemonic, i.op_str
        if mn == 'movw':
            nx = one.get(i.address + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', op)
            if nx and nx[0] == 'movt' and m:
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                regs[op.split(',')[0].strip()] = (hi << 16) | lo
                extra = '   ; %s = 0x%08X' % (op.split(',')[0].strip(), (hi << 16) | lo)
        if mn.startswith('str') and '[' in op:
            for rm in re.findall(r'\[(r\d+|ip|sp|lr)', op):
                if rm in regs:
                    writes.append((i.address, mn, op, regs[rm]))
        if mn.startswith('ldr') and '[' in op and not mn.startswith('str'):
            for rm in re.findall(r'\[(r\d+|ip|sp|lr)', op):
                if rm in regs:
                    reads.append((i.address, mn, op, regs[rm]))
        if mn in ('bl', 'blx'):
            calls.append((i.address, mn, op))
        emit('  %08X  %-8s %s%s' % (i.address, mn, op, extra))
        if mn == 'pop' and 'pc' in op:
            break
    emit('  -- writes --')
    for a, mn, op, t in writes: emit('     %08X %s %s  => 0x%08X' % (a, mn, op, t))
    emit('  -- reads  --')
    for a, mn, op, t in reads: emit('     %08X %s %s  <= 0x%08X' % (a, mn, op, t))
    emit('  -- calls  --')
    for a, mn, op in calls: emit('     %08X %s %s' % (a, mn, op))
    emit('')
    return writes, reads, calls

for nm, st in (('0x91D0A4E4', 0x91D0A4E4), ('0x91D0AD64', 0x91D0AD64), ('0x91D0A894', 0x91D0A894)):
    func_dump(nm, st)

# ============ 任务二附：状态数组 0x9200272C 邻域所有读写穷举 ============
emit('=' * 72)
emit('TASK2b  0x9200272C..0x92002744 邻域所有直接读写（literal pool + movw/movt）')
emit('=' * 72)
targets = [0x9200272C + 4 * k for k in range(8)]
for tgt in targets:
    hits = []
    for o in range(0, len(code) - 3, 4):
        val = struct.unpack_from('<I', code, o)[0]
        if val == tgt:
            for va, (mn, op) in sorted(one.items()):
                if mn.startswith(('ldr', 'str')) and '[pc' in op:
                    mm = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if mm and ((va + 8) & ~3) + int(mm.group(1), 16) == o + V:
                        hits.append('pool@0x%08X <- 0x%08X %s %s' % (V + o, va, mn, op))
    for a, (mn, op) in sorted(one.items()):
        if mn == 'movw' and re.search(r'#0x%04x\b' % (tgt & 0xFFFF), op, re.I):
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and re.search(r'#0x%04x\b' % (tgt >> 16), nx[1], re.I):
                hits.append('movw/movt @0x%08X %s' % (a, op))
    emit('  0x%08X : %s' % (tgt, ' | '.join(hits) if hits else '(无直接引用)'))
emit('')

open(r'D:\16\PD1610_81\work\round5_task1_task2.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task1_task2.txt')
