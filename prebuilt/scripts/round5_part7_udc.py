# -*- coding: utf-8 -*-
"""Round-5 part7: UDC / USB gadget 注册与 fastboot 轮询循环"""
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

def fn_start(before, back=0x4000):
    cands = [va for va, (mn, op) in sorted(one.items())
             if before - back <= va < before and mn == 'push' and 'lr' in op and 'pc' not in op]
    return cands[-1] if cands else None

def dump(name, s, maxlen=0x180):
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

# ---------- A. fastboot 命令分发函数的真起点与引用 ----------
emit('=' * 72)
emit('A. fastboot 命令分发 / UDC 关键函数引用')
emit('=' * 72)
for site, nm in ((0x91D42774, "'unknown command' 所在函数"),
                  (0x91D0C3A4, "'udc_start()' 所在函数"),
                  (0x91D33A10, "'udc_handle_setup: SET_CONFIGURATION' 所在函数"),
                  (0x91D8559F, "'fastboot mode...' 所在函数"),
                  (0x91D85712, "'fastboot mode.' 所在函数")):
    fs = fn_start(site)
    emit('  %s : 函数起点~%s' % (nm, ('0x%08X' % fs) if fs else '(未定位)'))
    if fs:
        for x in xrefs(fs)[:6]: emit('        %s' % x)
        br = branches(fs)
        if br: emit('        branch: %s' % ', '.join(br))
    for x in xrefs(site)[:4]: emit('        [site] %s' % x)
    emit('')

# ---------- B. udc_start 函数体 + 调用者 ----------
emit('=' * 72)
emit('B. udc_start() 函数体与调用者')
emit('=' * 72)
fs = fn_start(0x91D0C3A4)
dump('udc_start ~0x%08X' % fs, fs, 0x120)
emit('  callers of 0x%08X: %s' % (fs, ', '.join(branches(fs)) or '(none)'))
emit('')

# ---------- C. udc_handle_setup 所在函数（USB setup 包处理）----------
emit('=' * 72)
emit('C. udc_handle_setup 函数（USB 事件入口）')
emit('=' * 72)
fs2 = fn_start(0x91D33A10)
dump('udc_handle_setup ~0x%08X' % fs2, fs2, 0x160)
emit('  callers of 0x%08X: %s' % (fs2, ', '.join(branches(fs2)) or '(none)'))
emit('')

open(r'D:\16\PD1610_81\work\round5_task7.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task7.txt')
