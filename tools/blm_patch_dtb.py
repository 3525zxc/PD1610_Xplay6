#!/usr/bin/env python3
import argparse
import hashlib
import os
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9
FDT_HEADER_SIZE = 40


class FdtError(Exception):
    pass


def be32(buf, off):
    return struct.unpack_from('>I', buf, off)[0]


def put_be32(buf, off, value):
    struct.pack_into('>I', buf, off, value & 0xFFFFFFFF)


def align4(n):
    return (n + 3) & ~3


def align8(n):
    return (n + 7) & ~7


def cstring(data, off):
    end = data.find(b'\0', off)
    if end < 0:
        raise FdtError('unterminated cstring')
    return bytes(data[off:end]).decode('utf-8', 'replace')


def name_offsets(strings):
    out = {}
    pos = 0
    for raw in strings.split(b'\0'):
        if raw:
            out[raw.decode('utf-8', 'replace')] = pos
        pos += len(raw) + 1
    return out


def begin_node(name):
    raw = name.encode('utf-8') + b'\0'
    return struct.pack('>I', FDT_BEGIN_NODE) + raw + b'\0' * ((-len(raw)) & 3)


def end_node():
    return struct.pack('>I', FDT_END_NODE)


def prop(name, value, offsets):
    if name not in offsets:
        raise FdtError('missing string ' + name)
    pad = b'\0' * ((-len(value)) & 3)
    return struct.pack('>III', FDT_PROP, len(value), offsets[name]) + value + pad


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.blm_dtb_', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Fdt:
    def __init__(self, data):
        raw = bytes(data)
        if len(raw) < FDT_HEADER_SIZE or be32(raw, 0) != FDT_MAGIC:
            raise FdtError('not a flattened device tree')
        self.totalsize = be32(raw, 4)
        if self.totalsize < FDT_HEADER_SIZE or self.totalsize > len(raw):
            raise FdtError('bad totalsize')
        self.data = bytearray(raw[:self.totalsize])
        self.off_dt_struct = be32(self.data, 8)
        self.off_dt_strings = be32(self.data, 12)
        self.off_mem_rsvmap = be32(self.data, 16)
        self.version = be32(self.data, 20)
        self.last_comp_version = be32(self.data, 24)
        self.boot_cpuid = be32(self.data, 28)
        self.size_dt_strings = be32(self.data, 32)
        self.size_dt_struct = be32(self.data, 36)
        if self.off_dt_strings + self.size_dt_strings > self.totalsize:
            raise FdtError('strings block exceeds totalsize')
        if self.off_dt_struct + self.size_dt_struct > self.totalsize:
            raise FdtError('struct block exceeds totalsize')
        self.strings = bytes(self.data[self.off_dt_strings:self.off_dt_strings + self.size_dt_strings])
        self.string_offsets = name_offsets(self.strings)

    def parse_nodes(self):
        off = self.off_dt_struct
        end = off + self.size_dt_struct
        stack = []
        nodes = []
        while off < end:
            tag = be32(self.data, off)
            if tag == FDT_BEGIN_NODE:
                start = off
                name_off = off + 4
                name = cstring(self.data, name_off)
                name_end = self.data.find(b'\0', name_off)
                off = align4(name_end + 1)
                parent_path = stack[-1]['path'] if stack else None
                if parent_path is None:
                    path = '/'
                else:
                    path = parent_path.rstrip('/') + '/' + name
                stack.append({'name': name, 'path': path, 'start': start, 'end': None, 'props': {}})
                continue
            if tag == FDT_PROP:
                length = be32(self.data, off + 4)
                nameoff = be32(self.data, off + 8)
                value_off = off + 12
                name = cstring(self.strings, nameoff)
                value = bytes(self.data[value_off:value_off + length])
                if stack:
                    stack[-1]['props'][name] = value
                off = align4(value_off + length)
                continue
            if tag == FDT_END_NODE:
                if not stack:
                    raise FdtError('unbalanced END_NODE')
                node = stack.pop()
                node['end'] = off
                nodes.append(node)
                off += 4
                continue
            if tag == FDT_NOP:
                off += 4
                continue
            if tag == FDT_END:
                off += 4
                break
            raise FdtError('bad FDT tag ' + str(tag))
        if stack:
            raise FdtError('unclosed nodes')
        return nodes

    def find_reserved_memory(self, nodes):
        for node in nodes:
            base = node['name'].split('@')[0]
            if node['path'] == '/reserved-memory':
                return node
            if base == 'reserved-memory' and node['path'].count('/') == 1:
                return node
        raise FdtError('reserved-memory node not found')

    def find_log_node(self, reserved, nodes):
        prefix = reserved['path'].rstrip('/') + '/'
        for node in nodes:
            if node['name'].startswith('blm-ram-log@') and node['path'].startswith(prefix):
                return node
        return None

    def patch(self, ddr_base, fdt_offset, log_offset, log_size):
        if log_offset + log_size > L.LAYOUT['fdt_window_size']:
            raise FdtError('log region exceeds mapped FDT 2 MiB window')
        fdt_phys = ddr_base + fdt_offset
        log_phys = fdt_phys + log_offset
        if log_phys > 0xFFFFFFFF or log_size > 0xFFFFFFFF:
            raise FdtError('physical address exceeds 32-bit DTB cell')
        nodes = self.parse_nodes()
        reserved = self.find_reserved_memory(nodes)
        existing = self.find_log_node(reserved, nodes)
        if existing:
            reg = existing['props'].get('reg', b'')
            if len(reg) >= 16:
                cells = struct.unpack('>IIII', reg[:16])
                if cells[1] == log_phys and cells[3] == log_size:
                    return bytes(self.data), 'unchanged', log_phys
            raise FdtError('conflicting blm-ram-log node already exists')

        strings = bytearray(self.strings)
        offsets = dict(self.string_offsets)
        old_len = len(strings)
        for name in ['compatible', 'reg', 'label', 'status']:
            if name not in offsets:
                offsets[name] = len(strings)
                strings.extend(name.encode('utf-8'))
                strings.extend(b'\0')
        strings_added = bytes(strings[old_len:])
        pad = (-len(strings_added)) & 3
        if pad:
            strings.extend(b'\0' * pad)
            strings_added += b'\0' * pad

        node_name = 'blm-ram-log@%08x' % log_phys
        reg_value = struct.pack('>IIII', 0, log_phys, 0, log_size)
        node_bytes = (
            begin_node(node_name)
            + prop('compatible', b'blm,ram-log\0', offsets)
            + prop('reg', reg_value, offsets)
            + prop('label', b'blm_ram_log\0', offsets)
            + prop('status', b'okay\0', offsets)
            + end_node()
        )

        insert_off = reserved['end']
        if insert_off < self.off_dt_struct or insert_off > self.off_dt_strings:
            raise FdtError('reserved-memory END_NODE outside struct block')
        prefix = bytes(self.data[:insert_off])
        mid = bytes(self.data[insert_off:self.off_dt_strings])
        old_strings = bytes(self.data[self.off_dt_strings:self.off_dt_strings + self.size_dt_strings])
        tail = bytes(self.data[self.off_dt_strings + self.size_dt_strings:])
        new = bytearray(prefix + node_bytes + mid + old_strings + strings_added + tail)
        while len(new) & 3:
            new.extend(b'\0')
        new_off_dt_strings = self.off_dt_strings + len(node_bytes)
        new_size_dt_struct = self.size_dt_struct + len(node_bytes)
        new_size_dt_strings = self.size_dt_strings + len(strings_added)
        put_be32(new, 4, len(new))
        put_be32(new, 12, new_off_dt_strings)
        put_be32(new, 32, new_size_dt_strings)
        put_be32(new, 36, new_size_dt_struct)
        return bytes(new), 'patched', log_phys


