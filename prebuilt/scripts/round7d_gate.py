#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 7d: 解锁门控 0x91D3C344 全反汇编 + 全二进制 BL/B 调用者扫描 + Security Error 函数体。"""
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
FOFF = 0x8000
data = open(r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin', 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = True


def va2off(va):
    o = FOFF + (va - BASE)
    return o if 0 <= o < len(data) else None


def dis(va, n, label):
    o = va2off(va)
    print('\n' + '=' * 74)
    print('=== %s  VA %08X  off 0x%X' % (label, va, o))
    print('=' * 74)
    cnt = 0
    for i in md.disasm(data[o:o + n * 4], va):
        print('%08X  %-7s %s' % (i.address, i.mnemonic, i.op_str))
        cnt += 1
    print('  (%d)' % cnt)


def callers_of(target, arm_only=True):
    """扫全镜像 BL / B / BLX 立即数分支，返回调用点列表"""
    out = []
    for o in range(FOFF, len(data) - 4, 4):
        ins = struct.unpack_from('<I', data, o)[0]
        op = (ins >> 25) & 0x7
        if op != 0b101:
            continue
        link = (ins >> 24) & 1
        imm24 = ins & 0xFFFFFF
        if imm24 & 0x800000:
            imm24 -= 0x1000000
        va = BASE + o - FOFF
        tgt = va + 8 + (imm24 << 2)
        if tgt == target:
            out.append((va, 'BL' if link else 'B'))
    return out


# 1) 门控函数
dis(0x91D3C2C0, 80, 'unlock gate 0x91D3C344 (前方上下文)')
dis(0x91D13220, 40, 'Security-Error printer 0x91D13224')

# 2) 调用者
for t, name in [(0x91D3C344, 'unlock gate'), (0x91D13224, 'sec-error printer'),
                (0x91D12CFC, 'setter 0x91D12CFC'), (0x91D13228, 'getter 0x91D13228')]:
    c = callers_of(t)
    print('\n[callers] %-24s %08X  n=%d  %s' % (name, t, len(c), [(hex(a), k) for a, k in c]))

# 3) 0x91D12CFC / 0x91D12CF0 等写入者
dis(0x91D12CE0, 40, 'setter 0x91D12CFC 区域')
