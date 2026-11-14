#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L

NL = chr(10)
BOOT_OK = 18


def crc(data):
    return zlib.crc32(bytes(data)) & 0xFFFFFFFF


def put_u32(buf, off, value):
    struct.pack_into('<I', buf, off, value & 0xFFFFFFFF)


def put_u64(buf, off, value):
    struct.pack_into('<Q', buf, off, value & 0xFFFFFFFFFFFFFFFF)


def get_u32(buf, off):
    return struct.unpack_from('<I', buf, off)[0]


def get_u64(buf, off):
    return struct.unpack_from('<Q', buf, off)[0]


def read_meta(blob):
    if len(blob) < L.LAYOUT['meta_size']:
        return None
    if get_u64(blob, 0) != L.LAYOUT['meta_magic']:
        return None
    if get_u32(blob, 20) != crc(blob[:20]):
        return None
    return {
        'generation': get_u64(blob, 8),
        'last_bank': get_u32(blob, 16),
        'last_fdt_phys': get_u64(blob, 24),
        'last_log_phys': get_u64(blob, 32),
    }


def decode_bank(blob, bank_off, bank_index):
    cfg = L.LAYOUT
    if bank_off + cfg['bank_size'] > len(blob):
        return None
    h = blob[bank_off:bank_off + cfg['header_size']]
    if get_u64(h, 0) != cfg['magic']:
        return None
    if get_u32(h, 84) != crc(h[:84]):
        return None
    if get_u32(h, 88) != cfg['build_tag']:
        return None
    generation = get_u32(h, 80)
    fdt_phys = get_u64(h, 48)
    log_phys = get_u64(h, 56)
    ddr_hint = get_u64(h, 72)
    stages = []
    for idx in range(1, cfg['stage_slots']):
        so = bank_off + cfg['stage_area_off'] + idx * cfg['stage_slot_size']
        slot = blob[so:so + cfg['stage_slot_size']]
        if get_u32(slot, 0) != cfg['stage_magic']:
            continue
        if get_u32(slot, 24) != crc(slot[:24]):
            continue
        stage = get_u32(slot, 16)
        if stage > L.EXPECTED_DEFINES['BLM_STAGE_MAX']:
            continue
        stages.append({
            'stage': stage,
            'name': L.STAGE_NAMES.get(stage, 'UNKNOWN'),
            'seq': get_u32(slot, 4),
            'jiffies': get_u64(slot, 8),
        })
    lines = []
    for idx in range(cfg['line_slots']):
        lo = bank_off + cfg['line_area_off'] + idx * cfg['line_slot_size']
        slot = blob[lo:lo + cfg['line_slot_size']]
        if get_u32(slot, 0) != cfg['line_magic']:
            continue
        length = get_u32(slot, 16)
        if length > cfg['line_slot_fields']['text_len']:
            continue
        if get_u32(slot, 20) != crc(slot[:20]):
            continue
        text = bytes(slot[24:24 + length]).decode('utf-8', 'replace')
        lines.append({
            'seq': get_u32(slot, 4),
            'jiffies': get_u64(slot, 8),
            'text': text,
        })
    lines.sort(key=lambda x: x['seq'])
    stages.sort(key=lambda x: x['stage'])
    last_stage = stages[-1]['stage'] if stages else 0
    return {
        'bank_index': bank_index,
        'bank_offset': bank_off,
        'generation': generation,
        'fdt_phys': fdt_phys,
        'log_phys': log_phys,
        'ddr_hint': ddr_hint,
        'stages': stages,
        'lines': lines,
        'last_stage_id': last_stage,
        'last_stage_name': L.STAGE_NAMES.get(last_stage, 'NONE'),
        'text': NL.join(x['text'] for x in lines),
    }


