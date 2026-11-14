#!/usr/bin/env python3
"""Offline FDT structure audit + equal-length FDT_NOP control for the A/B test.

Source: idx79 DTB containing /reserved-memory/blm-ram-log@42100000.
Control: same DTB with ONLY the log node's struct bytes replaced by FDT_NOP
tags of identical length. Header fields, totalsize, all block offsets, the
strings block, the DTB chain length and the boot.img tail padding stay
byte-identical, so the A/B comparison has exactly one variable.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_patch_dtb as F

HEADER_FIELDS = {
    'magic': 0, 'totalsize': 4, 'off_dt_struct': 8, 'off_dt_strings': 12,
    'off_mem_rsvmap': 16, 'version': 20, 'last_comp_version': 24,
    'boot_cpuid_phys': 28, 'size_dt_strings': 32, 'size_dt_struct': 36,
}


def header(data):
    return {k: F.be32(data, o) for k, o in HEADER_FIELDS.items()}


def audit(data, label):
    """Full structural audit of a flattened device tree blob."""
    errors = []
    warnings = []
    h = header(data)
    if h['magic'] != 0xD00DFEED:
        errors.append('bad magic %s' % hex(h['magic']))
    if h['totalsize'] != len(data):
        errors.append('totalsize %d != file length %d' % (h['totalsize'], len(data)))
    if h['version'] != 17 or h['last_comp_version'] != 16:
        warnings.append('version=%d last_comp=%d' % (h['version'], h['last_comp_version']))
    if h['off_dt_struct'] % 4 or h['off_dt_strings'] % 4 or h['off_mem_rsvmap'] % 8:
        errors.append('unaligned block offset')
    if h['off_dt_struct'] < 40:
        errors.append('off_dt_struct below header')
    if h['off_dt_struct'] + h['size_dt_struct'] > h['off_dt_strings']:
        errors.append('struct block overlaps strings block')
    if h['off_dt_strings'] + h['size_dt_strings'] > h['totalsize']:
        errors.append('strings block exceeds totalsize')
    if h['off_mem_rsvmap'] < 40 or h['off_mem_rsvmap'] > h['off_dt_struct']:
        errors.append('mem_rsvmap outside [40, off_dt_struct)')

    # mem reserve map: 16-byte entries terminated by an all-zero entry
    p = h['off_mem_rsvmap']
    rsv_count = 0
    rsv_terminated = False
    while p + 16 <= h['off_dt_struct']:
        if data[p:p + 16] == b'\x00' * 16:
            rsv_terminated = True
            p += 16
            break
        rsv_count += 1
        p += 16
    if not rsv_terminated:
        warnings.append('mem_rsvmap has no zero terminator before struct block')
    if p != h['off_dt_struct']:
        warnings.append('mem_rsvmap end %d != off_dt_struct %d' % (p, h['off_dt_struct']))

    # full struct-block walk with tag/alignment/nameoff validation
    strings = data[h['off_dt_strings']:h['off_dt_strings'] + h['size_dt_strings']]
    off = h['off_dt_struct']
    end = off + h['size_dt_struct']
    depth = 0
    max_depth = 0
    tag_counts = {}
    props = 0
    nodes = 0
    node_names = []
    bad_nameoffs = []
    fdt_end_seen = False
    while off < end:
        if off % 4:
            errors.append('unaligned tag at %d' % off)
            break
        tag = F.be32(data, off)
        tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
        if tag == F.FDT_BEGIN_NODE:
            name_off = off + 4
            nul = data.find(b'\0', name_off, end)
            if nul < 0:
                errors.append('unterminated node name at %d' % off)
                break
            node_names.append(data[name_off:nul].decode('utf-8', 'replace'))
            nodes += 1
            depth += 1
            max_depth = max(max_depth, depth)
            off = F.align4(nul + 1)
        elif tag == F.FDT_PROP:
            length = F.be32(data, off + 4)
            nameoff = F.be32(data, off + 8)
            value_off = off + 12
            if nameoff >= len(strings) or strings.find(b'\0', nameoff) < 0:
                bad_nameoffs.append({'off': off, 'nameoff': nameoff})
            if value_off + length > end:
                errors.append('prop value overruns struct block at %d' % off)
                break
            props += 1
            off = F.align4(value_off + length)
        elif tag == F.FDT_END_NODE:
            depth -= 1
            if depth < 0:
                errors.append('unbalanced END_NODE at %d' % off)
                break
            off += 4
        elif tag == F.FDT_NOP:
            off += 4
        elif tag == F.FDT_END:
            fdt_end_seen = True
            off += 4
            break
        else:
            errors.append('unknown tag %d at %d' % (tag, off))
            break
    if depth != 0:
        errors.append('unclosed nodes, depth=%d' % depth)
    if not fdt_end_seen:
        errors.append('FDT_END missing')
    if off > end:
        errors.append('walk overran struct block: %d > %d' % (off, end))
    if bad_nameoffs:
        errors.append('bad prop nameoffs: %s' % repr(bad_nameoffs[:5]))
    if strings and strings[-1] != 0:
        warnings.append('strings block not NUL-terminated')

    # tail after the strings block (usually none)
    tail_start = h['off_dt_strings'] + h['size_dt_strings']
    tail = data[tail_start:]
    tail_nonzero = sum(1 for b in tail if b)

    result = {
        'label': label,
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'header': h,
        'mem_rsvmap': {'entries': rsv_count, 'zero_terminated': rsv_terminated,
                       'end': p},
        'struct_walk': {
            'tag_counts': tag_counts, 'nodes': nodes, 'props': props,
            'max_depth': max_depth, 'end_offset': off, 'expected_end': end,
            'fdt_end_seen': fdt_end_seen, 'balanced': depth == 0,
            'bad_nameoffs': len(bad_nameoffs),
        },
        'strings': {'size': h['size_dt_strings'], 'nul_terminated': bool(strings) and strings[-1] == 0},
        'tail': {'offset': tail_start, 'bytes': len(tail), 'nonzero': tail_nonzero},
        'node_names_sample': node_names[:8],
        'errors': errors,
        'warnings': warnings,
        'status': 'OK' if not errors else 'FAIL',
    }
    return result


def locate_log_node(data):
    fdt = F.Fdt(data)
    nodes = fdt.parse_nodes()
    reserved = fdt.find_reserved_memory(nodes)
    log = fdt.find_log_node(reserved, nodes)
    if not log:
        return None, None, len(nodes), len([n for n in nodes
                                            if n['path'].startswith(reserved['path'].rstrip('/') + '/')
                                            and n['path'] != reserved['path']])
    start = log['start']
    end = log['end'] + 4  # include the END_NODE tag itself
    children = len([n for n in nodes
                    if n['path'].startswith(reserved['path'].rstrip('/') + '/')
                    and n['path'] != reserved['path']])
    return (start, end), log, len(nodes), children


def make_control(data, start, end):
    span = end - start
    if span <= 0 or span % 4:
        raise SystemExit('NODE_SPAN_NOT_4_ALIGNED %d' % span)
    if F.be32(data, start) != F.FDT_BEGIN_NODE:
        raise SystemExit('NODE_START_NOT_BEGIN_NODE')
    if F.be32(data, end - 4) != F.FDT_END_NODE:
        raise SystemExit('NODE_END_NOT_END_NODE %s' % hex(F.be32(data, end - 4)))
    nop = struct.pack('>I', F.FDT_NOP) * (span // 4)
    out = bytearray(data)
    out[start:end] = nop
    return bytes(out), span


def diff_outside(a, b, start, end):
    """Verify all bytes outside [start,end) are identical."""
    diffs = []
    for off in range(0, min(len(a), len(b)), 4):
        if a[off:off + 4] != b[off:off + 4]:
            diffs.append(off)
    outside = [o for o in diffs if not (start <= o < end)]
    inside = [o for o in diffs if start <= o < end]
    ranges = []
    for o in inside:
        if ranges and ranges[-1][1] == o:
            ranges[-1][1] = o + 4
        else:
            ranges.append([o, o + 4])
    return {'diff_4b_blocks': len(diffs), 'outside_node': len(outside),
            'inside_node': len(inside), 'inside_ranges': ranges,
            'outside_sample': outside[:8]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--control-out', required=True)
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    src = Path(args.source).read_bytes()
    src_audit = audit(src, 'source_with_log_node')
    span_info, log, nodes_src, children_src = locate_log_node(src)
    if span_info is None or log is None:
        raise SystemExit('LOG_NODE_NOT_FOUND_IN_SOURCE')
    start, end = span_info
    src_audit['log_node'] = {'name': log['name'], 'start': start, 'end': end,
                             'span': end - start, 'props': sorted(log['props'].keys()),
                             'total_nodes': nodes_src, 'reserved_children': children_src}

    control, span = make_control(src, start, end)
    ctl_audit = audit(control, 'control_nop')
    ctl_span_info, c_log, nodes_ctl, children_ctl = locate_log_node(control)
    ctl_audit['log_node'] = {'present': c_log is not None,
                             'total_nodes': nodes_ctl,
                             'reserved_children': children_ctl}

    diff = diff_outside(src, control, start, end)
    hdr_same = header(src) == header(control)
    str_s = header(src)
    strings_same = (src[str_s['off_dt_strings']:str_s['off_dt_strings'] + str_s['size_dt_strings']]
                    == control[str_s['off_dt_strings']:str_s['off_dt_strings'] + str_s['size_dt_strings']])

    checks = [
        ('source_audit_ok', src_audit['status'] == 'OK', src_audit['errors']),
        ('control_audit_ok', ctl_audit['status'] == 'OK', ctl_audit['errors']),
        ('control_log_node_absent', c_log is None, c_log['name'] if c_log else ''),
        ('control_node_count_minus_one', nodes_ctl == nodes_src - 1, (nodes_src, nodes_ctl)),
        ('control_reserved_children_minus_one', children_ctl == children_src - 1, (children_src, children_ctl)),
        ('identical_length', len(src) == len(control), (len(src), len(control))),
        ('identical_header_all_fields', hdr_same, ''),
        ('identical_strings_block', strings_same, str_s['size_dt_strings']),
        ('no_diff_outside_node', diff['outside_node'] == 0, diff['outside_sample']),
        ('diff_inside_node_only', diff['inside_node'] > 0 and diff['diff_4b_blocks'] == diff['inside_node'], diff['inside_ranges']),
        ('control_span_4_aligned', span % 4 == 0, span),
        ('control_struct_size_unchanged', header(control)['size_dt_struct'] == str_s['size_dt_struct'], ''),
        ('control_off_strings_unchanged', header(control)['off_dt_strings'] == str_s['off_dt_strings'], ''),
        ('control_totalsize_unchanged', header(control)['totalsize'] == str_s['totalsize'], ''),
    ]
    npass = sum(1 for _, ok, _ in checks if ok)
    report = {
        'status': 'PASS' if npass == len(checks) else 'FAIL',
        'pass': npass,
        'total': len(checks),
        'source': str(args.source),
        'control': str(args.control_out),
        'node_span': span,
        'node_offset': [start, end],
        'source_audit': src_audit,
        'control_audit': ctl_audit,
        'diff': diff,
        'checks': [{'name': n, 'ok': bool(ok), 'detail': str(d)} for n, ok, d in checks],
    }
    Path(args.control_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.control_out).write_bytes(control)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('AB_AUDIT status=%s pass=%d/%d node_span=%d offset=[%d,%d) control_sha256=%s'
          % (report['status'], npass, len(checks), span, start, end, ctl_audit['sha256']))
    print('AB_AUDIT_DETAIL nodes=%d->%d reserved_children=%d->%d diff_4b=%d outside=%d header_same=%s strings_same=%s'
          % (nodes_src, nodes_ctl, children_src, children_ctl, diff['diff_4b_blocks'],
             diff['outside_node'], hdr_same, strings_same))
    print('AB_AUDIT_REPORT out=' + str(args.report))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
