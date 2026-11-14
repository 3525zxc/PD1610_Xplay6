#!/usr/bin/env python3
"""Decode the 16 fixed-position BLM trace slots ("TRC <tag> <hex>").

These slots are immune to printk floods: ordinary lines only occupy slots
[32, 384), so even a panic register dump cannot evict the last checkpoint.
Slot 0 holds the last do_one_initcall() function pointer; slots 1..11 are
usb_bam_probe() milestones; slot 15 is the watchdog snapshot; slots 16..26
are qpnp_vibrator_probe() milestones.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L
import blm_tools as T
from blm_initcall_report import load_symbols, resolve, pick_bank

TRACE_NAMES = {
    0: 'LAST_INITCALL',
    1: 'BAM_ENTER',
    2: 'BAM_DT_BEFORE',
    3: 'BAM_DT_AFTER',
    4: 'BAM_WQ_OK',
    5: 'BAM_ENABLE_BEFORE',
    6: 'BAM_ENABLE_AFTER',
    7: 'BAM_IPA_BEFORE',
    8: 'BAM_IPA_AFTER',
    9: 'BAM_PANIC_HDLR',
    10: 'EBAM_INIT_BEFORE',
    11: 'EBAM_INIT_AFTER',
    15: 'WATCHDOG',
    16: 'VIB_ENTER',
    17: 'VIB_SPMI_SET',
    18: 'VIB_RES_BEFORE',
    19: 'VIB_RES_AFTER',
    20: 'VIB_DT_BEFORE',
    21: 'VIB_CONFIG_BEFORE',
    22: 'VIB_READ1',
    23: 'VIB_READ2',
    24: 'VIB_PWM',
    25: 'VIB_CONFIG_DONE',
    26: 'VIB_TIMED',
    27: 'VIB_STUB_READ',
    28: 'VIB_STUB_WRITE',
}

VIB_NEXT = {
    16: 'spmi_get_resource',
    18: 'spmi_get_resource 返回值',
    20: 'qpnp_vib_parse_dt',
    21: 'qpnp_vibrator_config 入口',
    22: '第一次 SPMI 读 qpnp_vib_read_u8',
    23: '第二次 SPMI 读 qpnp_vib_read_u8',
    24: 'pwm_request / pwm_config',
    25: 'mutex / work / hrtimer 段',
    26: 'timed_output_dev_register',
    27: 'SPMI stub 读（Round 19 修复镜像专用）',
    28: 'SPMI stub 写（Round 19 修复镜像专用）',
}

TRC_RE = re.compile(r'^TRC\s+(\S+)\s+([0-9a-fA-F]{1,16})\s*$')


def main():
    ap = argparse.ArgumentParser(description='decode BLM fixed trace slots from a RAM dump')
    ap.add_argument('--input', required=True)
    ap.add_argument('--system-map', default='')
    ap.add_argument('--report', default='')
    ap.add_argument('--offset', type=lambda x: int(x, 0), default=0)
    args = ap.parse_args()

    blob = Path(args.input).read_bytes()
    region = blob[args.offset:args.offset + L.LAYOUT['log_size']]
    bank = pick_bank(region)
    if not bank:
        print('TRACE_REPORT_FAIL no valid bank')
        return 1

    syms, keys = [], []
    if args.system_map:
        syms = load_symbols(args.system_map)
        keys = [s[0] for s in syms]

    found = {}
    for ln in bank.get('lines', []):
        m = TRC_RE.match(ln.get('text', '').strip())
        if not m:
            continue
        sid = ln.get('seq', 0) & 0x1F
        tag, val_hex = m.group(1), m.group(2)
        val = int(val_hex, 16)
        item = {'id': sid, 'expected_name': TRACE_NAMES.get(sid, '?'),
                'tag': tag, 'seq': ln.get('seq'), 'jiffies': ln.get('jiffies'),
                'value': val, 'value_hex': hex(val)}
        if sid == 0 and syms:
            name, delta = resolve(syms, keys, val)
            item['symbol'] = name
            item['symbol_offset'] = delta
        found[sid] = item

    print('TRACE_REPORT input=%s bank=%d gen=%s last_stage=%s(%s) lines=%d' % (
        args.input, bank.get('bank_index', -1), bank.get('generation'),
        bank.get('last_stage_id'), bank.get('last_stage_name'), len(bank.get('lines', []))))
    print('--- fixed trace slots (present) ---')
    for sid in sorted(found):
        it = found[sid]
        extra = ''
        if 'symbol' in it:
            extra = ' -> %s+0x%x' % (it['symbol'] or '?', it['symbol_offset'] or 0)
        print('  id=%02d %-20s tag=%-20s val=%s j=%s%s' % (
            sid, it['expected_name'], it['tag'], it['value_hex'], it['jiffies'], extra))
    missing = [i for i in sorted(TRACE_NAMES) if i not in found]
    print('MISSING_SLOTS', missing)
    print('TRACE_SLOT_COUNT', len(found))

    # Highest reached usb_bam probe milestone decides the stall window.
    bam = [sid for sid in found if 1 <= sid <= 11]
    if bam:
        last = max(bam)
        nxt = min([x for x in TRACE_NAMES if 1 <= x <= 11 and x > last], default=None)
        print('LAST_BAM_MILESTONE id=%d %s (%s)' % (last, TRACE_NAMES[last], found[last]['tag']))
        print('NEXT_EXPECTED', (str(nxt) + ' ' + TRACE_NAMES[nxt]) if nxt else 'none (probe tail)')
    else:
        print('LAST_BAM_MILESTONE none (probe not entered)')

    vib = [sid for sid in found if 16 <= sid <= 28]
    if vib:
        last_vib = max(vib)
        print('LAST_VIB_MILESTONE id=%d %s (%s)' % (
            last_vib, TRACE_NAMES[last_vib], found[last_vib]['tag']))
        print('VIB_SUSPECTED_WINDOW', VIB_NEXT.get(last_vib, 'probe 尾部或之后'))
    else:
        last_vib = None
        print('LAST_VIB_MILESTONE none (qpnp_vibrator_probe not entered)')
        print('VIB_SUSPECTED_WINDOW spmi_driver_register 内部 / 设备未匹配')

    if args.report:
        out = {
            'input': args.input,
            'system_map': args.system_map or None,
            'bank_index': bank.get('bank_index'),
            'generation': bank.get('generation'),
            'last_stage_id': bank.get('last_stage_id'),
            'last_stage_name': bank.get('last_stage_name'),
            'found': found,
            'missing': missing,
            'last_bam_milestone': (max(bam) if bam else None),
            'last_vib_milestone': last_vib,
            'vib_suspected_window': (VIB_NEXT.get(last_vib, 'probe 尾部或之后')
                                     if vib else 'spmi_driver_register 内部 / 设备未匹配'),
        }
        Path(args.report).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print('REPORT_OK ' + args.report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
