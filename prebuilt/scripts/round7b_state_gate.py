#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round 7 (corrected): aboot 8.19.16 Security Error 状态机 [0x91D9DD98] 完整数据流。
映射修正：file_off = 0x8000 + (VA - 0x91D00000)，p_filesz=0x2FED40, p_memsz=0x331814。
"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
FOFF = 0x8000
IMG = r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin'
data = open(IMG, 'rb').read()

STATE = 0x91D9DD98
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = False


def va2off(va):
    o = FOFF + (va - BASE)
    return o if 0 <= o < len(data) else None


def dis(va, n=80, label='', stop_ret=True):
    o = va2off(va)
    print('\n' + '=' * 76)
    print('=== %s   VA %08X  off 0x%X' % (label, va, o))
    print('=' * 76)
    if o is None:
        print('  [unmapped]')
        return
    cnt = 0
    for i in md.disasm(data[o:o + n * 4], va):
        print('%08X  %-7s %s' % (i.address, i.mnemonic, i.op_str))
        cnt += 1
        if stop_ret and i.mnemonic in ('pop',) and 'pc' in i.op_str:
            print('   ; --- ret ---')
            break
        if stop_ret and i.mnemonic == 'bx' and 'lr' in i.op_str:
            print('   ; --- ret ---')
            break
    print('  (%d instr shown)' % cnt)


def imm_ops(lo16, hi16):
    """返回所有 movw/movt 立即数为指定值的指令 (va, mnemonic, rd, imm)"""
    out = []
    for i in range(FOFF, len(data) - 4, 4):
        ins = struct.unpack_from('<I', data, i)[0]
        if (ins & 0x0FF00000) == 0x03000000:
            imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
            if imm == lo16:
                out.append((BASE + i - FOFF, 'movw', (ins >> 12) & 0xF, imm, i))
        elif (ins & 0x0FF00000) == 0x03400000:
            imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
            if imm == hi16:
                out.append((BASE + i - FOFF, 'movt', (ins >> 12) & 0xF, imm, i))
    return out


print('image %d bytes; STATE VA %08X static=%d' % (
    len(data), STATE, struct.unpack_from('<I', data, va2off(STATE))[0]))

# ---------- A. 谁引用了 STATE ----------
print('\n' + '#' * 76)
print('# A. movw/movt 引用 0x%08X 的全部指令' % STATE)
print('#' * 76)
lo, hi = STATE & 0xFFFF, (STATE >> 16) & 0xFFFF
ops = imm_ops(lo, hi)
movw = [o for o in ops if o[1] == 'movw']
movt = [o for o in ops if o[1] == 'movt']
print('movw #0x%04X : %s' % (lo, [(hex(o[0]), 'r%d' % o[2]) for o in movw]))
print('movt #0x%04X : %s' % (hi, [(hex(o[0]), 'r%d' % o[2]) for o in movt]))
pairs = []
for w in movw:
    for t in movt:
        if w[2] == t[2] and 0 < abs(t[4] - w[4]) <= 64:
            pairs.append((min(w[0], t[0]), w[2]))
print('\n配对结果 (addr, reg):')
for a, r in sorted(set(pairs)):
    print('  %08X  r%d' % (a, r))

# ---------- B. handler ----------
dis(0x91D131E8, 90, 'handler 0x91D131E8 (Security Error 打印点)')
dis(0x91D132A4, 90, 'real func 0x91D132A4')

# ---------- C. verify wrapper ----------
dis(0x91D12DD0, 130, 'verify wrapper 0x91D12DD0')

# ---------- D. 三个写入者 ----------
for va in (0x91D12D6C, 0x91D12DB8, 0x91D130B8):
    dis(va - 0x60, 70, 'writer ctx %08X' % va)
