import re, os

SRC = r'C:\qfilx\backup'
DST = r'D:\16\PD1610_81\scripts\readback_81_all.xml'
FILES = ['readback_program.xml', 'supp_readback_program.xml', 'read_system.xml']

rows = []
for fn in FILES:
    with open(os.path.join(SRC, fn), encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s.startswith('<program '):
                s = re.sub(r'filename="backup_', 'filename="81_', s)
                rows.append('  ' + s)

seen = {}
for r in rows:
    m = re.search(r'label="([^"]+)"', r)
    if m:
        seen[m.group(1)] = r

out = ['<?xml version="1.0" ?>',
       '<!-- PD1610 Android 8.1 (PD1610_D_8.19.16) full read-only partition backup -->',
       '<!-- Generated from verified GPT sector table; output prefix 81_ -->',
       '<data>'] + list(seen.values()) + ['</data>', '']

with open(DST, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

print('source rows :', len(rows))
print('partitions  :', len(seen))
print('xml         :', DST)
print('labels      :', ' '.join(sorted(seen)))
