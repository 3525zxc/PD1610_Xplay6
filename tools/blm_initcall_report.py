#!/usr/bin/env python3
"""Resolve BLM 'IC <16 hex>' initcall trace lines against System.map.

The BLM instrumentation writes one line per do_one_initcall() entry.  On a
failed boot the last IC line is the initcall that never returned.  This tool
turns those raw pointers into symbol names + offsets and prints the last
console lines as well, so the failure window becomes a concrete function.
"""
import argparse
import bisect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L
import blm_tools as T


def load_symbols(path):
    syms = []
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        parts = line.split()
        if len(parts) >= 3 and re.fullmatch(r'[0-9a-fA-F]+', parts[0]):
            syms.append((int(parts[0], 16), parts[2]))
    syms.sort(key=lambda x: x[0])
    return syms


def resolve(syms, keys, addr):
    i = bisect.bisect_right(keys, addr) - 1
    if i < 0:
        return None, None
    base, name = syms[i]
    return name, addr - base


def pick_bank(blob):
    banks = []
    for idx, off in enumerate(L.LAYOUT['bank_offsets']):
        bank = T.decode_bank(blob, off, idx)
        if bank:
            banks.append(bank)
    if not banks:
        return None
    return max(banks, key=lambda b: b.get('generation', 0))


def main():
    ap = argparse.ArgumentParser(description='resolve BLM initcall trace from a RAM dump')
    ap.add_argument('--input', required=True)
    ap.add_argument('--system-map', required=True)
    ap.add_argument('--report', default='')
    ap.add_argument('--tail', type=int, default=25)
    ap.add_argument('--offset', type=lambda x: int(x, 0), default=0)
    args = ap.parse_args()

    blob = Path(args.input).read_bytes()
    region = blob[args.offset:args.offset + L.LAYOUT['log_size']]
    bank = pick_bank(region)
    if not bank:
        print('INITCALL_REPORT_FAIL no valid bank')
        return 1

    lines = sorted(bank.get('lines', []), key=lambda x: x.get('seq', 0))
    ics = []
    for ln in lines:
        text = ln.get('text', '')
        if not text.startswith('IC '):
            continue
        raw = text[3:].strip()
        if not re.fullmatch(r'[0-9a-fA-F]{1,16}', raw):
            continue
        addr = int(raw, 16)
        ics.append({'seq': ln.get('seq'), 'jiffies': ln.get('jiffies'),
                    'addr': addr, 'addr_hex': hex(addr), 'raw': raw})

    syms = load_symbols(args.system_map)
    keys = [s[0] for s in syms]
    for item in ics:
        name, delta = resolve(syms, keys, item['addr'])
        item['symbol'] = name
        item['symbol_offset'] = delta

    tags = [ln for ln in lines if ln.get('text', '').startswith('BLM ')]
    printk_lines = [ln for ln in lines if not ln.get('text', '').startswith(('IC ', 'BLM '))]

    print('INITCALL_REPORT input=%s bank=%d gen=%s last_stage=%s(%s)' % (
        args.input, bank.get('bank_index', -1), bank.get('generation'),
        bank.get('last_stage_id'), bank.get('last_stage_name')))
    print('SYMBOLS=%d  LINES=%d  IC_ENTRIES=%d  BLM_TAGS=%d  PRINTK_LINES=%d' % (
        len(syms), len(lines), len(ics), len(tags), len(printk_lines)))
    print('--- BLM milestone lines ---')
    for ln in tags:
        print('  seq=%s j=%s %s' % (ln.get('seq'), ln.get('jiffies'), ln.get('text', '').rstrip()))
    print('--- last %d initcall entries ---' % args.tail)
    for item in ics[-args.tail:]:
        print('  seq=%s j=%s %s -> %s+0x%x' % (
            item['seq'], item['jiffies'], item['addr_hex'],
            item['symbol'] or '?', item['symbol_offset'] or 0))
    print('--- last %d non-trace console lines ---' % args.tail)
    for ln in printk_lines[-args.tail:]:
        print('  seq=%s j=%s %s' % (ln.get('seq'), ln.get('jiffies'), ln.get('text', '').rstrip()))
    if ics:
        last = ics[-1]
        print('SUSPECTED_STALL seq=%s addr=%s symbol=%s+0x%x' % (
            last['seq'], last['addr_hex'], last['symbol'] or '?', last['symbol_offset'] or 0))
    else:
        print('SUSPECTED_STALL none (no IC entries captured)')

    if args.report:
        out = {
            'input': args.input,
            'system_map': args.system_map,
            'bank_index': bank.get('bank_index'),
            'generation': bank.get('generation'),
            'last_stage_id': bank.get('last_stage_id'),
            'last_stage_name': bank.get('last_stage_name'),
            'symbol_count': len(syms),
            'line_count': len(lines),
            'initcall_count': len(ics),
            'initcalls': ics,
            'milestones': tags,
            'console_tail': printk_lines[-args.tail:],
            'suspected_stall': ics[-1] if ics else None,
        }
        Path(args.report).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print('REPORT_OK ' + args.report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
