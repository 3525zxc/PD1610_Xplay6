#!/usr/bin/env python3
"""Generate an equal-length FDT_NOP bypass for the qpnp-vibrator device node.

Single variable vs the Round 17 image: the 148-byte struct-block span of
/soc/qcom,spmi@400f000/qcom,pm8994@1/qcom,vibrator@5100 is replaced by 37
FDT_NOP tags.  Header (all 10 fields), totalsize, strings block, struct-block
size, DTB chain length and boot.img tail padding stay byte-identical.

The BLM reserved-memory node is kept, so BLM logging is unchanged.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_patch_dtb as F
import blm_ab_audit as A

VIBRATOR_PATH_SUFFIX = 'qcom,vibrator@5100'


def find_vibrator(data):
    fdt = F.Fdt(data)
    nodes = fdt.parse_nodes()
    hits = [n for n in nodes if n['name'] == VIBRATOR_PATH_SUFFIX
            or ('vibrator' in n['name'].lower() and 'spmi' in n['path'].lower())]
    if len(hits) != 1:
        raise SystemExit('VIBRATOR_NODE_COUNT_EXPECTED_1_GOT_%d' % len(hits))
    n = hits[0]
    return fdt, nodes, n, (n['start'], n['end'] + 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='idx79 DTB with BLM node (Round 17 basis)')
    ap.add_argument('--bypass-out', required=True)
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    src = Path(args.source).read_bytes()
    fdt, nodes, node, (start, end) = find_vibrator(src)
    src_audit = A.audit(src, 'source_with_vibrator')
    if src_audit['status'] != 'OK':
        raise SystemExit('SOURCE_AUDIT_FAIL %s' % src_audit['errors'])

    # Sanity: no phandle on the node => nothing else can reference it
    if 'phandle' in node['props'] or 'linux,phandle' in node['props']:
        raise SystemExit('VIBRATOR_HAS_PHANDLE - whole-node NOP unsafe')

    bypass, span = A.make_control(src, start, end)
    by_audit = A.audit(bypass, 'bypass_vibrator_nop')

    bf, bn, _, _ = (None, None, None, None)
    # After NOP the vibrator node must be gone; BLM node must remain.
    bf = F.Fdt(bypass)
    bnodes = bf.parse_nodes()
    vib_after = [n for n in bnodes if n['name'] == VIBRATOR_PATH_SUFFIX]
    reserved = bf.find_reserved_memory(bnodes)
    log = bf.find_log_node(reserved, bnodes)

    diff = A.diff_outside(src, bypass, start, end)
    hs, hb = A.header(src), A.header(bypass)
    strings_same = (src[hs['off_dt_strings']:hs['off_dt_strings'] + hs['size_dt_strings']]
                    == bypass[hb['off_dt_strings']:hb['off_dt_strings'] + hb['size_dt_strings']])

    checks = [
        ('source_audit_ok', src_audit['status'] == 'OK', src_audit['errors']),
        ('bypass_audit_ok', by_audit['status'] == 'OK', by_audit['errors']),
        ('vibrator_node_absent', len(vib_after) == 0, [n['path'] for n in vib_after]),
        ('blm_log_node_present', log is not None, ''),
        ('node_count_minus_one', len(bnodes) == len(nodes) - 1, (len(nodes), len(bnodes))),
        ('identical_length', len(src) == len(bypass), (len(src), len(bypass))),
        ('identical_header_all_fields', hs == hb, ''),
        ('identical_strings_block', strings_same, ''),
        ('no_diff_outside_node', diff['outside_node'] == 0, diff['outside_sample']),
        ('diff_inside_node_only', diff['inside_node'] > 0
         and diff['diff_4b_blocks'] == diff['inside_node'], diff['inside_ranges']),
        ('span_4_aligned', span % 4 == 0, span),
        ('span_is_148', span == 148, span),
        ('struct_size_unchanged', hb['size_dt_struct'] == hs['size_dt_struct'], ''),
        ('off_strings_unchanged', hb['off_dt_strings'] == hs['off_dt_strings'], ''),
        ('totalsize_unchanged', hb['totalsize'] == hs['totalsize'], ''),
    ]
    npass = sum(1 for _, ok, _ in checks if ok)
    report = {
        'status': 'PASS' if npass == len(checks) else 'FAIL',
        'pass': npass,
        'total': len(checks),
        'source': str(args.source),
        'bypass': str(args.bypass_out),
        'node': {'name': node['name'], 'path': node['path'],
                 'start': start, 'end': end, 'span': span,
                 'props': sorted(node['props'].keys())},
        'source_audit': src_audit,
        'bypass_audit': by_audit,
        'diff': diff,
        'checks': [{'name': n, 'ok': bool(ok), 'detail': str(d)} for n, ok, d in checks],
    }
    Path(args.bypass_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.bypass_out).write_bytes(bypass)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BYPASS_DTB status=%s pass=%d/%d span=%d offset=[%d,%d) sha256=%s'
          % (report['status'], npass, len(checks), span, start, end,
             hashlib.sha256(bypass).hexdigest()))
    print('BYPASS_DTB_DETAIL vibrator_absent=%s blm_node_present=%s nodes=%d->%d diff_4b=%d outside=%d'
          % (len(vib_after) == 0, log is not None, len(nodes), len(bnodes),
             diff['diff_4b_blocks'], diff['outside_node']))
    print('REPORT_OK ' + str(args.report))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
