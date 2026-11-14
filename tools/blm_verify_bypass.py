#!/usr/bin/env python3
"""Image-level single-variable verification for the qpnp-vibrator bypass.

Baseline = Round 17 image (boot_los16_blm_vib_20261114160500.img)
Bypass   = same kernel + same DTB chain, except the 148-byte vibrator node
           inside idx79 replaced by FDT_NOP tags.

Expected differences in the whole 58 MB file:
  * header id at [0x240, 0x254)
  * vibrator node span inside idx79
Everything else (gzip payload, first 79 DTBs, rest of idx79, chain length,
tail padding, ramdisk, signature, all other header fields) must be identical.
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
VIBRATOR_NAME = 'qcom,vibrator@5100'


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


def count_vibrator(data):
    fdt = F.Fdt(data)
    nodes = fdt.parse_nodes()
    vib = [n for n in nodes if n['name'] == VIBRATOR_NAME]
    res = fdt.find_reserved_memory(nodes)
    log = fdt.find_log_node(res, nodes)
    return nodes, vib, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--bypass', required=True)
    ap.add_argument('--dtb-baseline', required=True)
    ap.add_argument('--dtb-bypass', required=True)
    ap.add_argument('--node-start', type=int, required=True)
    ap.add_argument('--node-end', type=int, required=True)
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    a = Path(args.baseline).read_bytes()
    b = Path(args.bypass).read_bytes()
    da = Path(args.dtb_baseline).read_bytes()
    db = Path(args.dtb_bypass).read_bytes()
    page, ks, rs, ss, A, LBL = B.layout(a)
    sig_len = B.SIG_LEN

    hits, merged = diff_ranges(a, b)
    ka, kb = a[page:page + ks], b[page:page + ks]
    ga, gb = B.first_dtb(ka), B.first_dtb(kb)
    ca, cb = B.count_dtbs(ka, ga), B.count_dtbs(kb, gb)
    i79 = ca[79][0]
    idx79_a = ka[i79:i79 + ca[79][1]]
    idx79_b = kb[cb[79][0]:cb[79][0] + cb[79][1]]

    node_abs_start = page + i79 + args.node_start
    node_abs_end = page + i79 + args.node_end
    id_start, id_end = 0x240, 0x254
    unexpected = [o for o in hits
                  if not (id_start <= o < id_end or node_abs_start <= o < node_abs_end)]
    in_id = [o for o in hits if id_start <= o < id_end]
    in_node = [o for o in hits if node_abs_start <= o < node_abs_end]

    dtb_hits = [i for i in range(0, min(len(da), len(db)), 4)
                if da[i:i + 4] != db[i:i + 4]]
    dtb_outside = [i for i in dtb_hits if not (args.node_start <= i < args.node_end)]
    dtb_inside = [i for i in dtb_hits if args.node_start <= i < args.node_end]

    nodes_a, vib_a, log_a = count_vibrator(da)
    nodes_b, vib_b, log_b = count_vibrator(db)

    checks = [
        ('sizes_equal', len(a) == len(b) == 58483968, (len(a), len(b))),
        ('header_before_id_identical', a[:id_start] == b[:id_start], ''),
        ('header_after_id_identical', a[id_end:page] == b[id_end:page], ''),
        ('header_id_differs', a[id_start:id_end] != b[id_start:id_end], ''),
        ('header_id_recomputed_bypass',
         b[id_start:id_end] == B.compute_id(kb, b[page + A(ks):page + A(ks) + rs]), ''),
        ('gzip_identical', ka[:ga] == kb[:gb], ga),
        ('first_79_dtbs_identical', ka[ga:i79] == kb[gb:cb[79][0]], i79 - ga),
        ('dtb_count_equal', len(ca) == len(cb) == 80, (len(ca), len(cb))),
        ('idx79_sizes_equal', len(idx79_a) == len(idx79_b) == 409688, (len(idx79_a), len(idx79_b))),
        ('idx79_headers_identical', da[:40] == db[:40], ''),
        ('idx79_strings_identical',
         da[F.be32(da, 12):F.be32(da, 12) + F.be32(da, 32)]
         == db[F.be32(db, 12):F.be32(db, 12) + F.be32(db, 32)], ''),
        ('idx79_diff_confined_to_vibrator_node', len(dtb_outside) == 0, dtb_outside[:8]),
        ('idx79_diff_inside_node_present', len(dtb_inside) > 0, len(dtb_inside)),
        # Some 4-byte blocks inside the node already equal FDT_NOP, so the
        # byte diff count can be smaller than span/4. The real invariant is
        # that the whole span in the bypass DTB consists of FDT_NOP tags.
        ('bypass_node_span_all_fdt_nop',
         db[args.node_start:args.node_end]
         == struct.pack('>I', F.FDT_NOP) * ((args.node_end - args.node_start) // 4),
         (args.node_end - args.node_start) // 4),
        ('bypass_node_span_37_tags',
         (args.node_end - args.node_start) // 4 == 37,
         (args.node_end - args.node_start) // 4),
        ('baseline_has_vibrator_node', len(vib_a) == 1, len(vib_a)),
        ('bypass_has_no_vibrator_node', len(vib_b) == 0, len(vib_b)),
        ('blm_node_present_in_both', log_a is not None and log_b is not None, ''),
        ('node_count_minus_one', len(nodes_b) == len(nodes_a) - 1, (len(nodes_a), len(nodes_b))),
        ('tail_padding_identical',
         ka[ca[-1][0] + ca[-1][1]:] == kb[cb[-1][0] + cb[-1][1]:], ''),
        ('pad_length_identical',
         len(ka) - (ca[-1][0] + ca[-1][1]) == len(kb) - (cb[-1][0] + cb[-1][1]), ''),
        ('ramdisk_identical',
         a[page + A(ks):page + A(ks) + rs] == b[page + A(ks):page + A(ks) + rs], rs),
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
        'baseline': {'path': str(args.baseline), 'sha256': hashlib.sha256(a).hexdigest(), 'size': len(a)},
        'bypass': {'path': str(args.bypass), 'sha256': hashlib.sha256(b).hexdigest(), 'size': len(b)},
        'layout': {'page': page, 'kernel_size': ks, 'gzip_len': ga,
                   'dtb_chain_len': ca[-1][0] + ca[-1][1] - ga,
                   'pad': len(ka) - (ca[-1][0] + ca[-1][1]),
                   'idx79_offset_in_kernel': i79, 'idx79_size': len(idx79_a)},
        'expected_diff_regions': {
            'header_id': [id_start, id_end],
            'vibrator_node_absolute': [node_abs_start, node_abs_end],
            'vibrator_node_in_dtb': [args.node_start, args.node_end],
        },
        'diff': {'blocks_4b': len(hits),
                 'ranges': [{'start': x, 'end': y} for x, y in merged],
                 'in_id': len(in_id), 'in_node': len(in_node),
                 'unexpected': unexpected[:8], 'dtb_blocks_4b': len(dtb_hits),
                 'dtb_outside_node': len(dtb_outside)},
        'checks': [{'name': n, 'ok': bool(ok), 'detail': str(d)} for n, ok, d in checks],
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BYPASS_VERIFY status=%s pass=%d/%d diff_4b=%d in_id=%d in_node=%d unexpected=%d'
          % (report['status'], npass, len(checks), len(hits), len(in_id), len(in_node), len(unexpected)))
    print('BYPASS_VERIFY_RANGES ' + repr([{'start': x, 'end': y} for x, y in merged]))
    print('BYPASS_VERIFY_BYPASS sha256=' + report['bypass']['sha256'])
    print('REPORT_OK ' + str(args.report))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
