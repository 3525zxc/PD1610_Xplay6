#!/usr/bin/env python3
"""Offline diff of PD1610 devinfo: 6.0.1 backup vs 8.1 readback.

Field offsets come from the project's verified aboot disassembly (2026-11-10):
  +0x10 is_unlocked, +0x14 is_tampered,
  +0x18 is_unlock_critical, +0x1C (charger/verified flag)
  vivo_bsp unlock_vivo writes 1 to [devinfo+0x10];
  bbk unlock_vivo compares [devinfo+0x10] with 1.

Output: D:\\16\\PD1610_81\\evidence\\devinfo_601_vs_81.txt
"""
import collections
import hashlib
import math
import os

P6 = r'C:\qfilx\backup\backup_devinfo_LUN4.bin'
P8 = r'D:\16\PD1610_81\backup\81_devinfo_LUN4.bin'
OUT = r'D:\16\PD1610_81\evidence\devinfo_601_vs_81.txt'

FIELDS = [(0x10, 'is_unlocked'), (0x14, 'is_tampered'),
          (0x18, 'is_unlock_critical'), (0x1C, 'charger/verified')]

a, b = open(P6, 'rb').read(), open(P8, 'rb').read()
lines = []
def emit(s=''):
    lines.append(s)
    print(s)

emit('PD1610 devinfo: 6.0.1 (C:\\qfilx\\backup) vs 8.1 (D:\\16\\PD1610_81\\backup)')
emit('PURE OFFLINE - no device access, no writes')
emit('')
emit('6.0.1 : %d B  sha256 %s' % (len(a), hashlib.sha256(a).hexdigest()))
emit('8.1   : %d B  sha256 %s' % (len(b), hashlib.sha256(b).hexdigest()))
diff = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
emit('differing bytes: %d / %d' % (len(diff), min(len(a), len(b))))
emit('differing offsets (first 12): %s' % [hex(i) for i in diff[:12]])

emit('')
emit('=== header bytes 0..0x1F ===')
for i in range(0, 0x20):
    mark = '  <-- ONLY HEADER DIFF' if a[i] != b[i] else ''
    emit('  +0x%02X  6.0.1=0x%02X  8.1=0x%02X%s' % (i, a[i], b[i], mark))

emit('')
emit('=== verified struct fields (from aboot disassembly) ===')
for off, name in FIELDS:
    emit('  +0x%02X  %-22s 6.0.1=%d  8.1=%d  %s' %
         (off, name, a[off], b[off], 'CHANGED' if a[off] != b[off] else 'same'))
emit('  magic @0 = %r (both)' % a[:13])

emit('')
emit('=== correlates with fastboot oem device-info on 8.1 ===')
emit('  Device tampered: false          <- +0x14 = 0')
emit('  Device unlocked: false          <- +0x10 = 0   (was 1 in 6.0.1)')
emit('  Device critical unlocked: true  <- +0x18 = 1')
emit('  Charger screen enabled: false   <- +0x1C = 0')
emit('  getvar unlocked: no')

emit('')
emit('=== trailing region 0xE4..0xFFF (228..4095) ===')
for tag, d in (('6.0.1', a), ('8.1', b)):
    seg = d[228:]
    c = collections.Counter(seg)
    H = -sum(v / len(seg) * math.log2(v / len(seg)) for v in c.values())
    emit('  %-6s len=%d entropy=%.3f bit/B distinct=%d DER=%.0f first16=%s' %
         (tag, len(seg), H, len(c), seg.find(b'\x30\x82'), seg[:16].hex()))
emit('  => high-entropy blob, no DER/PEM, completely different between builds.')
emit('     Identical runs: (0,16) and (17,228) are the only large ones.')
emit('     Interpretation (hypothesis): vivo attestation / encrypted blob rewritten')
emit('     on each devinfo write. NOT verified. Whether it covers +0x10 is unknown.')

emit('')
emit('=== CONCLUSION ===')
emit('1. The ONLY semantic difference in the struct is +0x10 is_unlocked:')
emit('   6.0.1 = 1 (unlocked)  ->  8.1 = 0 (locked).')
emit('   This is why fastboot flash now fails with "device is lock", while the')
emit('   6.0.1-era fastboot could write partitions. 17:05\'s extra "unlocked:yes"')
emit('   getvar line is consistent with the earlier unlocked state.')
emit('2. How devinfo was cleared: NOT established. Candidate: an official OTA /')
emit('   recovery step rewrote devinfo; no log proves which. Mark as open.')
emit('3. Restoring fastboot write access would be a 1-byte change (+0x10 = 1),')
emit('   which matches exactly what vivo_bsp unlock_vivo writes officially.')
emit('   This is a STRONG INFERENCE from verified disassembly + the 6.0.1 backup,')
emit('   NOT a live-verified result. No device write performed.')
emit('4. Risk: if the 0xE4+ blob is a signature/hash covering the struct, a raw')
emit('   byte patch could invalidate devinfo (tampered / reset / FDE key mismatch,')
emit('   cf. the X9 tutorial password screen). The X9s devinfo.img (16 MB, 0xFF)')
emit('   is a different device and must NOT be flashed here.')
emit('5. EDL/9008 does not consult is_unlocked at all (47-partition read/write')
emit('   already verified), so this patch is optional - a convenience, not a gate.')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print('\n[written] ' + OUT)
