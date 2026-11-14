# -*- coding: utf-8 -*-
"""Round-5 part2: 数组元素读写方向、fastboot_init 全函数与 USB 循环、flag 时序、模块框架"""
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

def cstr(va, maxn=100):
    off = O + (va - V)
    if off < 0 or off >= len(d): return None
    end = d.find(b'\x00', off)
    return d[off:min(end, off + maxn)].decode('latin1', 'replace')

def dump(name, s, maxlen=0x1400, stop_pop=True):
    emit('=== %s @0x%08X ===' % (name, s))
    for i in dis(s, s + maxlen):
        extra = ''
        if i.mnemonic == 'movw':
            nx = one.get(i.address + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', i.op_str)
            if nx and nx[0] == 'movt' and m:
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                extra = '   ; = 0x%08X' % ((hi << 16) | lo)
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
        if stop_pop and i.mnemonic == 'pop' and 'pc' in i.op_str:
            break
    emit('')

# ---------- A. 数组邻域每个引用的读/写方向 ----------
emit('=' * 72)
emit('A. 0x9200272C..0x92002740 每个物化点的读写方向与上下文')
emit('=' * 72)
for tgt in (0x9200272C, 0x92002730, 0x92002734, 0x92002738, 0x9200273C, 0x92002740):
    refs = []
    for a, (mn, op) in sorted(one.items()):
        if mn == 'movw' and re.search(r'#0x%04x\b' % (tgt & 0xFFFF), op, re.I):
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and re.search(r'#0x%04x\b' % (tgt >> 16), nx[1], re.I):
                reg = op.split(',')[0].strip()
                refs.append(a)
    for o in range(0, len(code) - 3, 4):
        if struct.unpack_from('<I', code, o)[0] == tgt:
            for va, (mn, op) in sorted(one.items()):
                if mn.startswith('ldr') and '[pc' in op:
                    mm = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if mm and ((va + 8) & ~3) + int(mm.group(1), 16) == o + V:
                        refs.append(va)
    emit('--- 0x%08X ---' % tgt)
    for a in sorted(set(refs)):
        ctx = list(dis(max(a - 0x18, 0x91D00000), a + 0x20))
        # find the movw/movt pair index
        kind = []
        for i in ctx:
            if i.address == a:
                kind.append('MAT@0x%08X %s %s' % (i.address, i.mnemonic, i.op_str))
        # look ahead 8 instr for usage of the reg
        reg = None
        for i in ctx:
            if i.address == a and i.mnemonic == 'movw':
                reg = i.op_str.split(',')[0].strip()
        usage = []
        if reg:
            seen = False
            for i in ctx:
                if i.address == a: seen = True; continue
                if seen and ('[%s]' % reg) in i.op_str.replace(' ', ''):
                    usage.append('0x%08X %s %s' % (i.address, i.mnemonic, i.op_str))
                    if len(usage) >= 3: break
        rd = any('ldr' in u for u in usage); wr = any('str' in u for u in usage)
        emit('   %s  [%s]' % (', '.join(kind), 'READ+WRITE' if (rd and wr) else ('READ' if rd else ('WRITE' if wr else '?'))))
        for u in usage: emit('        %s' % u)
    emit('')

# ---------- B. fastboot_init 全函数 + USB 轮询入口 ----------
emit('=' * 72)
emit('B. fastboot_init 0x91D40974 全函数尾部（找是否有轮询循环）')
emit('=' * 72)
dump('0x91D40974', 0x91D40974, 0x1600)
emit('callers of 0x91D40974: %s' % ', '.join(
    '0x%08X' % va for va, (mn, op) in sorted(one.items()) if mn in ('bl', 'b') and '0x91d40974' in op))
emit('')

# ---------- C. 模块框架：0x91D38350 与 0x91D39B80/0x91D39BC4 ----------
emit('=' * 72)
emit('C. 模块框架：0x91D38350 函数（调用遍历器）上下文')
emit('=' * 72)
dump('0x91D38350', 0x91D38350, 0x400)

open(r'D:\16\PD1610_81\work\round5_task3.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task3.txt')
