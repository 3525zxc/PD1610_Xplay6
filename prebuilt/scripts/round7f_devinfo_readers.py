#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 7f: 枚举 aboot 8.19.16 中对 devinfo 内存副本 0x91DA1318 的所有字段读取。
目的：确认 8.19.16 是否仍消费 is_unlocked(+0x10)，以及是否有别的偏移被当作解锁位。"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
FOFF = 0x8000
data = open(r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin', 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

DEVINFO = 0x91DA1318


def va2off(va):
    o = FOFF + (va - BASE)
    return o if 0 <= o < len(data) else None


def ins_at(va):
    o = va2off(va)
    return None if o is None else struct.unpack_from('<I', data, o)[0]


def dec(va):
    o = va2off(va)
    if o is None:
        return None
    g = list(md.disasm(data[o:o + 4], va))
    return g[0] if g else None


# 1) 找 movw/movt 加载 0x91DA1318 的位置
lo, hi = DEVINFO & 0xFFFF, (DEVINFO >> 16) & 0xFFFF
sites = []
for o in range(FOFF, len(data) - 4, 4):
    ins = struct.unpack_from('<I', data, o)[0]
    if (ins & 0x0FF00000) != 0x03000000:
        continue
    imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
    if imm != lo:
        continue
    rd = (ins >> 12) & 0xF
    va = BASE + o - FOFF
    for k in range(1, 9):
        nin = ins_at(va + 4 * k)
        if nin is None:
            break
        if (nin & 0x0FF00000) == 0x03400000:
            imm2 = ((nin >> 16) & 0xF) << 12 | (nin & 0xFFF)
            if ((nin >> 12) & 0xF) == rd and imm2 == hi:
                sites.append((va, rd))
                break

print('加载 0x%08X 的位置: %d' % (DEVINFO, len(sites)))
for a, r in sites:
    print('  %08X  r%d' % (a, r))

# 2) 每个点向后扫，提取 [rN, #imm] 的 ldr/ldrb/ldrh 以及寄存器传递
print('\n' + '=' * 74)
print('每个加载点后的字段访问（含寄存器传递追踪）')
print('=' * 74)
for a, reg in sites:
    print('\n--- site %08X (base reg r%d) ---' % (a, reg))
    tracked = {reg}
    for k in range(0, 40):
        va = a + 4 * k
        d = dec(va)
        if d is None:
            break
        mn, ops = d.mnemonic, d.op_str
        mark = '>>' if k == 0 else '  '
        print('%s %08X  %-6s %s' % (mark, va, mn, ops))
        if mn in ('pop', 'bx') and ('pc' in ops or 'lr' in ops):
            break
        if mn == 'b':
            print('   ; tail branch')
            break
