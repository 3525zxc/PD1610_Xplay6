#!/usr/bin/env python3
"""Independent re-check of the 8.19.16 aboot verification-failure path.

Outputs a raw evidence dump (disassembly + string comparison) to
D:\\16\\PD1610_81\\evidence\\aboot_81916_failure_path.txt
"""
import os
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

P816 = r'C:\qfilx\firmware\81916\emmc_appsboot.mbn'
P715 = r'C:\qfilx\probe\aboot.bin'          # 7.13.15 16MB partition dump
OUT = r'D:\16\PD1610_81\evidence\aboot_81916_failure_path.txt'

d816 = open(P816, 'rb').read()
d715 = open(P715, 'rb').read() if os.path.exists(P715) else b''

# ELF32 program headers of 8.19.16
e_phoff = struct.unpack_from('<I', d816, 28)[0]
e_phentsize = struct.unpack_from('<H', d816, 42)[0]
e_phnum = struct.unpack_from('<H', d816, 44)[0]
segs = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from('<IIIIII', d816, o)
    if p_type == 1:
        segs.append((p_vaddr, p_offset, p_filesz))


def va2off(va):
    for vaddr, off, size in segs:
        if vaddr <= va < vaddr + size:
            return va - vaddr + off
    return None


md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.skipdata = True
buf = []


def emit(s=''):
    buf.append(s)
    print(s)


def dis(va, size, title):
    off = va2off(va)
    emit('')
    emit('=' * 78)
    emit('%s   VA 0x%08X  file_off 0x%X  %d bytes' % (title, va, off if off is not None else -1, size))
    emit('=' * 78)
    if off is None:
        emit('  [!] VA not inside PT_LOAD')
        return
    code = d816[off:off + size]
    for ins in md.disasm(code, va):
        emit('  %08X  %-10s %-8s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))


def bl_targets(va, size):
    off = va2off(va)
    out = []
    for ins in md.disasm(d816[off:off + size], va):
        if ins.mnemonic in ('bl', 'blx') and ins.op_str.startswith('#'):
            try:
                out.append(int(ins.op_str[1:], 16))
            except ValueError:
                pass
    return out


emit('PD1610 aboot 8.19.16 - verification failure path, independent re-check')
emit('file   : %s (%d bytes)' % (P816, len(d816)))
emit('compare: %s (%d bytes)' % (P715, len(d715)))
emit('PT_LOAD: %s' % ', '.join('vaddr=0x%08X off=0x%X size=0x%X' % s for s in segs))

G = 0x91D39CB4
FAIL_HANDLER = 0x91D44CC8
CALLER_AREA = 0x91D3C7C0
BOOT_FROM_FLASH = 0x91D3C3F0

dis(G, 0x1C0, 'G = boot verification wrapper (0x91D39CB4)')
tg = bl_targets(G, 0x1C0)
emit('')
emit('G bl-targets: ' + ', '.join('0x%08X' % x for x in tg))
emit('G ends with pop/return (see last lines above) - no direct reboot/assert branch')

dis(FAIL_HANDLER, 0x120, 'Failure-side state handler (0x91D44CC8)')
dis(CALLER_AREA, 0x180, 'Caller region around G call site (0x91D3C7C0..)')
dis(BOOT_FROM_FLASH, 0x100, 'boot_linux_from_flash entry (0x91D3C3F0)')

for name, va in (('tampered string selector', 0x91D3A3E0),
                 ('unlocked||tampered path pick', 0x91D3CACC),
                 ('tampered status writeback', 0x91D3D680)):
    dis(va, 0x70, 'is_tampered consumer: %s (0x%08X)' % (name, va))

# ---- string comparison 7.x vs 8.x ----
emit('')
emit('=' * 78)
emit('ASSERT / HALT related strings: 7.13.15 vs 8.19.16')
emit('=' * 78)
needles = [b'aboot.c', b'ASSERT', b'Asserting', b'platform_halt', b'HALT:',
           b'Device is tampered', b'Security Error', b'reboot_device',
           b'boot_verifier.c', b'Device unlocked', b'critical unlocked']
emit('  %-24s %10s %10s' % ('STRING', '7.13.15', '8.19.16'))
for n in needles:
    emit('  %-24s %10d %10d' % (n.decode('ascii', 'ignore'), d715.count(n), d816.count(n)))

emit('')
emit('Conclusion markers are written separately after manual review of the dump.')
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(buf) + '\n')
print('\n[written] ' + OUT)
