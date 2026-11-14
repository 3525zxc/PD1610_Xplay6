#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 7e: 找 0x91D3C344 的间接引用（函数指针表） + 解析 setter 跳表 + G 的调用序列。"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
FOFF = 0x8000
data = open(r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin', 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)


def va2off(va):
    o = FOFF + (va - BASE)
    return o if 0 <= o < len(data) else None


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


# ---------- 1. 原始字节搜函数指针 ----------
print('#' * 74)
print('# 1. 原始 4 字节指针搜索')
print('#' * 74)
for tgt, name in [(0x91D3C344, 'unlock gate'), (0x91D3C345, 'unlock gate+1(thumb)'),
                  (0x91D12CFC, 'state setter'), (0x91D12594, 'verify func')]:
    pat = struct.pack('<I', tgt)
    s = 0
    hits = []
    while True:
        i = data.find(pat, s)
        if i < 0:
            break
        hits.append(i)
        s = i + 1
    print('%-26s %08X  raw hits=%d  %s' % (name, tgt, len(hits), [hex(h) for h in hits[:12]]))
    for h in hits[:12]:
        ctx = data[max(0, h - 16):h + 20]
        print('    off 0x%06X VA %08X  ctx %s' % (h, BASE + h - FOFF, ctx.hex()))

# ---------- 2. setter 跳表 ----------
print('\n' + '#' * 74)
print('# 2. setter 0x91D12CFC 跳表解析')
print('#' * 74)
o = va2off(0x91D12D20)
print('table bytes:', data[o:o + 32].hex())
for k in range(6):
    w = struct.unpack_from('<I', data, o + 4 * k)[0]
    print('  entry[%d] = %08X  -> VA %08X' % (k, w, w))

# ---------- 3. 各 setter 调用点 ----------
for va in (0x91D13078, 0x91D45040, 0x91D45574):
    dis(va - 0x24, 24, 'setter call ctx %08X' % va)

# ---------- 4. G 的完整调用序列 ----------
dis(0x91D39CB4, 90, 'G 0x91D39CB4')

# ---------- 5. verify 函数入口 ----------
dis(0x91D12594, 60, 'verify func 0x91D12594')