def match_rule(selected, banks):
    text = selected['text'].lower() if selected else ''
    for rule in L.DIAGNOSIS_RULES:
        if rule['when'] == 'no_valid_bank':
            if not banks:
                return rule
            continue
        if not selected:
            continue
        stage = selected['last_stage_id']
        if stage < rule['stage_min'] or stage > rule['stage_max']:
            continue
        keys = [k.lower() for k in rule['keywords_any']]
        if keys and not any(k in text for k in keys):
            continue
        return rule
    return {
        'id': 'unclassified',
        'diagnosis': '未匹配到判定规则。',
        'next_action': '检查日志格式、bank 选择规则与关键字表。',
        'confidence': '[U]',
    }


def analyze_blob(blob):
    cfg = L.LAYOUT
    if len(blob) < cfg['log_size']:
        blob = bytes(blob) + bytes(cfg['log_size'] - len(blob))
    meta = read_meta(blob)
    banks = []
    for idx, off in enumerate(cfg['bank_offsets']):
        bank = decode_bank(blob, off, idx)
        if bank:
            banks.append(bank)
    candidates = [b for b in banks if b['last_stage_id'] != BOOT_OK]
    selected = max(candidates or banks, key=lambda b: (b['last_stage_id'], b['generation'])) if banks else None
    rule = match_rule(selected, banks)
    last_lines = [x['text'] for x in selected['lines'][-8:]] if selected else []
    return {
        'sha256': hashlib.sha256(bytes(blob[:cfg['log_size']])).hexdigest(),
        'meta': meta,
        'bank_count': len(banks),
        'banks': [
            {
                'bank_index': b['bank_index'],
                'generation': b['generation'],
                'last_stage_id': b['last_stage_id'],
                'last_stage_name': b['last_stage_name'],
                'line_count': len(b['lines']),
            }
            for b in banks
        ],
        'selected_bank': None if not selected else {
            'bank_index': selected['bank_index'],
            'generation': selected['generation'],
            'fdt_phys': hex(selected['fdt_phys']),
            'log_phys': hex(selected['log_phys']),
            'ddr_hint': hex(selected['ddr_hint']),
            'last_stage_id': selected['last_stage_id'],
            'last_stage_name': selected['last_stage_name'],
        },
        'rule_id': rule['id'],
        'diagnosis': rule['diagnosis'],
        'next_action': rule['next_action'],
        'confidence': rule['confidence'],
        'last_lines': last_lines,
    }


def human_report(result):
    out = []
    out.append('BLM analysis')
    out.append('sha256=' + result['sha256'])
    out.append('bank_count=' + str(result['bank_count']))
    if result['meta']:
        out.append('meta_generation=' + str(result['meta']['generation']))
    else:
        out.append('meta_generation=INVALID')
    if result['selected_bank']:
        b = result['selected_bank']
        out.append('selected_bank=' + str(b['bank_index']) + ' generation=' + str(b['generation']))
        out.append('fdt_phys=' + b['fdt_phys'] + ' log_phys=' + b['log_phys'] + ' ddr_hint=' + b['ddr_hint'])
        out.append('last_stage=' + str(b['last_stage_id']) + ' ' + b['last_stage_name'])
    else:
        out.append('selected_bank=NONE')
        out.append('last_stage=0 NONE')
    out.append('rule=' + result['rule_id'])
    out.append('diagnosis=' + result['diagnosis'])
    out.append('next_action=' + result['next_action'])
    out.append('confidence=' + result['confidence'])
    if result['last_lines']:
        out.append('last_lines:')
        for line in result['last_lines']:
            out.append('  ' + line)
    return NL.join(out)


def write_meta(blob, generation, bank, fdt, log):
    put_u64(blob, 0, L.LAYOUT['meta_magic'])
    put_u64(blob, 8, generation)
    put_u32(blob, 16, bank)
    put_u64(blob, 24, fdt)
    put_u64(blob, 32, log)
    put_u32(blob, 20, crc(blob[:20]))


