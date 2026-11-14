# -*- coding: utf-8 -*-
"""Round-5 part4: fastboot USB 轮询入口搜索 + 模块框架调用者 + flag 读点时序"""
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

def xrefs_to_va(target):
    """返回 [(kind, addr, text)]：literal-pool 引用 与 movw/movt 物化"""
    out = []
    for o in range(0, len(code) - 3, 4):
        if struct.unpack_from('<I', code, o)[0] == target:
            for va, (mn, op) in sorted(one.items()):
                if mn.startswith(('ldr', 'str')) and '[pc' in op:
                    mm = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if mm and ((va + 8) & ~3) + int(mm.group(1), 16) == o + V:
                        out.append(('pool@0x%08X' % (V + o), va, '%s %s' % (mn, op)))
    lo, hi = target & 0xFFFF, target >> 16
    for a, (mn, op) in sorted(one.items()):
        if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
                out.append(('movw/movt', a, '%s | %s' % (op, nx[1])))
    return out

def dump(name, s, maxlen=0x200):
    emit('=== %s @0x%08X ===' % (name, s))
    for i in dis(s, s + maxlen):
        extra = ''
        if i.mnemonic == 'movw':
            nx = one.get(i.address + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', i.op_str)
            if nx and nx[0] == 'movt' and m:
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                va = (hi << 16) | lo
                extra = '   ; = 0x%08X%s' % (va, (' = %r' % cstr(va)) if cstr(va) else '')
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
    emit('')

# ---------- A. fastboot 协议字符串 → 代码引用 ----------
emit('=' * 72)
emit('A. fastboot 协议字符串与代码引用')
emit('=' * 72)
for needle in (b'FASTBOOT', b'OKAY', b'FAIL', b'total time', b'fastboot: ', b'Invalid command',
               b'unknown command', b'download:', b'boot:', b'flash:', b'continue boot'):
    pos = 0
    while True:
        pos = d.find(needle, pos)
        if pos == -1: break
        if O <= pos < O + FSZ:
            va = V + pos - O
            emit('  str 0x%08X: %r' % (va, cstr(va, 60)))
            for kind, a, txt in xrefs_to_va(va)[:4]:
                emit('      <- %s @0x%08X (%s)' % (kind, a, txt))
        pos += 1
emit('')

# ---------- B. 模块框架调用者 ----------
emit('=' * 72)
emit('B. 模块框架：0x91D39B80 / 0x91D39BC4 的引用来源')
emit('=' * 72)
for t in (0x91D39B80, 0x91D39BC4, 0x91D40FCC):
    emit('  target 0x%08X:' % t)
    for kind, a, txt in xrefs_to_va(t):
        emit('      %s @0x%08X (%s)' % (kind, a, txt))
    br = ['0x%08X(%s)' % (va, one[va][0]) for va, (mn, op) in sorted(one.items())
          if mn in ('bl', 'b') and ('0x%08x' % t) in op]
    emit('      branch: %s' % (', '.join(br) or '(none)'))
emit('')
dump('0x91D39B40..0x91D39BC4 region', 0x91D39B40, 0x90)

# ---------- C. flag 读点#1 的上层调用者（时序） ----------
emit('=' * 72)
emit('C. flag 活读点 0x91D3AD40 所在函数与调用者（时序）')
emit('=' * 72)
cands = [va for va, (mn, op) in sorted(one.items())
         if 0x91D38000 <= va < 0x91D3AD40 and mn == 'push' and 'lr' in op and 'pc' not in op]
emit('  prologue candidates before 0x91D3AD40: %s' % ', '.join('0x%08X' % x for x in cands[-4:]))
if cands:
    fn = cands[-1]
    emit('  function start = 0x%08X' % fn)
    for t in (fn,):
        emit('  callers of 0x%08X:' % t)
        for kind, a, txt in xrefs_to_va(t):
            emit('      %s @0x%08X (%s)' % (kind, a, txt))
        br = ['0x%08X(%s)' % (va, one[va][0]) for va, (mn, op) in sorted(one.items())
              if mn in ('bl', 'b') and ('0x%08x' % t) in op]
        emit('      branch: %s' % (', '.join(br) or '(none)'))
    dump('function head 0x%08X' % fn, fn, 0x60)
emit('')

# ---------- D. G 的调用者：谁在上层（boot 主函数）里 ----------
emit('=' * 72)
emit('D. boot 主函数 0x91D3C3F0 与 G 调用点的相对位置')
emit('=' * 72)
for t in (0x91D3C3F0, 0x91D3C84C, 0x91D3D764, 0x91D3E380, 0x91D39CB4):
    br = ['0x%08X(%s)' % (va, one[va][0]) for va, (mn, op) in sorted(one.items())
          if mn in ('bl', 'b') and ('0x%08x' % t) in op]
    emit('  0x%08X branch-calls: %s' % (t, ', '.join(br) or '(none)'))
emit('')

open(r'D:\16\PD1610_81\work\round5_task4.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task4.txt')
