# -*- coding: utf-8 -*-
"""Round-6: 定位 aboot 8.19.16 中「boot image 验签失败 → 重启」路径。
策略：先枚举 reboot/verif/tamper/unlock 相关字符串及其引用函数，再反向追调用者。"""
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

def cstr(va, maxn=120):
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
                        out.append(('pool', o + V, va, mn, op))
    lo, hi = target & 0xFFFF, target >> 16
    for a, (mn, op) in sorted(one.items()):
        if mn == 'movw' and re.search(r'#0x%04x\b' % lo, op, re.I):
            nx = one.get(a + 4)
            if nx and nx[0] == 'movt' and re.search(r'#0x%04x\b' % hi, nx[1], re.I):
                out.append(('movw', a, a + 4, mn, op))
    return out

def fn_start(before, back=0x6000):
    cands = [va for va, (mn, op) in sorted(one.items())
             if before - back <= va < before and mn == 'push' and 'lr' in op and 'pc' not in op]
    return cands[-1] if cands else None

# ---------- A. 关键字符串枚举 ----------
emit('=' * 72)
emit('A. reboot / verif / tamper / unlock 相关字符串及其引用')
emit('=' * 72)
needles = [b'Rebooting', b'reboot', b'Reboot', b'Verification failed', b'verification',
           b'tamper', b'Tamper', b'unlocked', b'Unlock', b'signature', b'Signature',
           b'Could not do normal boot', b'not signed', b'invalid signature', b'Bad magic']
seen = set()
for nd in needles:
    pos = 0
    while True:
        pos = d.find(nd, pos)
        if pos == -1: break
        if O <= pos < O + FSZ:
            va = V + pos - O
            # 定位字符串起点（回退到可打印起点）
            start = va
            while start > V and 32 <= d[O + (start - 1 - V)] < 127:
                start -= 1
            s = cstr(start, 140)
            if s and s not in seen and len(s) < 130:
                seen.add(s)
                emit('  0x%08X : %r' % (start, s))
                for kind, a, b, mn, op in xrefs(start)[:3]:
                    fs = fn_start(a)
                    emit('        <- %s@0x%08X  函数起点~0x%08X' % (kind, a, fs if fs else 0))
        pos += 1
emit('')

open(r'D:\16\PD1610_81\work\round6_strings.txt', 'w', encoding='utf-8').write('\n'.join(OUT))
print('written work\\round6_strings.txt')
