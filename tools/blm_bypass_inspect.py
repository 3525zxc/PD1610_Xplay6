#!/usr/bin/env python3
"""Offline inspection before the qpnp-vibrator bypass experiment.

Answers three questions without touching the device:
  1. What does the idx79 `qpnp-vibrator` node look like (props, span, phandle)?
  2. Is that node referenced by any phandle elsewhere in the DTB?
  3. Do stock vs custom DTBs differ for vibrator / SPMI / PMIC-ARB resources?

Usage:
  python3 blm_bypass_inspect.py --custom idx79.dtb --stock stock.dtb --report out.json
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_patch_dtb as F


def load(path):
    return Path(path).read_bytes()


def dump_node(fdt, node):
    props = {}
    for name, value in sorted(node['props'].items()):
        props[name] = {
            'len': len(value),
            'hex': value[:64].hex(),
            'text': value.split(b'\0')[0].decode('utf-8', 'replace') if len(value) < 128 else '',
        }
    return {
        'name': node['name'], 'path': node['path'],
        'start': node['start'], 'end': node['end'],
        'span': node['end'] + 4 - node['start'],
        'props': props,
    }


def find_vibrator(nodes):
    hits = [n for n in nodes if 'vibrator' in n['name'].lower()
            or 'qpnp-vib' in n['name'].lower()]
    return hits


def phandle_refs(fdt, nodes, target):
    """Find every property whose 4-byte value equals target phandle."""
    pv = target['props'].get('phandle')
    if not pv:
        return {'phandle': None, 'refs': [], 'note': 'node has no phandle property'}
    val = pv['hex']
    raw = bytes.fromhex(val)
    if len(raw) < 4:
        return {'phandle': None, 'refs': [], 'note': 'short phandle'}
    ph = struct.unpack('>I', raw[:4])[0]
    refs = []
    for n in nodes:
        if n is target:
            continue
        for pname, pval in n['props'].items():
            if len(pval) % 4 == 0 and len(pval) >= 4:
                for i in range(0, len(pval) - 3, 4):
                    if struct.unpack_from('>I', pval, i)[0] == ph:
                        refs.append({'node': n['path'], 'prop': pname, 'cell': i // 4})
    return {'phandle': ph, 'refs': refs, 'note': ''}


def resource_summary(fdt, nodes):
    out = {'spmi_nodes': [], 'pmic_arb_nodes': [], 'vibrator_nodes': []}
    for n in nodes:
        name = n['name']
        low = name.lower()
        if 'spmi' in low or 'pmic-arb' in low or 'pmic_arb' in low:
            entry = {'path': n['path'], 'name': name,
                     'props': {k: v[:48].hex() for k, v in sorted(n['props'].items())}}
            if 'pmic-arb' in low or 'pmic_arb' in low:
                out['pmic_arb_nodes'].append(entry)
            else:
                out['spmi_nodes'].append(entry)
        if 'vibrator' in low or 'qpnp-vib' in low:
            out['vibrator_nodes'].append(dump_node(fdt, n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--custom', required=True, help='idx79 DTB from candidate boot.img (with BLM node)')
    ap.add_argument('--stock', required=True, help='stock idx79 DTB baseline')
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    custom_raw, stock_raw = load(args.custom), load(args.stock)
    cf, sf = F.Fdt(custom_raw), F.Fdt(stock_raw)
    cn, sn = cf.parse_nodes(), sf.parse_nodes()

    cvib, svib = find_vibrator(cn), find_vibrator(sn)
    result = {
        'custom': {'file': str(args.custom), 'size': len(custom_raw),
                   'sha256': hashlib.sha256(custom_raw).hexdigest(), 'nodes': len(cn)},
        'stock': {'file': str(args.stock), 'size': len(stock_raw),
                  'sha256': hashlib.sha256(stock_raw).hexdigest(), 'nodes': len(sn)},
        'custom_vibrator': [dump_node(cf, n) for n in cvib],
        'stock_vibrator': [dump_node(sf, n) for n in svib],
        'phandle_refs': [phandle_refs(cf, cn, n) for n in cvib],
        'custom_resources': resource_summary(cf, cn),
        'stock_resources': resource_summary(sf, sn),
    }

    # compat/resource diff between stock and custom for the vibrator node
    def sig(nodes):
        return sorted([(n['path'], n['name'],
                        sorted((k, v.hex()) for k, v in n['props'].items())) for n in nodes])
    result['vibrator_props_identical'] = sig(cvib) == sig(svib)
    result['spmi_node_paths_identical'] = (
        [n['path'] for n in cn if 'spmi' in n['name'].lower()]
        == [n['path'] for n in sn if 'spmi' in n['name'].lower()])

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BYPASS_INSPECT custom_vibrator=%d stock_vibrator=%d' % (len(cvib), len(svib)))
    for n in cvib:
        print('  NODE %s span=%d props=%s' % (n['path'], n['end'] + 4 - n['start'],
                                              ','.join(sorted(n['props'].keys()))))
    for r in result['phandle_refs']:
        print('  PHANDLE %s refs=%d %s' % (r['phandle'], len(r['refs']), r['note']))
    print('  VIBRATOR_PROPS_IDENTICAL=%s SPMI_PATHS_IDENTICAL=%s'
          % (result['vibrator_props_identical'], result['spmi_node_paths_identical']))
    print('  SPMI_NODES custom=%d stock=%d PMIC_ARB custom=%d stock=%d'
          % (len(result['custom_resources']['spmi_nodes']),
             len(result['stock_resources']['spmi_nodes']),
             len(result['custom_resources']['pmic_arb_nodes']),
             len(result['stock_resources']['pmic_arb_nodes'])))
    print('REPORT_OK ' + str(args.report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
