# -*- coding: utf-8 -*-
"""构建 devinfo 解锁标志变体（每个变体只动 1 个字节），用于验证 aboot 的
'Device is unlocked! Skipping verification' 分支（函数 0x91D3C344 读 [r3,#0x10]）。
原文件保留为基准，任何时候可写回还原。"""
import hashlib, os, shutil

BACK = r'D:\16\PD1610_81\backup'
WORK = r'D:\16\PD1610_81\work'
SCR  = r'D:\16\PD1610_81\scripts'
src = os.path.join(BACK, '81_devinfo_LUN4.bin')
base = bytearray(open(src, 'rb').read())
print('基准 devinfo: %d B  sha256=%s' % (len(base), hashlib.sha256(bytes(base)).hexdigest()))
print('基准关键字节: +0x10=%d  +0x18=%d  +0x20=%d  +0x21=%d  +0x22=%d  +0x23=%d'
      % (base[0x10], base[0x18], base[0x20], base[0x21], base[0x22], base[0x23]))

VARIANTS = {
    'devinfo_u10.bin':  [(0x10, 1)],   # is_unlocked 候选 A
    'devinfo_u20.bin':  [(0x20, 1)],   # is_unlocked 候选 B (CAF struct 偏移)
    'devinfo_u10u20.bin': [(0x10, 1), (0x20, 1)],
}
for fn, edits in VARIANTS.items():
    b = bytearray(base)
    for off, val in edits:
        b[off] = val
    p = os.path.join(WORK, fn)
    with open(p, 'wb') as f:
        f.write(bytes(b))
    d = [i for i in range(len(b)) if b[i] != base[i]]
    print('%s : 改动字节 %s  sha256=%s' % (fn, [(hex(i), hex(base[i]), hex(b[i])) for i in d],
                                           hashlib.sha256(bytes(b)).hexdigest()))
    xml = ('<?xml version="1.0" ?>\n<data>\n'
           '  <program SECTOR_SIZE_IN_BYTES="4096" file_sector_offset="0" filename="%s" '
           'label="devinfo" num_partition_sectors="1" physical_partition_number="4" start_sector="882954"/>\n'
           '</data>\n') % fn
    with open(os.path.join(SCR, 'write_' + fn.replace('.bin', '') + '.xml'), 'w', encoding='utf-8') as f:
        f.write(xml)
    print('   XML: scripts\\write_%s.xml' % fn.replace('.bin', ''))

# 还原用 XML（写回原始备份）
xml = ('<?xml version="1.0" ?>\n<data>\n'
       '  <program SECTOR_SIZE_IN_BYTES="4096" file_sector_offset="0" filename="81_devinfo_LUN4.bin" '
       'label="devinfo" num_partition_sectors="1" physical_partition_number="4" start_sector="882954"/>\n'
       '</data>\n')
with open(os.path.join(SCR, 'restore_devinfo.xml'), 'w', encoding='utf-8') as f:
    f.write(xml)
print('\n还原: scripts\\restore_devinfo.xml（文件 81_devinfo_LUN4.bin 在 backup\\，用 --search_path 指向 backup）')
