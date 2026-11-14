#!/usr/bin/env python3
"""Mandatory pre-flash gate: refuse any boot.img whose kernel would overwrite
the FDT at 0x42000000 with its BSS-clear region.

Reads the built Image.gz-dtb + System.map + boot.img report, recomputes the
physical _end from the ACTUAL kernel binary that is inside the boot.img, and
compares with the FDT address aboot uses at runtime.
"""
import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_build_bootimg as B
import blm_layout as L

DDR_BASE = 0x40000000
TEXT_OFFSET = 0x80000
TEXT_VIRT = 0xffffffc000000000 + TEXT_OFFSET
FDT_PHYS = DDR_BASE + L.LAYOUT['fdt_base_offset_from_ddr']
LOG_PHYS = FDT_PHYS + L.LAYOUT['fdt_log_offset']


def sym(smap, name):
    m = re.search(r'^([0-9a-f]+) [A-Za-z] ' + re.escape(name) + r'$', smap, re.M)
    return int(m.group(1), 16) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True, help='compiled Image.gz-dtb')
    ap.add_argument('--system-map', required=True)
    ap.add_argument('--bootimg', required=True)
    ap.add_argument('--bootimg-report', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--min-margin', type=lambda x: int(x, 0), default=0x100000)
    args = ap.parse_args()

    raw = Path(args.image).read_bytes()
    gz_end = B.first_dtb(raw)
    z = zlib.decompressobj(16 + zlib.MAX_WBITS)
    image = z.decompress(raw[:gz_end]) + z.flush()
    ah = B.arm64_header(image)
    smap = Path(args.system_map).read_text(encoding='utf-8', errors='replace')
    bss0, bss1, end = sym(smap, '__bss_start'), sym(smap, '__bss_stop'), sym(smap, '_end')
    if None in (bss0, bss1, end):
        raise SystemExit('SYMBOL_MISSING')

    load = DDR_BASE + TEXT_OFFSET
    delta = load - TEXT_VIRT
    bss0_p, bss1_p, end_p = bss0 + delta, bss1 + delta, end + delta
    margin = FDT_PHYS - end_p

    boot = Path(args.bootimg).read_bytes()
    rep = json.loads(Path(args.bootimg_report).read_text())
    page, ks, rs, ss, A, LBL = B.layout(boot)
    kernel = boot[page:page + ks]
    inner_gz = B.first_dtb(kernel)
    z2 = zlib.decompressobj(16 + zlib.MAX_WBITS)
    embedded = z2.decompress(kernel[:inner_gz]) + z2.flush()
    embedded_ah = B.arm64_header(embedded)

    dtbs = B.count_dtbs(kernel, inner_gz)
    idx79 = kernel[dtbs[79][0]:dtbs[79][0] + dtbs[79][1]] if len(dtbs) >= 80 else b''

    checks = [
        ('compiled_gzip_eof', z.eof, ''),
        ('compiled_arm64_magic', ah is not None and ah['magic'] == 0x644D5241,
         hex(ah['magic']) if ah else 'n/a'),
        ('compiled_text_offset_0x80000', ah is not None and ah['text_offset'] == TEXT_OFFSET, ''),
        ('bootimg_embedded_gzip_matches', embedded == image, len(embedded)),
        ('bootimg_embedded_image_size_matches',
         embedded_ah is not None and ah is not None
         and embedded_ah['image_size'] == ah['image_size'], ''),
        ('END_BELOW_FDT', end_p < FDT_PHYS, hex(end_p)),
        ('FDT_OUTSIDE_BSS', not (bss0_p <= FDT_PHYS <= bss1_p), ''),
        ('FDT_OUTSIDE_IMAGE', not (load <= FDT_PHYS < end_p), ''),
        ('MARGIN_AT_LEAST_MIN', margin >= args.min_margin, hex(margin)),
        ('LOG_OUTSIDE_IMAGE', LOG_PHYS >= end_p, hex(LOG_PHYS)),
        ('bootimg_report_pass', rep.get('status') == 'PASS', rep.get('status')),
        ('bootimg_size_fixed', len(boot) == 58483968 and ks == 56551493, len(boot)),
        ('gzip_matches_report', inner_gz == rep.get('gzip_len'), inner_gz),
        ('dtb_chain_80', len(dtbs) == 80, len(dtbs)),
        ('idx79_model_present', b'vivo MSM 8996 v3 + PMI8996 PD1610' in idx79, ''),
        ('blm_node_present', b'blm-ram-log@42100000' in idx79, ''),
        ('M1_adjacency', kernel[inner_gz:inner_gz + 4] == B.MAGIC, ''),
    ]
    npass = sum(1 for _, ok, _ in checks if ok)
    status = 'PASS' if npass == len(checks) else 'FAIL'
    report = {
        'status': status,
        'pass': npass,
        'total': len(checks),
        'verdict': 'SAFE_TO_FLASH' if status == 'PASS' else 'REFUSE_TO_FLASH',
        'compiled': {
            'image': str(args.image), 'gzip_len': gz_end,
            'image_len': len(image), 'image_size': ah['image_size'] if ah else None,
            'image_size_hex': hex(ah['image_size']) if ah else '',
            'bss_phys': [hex(bss0_p), hex(bss1_p)], 'end_phys': hex(end_p),
        },
        'runtime_addresses': {
            'ddr_base': hex(DDR_BASE), 'kernel_load': hex(load),
            'fdt': hex(FDT_PHYS), 'blm_log': hex(LOG_PHYS),
            'margin_to_fdt': margin, 'margin_hex': hex(margin) if margin >= 0 else '-' + hex(-margin),
            'min_margin_required': hex(args.min_margin),
        },
        'bootimg': {
            'path': str(args.bootimg), 'sha256': rep.get('sha256'),
            'size': len(boot), 'gzip_len': inner_gz, 'dtb_count': len(dtbs),
            'report_status': rep.get('status'),
        },
        'checks': [{'name': n, 'ok': bool(ok), 'detail': str(d)} for n, ok, d in checks],
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PREFLIGHT status=%s pass=%d/%d verdict=%s end_phys=%s fdt=%s margin=%s'
          % (status, npass, len(checks), report['verdict'], hex(end_p), hex(FDT_PHYS), hex(margin)))
    for n, ok, d in checks:
        if not ok:
            print('PREFLIGHT_FAIL ' + n + ' ' + str(d))
    print('PREFLIGHT_REPORT out=' + str(args.report))
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
