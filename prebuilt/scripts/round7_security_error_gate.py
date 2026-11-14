#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round 7: 定位 aboot 8.19.16 中 Security Error 状态机 [0x91D9DD98] 的完整判定条件。
目标：找出「验签失败 -> 打印 Security Error -> HALT」这条路上，是否存在任何可被
      解锁位 / 外部分区 / cmdline 影响的前置分支。

已知：
  G        = 0x91D39CB4   (外层)
  verify   = 0x91D12DD0   (真实验签，不读 devinfo)
  handler  = 0x91D131E8   (读 [0x91D9DD98], ==3 -> Security Error)
  state    = 0x91D9DD98   (.data 初值 3)
  writers  = 0x91D12D6C / 0x91D12DB8 / 0x91D130B8
"""
import os
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x91D00000
IMG = r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin'

md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = False


def va2off(va):
    return va - BASE


def dis(va, n_instr=120, label=''):
    off = va2off(va)
    if off < 0 or off >= len(data):
        print('  [out of range] %08X' % va)
        return
    print('\n' + '=' * 78)
    print('=== %s  VA %08X  (file 0x%X)' % (label, va, off))
    print('=' * 78)
    code = data[off:off + n_instr * 4]
    for i in md.disasm(code, va):
        mark = ''
        line = '%08X  %-8s %s' % (i.address, i.mnemonic, i.op_str)
        print(line)
        # 遇到函数尾常见形态后不再硬停，由调用者控制条数


def find_literal_pool_refs(va_val):
    """找 literal pool 中指向 va_val 的 4 字节常量，返回其所在位置（作为 pool 基址候选）"""
    pat = struct.pack('<I', va_val)
    out = []
    s = 0
    while True:
        i = data.find(pat, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def find_writers(target_va):
    """暴力扫描所有可能以立即数形式写入 target_va 的指令：
       - movw/movt 组合得到目标地址
       - ldr/str 使用 literal pool 指向目标地址
       返回 [(insn_off, text)]"""
    hits = []
    # 1) movw/movt 配对
    t_lo = target_va & 0xFFFF
    t_hi = (target_va >> 16) & 0xFFFF
    movw = {}
    for i in range(0, len(data) - 4, 4):
        ins = struct.unpack_from('<I', data, i)[0]
        # movw: cond 0011 0000 imm4 rd imm12
        if (ins & 0x0FF00000) == 0x03000000:
            imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
            rd = (ins >> 12) & 0xF
            if imm == t_lo:
                movw.setdefault(rd, []).append(i)
        elif (ins & 0x0FF00000) == 0x03400000:
            imm = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
            rd = (ins >> 12) & 0xF
            if imm == t_hi:
                for p in movw.get(rd, []):
                    if 0 < i - p <= 64:
                        hits.append((p, 'movw/movt -> %08X @ movt %08X' % (target_va, i)))
    # 2) literal pool
    pool = find_literal_pool_refs(target_va)
    for p in pool:
        # 找以 PC 相对 ldr 命中该 pool 的指令
        pool_va = BASE + p
        for j in range(max(0, p - 0x1000), min(len(data) - 4, p + 0x100), 4):
            ins = struct.unpack_from('<I', data, j)[0]
            # ldr/str rd, [pc, #+-imm12]
            if (ins & 0x0F7F0000) in (0x051F0000, 0x050F0000, 0x041F0000, 0x040F0000):
                u = (ins >> 23) & 1
                imm = ins & 0xFFF
                pc = BASE + j + 8
                ea = pc + imm if u else pc - imm
                if ea == pool_va:
                    hits.append((j, '%s pool@%08X' % (
                        'ldr' if (ins & 0x00100000) else 'str', pool_va)))
    return sorted(set(hits))


data = open(IMG, 'rb').read()
print('image %s  size %d (%.1f MB)' % (os.path.basename(IMG), len(data), len(data) / 1048576.0))
print('state var 0x91D9DD98 file offset 0x%X' % va2off(0x91D9DD98))
print('current bytes at that off:', data[va2off(0x91D9DD98):va2off(0x91D9DD98) + 4].hex())

# ---- 0) 状态变量在文件里的静态初值 ----
print('\n[0] state var 静态初值 =', struct.unpack_from('<I', data, va2off(0x91D9DD98))[0])

# ---- 1) 谁引用这个地址 ----
print('\n[1] 引用了 0x91D9DD98 的指令位置:')
for off, txt in find_writers(0x91D9DD98):
    print('  0x%08X  (VA %08X)  %s' % (off, BASE + off, txt))

# ---- 2) 反汇编 handler ----
dis(0x91D131E8, 160, 'Security Error handler')

# ---- 3) 反汇编 verify wrapper ----
dis(0x91D12DD0, 200, 'verify wrapper 0x91D12DD0')

# ---- 4) 三个写入者所在函数 ----
for va in (0x91D12D6C, 0x91D12DB8, 0x91D130B8):
    dis(va - 0x40, 80, 'writer region around %08X' % va)
