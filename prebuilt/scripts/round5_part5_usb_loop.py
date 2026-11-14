# -*- coding: utf-8 -*-
"""Round-5 part5: fastboot 命令处理函数与其轮询循环；update_cmdline 调用时序"""
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

def dump(name, s, maxlen=0x260):
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

def fn_start(before):
    cands = [va for va, (mn, op) in sorted(one.items())
             if before - 0x2000 <= va < before and mn == 'push' and 'lr' in op and 'pc' not in op]
    return cands[-1] if cands else None

def callers_of(t):
    br = ['0x%08X(%s)' % (va, one[va][0]) for va, (mn, op) in sorted(one.items())
          if mn in ('bl', 'b') and ('0x%08x' % t) in op]
    return br

# ---------- A. fastboot 命令处理函数 ----------
emit('=' * 72)
emit('A. fastboot 命令处理区 0x91D42500 附近')
emit('=' * 72)
dump('0x91D424E0..0x91D42590', 0x91D424E0, 0xB0)
dump('0x91D42740..0x91D427C0', 0x91D42740, 0x80)
fs = fn_start(0x91D42500)
emit('  fastboot-handler 函数起点 ~0x%08X  callers: %s' % (fs, ', '.join(callers_of(fs)) or '(none)'))
emit('')

# ---------- B. FASTBOOT MODE 横幅处 ----------
emit('=' * 72)
emit('B. "FASTBOOT MODE" 打印处 0x91D143D8 上下文')
emit('=' * 72)
dump('0x91D143A0..0x91D14440', 0x91D143A0, 0xA0)
fs2 = fn_start(0x91D143D8)
emit('  banner 函数起点 ~0x%08X  callers: %s' % (fs2, ', '.join(callers_of(fs2)) or '(none)'))
emit('')

# ---------- C. update_cmdline(0x91D3AB94) 的调用者链 ----------
emit('=' * 72)
emit('C. update_cmdline 时序：0x91D3BD58 所在函数与调用者')
emit('=' * 72)
dump('0x91D3BD40..0x91D3BD90', 0x91D3BD40, 0x50)
fs3 = fn_start(0x91D3BD58)
emit('  0x91D3BD58 所在函数 ~0x%08X  callers: %s' % (fs3, ', '.join(callers_of(fs3)) or '(none)'))
emit('')
dump('该函数头 0x%08X' % fs3, fs3, 0x70)
emit('  该函数内部被调函数：')
for va, (mn, op) in sorted(one.items()):
    if fs3 <= va < fs3 + 0x400 and mn in ('bl', 'blx'):
        emit('    0x%08X %s %s' % (va, mn, op))
emit('')

# ---------- D. 谁调用 0x91D3C3F0 的第二个入口 0x91D3D8DC 所在函数 ----------
emit('=' * 72)
emit('D. boot 主函数两个入口的上下文')
emit('=' * 72)
dump('0x91D3D8B0..0x91D3D8F0', 0x91D3D8B0, 0x40)
fs4 = fn_start(0x91D3D8DC)
emit('  0x91D3D8DC 所在函数 ~0x%08X  callers: %s' % (fs4, ', '.join(callers_of(fs4)) or '(none)'))
emit('')

open(r'D:\16\PD1610_81\work\round5_task5.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round5_task5.txt')
