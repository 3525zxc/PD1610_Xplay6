#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L
import blm_tools


def default_phys_base(ddr_base):
    return ddr_base + L.LAYOUT['fdt_base_offset_from_ddr'] + L.LAYOUT['fdt_log_offset']


def cmd_emit_command(args):
    phys = args.phys_base if args.phys_base is not None else default_phys_base(args.ddr_base)
    offset = phys - args.dump_base
    if offset < 0:
        print('READER_ERROR phys_base below dump_base')
        return 1
    bs = 4096
    skip = offset // bs
    count = L.LAYOUT['log_size'] // bs
    q = chr(39)
    prefix = 'adb'
    if args.serial:
        prefix += ' -s ' + args.serial
    dd = 'dd if=/dev/mem bs=' + str(bs) + ' skip=' + str(skip) + ' count=' + str(count) + ' of=/sdcard/blm_ram.bin'
    print(prefix + ' shell su -c ' + q + dd + q)
    print(prefix + ' pull /sdcard/blm_ram.bin ' + args.out)
    print('READER_HINT ddr_base=' + hex(args.ddr_base) + ' phys_base=' + hex(phys) + ' dump_base=' + hex(args.dump_base) + ' offset=' + hex(offset))
    print('READER_HINT phys_base=' + hex(phys) + '; verify ddr_base with blm_tools.py probe-ddr --iomem-file iomem.txt before device use')
    print('READER_HINT /dev/mem is absent on stock LOS16; prefer EDL peek at phys_base (0x42100000) after a failed boot')
    return 0


def cmd_read(args):
    data = Path(args.input).read_bytes()
    cfg = L.LAYOUT
    if args.already_region:
        off = 0
    elif args.offset is not None:
        off = args.offset
    else:
        phys = args.phys_base if args.phys_base is not None else default_phys_base(args.ddr_base)
        off = phys - args.dump_base
    if off < 0 or off > len(data):
        print('READER_ERROR offset outside dump')
        return 1
    region = data[off:off + cfg['log_size']]
    result = blm_tools.analyze_blob(region)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(blm_tools.human_report(result))
    print('READ_OK input=' + args.input + ' offset=' + hex(off) + ' size=' + str(len(region)))
    return 0


def cmd_selftest(args):
    blob = blm_tools.make_synthetic_blob('scmi')
    result = blm_tools.analyze_blob(blob)
    if result['rule_id'] != 'scmi_timeout':
        print('BLM_READ_SELFTEST_FAIL rule=' + result['rule_id'])
        return 1
    print('BLM_READ_SELFTEST_OK rule=' + result['rule_id'])
    return 0


def main():
    ap = argparse.ArgumentParser(description='read and judge a BLM RAM log after a failed boot')
    ap.add_argument('--input')
    ap.add_argument('--already-region', action='store_true')
    ap.add_argument('--offset', type=lambda x: int(x, 0))
    ap.add_argument('--phys-base', type=lambda x: int(x, 0))
    ap.add_argument('--ddr-base', type=lambda x: int(x, 0), default=0x40000000)
    ap.add_argument('--dump-base', type=lambda x: int(x, 0), default=0)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--emit-command', action='store_true')
    ap.add_argument('--serial', default='')
    ap.add_argument('--out', default='blm_ram.bin')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return cmd_selftest(args)
    if args.emit_command:
        return cmd_emit_command(args)
    if not args.input:
        ap.print_help()
        return 1
    return cmd_read(args)


if __name__ == '__main__':
    sys.exit(main())
