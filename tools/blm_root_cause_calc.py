#!/usr/bin/env python3
"""Compute the physical overlap between the candidate kernel's BSS-clear
region and the FDT address that aboot writes, from System.map + boot report.

Reproduces the Round 12 root-cause interval calculation. Pure offline.
"""
import argparse
import json
import re
from pathlib import Path


def sym(smap, name):
    m = re.search(r'^([0-9a-f]+) [A-Za-z] ' + re.escape(name) + r'$', smap, re.M)
    if not m:
        raise SystemExit('SYMBOL_MISSING ' + name)
    return int(m.group(1), 16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--system-map', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--ddr-base', type=lambda x: int(x, 0), default=0x40000000)
    ap.add_argument('--fdt-offset', type=lambda x: int(x, 0), default=0x2000000)
    ap.add_argument('--log-offset', type=lambda x: int(x, 0), default=0x100000)
    ap.add_argument('--text-offset', type=lambda x: int(x, 0), default=0x80000)
    ap.add_argument('--stock-image-size', type=lambda x: int(x, 0), default=0x1C9A000)
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    smap = Path(args.system_map).read_text(encoding='utf-8', errors='replace')
    report = json.loads(Path(args.report).read_text())
    bss0 = sym(smap, '__bss_start')
    bss1 = sym(smap, '__bss_stop')
    end = sym(smap, '_end')
    image_size = report['arm64_header']['image_size']

    load = args.ddr_base + args.text_offset
    fdt = args.ddr_base + args.fdt_offset
    log = fdt + args.log_offset
    # ARM64 3.18: linear map, so virt - _text_virt == phys - load_phys.
    text_virt = 0xffffffc000000000 + args.text_offset
    delta = load - text_virt
    bss0_p, bss1_p, end_p = bss0 + delta, bss1 + delta, end + delta
    stock_end = load + args.stock_image_size

    result = {
        'ddr_base': hex(args.ddr_base),
        'kernel_load_phys': hex(load),
        'fdt_phys': hex(fdt),
        'blm_log_phys': hex(log),
        'candidate': {
            'text_virt': hex(text_virt),
            '__bss_start_virt': hex(bss0), '__bss_stop_virt': hex(bss1), '_end_virt': hex(end),
            'image_size': image_size, 'image_size_hex': hex(image_size),
            '__bss_start_phys': hex(bss0_p), '__bss_stop_phys': hex(bss1_p), '_end_phys': hex(end_p),
            'image_span_phys': [hex(load), hex(load + image_size)],
        },
        'stock': {'image_size': args.stock_image_size, 'image_size_hex': hex(args.stock_image_size),
                  '_end_phys': hex(stock_end),
                  'iomem_kernel_data_end': '0x41d19fff'},
        'checks': {
            'fdt_inside_candidate_image': load <= fdt < end_p,
            'fdt_inside_candidate_bss': bss0_p <= fdt <= bss1_p,
            'fdt_inside_stock_image': load <= fdt < stock_end,
            'blm_log_outside_candidate_image': log >= end_p,
            'candidate_overlap_bytes': end_p - fdt if end_p > fdt else 0,
            'candidate_overlap_hex': hex(end_p - fdt) if end_p > fdt else '0x0',
            'stock_gap_to_fdt_bytes': fdt - stock_end,
            'stock_gap_to_fdt_hex': hex(fdt - stock_end),
            'shrink_needed_to_clear_fdt_bytes': end_p - fdt,
        },
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding='utf-8')
    print('ROOT_CAUSE_CALC fdt=%s candidate_bss=[%s,%s] candidate_end=%s stock_end=%s'
          % (hex(fdt), hex(bss0_p), hex(bss1_p), hex(end_p), hex(stock_end)))
    print('ROOT_CAUSE_CHECKS fdt_in_candidate_bss=%s fdt_in_stock=%s log_outside=%s overlap=%s shrink_needed=%d'
          % (result['checks']['fdt_inside_candidate_bss'],
             result['checks']['fdt_inside_stock_image'],
             result['checks']['blm_log_outside_candidate_image'],
             result['checks']['candidate_overlap_hex'],
             result['checks']['shrink_needed_to_clear_fdt_bytes']))
    return 0


if __name__ == '__main__':
    sys_exit = __import__('sys').exit
    sys_exit(main())
