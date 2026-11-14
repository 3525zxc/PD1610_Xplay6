#!/usr/bin/env python3
# 枚举 aboot 8.19.16 中所有 fastboot_register 调用（name + handler），并检查 boot/flash handler 是否验签
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

PATH = r'D:\16\PD1610_81\backup\81_aboot_LUN4.bin'
BASE = 0x91D00000
FOFF = 0x8000
REG = 0x91D41D3C            # fastboot_register
VERIFY = 0x91D12DD0         # 真实验签
G = 0x91D39CB4              # 外层 G

d = open(PATH, 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = False

def va2off(va):
    return FOFF + (va - BASE)

def s_at(va):
    o = va2off(va)
    if o < 0 or o >= len(d):
        return '?'
    e = d.find(b'\x00', o)
    return d[o:e].decode('ascii', 'replace')

def bl_target(ins, addr):
    imm = ins & 0xFFFFFF
    if imm & 0x800000:
        imm -= 0x1000000
    return addr + 8 + imm * 4

# ---------- 1. 扫描所有 BL，找调用 fastboot_register 的 ----------
print('=' * 78)
print('A. fastboot_register 调用点（回溯 r0=name, r1=handler）')
print('=' * 78)

code_lo = FOFF
code_hi = len(d) - 4
calls = []
for off in range(code_lo, code_hi, 4):
    ins = struct.unpack_from('<I', d, off)[0]
    if (ins & 0x0F000000) != 0x0B000000:
        continue
    addr = BASE + (off - FOFF)
    if bl_target(ins, addr) != REG:
        continue
    # 回溯 40 条指令，收集 movw/movt
    regs = {}
    lo_part = {}
    hi_part = {}
    for k in range(1, 41):
        o2 = off - 4 * k
        if o2 < code_lo:
            break
        i2 = struct.unpack_from('<I', d, o2)[0]
        rd = (i2 >> 12) & 0xF
        if (i2 & 0xFFF0F000) == 0xE3000000:      # movw
            imm = ((i2 >> 16) & 0xF) << 12 | (i2 & 0xFFF)
            if rd not in lo_part:
                lo_part[rd] = imm
        elif (i2 & 0xFFF0F000) == 0xE3400000:    # movt
            imm = ((i2 >> 16) & 0xF) << 12 | (i2 & 0xFFF)
            if rd not in hi_part:
                hi_part[rd] = imm
        elif (i2 & 0x0F000000) == 0x0B000000:    # 遇到另一个 BL 就停
            break
    def val(r):
        if r in lo_part and r in hi_part:
            return (hi_part[r] << 16) | lo_part[r]
        return None
    name_va = val(0)
    handler_va = val(1)
    calls.append((addr, name_va, handler_va))

calls.sort(key=lambda x: x[0])
seen = set()
rows = []
for addr, nva, hva in calls:
    if nva is None:
        txt = '<r0 not const>'
    else:
        txt = s_at(nva)[:46]
    key = (txt, hva)
    rows.append((addr, txt, hva))
    print('  %08X  name=%-48r handler=%s' % (addr, txt, ('0x%08X' % hva) if hva else '?'))

print()
print('  共 %d 处 fastboot_register' % len(rows))

# ---------- 2. 找出关键命令的 handler ----------
print()
print('=' * 78)
print('B. 关键命令的 handler')
print('=' * 78)
targets = {}
for addr, txt, hva in rows:
    for kw in ('boot', 'flash:', 'erase:', 'preflash', 'device-info', 'lock_vivo', 'unlock_vivo', 'reboot', 'continue', 'oem'):
        if txt.strip() == kw or txt.strip().startswith(kw):
            targets.setdefault(txt.strip(), []).append((addr, hva))
for k, v in targets.items():
    for addr, hva in v:
        print('  %-18s registered@%08X  handler=%s' % (k, addr, ('0x%08X' % hva) if hva else '?'))

# ---------- 3. 在所有 handler 里找验签调用 ----------
print()
print('=' * 78)
print('C. 各 handler 是否调用验签 0x91D12DD0 / 外层 G 0x91D39CB4')
print('=' * 78)

def find_calls_in_range(start_va, max_ins=260):
    """从 start_va 起反汇编，找 BL 目标，遇到返回(pop/ bx lr) 结束"""
    o = va2off(start_va)
    res = []
    n = 0
    for i in md.disasm(d[o:o + max_ins * 4], start_va):
        n += 1
        if i.mnemonic == 'bl':
            t = int(i.op_str.replace('#', ''), 16)
            res.append((i.address, t))
        if i.mnemonic in ('pop',) and 'pc' in i.op_str:
            break
        if i.mnemonic == 'bx' and i.op_str == 'lr':
            break
        if i.mnemonic == 'b' and i.op_str.startswith('#0x'):
            # 尾跳，记录并停止
            res.append((i.address, int(i.op_str.replace('#', ''), 16)))
            break
        if n >= max_ins:
            break
    return res, n

for name, lst in targets.items():
    for regaddr, hva in lst:
        if not hva:
            continue
        calls2, n = find_calls_in_range(hva, 300)
        verify_hit = [c for c in calls2 if c[1] == VERIFY]
        g_hit = [c for c in calls2 if c[1] == G]
        print('  %-18s handler=%08X  指令数≈%-4d BL数=%-3d  验签调用=%s  G调用=%s' % (
            name, hva, n, len(calls2),
            [hex(c[0]) for c in verify_hit] or '无',
            [hex(c[0]) for c in g_hit] or '无'))