def make_synthetic_dtb():
    strings = b'#address-cells\0#size-cells\0ranges\0'
    offsets = name_offsets(strings)
    st = bytearray()
    st += begin_node('')
    st += prop('#address-cells', struct.pack('>I', 2), offsets)
    st += prop('#size-cells', struct.pack('>I', 2), offsets)
    st += begin_node('reserved-memory')
    st += prop('#address-cells', struct.pack('>I', 2), offsets)
    st += prop('#size-cells', struct.pack('>I', 2), offsets)
    st += prop('ranges', b'', offsets)
    st += end_node()
    st += end_node()
    st += struct.pack('>I', FDT_END)
    off_struct = align8(FDT_HEADER_SIZE + 16)
    off_strings = align4(off_struct + len(st))
    totalsize = off_strings + len(strings)
    out = bytearray(totalsize)
    put_be32(out, 0, FDT_MAGIC)
    put_be32(out, 4, totalsize)
    put_be32(out, 8, off_struct)
    put_be32(out, 12, off_strings)
    put_be32(out, 16, FDT_HEADER_SIZE)
    put_be32(out, 20, 17)
    put_be32(out, 24, 16)
    put_be32(out, 28, 0)
    put_be32(out, 32, len(strings))
    put_be32(out, 36, len(st))
    out[off_struct:off_struct + len(st)] = st
    out[off_strings:off_strings + len(strings)] = strings
    return bytes(out)


