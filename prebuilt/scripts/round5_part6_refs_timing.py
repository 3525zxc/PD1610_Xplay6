# -*- coding: utf-8 -*-
"""Round-5 part6: fastboot USB 轮询入口 + cmdline/G 时序精确化"""
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

def fn_start(before, back=0x3000):
    cands = [va for va, (mn, op) in sorted(one.items())
             if before - back <= va < before and mn == 'push' and 'lr' in op and 'pc' not in op]
    return cands[-1] if cands else None

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
                sv = cstr(va)
                extra = '   ; = 0x%08X%s' % (va, (' = %r' % sv) if sv else '')
        emit('  %08X  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, extra))
    emit('')

# ---------- A. fastboot 关键函数的引用来源 ----------
emit('=' * 72)
emit('A. fastboot 相关函数引用来源（找函数指针注册表 / 轮询循环）')
emit('=' * 72)
for t, nm in ((0x91D42414, 'fastboot cmd dispatcher?'),
              (0x91D41E18, 'OKAY/FAIL writer'),
              (0x91D425A8, 'FAIL helper'),
              (0x91D42740, 'unknown-cmd path'),
              (0x91D1430C, 'FASTBOOT MODE banner fn'),
              (0x91D14788, 'banner caller'),
              (0x91D13498, 'banner caller b'),
              (0x91D40848, 'getid?'),
              (0x91D47AC4, 'string out')):
    emit('  0x%08X %s' % (t, nm))
    for x in xrefs(t)[:5]: emit('      %s' % x)
    br = branches(t)
    if br: emit('      branch: %s' % ', '.join(br))
    emit('')

# ---------- B. cmdline 调用点 vs G 调用点的函数归属与先后 ----------
emit('=' * 72)
emit('B. update_cmdline 调用点 与 G 调用点 的函数归属/先后')
emit('=' * 72)
sites = {'G@0x91D3C84C': 0x91D3C84C, 'G@0x91D3D764': 0x91D3D764, 'G@0x91D3E380': 0x91D3E380,
         'cmdline@0x91D3CB2C': 0x91D3CB2C, 'cmdline@0x91D3D308': 0x91D3D308, 'cmdline@0x91D3E5F4': 0x91D3E5F4}
for k, v in sites.items():
    fs = fn_start(v)
    emit('  %-24s site=0x%08X  函数起点~0x%08X  函数内 G 调用点: %s' % (
        k, v, fs,
        ', '.join('0x%08X' % g for g in (0x91D3C84C, 0x91D3D764, 0x91D3E380) if fs and fs <= g <= v + 0x900) or '—'))
emit('')

# ---------- C. usb / fastboot mode 相关字符串 ----------
emit('=' * 72)
emit('C. usb/dload/fastboot 相关字符串')
emit('=' * 72)
for needle in (b'usb', b'udc', b'dload', b'fastboot mode', b'bootloader', b'enter fastboot'):
    pos = 0; hits = 0
    while True:
        pos = d.find(needle, pos)
        if pos == -1: break
        if O <= pos < O + FSZ:
            va = V + pos - O
            s = cstr(va, 60)
            if s and s[0].isascii():
                emit('  0x%08X: %r' % (va, s))
                for x in xrefs(va)[:3]: emit('        %s' % x)
                hits += 1
                if hits > 6: break
        pos += 1
emit('')

open(r'D:\16\PD1610_81\work\round5_task6.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task6.txt')
