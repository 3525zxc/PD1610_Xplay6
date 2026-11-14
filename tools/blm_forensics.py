#!/usr/bin/env python3
"""Expand a BLM RAM dump into structured forensic JSON (meta + every bank)."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L
import blm_tools as T


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix('.forensics.json')
    blob = src.read_bytes()
    meta = T.read_meta(blob)
    banks = []
    for idx, off in enumerate(L.LAYOUT['bank_offsets']):
        bank = T.decode_bank(blob, off, idx)
        if bank:
            banks.append(bank)
    analysis = T.analyze_blob(blob)
    out = {
        'input': str(src),
        'size': len(blob),
        'sha256': hashlib.sha256(blob).hexdigest(),
        'layout_schema': L.LAYOUT['schema'],
        'meta': meta,
        'bank_count': len(banks),
        'banks': banks,
        'analysis': analysis,
        'stage_names': L.STAGE_NAMES,
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FORENSICS_OK out=' + str(dst) + ' banks=' + str(len(banks)))
    for b in banks:
        print('BANK %d gen=%s last_stage=%s(%s) stages=%d lines=%d fdt=%s log=%s ddr=%s' % (
            b['bank_index'], b['generation'], b['last_stage_id'], b['last_stage_name'],
            len(b['stages']), len(b['lines']), hex(b['fdt_phys']), hex(b['log_phys']), hex(b['ddr_hint'])))
        print('  stage_seq=' + ','.join(s['name'] for s in b['stages']))
        print('  lines=' + repr([x['text'] for x in b['lines']]))
    print('ANALYSIS rule=' + analysis['rule_id'] + ' bank=' + str(analysis['selected_bank']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