def inspect_fdt(path):
    data = Path(path).read_bytes()
    fdt = Fdt(data)
    nodes = fdt.parse_nodes()
    reserved = fdt.find_reserved_memory(nodes)
    prefix = reserved['path'].rstrip('/') + '/'
    children = [n for n in nodes if n['path'].startswith(prefix) and n['path'] != reserved['path']]
    print('FDT_INSPECT magic=OK totalsize=' + str(fdt.totalsize) + ' version=' + str(fdt.version) + ' nodes=' + str(len(nodes)))
    print('RESERVED_MEMORY path=' + reserved['path'] + ' children=' + str(len(children)))
    log = fdt.find_log_node(reserved, nodes)
    if not log:
        print('BLM_NODE=ABSENT')
        return False
    reg = log['props'].get('reg', b'')
    if len(reg) < 16:
        print('BLM_NODE=PRESENT reg=MISSING')
        return False
    cells = struct.unpack('>IIII', reg[:16])
    print('BLM_NODE=PRESENT name=' + log['name'] + ' log_phys=' + hex(cells[1]) + ' size=' + hex(cells[3]))
    return True


def cmd_selftest(args):
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    src = out_dir / 'synthetic.dtb'
    dst = out_dir / 'synthetic.blm.dtb'
    raw = make_synthetic_dtb()
    atomic_write(src, raw)
    fdt = Fdt(raw)
    patched, status, log_phys = fdt.patch(0x40000000, L.LAYOUT['fdt_base_offset_from_ddr'], L.LAYOUT['fdt_log_offset'], L.LAYOUT['log_size'])
    atomic_write(dst, patched)
    check = Fdt(patched)
    nodes = check.parse_nodes()
    reserved = check.find_reserved_memory(nodes)
    log = check.find_log_node(reserved, nodes)
    if not log or status != 'patched' or log_phys != 0x42100000:
        print('DTB_SELFTEST_FAIL status=' + status + ' log_phys=' + hex(log_phys))
        return 1
    print('DTB_SELFTEST_OK synthetic=' + str(src.name) + ' patched=' + str(dst.name) + ' log_phys=' + hex(log_phys))
    return 0


def cmd_patch(args):
    raw = Path(args.input).read_bytes()
    fdt = Fdt(raw)
    patched, status, log_phys = fdt.patch(args.ddr_base, args.fdt_offset, args.log_offset, args.size)
    atomic_write(args.output, patched)
    digest = hashlib.sha256(patched).hexdigest()
    print('DTB_PATCH_OK status=' + status + ' in=' + str(Path(args.input).name) + ' out=' + args.output + ' log_phys=' + hex(log_phys) + ' size=' + hex(args.size) + ' sha256=' + digest)
    return 0


def cmd_inspect(args):
    ok = inspect_fdt(args.input)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='pure-python FDT reserved-memory patcher for BLM RAM log')
    sub = ap.add_subparsers(dest='cmd')

    p = sub.add_parser('selftest')
    p.add_argument('--out-dir', default=str(Path(__file__).resolve().parents[1] / 'tests'))
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser('patch')
    p.add_argument('--in', dest='input', required=True)
    p.add_argument('--out', dest='output', required=True)
    p.add_argument('--ddr-base', type=lambda x: int(x, 0), required=True)
    p.add_argument('--fdt-offset', type=lambda x: int(x, 0), default=L.LAYOUT['fdt_base_offset_from_ddr'])
    p.add_argument('--log-offset', type=lambda x: int(x, 0), default=L.LAYOUT['fdt_log_offset'])
    p.add_argument('--size', type=lambda x: int(x, 0), default=L.LAYOUT['log_size'])
    p.set_defaults(func=cmd_patch)

    p = sub.add_parser('inspect')
    p.add_argument('--in', dest='input', required=True)
    p.set_defaults(func=cmd_inspect)

    args = ap.parse_args()
    if not hasattr(args, 'func'):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
