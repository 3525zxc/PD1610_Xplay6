# -*- coding: utf-8 -*-
"""Round-5 part8: fastboot 分发函数引用、模式字符串引用、常驻循环定位"""
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

def xrefs(target):
    out = []
    for o in range(0, len(code) - 3, 4):
        if struct.unpack_from('<I', code, o)[0] == target:
            for va, (mn, op) in sorted(one.items()):
                if mn.startswith(('ldr', 'str')) and '[pc' in op:
                    mm = re.search(r'#(?:0x)?([0-9a-fA-F]+)\]', op)
                    if mm and ((va + 8) & ~3) + int(mm.group(1), 16) == o + V:
                        out.append('pool@0x%08X <- 0x%08X %s %s' % (V + o, va, mn, op))
    lo, hi = target & 0xFFFF, target >> 16
    for a, (mn, op) in sorted(one.items()):
        if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
                out.append('movw/movt @0x%08X' % a)
    return out

def branches(target):
    return ['0x%08X(%s %s)' % (va, one[va][0], one[va][1]) for va, (mn, op) in sorted(one.items())
            if mn in ('bl', 'b', 'blx') and ('0x%08x' % target) in op]

def dump(name, s, maxlen=0x140):
    emit('=== %s @0x%08X ===' % (name, s))
    for i in dis(s, s + maxlen):
        extra = ''
        if i.mnemonic == 'movw':
            nx = one.get(i.address + 4)
            m = re.search(r'#(0x[0-9a-f]+)\s*$', i.op_str)
            if nx and nx[0] == 'movt' and m:
                lo = int(m.group(1), 16); hi = int(re.search(r'#(0x[0-9a-f]+)', nx[1]).group(1), 16)
                va = (hi << 16) | lo
                sv = cstr(va)
                extra = '   ; = 0x%08X%s' % (va, (' = %r' % sv) if sv else '')
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
    emit('')

# ---------- A. fastboot 命令处理簇的入口探测 ----------
emit('=' * 72)
emit('A. fastboot 命令处理簇 0x91D41D00..0x91D42A00：入口与引用')
emit('=' * 72)
for cand in (0x91D41E18, 0x91D42000, 0x91D42414, 0x91D42650, 0x91D42960):
    x = xrefs(cand); br = branches(cand)
    emit('  0x%08X: pool/movw=%s  branch=%s' % (cand, (x[:3] or '—'), (br[:4] or '—')))
emit('')
dump('0x91D42650 head（是否函数起点）', 0x91D42650, 0x60)
dump('0x91D426F0..0x91D42750（分发主体）', 0x91D426F0, 0x60)

# ---------- B. fastboot 模式字符串引用 ----------
emit('=' * 72)
emit('B. fastboot 模式字符串引用')
emit('=' * 72)
for va in (0x91D8559F, 0x91D85712, 0x91D873F0):
    emit('  0x%08X %r' % (va, cstr(va, 40)))
    for x in xrefs(va): emit('      %s' % x)
    br = branches(va)
    if br: emit('      branch: %s' % ', '.join(br))
    emit('')

# ---------- C. 向后分支（循环）普查：fastboot/udc 区与模块框架区 ----------
emit('=' * 72)
emit('C. 向后分支（潜在常驻循环）')
emit('=' * 72)
for lo, hi, tag in ((0x91D41000, 0x91D42A00, 'fastboot 区'),
                    (0x91D0C000, 0x91D0D400, 'udc 区'),
                    (0x91D38000, 0x91D3E000, 'boot 主流程区'),
                    (0x91D39800, 0x91D39C00, '模块框架区')):
    emit('  -- %s 0x%08X..0x%08X --' % (tag, lo, hi))
    cnt = 0
    for va, (mn, op) in sorted(one.items()):
        if not (lo <= va < hi): continue
        if mn in ('b', 'bl') and mn == 'b':
            m = re.search(r'#0x([0-9a-f]+)', op)
            if m:
                t = int(m.group(1), 16)
                if t < va and (va - t) < 0x400:
                    emit('      0x%08X  b 0x%08X   (回跳 %d B)' % (va, t, va - t))
                    cnt += 1
                    if cnt > 14: break
    emit('')

open(r'D:\16\PD1610_81\work\round5_task8.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task8.txt')
