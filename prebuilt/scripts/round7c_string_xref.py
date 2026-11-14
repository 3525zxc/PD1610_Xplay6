#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精确 movw/movt 配对：找指定 VA 的加载点，并反汇编上下文。"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
FOFF = 0x8000
data = open(r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin', 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)


def va2off(va):
    o = FOFF + (va - BASE)
    return o if 0 <= o < len(data) else None


def ins_at(va):
    o = va2off(va)
    if o is None:
        return None
    return struct.unpack_from('<I', data, o)[0]


def decode(va):
    o = va2off(va)
    if o is None:
        return None
    g = list(md.disasm(data[o:o + 4], va))
    return g[0] if g else None


WRITERS_TO_REG = ('mov', 'ldr', 'add', 'sub', 'and', 'orr', 'eor', 'lsl', 'lsr', 'asr', 'mvn', 'mul')


def find_loaders(target_va, window=10):
    lo = target_va & 0xFFFF
    hi = (target_va >> 16) & 0xFFFF
    hits = []
    o_start = FOFF
    for i in range(o_start, len(data) - 4, 4):
        ins = struct.unpack_from('<I', data, i)[0]
        if (ins & 0x0FF00000) != 0x03000000:
            continue
        imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
        if imm != lo:
            continue
        rd = (ins >> 12) & 0xF
        va = BASE + i - FOFF
        # 向后最多 window 条找 movt 同寄存器同 hi
        ok = False
        clobbered = False
        for k in range(1, window + 1):
            nva = va + 4 * k
            nin = ins_at(nva)
            if nin is None:
                break
            if (nin & 0x0FF00000) == 0x03400000:
                imm2 = ((nin >> 16) & 0xF) << 12 | (nin & 0xFFF)
                rd2 = (nin >> 12) & 0xF
                if rd2 == rd and imm2 == hi:
                    ok = True
                    break
            # 粗略判断该寄存器是否被改写
            if (nin & 0x0FFF0000) in (0x01A00000,) and ((nin >> 12) & 0xF) == rd:
                # mov rd, ...
                if ((nin >> 16) & 0xF) != rd:
                    clobbered = True
                    break
        if ok and not clobbered:
            hits.append(va)
    return hits


def show(va, before=6, after=14, tag=''):
    print('\n' + '-' * 74)
    print('--- %s  VA %08X ---' % (tag, va))
    print('-' * 74)
    for k in range(-before, after + 1):
        a = va + 4 * k
        d = decode(a)
        if d is None:
            continue
        mark = '>>' if k == 0 else '  '
        print('%s %08X  %-7s %s' % (mark, d.address, d.mnemonic, d.op_str))


targets = [
    ('Security Error msg', 0x91D7C88C),
    ('Device is unlocked! Skipping verification', 0x91D840C4),
    ('HALT reboot into dload', 0x91D7968C),
    ('HALT spinning forever', 0x91D796B0),
]

for name, va in targets:
    hs = find_loaders(va)
    print('\n' + '#' * 74)
    print('# %s   %08X   loaders=%d' % (name, va, len(hs)))
    print('#' * 74)
    print([hex(h) for h in hs])
    for h in hs[:4]:
        show(h, tag=name)