def write_header(blob, off, generation, fdt, log, ddr_hint):
    cfg = L.LAYOUT
    put_u64(blob, off + 0, cfg['magic'])
    put_u32(blob, off + 8, cfg['version'])
    put_u32(blob, off + 12, cfg['log_size'])
    put_u32(blob, off + 16, cfg['header_size'])
    put_u32(blob, off + 20, cfg['stage_area_off'])
    put_u32(blob, off + 24, cfg['stage_slot_size'])
    put_u32(blob, off + 28, cfg['stage_slots'])
    put_u32(blob, off + 32, cfg['line_area_off'])
    put_u32(blob, off + 36, cfg['line_slot_size'])
    put_u32(blob, off + 40, cfg['line_slots'])
    put_u32(blob, off + 44, cfg['used_size'])
    put_u64(blob, off + 48, fdt)
    put_u64(blob, off + 56, log)
    put_u64(blob, off + 64, cfg['fdt_log_offset'])
    put_u64(blob, off + 72, ddr_hint)
    put_u32(blob, off + 80, generation)
    put_u32(blob, off + 84, crc(blob[off:off + 84]))
    put_u32(blob, off + 88, cfg['build_tag'])


def write_stage(blob, off, stage, seq, jiffies):
    cfg = L.LAYOUT
    so = off + cfg['stage_area_off'] + stage * cfg['stage_slot_size']
    put_u32(blob, so + 0, cfg['stage_magic'])
    put_u32(blob, so + 4, seq)
    put_u64(blob, so + 8, jiffies)
    put_u32(blob, so + 16, stage)
    put_u32(blob, so + 20, 0)
    put_u32(blob, so + 24, crc(blob[so:so + 24]))
    put_u32(blob, so + 28, 0x424C4D53)


def write_line(blob, off, seq, text):
    cfg = L.LAYOUT
    lo = off + cfg['line_area_off'] + (seq % cfg['line_slots']) * cfg['line_slot_size']
    raw = text.encode('utf-8', 'replace')[:cfg['line_slot_fields']['text_len']]
    put_u32(blob, lo + 0, cfg['line_magic'])
    put_u32(blob, lo + 4, seq)
    put_u64(blob, lo + 8, seq)
    put_u32(blob, lo + 16, len(raw))
    blob[lo + 24:lo + 24 + len(raw)] = raw
    put_u32(blob, lo + 20, crc(blob[lo:lo + 20]))


def make_synthetic_blob(case):
    cfg = L.LAYOUT
    blob = bytearray(cfg['log_size'])
    if case == 'no_log':
        return bytes(blob)
    fdt = 0x42000000
    log = fdt + cfg['fdt_log_offset']
    ddr = fdt - cfg['fdt_base_offset_from_ddr']
    bank_index = 1
    off = cfg['bank_offsets'][bank_index]
    write_meta(blob, 3, bank_index, fdt, log)
    write_header(blob, off, 3, fdt, log, ddr)
    cases = {
        'early': {
            'stages': [1, 2],
            'lines': ['BLM monitor init'],
        },
        'scmi': {
            'stages': [1, 3, 4, 6, 8, 9, 11, 12, 13, 16],
            'lines': [
                '[1.112] arm-scmi arm-scmi.1.auto timed out in resp',
                'scmi_cpuss_telemetry_probe: Not able to find shared memory location',
                'Kernel panic - not syncing: BLM selftest',
            ],
        },
        'fbe': {
            'stages': [1, 3, 4, 6, 8, 9, 11, 12, 13, 14, 15],
            'lines': [
                'init: Failed to mount /data',
                'FBE decryption blocked',
                'vold not running',
            ],
        },
    }
    data = cases[case]
    seq = 0
    for stage in data['stages']:
        seq += 1
        write_stage(blob, off, stage, seq, seq)
    for text in data['lines']:
        seq += 1
        write_line(blob, off, seq, text)
    return bytes(blob)


