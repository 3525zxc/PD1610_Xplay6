#!/usr/bin/env python3
"""Verify that the A/B boot.img pair differs ONLY in the header id and the
128-byte blm-ram-log node region inside idx79.

Everything else - gzip payload, first 79 DTBs, the rest of idx79, DTB chain
length, tail padding length and bytes, ramdisk, signature block, all header
fields except id - must be byte-identical.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_build_bootimg as B
import blm_patch_dtb as F

HDR_FIELDS = {
    'kernel_size': 8, 'kernel_addr': 12, 'ramdisk_size': 16, 'ramdisk_addr': 20,
    'second_size': 24, 'second_addr': 28, 'tags_addr': 32, 'page_size': 36,
}
NODE_START = 370360
NODE_END = 370488


def diff_ranges(a, b, block=4):
    if len(a) != len(b):
        raise SystemExit('SIZE_MISMATCH %d %d' % (len(a), len(b)))
    hits = [o for o in range(0, len(a), block) if a[o:o + block] != b[o:o + block]]
    merged = []
    for o in hits:
        if merged and merged[-1][1] == o:
            merged[-1][1] = o + block
        else:
            merged.append([o, o + block])
    return hits, merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-node', required=True)
    ap.add_argument('--control', required=True)
    ap.add_argument('--dtb-with-node', required=True)
    ap.add_argument('--dtb-control', required=True)
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    a = Path(args.with_node).read_bytes()
    b = Path(args.control).read_bytes()
    da = Path(args.dtb_with_node).read_bytes()
    db = Path(args.dtb_control).read_bytes()
    page, ks, rs, ss, A, LBL = B.layout(a)
    sig_len = 5376

    hits, merged = diff_ranges(a, b)
    ka, kb = a[page:page + ks], b[page:page + ks]
    ga, gb = B.first_dtb(ka), B.first_dtb(kb)
    ca, cb = B.count_dtbs(ka, ga), B.count_dtbs(kb, gb)
    i79 = ca[79][0]
    idx79_a = ka[ca[79][0]:ca[79][0] + ca[79][1]]
    idx79_b = kb[cb[79][0]:cb[79][0] + cb[79][1]]

    # expected differing regions: header id [0x240,0x254) and the node span
    # inside idx79 (absolute = page + gzip_len + i79 + NODE_START/END)
    # count_dtbs() offsets are already relative to the start of the kernel
    # segment, so idx79's absolute offset is page + i79 (no extra gzip term).
    node_abs_start = page + i79 + NODE_START
    node_abs_end = page + i79 + NODE_END
    id_start, id_end = 0x240, 0x254
    unexpected = [o for o in hits
                  if not (id_start <= o < id_end or node_abs_start <= o < node_abs_end)]
    in_id = [o for o in hits if id_start <= o < id_end]
    in_node = [o for o in hits if node_abs_start <= o < node_abs_end]

    # byte-level diff inside idx79
    dtb_hits = [i for i in range(0, min(len(da), len(db)), 4)
                if da[i:i + 4] != db[i:i + 4]]
    dtb_outside = [i for i in dtb_hits if not (NODE_START <= i < NODE_END)]
    dtb_inside = [i for i in dtb_hits if NODE_START <= i < NODE_END]

    fdt_a = F.Fdt(da)
    fdt_b = F.Fdt(db)
    nodes_a = fdt_a.parse_nodes()
    nodes_b = fdt_b.parse_nodes()
    res_a = fdt_a.find_reserved_memory(nodes_a)
    res_b = fdt_b.find_reserved_memory(nodes_b)
    log_a = fdt_a.find_log_node(res_a, nodes_a)
    log_b = fdt_b.find_log_node(res_b, nodes_b)

    checks = [
        ('sizes_equal', len(a) == len(b) == 58483968, (len(a), len(b))),
        ('header_before_id_identical', a[:id_start] == b[:id_start], ''),
        ('header_after_id_identical', a[id_end:page] == b[id_end:page], ''),
        ('header_id_differs', a[id_start:id_end] != b[id_start:id_end], ''),
        ('header_id_recomputed_control', b[id_start:id_end] == B.compute_id(kb, b[page + A(ks):page + A(ks) + rs]), ''),
        ('gzip_identical', ka[:ga] == kb[:gb], ga),
        ('first_79_dtbs_identical', ka[ga:ca[79][0]] == kb[gb:cb[79][0]], ca[79][0] - ga),
        ('dtb_count_equal', len(ca) == len(cb) == 80, (len(ca), len(cb))),
        ('idx79_sizes_equal', len(idx79_a) == len(idx79_b) == 409688, (len(idx79_a), len(idx79_b))),
        ('idx79_headers_identical', da[:40] == db[:40], ''),
        ('idx79_strings_identical',
         da[F.be32(da, 12):F.be32(da, 12) + F.be32(da, 32)]
         == db[F.be32(db, 12):F.be32(db, 12) + F.be32(db, 32)], ''),
        ('idx79_diff_confined_to_node', len(dtb_outside) == 0, dtb_outside[:8]),
        ('idx79_diff_inside_node_present', len(dtb_inside) > 0, len(dtb_inside)),
        ('idx79_diff_span_exact', len(dtb_inside) == (NODE_END - NODE_START) // 4,
         (len(dtb_inside), (NODE_END - NODE_START) // 4)),
        ('with_node_has_log_node', log_a is not None, log_a['name'] if log_a else ''),
        ('control_has_no_log_node', log_b is None, log_b['name'] if log_b else ''),
        ('node_count_minus_one', len(nodes_b) == len(nodes_a) - 1, (len(nodes_a), len(nodes_b))),
        ('tail_padding_identical',
         ka[ca[-1][0] + ca[-1][1]:] == kb[cb[-1][0] + cb[-1][1]:], ''),
        ('pad_length_identical',
         len(ka) - (ca[-1][0] + ca[-1][1]) == len(kb) - (cb[-1][0] + cb[-1][1]), ''),
        ('ramdisk_identical', a[page + A(ks):page + A(ks) + rs] == b[page + A(ks):page + A(ks) + rs], rs),
        ('signature_identical', a[LBL:LBL + sig_len] == b[LBL:LBL + sig_len], sig_len),
        ('all_header_fields_identical',
         all(struct.unpack_from('<I', a, o) == struct.unpack_from('<I', b, o)
             for o in HDR_FIELDS.values()), ''),
        ('no_unexpected_diff', len(unexpected) == 0, unexpected[:8]),
        ('diff_only_in_expected_regions',
         len(in_id) > 0 and len(in_node) > 0 and len(hits) == len(in_id) + len(in_node),
         (len(hits), len(in_id), len(in_node))),
    ]

    npass = sum(1 for _, ok, _ in checks if ok)
    report = {
        'status': 'PASS' if npass == len(checks) else 'FAIL',
        'pass': npass,
        'total': len(checks),
        'with_node': {'path': str(args.with_node), 'sha256': hashlib.sha256(a).hexdigest(), 'size': len(a)},
        'control': {'path': str(args.control), 'sha256': hashlib.sha256(b).hexdigest(), 'size': len(b)},
        'dtb_with_node': {'path': str(args.dtb_with_node), 'sha256': hashlib.sha256(da).hexdigest(), 'size': len(da)},
        'dtb_control': {'path': str(args.dtb_control), 'sha256': hashlib.sha256(db).hexdigest(), 'size': len(db)},
        'layout': {'page': page, 'kernel_size': ks, 'ramdisk_size': rs, 'gzip_len': ga,
                   'dtb_chain_len': ca[-1][0] + ca[-1][1] - ga,
                   'pad': len(ka) - (ca[-1][0] + ca[-1][1]), 'pos': ga,
                   'idx79_offset_in_kernel': i79, 'idx79_size': len(idx79_a)},
        'expected_diff_regions': {
            'header_id': [id_start, id_end],
            'log_node_absolute': [node_abs_start, node_abs_end],
            'log_node_in_dtb': [NODE_START, NODE_END],
        },
        'diff': {'blocks_4b': len(hits), 'ranges': [{'start': x, 'end': y} for x, y in merged],
                 'in_id': len(in_id), 'in_node': len(in_node), 'unexpected': unexpected[:8],
                 'dtb_blocks_4b': len(dtb_hits), 'dtb_outside_node': len(dtb_outside)},
        'fdt': {'nodes_with_node': len(nodes_a), 'nodes_control': len(nodes_b),
                'log_node_with': log_a['name'] if log_a else None,
                'reserved_children_with': len([n for n in nodes_a if n['path'].startswith(res_a['path'].rstrip('/') + '/') and n['path'] != res_a['path']]),
                'reserved_children_control': len([n for n in nodes_b if n['path'].startswith(res_b['path'].rstrip('/') + '/') and n['path'] != res_b['path']])},
        'checks': [{'name': n, 'ok': bool(ok), 'detail': str(d)} for n, ok, d in checks],
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('AB_VERIFY status=%s pass=%d/%d diff_4b=%d in_id=%d in_node=%d unexpected=%d'
          % (report['status'], npass, len(checks), len(hits), len(in_id), len(in_node), len(unexpected)))
    print('AB_VERIFY_RANGES ' + repr([{'start': x, 'end': y} for x, y in merged]))
    print('AB_VERIFY_CONTROL sha256=' + report['control']['sha256'])
    print('AB_VERIFY_REPORT out=' + str(args.report))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
