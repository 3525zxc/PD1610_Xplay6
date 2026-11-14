#!/usr/bin/env python3
# 对比 fastboot boot 路径 与 正常开机路径 是否调用解锁门控
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

PATH = r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin'
BASE = 0x91D00000
FOFF = 0x8000

TARGETS = {
    '解锁门控 0x91D3C33C': 0x91D3C33C,
    '验签 0x91D12DD0': 0x91D12DD0,
    '外层 G 0x91D39CB4': 0x91D39CB4,
    'getter恒1 0x91D37814': 0x91D37814,
    '检查A 0x91D37B78': 0x91D37B78,
    '检查B 0x91D377A8': 0x91D377A8,
}

d = open(PATH, 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

def va2off(va):
    return FOFF + (va - BASE)

def s_at(va):
    o = va2off(va)
    if o < 0 or o >= len(d):
        return '?'
    e = d.find(b'\x00', o)
    return d[o:e].decode('ascii', 'replace')

def func_start(va, limit=400):
    for k in range(0, limit):
        a = va - 4 * k
        o = va2off(a)
        if o < FOFF or o + 4 > len(d):
            break
        g = list(md.disasm(d[o:o + 4], a))
        if not g:
            continue
        i = g[0]
        if i.mnemonic == 'push' and 'lr' in i.op_str:
            return a
        if i.mnemonic == 'str' and i.op_str.startswith('lr, [sp, #-4]'):
            return a
    return None

code = d[FOFF:]
n = len(code) // 4
print('=' * 78)
print('全部 BL / B 调用者统计（PD1610 aboot 8.19.16）')
print('=' * 78)

for name, tva in TARGETS.items():
    bl_hits, b_hits = [], []
    for k in range(n):
        off = k * 4
        ins = struct.unpack_from('<I', code, off)[0]
        op = ins & 0x0F000000
        if op not in (0x0B000000, 0x0A000000):
            continue
        imm = ins & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        addr = BASE + off
        tgt = addr + 8 + imm * 4
        if tgt != tva:
            continue
        (bl_hits if op == 0x0B000000 else b_hits).append(addr)
    pat = struct.pack('<I', tva)
    ptr = []
    s = 0
    while True:
        j = code.find(pat, s)
        if j < 0:
            break
        ptr.append(BASE + j)
        s = j + 1
    print()
    print('  %s' % name)
    print('    BL  : %d  %s' % (len(bl_hits), ['0x%08X' % x for x in bl_hits]))
    print('    B   : %d  %s' % (len(b_hits), ['0x%08X' % x for x in b_hits]))
    print('    ptr : %d  %s' % (len(ptr), ['0x%08X' % x for x in ptr][:8]))
    for x in (bl_hits + b_hits):
        fs = func_start(x)
        print('      caller 0x%08X → 所在函数 0x%08X' % (x, fs if fs else 0))