def parse_defines(path):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    defs = {}
    pat = r'^\s*#define\s+(BLM_[A-Z0-9_]+)\s+(0[xX][0-9A-Fa-f]+|[0-9]+)(?:ULL|UL|U|u|L)?\b'
    for m in re.finditer(pat, text, re.M):
        defs[m.group(1)] = int(m.group(2), 0)
    stages = {}
    spat = r'^\s*#define\s+BLM_STAGE_([A-Z0-9_]+)\s+([0-9]+)U?\b'
    for m in re.finditer(spat, text, re.M):
        name = m.group(1)
        if name == 'MAX':
            continue
        stages[name] = int(m.group(2))
    return defs, stages


def cmd_validate_layout(args):
    defs, stages = parse_defines(args.header)
    errors = []
    for key, expected in L.EXPECTED_DEFINES.items():
        got = defs.get(key)
        if got is None:
            errors.append('missing ' + key)
        elif got != expected:
            errors.append(key + ' got=' + str(got) + ' expected=' + str(expected))
    expected_stages = {name: sid for sid, name in L.STAGE_NAMES.items()}
    for name, sid in expected_stages.items():
        got = stages.get(name)
        if got is None:
            errors.append('missing stage ' + name)
        elif got != sid:
            errors.append('stage ' + name + ' got=' + str(got) + ' expected=' + str(sid))
    if errors:
        for e in errors:
            print('LAYOUT_ERROR ' + e)
        return 1
    print('VALIDATE_LAYOUT_OK defines=' + str(len(L.EXPECTED_DEFINES)) + ' stages=' + str(len(expected_stages)))
    return 0


def cmd_selftest(args):
    expected = {
        'no_log': 'no_valid_bank',
        'early': 'pre_setup_arch',
        'scmi': 'scmi_timeout',
        'fbe': 'fbe_mount',
    }
    for case, want in expected.items():
        blob = make_synthetic_blob(case)
        result = analyze_blob(blob)
        got = result['rule_id']
        if got != want:
            print('SELFTEST_FAIL case=' + case + ' want=' + want + ' got=' + got)
            return 1
        print('SELFTEST_OK case=' + case + ' rule=' + got + ' stage=' + result['selected_bank']['last_stage_name'] if result['selected_bank'] else 'SELFTEST_OK case=' + case + ' rule=' + got)
    print('BLM_TOOLS_SELFTEST_OK')
    return 0


def cmd_make_fixture(args):
    blob = make_synthetic_blob(args.case)
    Path(args.out).write_bytes(blob)
    print('FIXTURE_OK case=' + args.case + ' out=' + args.out + ' size=' + str(len(blob)))
    return 0


def cmd_analyze(args):
    blob = Path(args.file).read_bytes()
    off = args.offset
    cfg = L.LAYOUT
    region = blob[off:off + cfg['log_size']]
    result = analyze_blob(region)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(human_report(result))
    return 0


def cmd_probe_ddr(args):
    text = Path(args.iomem_file).read_text(encoding='utf-8', errors='replace')
    pat = r'^([0-9A-Fa-f]+)-([0-9A-Fa-f]+)\s+:\s+System RAM'
    for line in text.splitlines():
        m = re.match(pat, line.strip())
        if m:
            print('DDR_BASE=0x' + m.group(1).lower())
            return 0
    print('DDR_BASE=UNKNOWN')
    return 1


def main():
    parser = argparse.ArgumentParser(description='bootloop monitor host tools')
    sub = parser.add_subparsers(dest='cmd')

    p = sub.add_parser('validate-layout')
    p.add_argument('--header', default=str(Path(__file__).resolve().parents[1] / 'kernel' / 'blm_layout.h'))
    p.set_defaults(func=cmd_validate_layout)

    p = sub.add_parser('selftest')
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser('make-fixture')
    p.add_argument('--case', choices=['no_log', 'early', 'scmi', 'fbe'], required=True)
    p.add_argument('--out', required=True)
    p.set_defaults(func=cmd_make_fixture)

    p = sub.add_parser('analyze')
    p.add_argument('--file', required=True)
    p.add_argument('--offset', type=lambda x: int(x, 0), default=0)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser('probe-ddr')
    p.add_argument('--iomem-file', required=True)
    p.set_defaults(func=cmd_probe_ddr)

    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
