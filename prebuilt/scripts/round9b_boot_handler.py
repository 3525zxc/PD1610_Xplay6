#!/usr/bin/env python3
# 反汇编 fastboot boot / flash: handler，判定是否验签
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

PATH = r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin'
BASE = 0x91D00000
FOFF = 0x8000
VERIFY = 0x91D12DD0
G = 0x91D39CB4

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

def dis_range(start, n, label):
    print('=' * 78)
    print('%s  0x%08X' % (label, start))
    print('=' * 78)
    o = va2off(start)
    out = []
    for i in md.disasm(d[o:o + n * 4], start):
        mark = ''
        if i.mnemonic == 'bl':
            t = int(i.op_str.replace('#', ''), 16)
            if t == VERIFY:
                mark = '   <== 调用验签 0x91D12DD0'
            elif t == G:
                mark = '   <== 调用外层 G'
            else:
                # 标注已知函数
                named = {
                    0x91D41D3C: 'fastboot_register',
                    0x91D41DB0: 'fastboot_publish',
                    0x91D40FCC: 'aboot_init',
                }.get(t)
                if named:
                    mark = '   <== %s' % named
        print('  %08X  %-7s %-34s%s' % (i.address, i.mnemonic, i.op_str, mark))
        out.append((i.address, i.mnemonic, i.op_str))
    return out

# boot handler
ins = dis_range(0x91D3E000, 130, 'fastboot "boot" handler')
print()
bls = [(a, int(o.replace('#', ''), 16)) for a, m, o in ins if m == 'bl']
print('  BL 目标汇总:')
for a, t in bls:
    tag = ''
    if t == VERIFY:
        tag = '  *** 验签 ***'
    elif t == G:
        tag = '  *** 外层 G ***'
    print('    %08X -> %08X%s' % (a, t, tag))

print()
ins2 = dis_range(0x91D3FBD4, 90, 'fastboot "flash:" handler')
print()
bls2 = [(a, int(o.replace('#', ''), 16)) for a, m, o in ins2 if m == 'bl']
print('  BL 目标汇总:')
for a, t in bls2:
    tag = ''
    if t == VERIFY:
        tag = '  *** 验签 ***'
    elif t == G:
        tag = '  *** 外层 G ***'
    print('    %08X -> %08X%s' % (a, t, tag))
