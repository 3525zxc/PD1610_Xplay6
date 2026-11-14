import os
import xml.etree.ElementTree as ET

SRC = r'D:\16\PD1610_81\scripts\readback_81_all.xml'
DST = r'D:\16\PD1610_81\scripts\restore_81_all.xml'
BACKUP = r'D:\16\PD1610_81\backup'

root = ET.parse(SRC).getroot()
rows = root.findall('program')
lines = [
    '<?xml version="1.0" ?>',
    '<!-- PD1610 Android 8.1 (8.19.16) FULL PARTITION RESTORE - 47 partitions -->',
    '<!-- Source: D:\\16\\PD1610_81\\backup\\81_*.bin (verified byte-for-byte vs sector counts) -->',
    '<data>',
]
bad = []
for r in rows:
    fn = r.get('filename')
    secs = int(r.get('num_partition_sectors'))
    path = os.path.join(BACKUP, fn)
    if not os.path.exists(path) or os.path.getsize(path) != secs * 4096:
        bad.append(fn)
    attrs = [
        ('SECTOR_SIZE_IN_BYTES', '4096'),
        ('file_sector_offset', '0'),
        ('filename', fn),
        ('label', r.get('label')),
        ('num_partition_sectors', str(secs)),
        ('partofsingleimage', 'false'),
        ('physical_partition_number', r.get('physical_partition_number')),
        ('readbackverify', 'false'),
        ('size_in_KB', '%.1f' % (secs * 4)),
        ('sparse', 'false'),
        ('start_sector', r.get('start_sector')),
    ]
    lines.append('  <program ' + ' '.join('%s="%s"' % kv for kv in attrs) + '/>')
lines.append('</data>')
lines.append('')

if bad:
    raise SystemExit('[X] 备份文件缺失或大小不符: %s' % bad)

with open(DST, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

total = sum(int(r.get('num_partition_sectors')) * 4096 for r in rows)
print('分区数 :', len(rows))
print('总字节 :', total, '(%.2f GB)' % (total / 1073741824))
print('校验   : 全部文件存在且大小吻合')
print('输出   :', DST)
