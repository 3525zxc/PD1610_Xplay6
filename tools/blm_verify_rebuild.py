#!/usr/bin/env python3
"""Independent verification of a DDR_BASE-corrected BLM boot.img rebuild.

Checks that the rebuilt image differs from the previous one only in the
idx79 BLM reserved-memory node and the recomputed boot header id, extracts
the patched DTB, and reports the runtime address fields from the header.
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
import blm_layout as L

HDR_FIELDS = {
    'kernel_size': 8,
    'kernel_addr': 12,
    'ramdisk_size': 16,
    'ramdisk_addr': 20,
    'second_size': 24,
    'second_addr': 28,
    'tags_addr': 32,
    'page_size': 36,
}


def diff_blocks(a, b, block=4096):
    if len(a) != len(b):
        raise SystemExit('SIZE_MISMATCH')
    hits = [off for off in range(0, len(a), block)
            if a[off:off + block] != b[off:off + block]]
    merged = []
    for off in hits:
        if merged and off == merged[-1][1]:
            merged[-1][1] = off + block
        else:
            merged.append([off, off + block])
    return hits, merged


def describe(off, page, ks, rs, ss, A, LBL, sig_len):
    kernel_end = page + ks
    ramdisk_start = page + A(ks)
    ramdisk_end = ramdisk_start + rs
    sig_start = LBL
    if off < page:
        return 'header'
    if off < kernel_end:
        return 'kernel_segment'
    if off < ramdisk_start:
        return 'kernel_padding'
    if off < ramdisk_end:
        return 'ramdisk'
    if off < sig_start:
        return 'ramdisk_padding'
    if off < sig_start + sig_len:
        return 'signature'
    return 'tail'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True)
    ap.add_argument('--new', required=True)
    ap.add_argument('--dtb-out', required=True)
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    old = Path(args.old).read_bytes()
    new = Path(args.new).read_bytes()
    page, ks, rs, ss, A, LBL = B.layout(old)
    sig_len = 5376

    hits, merged = diff_blocks(old, new)
    regions = sorted({describe(o, page, ks, rs, ss, A, LBL, sig_len) for o in hits})

    k_old = old[page:page + ks]
    k_new = new[page:page + ks]
    g_old = B.first_dtb(k_old)
    g_new = B.first_dtb(k_new)
    chain_old = B.count_dtbs(k_old, g_old)
    chain_new = B.count_dtbs(k_new, g_new)
    idx79_old = k_old[chain_old[79][0]:chain_old[79][0] + chain_old[79][1]]
    idx79_new = k_new[chain_new[79][0]:chain_new[79][0] + chain_new[79][1]]

    ramdisk_old = old[page + A(ks):page + A(ks) + rs]
    ramdisk_new = new[page + A(ks):page + A(ks) + rs]
    sig_old = old[LBL:LBL + sig_len]
    sig_new = new[LBL:LBL + sig_len]
    pad_off = page + g_new + len(k_new[g_new:g_new + chain_new[-1][0] + chain_new[-1][1]])

    fdt = F.Fdt(idx79_new)
    nodes = fdt.parse_nodes()
    reserved = fdt.find_reserved_memory(nodes)
    log = fdt.find_log_node(reserved, nodes)
    reg = log['props'].get('reg', b'') if log else b''
    cells = struct.unpack('>IIII', reg[:16]) if len(reg) >= 16 else None

    header = {k: hex(struct.unpack_from('<I', new, off)[0]) for k, off in HDR_FIELDS.items()}

    checks = [
        ('size_equal', len(old) == len(new), len(new)),
        ('header_before_id_identical', old[:0x240] == new[:0x240], ''),
        ('header_after_id_identical', old[0x254:page] == new[0x254:page], ''),
        ('header_id_recomputed', new[0x240:0x254] == B.compute_id(k_new, ramdisk_new), ''),
        ('header_id_changed', old[0x240:0x254] != new[0x240:0x254], ''),
        ('gzip_payload_identical', k_old[:g_old] == k_new[:g_new], g_new),
        ('first_79_dtbs_identical', k_old[g_old:chain_old[79][0]] == k_new[g_new:chain_new[79][0]], chain_old[79][0] - g_old),
        ('dtb_count_unchanged', len(chain_old) == len(chain_new) == 80, len(chain_new)),
        ('idx79_size_unchanged', len(idx79_old) == len(idx79_new), len(idx79_new)),
        ('idx79_changed', idx79_old != idx79_new, ''),
        ('tail_padding_identical', k_old[chain_old[-1][0] + chain_old[-1][1]:] == k_new[chain_new[-1][0] + chain_new[-1][1]:], pad_off),
        ('ramdisk_identical', ramdisk_old == ramdisk_new, rs),
        ('signature_identical', sig_old == sig_new, sig_len),
        ('diff_regions_expected', regions == ['header', 'kernel_segment'], regions),
        ('blm_node_present', log is not None, log['name'] if log else 'ABSENT'),
        ('blm_node_name_42100000', bool(log) and log['name'] == 'blm-ram-log@42100000', log['name'] if log else ''),
        ('blm_reg_42100000_0x40000', cells is not None and (cells[1], cells[3]) == (0x42100000, 0x40000),
         (hex(cells[1]), hex(cells[3])) if cells else ''),
        ('blm_node_name_82100000_absent', b'blm-ram-log@82100000' not in k_new, ''),
        ('stock_model_string_retained', b'vivo MSM 8996 v3 + PMI8996 PD1610' in idx79_new, ''),
    ]

    Path(args.dtb_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.dtb_out).write_bytes(idx79_new)

    npass = sum(1 for _, ok, _ in checks if ok)
    report = {
        'status': 'PASS' if npass == len(checks) else 'FAIL',
        'pass': npass,
        'total': len(checks),
        'old': {'path': str(args.old), 'sha256': hashlib.sha256(old).hexdigest(), 'size': len(old)},
        'new': {'path': str(args.new), 'sha256': hashlib.sha256(new).hexdigest(), 'size': len(new)},
        'header_fields': header,
        'layout': {'page': page, 'kernel_size': ks, 'ramdisk_size': rs, 'second_size': ss, 'signature_off': LBL},
        'gzip_len': g_new,
        'dtb_count': len(chain_new),
        'idx79_size': len(idx79_new),
        'idx79_sha256': hashlib.sha256(idx79_new).hexdigest(),
        'diff_block_count': len(hits),
        'diff_ranges': [{'start': hex(a), 'end': hex(b), 'bytes': b - a} for a, b in merged],
        'diff_regions': regions,
        'blm_node': {'name': log['name'] if log else None,
                     'reg': [hex(c) for c in cells] if cells else None},
        'fdt_phys_expected': hex(0x40000000 + L.LAYOUT['fdt_base_offset_from_ddr']),
        'checks': [{'name': n, 'ok': bool(ok), 'detail': str(d)} for n, ok, d in checks],
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('REBUILD_VERIFY status=' + report['status'] + ' pass=' + str(npass) + '/' + str(len(checks))
          + ' diff_blocks=' + str(len(hits)) + ' diff_regions=' + ','.join(regions)
          + ' blm_node=' + str(report['blm_node']['name']) + ' reg=' + str(report['blm_node']['reg'])
          + ' tags_addr=' + header['tags_addr'] + ' kernel_addr=' + header['kernel_addr'])
    print('REBUILD_VERIFY_REPORT out=' + str(args.report))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
