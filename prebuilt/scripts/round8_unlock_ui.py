#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 8: 定位 aboot 8.19.16 的 bootloader 解锁 UI / 状态判定代码。
字符串文件偏移来自 strings 扫描，VA = BASE + off - 0x8000。
"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
FOFF = 0x8000
data = open(r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin', 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)


def va2off(va):
    o = FOFF + (va - BASE)
    return o if 0 <= o < len(data) else None


def off2va(o):
    return BASE + o - FOFF


def ins_at(va):
    o = va2off(va)
    return None if o is None else struct.unpack_from('<I', data, o)[0]


def find_loaders(target_va, window=8):
    lo, hi = target_va & 0xFFFF, (target_va >> 16) & 0xFFFF
    out = []
    for o in range(FOFF, len(data) - 4, 4):
        ins = struct.unpack_from('<I', data, o)[0]
        if (ins & 0x0FF00000) != 0x03000000:
            continue
        imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
        if imm != lo:
            continue
        rd = (ins >> 12) & 0xF
        va = off2va(o)
        for k in range(1, window + 1):
            nin = ins_at(va + 4 * k)
            if nin is None:
                break
            if (nin & 0x0FF00000) == 0x03400000:
                imm2 = ((nin >> 16) & 0xF) << 12 | (nin & 0xFFF)
                if ((nin >> 12) & 0xF) == rd and imm2 == hi:
                    out.append(va)
                    break
    return out


def dis(va, n, label):
    o = va2off(va)
    print('\n' + '=' * 74)
    print('=== %s  VA %08X  off 0x%X' % (label, va, o))
    print('=' * 74)
    if o is None:
        print('  unmapped')
        return
    for i in md.disasm(data[o:o + n * 4], va):
        print('%08X  %-7s %s' % (i.address, i.mnemonic, i.op_str))


strs = {
    'Unlock bootloader?': 543664,
    'will also delete all personal data': 543928,
    'Unlock bootloader(may void warranty)': 544188,
    'Do not unlock bootloader and restart phone': 544232,
    'locked': 544604,
    'unlocked': 544612,
    'checked for corruption. Please lock the bootloader': 545122,
}

for name, off in strs.items():
    va = off2va(off)
    hs = find_loaders(va)
    print('\n' + '#' * 74)
    print('# %-52s VA %08X  loaders=%d' % (name, va, len(hs)))
    print('#' * 74)
    print(' ', [hex(h) for h in hs])
    for h in hs[:3]:
        dis(h - 0x30, 34, name + ' @ %08X' % h)
