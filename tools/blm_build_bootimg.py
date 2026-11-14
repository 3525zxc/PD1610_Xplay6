#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_layout as L
import blm_patch_dtb as F

MAGIC = struct.pack('>I', 0xD00DFEED)
L_OFF = 0x3F8
SIG_LEN = 5376
ARM64_MAGIC = 0x644D5241
C6_NAMES = ('c6_01_isroot', 'c6_su_detect', 'vivo_obf_decode', 'c6_mount_state', 'c6_vivo_gate_should_check')
C6_MARKERS = (b'vivo-isroot(C6-01)', b'vivo-obf(C6-02)', b'c6_su_detect')
BLM_SYMS = ('blm_early_init', 'blm_reserve_logmem', 'blm_mark', 'blm_write_bytes', 'blm_write_text', 'blm_arm_watchdog', 'blm_disarm_watchdog')
BLM_MARKERS = (b'BLM monitor init', b'BLM memblock reserve', b'blm_watchdog_secs')


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.blm_img_', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data if isinstance(data, bytes) else data.encode('utf-8'))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def layout(d):
    page = struct.unpack_from('<I', d, 0x24)[0]
    ks, rs, ss = (struct.unpack_from('<I', d, o)[0] for o in (8, 0x10, 0x18))
    A = lambda x: (x + page - 1) // page * page
    return page, ks, rs, ss, A, page + A(ks) + A(rs) + A(ss)


def compute_id(k, r):
    h = hashlib.sha1()
    for blob, n in ((k, len(k)), (r, len(r)), (None, 0), (None, 0)):
        if blob is not None:
            h.update(blob)
        h.update(struct.pack('<I', n))
    return h.digest()


def first_dtb(kernel):
    i = 0
    while True:
        j = kernel.find(MAGIC, i)
        if j < 0:
            return None
        if j + 8 <= len(kernel):
            tot = struct.unpack_from('>I', kernel, j + 4)[0]
            if 1000 < tot < 2000000:
                return j
        i = j + 4


def count_dtbs(kernel, start):
    out = []
    p = start
    while p + 40 <= len(kernel):
        if kernel[p:p + 4] != MAGIC:
            break
        tot = struct.unpack_from('>I', kernel, p + 4)[0]
        if tot < 40 or p + tot > len(kernel):
            break
        out.append((p, tot))
        p += tot
    return out


def arm64_header(image):
    if len(image) < 0x40:
        return None
    return {
        'code0': struct.unpack_from('<I', image, 0)[0],
        'text_offset': struct.unpack_from('<Q', image, 8)[0],
        'image_size': struct.unpack_from('<Q', image, 16)[0],
        'flags': struct.unpack_from('<Q', image, 24)[0],
        'magic': struct.unpack_from('<I', image, 0x38)[0],
    }


def read_env(path):
    out = {}
    p = Path(path)
    if not p.is_file():
        return out
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def resolve_tag(root, tag):
    if tag:
        return tag
    cur = root / 'build' / 'current.txt'
    if not cur.is_file():
        raise SystemExit('BUILD_TAG_MISSING: pass --tag or run blm_build_kernel.sh first')
    return cur.read_text(encoding='utf-8').strip()


def main():
    ap = argparse.ArgumentParser(description='build a BLM-instrumented boot.img from a compiled 3.18.120 Image.gz-dtb')
    ap.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--tag', default='')
    ap.add_argument('--build-dir')
    ap.add_argument('--kernel-image')
    ap.add_argument('--system-map')
    ap.add_argument('--stock-boot', default='/mnt/d/16/PD1610_81/release/PD1610_LOS16_20261112/images/boot.img')
    ap.add_argument('--output')
    ap.add_argument('--report')
    ap.add_argument('--ddr-base', type=lambda x: int(x, 0), default=0x40000000)
    ap.add_argument('--ddr-base-status', default='[H]',
                    help='evidence level for ddr_base, e.g. [H] hypothesis or [O] observed/inferred')
    ap.add_argument('--ddr-base-evidence', default='',
                    help='short note recording how ddr_base was established')
    ap.add_argument('--idx79-dtb', default='',
                    help='use an externally supplied idx79 DTB verbatim (A/B control)')
    ap.add_argument('--expect-log-node', choices=('present', 'absent'), default='present',
                    help='whether the blm-ram-log node is expected in the chain')
    ap.add_argument('--append-cmdline', default='',
                    help='append ASCII token(s) to the v0 header cmdline field, '
                         'space-separated, e.g. "blm_watchdog_secs=20 audit=0"')
    args = ap.parse_args()

    root = Path(args.root)
    tag = resolve_tag(root, args.tag)
    build_dir = Path(args.build_dir) if args.build_dir else root / 'build' / tag
    kernel_image = Path(args.kernel_image) if args.kernel_image else build_dir / 'Image.gz-dtb'
    system_map = Path(args.system_map) if args.system_map else build_dir / 'System.map'
    output = Path(args.output) if args.output else root / 'images' / ('boot_los16_blm_' + tag + '.img')
    report_path = Path(args.report) if args.report else root / 'images' / ('boot_los16_blm_' + tag + '.report.json')

    stock = Path(args.stock_boot).read_bytes()
    built = kernel_image.read_bytes()
    env = read_env(build_dir / 'kernel_build.env')
    smap = system_map.read_text(encoding='utf-8', errors='replace')

    page, ks, rs, ss, A, LBL = layout(stock)
    ref_kernel = stock[page:page + ks]
    ramdisk = stock[page + A(ks):page + A(ks) + rs]
    sig = stock[LBL:LBL + SIG_LEN]

    built_dtb_start = first_dtb(built)
    old_gzip_end = first_dtb(ref_kernel)
    if built_dtb_start is None or old_gzip_end is None:
        raise SystemExit('DTB_MAGIC_NOT_FOUND')
    clean_gzip = built[:built_dtb_start]
    full_dtbs = ref_kernel[old_gzip_end:]
    all_dtbs = count_dtbs(full_dtbs, 0)
    if len(all_dtbs) < 80:
        raise SystemExit('CHAIN_TOO_SHORT ' + str(len(all_dtbs)))

    idx79_start, idx79_size = all_dtbs[79]
    idx79_raw = full_dtbs[idx79_start:idx79_start + idx79_size]
    if args.idx79_dtb:
        ext = Path(args.idx79_dtb)
        if not ext.is_file():
            raise SystemExit('EXTERNAL_IDX79_DTB_MISSING ' + str(ext))
        patched_dtb = ext.read_bytes()
        patch_status = 'external'
        log_phys = (args.ddr_base + L.LAYOUT['fdt_base_offset_from_ddr']
                    + L.LAYOUT['fdt_log_offset'])
    else:
        fdt = F.Fdt(idx79_raw)
        patched_dtb, patch_status, log_phys = fdt.patch(
            args.ddr_base,
            L.LAYOUT['fdt_base_offset_from_ddr'],
            L.LAYOUT['fdt_log_offset'],
            L.LAYOUT['log_size'],
        )
    reference_dtb, _, _ = F.Fdt(idx79_raw).patch(
        args.ddr_base,
        L.LAYOUT['fdt_base_offset_from_ddr'],
        L.LAYOUT['fdt_log_offset'],
        L.LAYOUT['log_size'],
    )
    if len(patched_dtb) != len(reference_dtb):
        raise SystemExit('IDX79_LENGTH_MISMATCH %d != %d'
                         % (len(patched_dtb), len(reference_dtb)))
    patched_size = len(patched_dtb)
    patched_totalsize = struct.unpack_from('>I', patched_dtb, 4)[0]
    new_chain = full_dtbs[:idx79_start] + patched_dtb
    dtbs_new = count_dtbs(new_chain, 0)
    pad = ks - len(clean_gzip) - len(new_chain)
    if pad < 0:
        raise SystemExit('LAYOUT_OVERFLOW ' + str(-pad))

    kernel = clean_gzip + new_chain + bytes(pad)
    img = bytearray(stock)
    img[page:page + ks] = kernel
    cmdline_append = b''
    if args.append_cmdline:
        cl_off, cl_len = 0x40, 0x200
        original = bytes(img[cl_off:cl_off + cl_len]).split(b'\x00', 1)[0]
        tokens = args.append_cmdline.encode('ascii').split()
        if not tokens or any(b'\x00' in t for t in tokens):
            raise SystemExit('CMDLINE_TOKEN_INVALID')
        cmdline_append = b' '.join(tokens)
        for t in tokens:
            if t in original.split(b' '):
                raise SystemExit('CMDLINE_TOKEN_ALREADY_PRESENT ' + t.decode('ascii'))
        merged = original + b''.join(b' ' + t for t in tokens)
        if len(merged) + 1 > cl_len:
            raise SystemExit('CMDLINE_OVERFLOW %d' % len(merged))
        img[cl_off:cl_off + cl_len] = merged + bytes(cl_len - len(merged))
    img[0x240:0x254] = compute_id(kernel, ramdisk)
    out = bytes(img)

    page2, ks2, rs2, ss2, A2, cL = layout(out)
    der = struct.unpack('>I', out[cL + L_OFF:cL + L_OFF + 4])[0]
    new_ramdisk = out[page2 + A2(ks2):page2 + A2(ks2) + rs2]
    new_sig = out[cL:cL + SIG_LEN]

    try:
        z = zlib.decompressobj(16 + zlib.MAX_WBITS)
        image = z.decompress(kernel) + z.flush()
        gzip_eof = z.eof
        gzip_error = ''
        pos = ks - len(z.unused_data)
    except Exception as e:
        image = b''
        gzip_eof = False
        gzip_error = repr(e)
        pos = -1
    ah = arm64_header(image)
    dtbs_final = count_dtbs(kernel, pos) if pos >= 0 else []
    log_node_name = ('blm-ram-log@%08x' % log_phys).encode('ascii')
    fdt_phys = args.ddr_base + L.LAYOUT['fdt_base_offset_from_ddr']

    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})

    chk('magic ANDROID!', out[:8] == b'ANDROID!')
    chk('file size equals stock', len(out) == len(stock), str(len(out)))
    chk('kernel_size fixed', ks2 == ks == 56551493, str(ks2))
    chk('ramdisk/second/page unchanged', (rs2, ss2, page2) == (rs, ss, page))
    chk('layout L unchanged', cL == LBL, hex(cL))
    chk('DER INTEGER L unchanged', der == LBL, hex(der))
    chk('signature block byte-identical', new_sig == sig)
    chk('ramdisk byte-identical', new_ramdisk == ramdisk)
    if args.append_cmdline:
        cl_new = out[0x40:0x240]
        cl_old = stock[0x40:0x240].split(b'\x00', 1)[0]
        used = len(cl_old) + 1 + len(cmdline_append)
        chk('header unchanged except id and appended cmdline',
            out[:0x40] == stock[:0x40]
            and out[0x254:page] == stock[0x254:page]
            and cl_new.startswith(cl_old)
            and cl_new[len(cl_old):used] == b' ' + cmdline_append
            and cl_new[used:] == bytes(0x200 - used))
    else:
        chk('header unchanged except id', out[:0x240] == stock[:0x240] and out[0x254:page] == stock[0x254:page])
    chk('header id recomputed', out[0x240:0x254] == compute_id(kernel, ramdisk))
    chk('gzip payload from compiled Image.gz-dtb', kernel[:len(clean_gzip)] == clean_gzip, str(len(clean_gzip)))
    chk('first 79 DTBs byte-identical', new_chain[:idx79_start] == full_dtbs[:idx79_start], str(idx79_start))
    chk('idx79 patched DTB totalsize', patched_totalsize == patched_size, str(patched_size))
    chk('patched DTB status', patch_status in ('patched', 'unchanged', 'external'), patch_status)
    chk('DTB chain truncated after idx79', len(dtbs_new) == 80, str(len(dtbs_new)))
    chk('idx79 is last DTB', dtbs_new and dtbs_new[-1][0] == idx79_start and dtbs_new[-1][1] == patched_size)
    if args.expect_log_node == 'present':
        chk('log node name in chain', log_node_name in new_chain)
        chk('log compatible in chain', b'blm,ram-log' in new_chain)
    else:
        chk('log node name absent in chain', log_node_name not in new_chain)
        chk('log compatible absent in chain', b'blm,ram-log' not in new_chain)
    chk('idx79 model string retained', b'vivo MSM 8996 v3 + PMI8996 PD1610' in patched_dtb)
    chk('PD1610 board strings', b'PD1610' in kernel and b's6e3fh4' in kernel)
    chk('board-id hit', struct.pack('>4I', 1, 0xA, 0x1000001, 0) in kernel)
    chk('log physical address derived', log_phys == fdt_phys + L.LAYOUT['fdt_log_offset'], hex(log_phys))
    chk('log region inside FDT 2 MiB window', L.LAYOUT['fdt_log_offset'] + L.LAYOUT['log_size'] <= L.LAYOUT['fdt_window_size'])
    chk('tail padding all zero', kernel[len(clean_gzip) + len(new_chain):] == bytes(pad), str(pad))
    chk('gzip eof', gzip_eof, gzip_error)
    chk('M1 pos equals gzip length', pos == len(clean_gzip), str(pos))
    chk('M1 pos FDT magic', pos >= 0 and kernel[pos:pos + 4] == MAGIC)
    chk('M1 pos totalsize legal', bool(dtbs_final) and struct.unpack_from('>I', kernel, pos + 4)[0] == dtbs_final[0][1])
    chk('M1 chain ends at padding', bool(dtbs_final) and dtbs_final[-1][0] + dtbs_final[-1][1] == len(clean_gzip) + len(new_chain))
    chk('ARM64 magic', ah is not None and ah['magic'] == ARM64_MAGIC, hex(ah['magic']) if ah else 'n/a')
    chk('text_offset 0x80000', ah is not None and ah['text_offset'] == 0x80000)
    chk('flags zero', ah is not None and ah['flags'] == 0)
    chk('image_size positive', ah is not None and ah['image_size'] > 0)
    chk('BLM strings in decompressed Image', all(x in image for x in BLM_MARKERS))
    chk('BLM symbols in System.map', all(x in smap for x in BLM_SYMS))
    chk('C6 markers absent in Image', all(x not in image for x in C6_MARKERS))
    chk('C6 symbols absent in System.map', all(x not in smap for x in C6_NAMES))
    chk('kernel_build rc=0', env.get('BUILD_RC') == '0', env.get('BUILD_RC', 'MISSING'))
    chk('kernel_build BLM symbols>=7', int(env.get('BLM_SYMBOLS', '0')) >= 7, env.get('BLM_SYMBOLS', 'MISSING'))
    chk('kernel_build C6 purity', all(env.get(k, '1') == '0' for k in ('C6_FILES', 'C6_MAKEFILE', 'C6_HOOK', 'C6_SYMBOLS')))

    npass = sum(1 for c in checks if c['ok'])
    status = 'PASS' if npass == len(checks) else 'FAIL'
    unexecuted = [
        'fastboot flash boot',
        'device reboot and ramoops/EDL readback',
        'warm reset DRAM retention test',
        'direct read of aboot DDR_BASE global at 0x91FFF990',
    ]
    if args.ddr_base_status == '[H]':
        unexecuted.append('real DDR_BASE confirmation from /proc/iomem')
    report = {
        'status': status,
        'pass': npass,
        'total': len(checks),
        'output': str(output),
        'sha256': hashlib.sha256(out).hexdigest(),
        'size': len(out),
        'tag': tag,
        'append_cmdline': args.append_cmdline or None,
        'build_dir': str(build_dir),
        'kernel_image': str(kernel_image),
        'stock_boot': str(args.stock_boot),
        'system_map': str(system_map),
        'ddr_base': hex(args.ddr_base),
        'ddr_base_status': args.ddr_base_status,
        'ddr_base_evidence': args.ddr_base_evidence or None,
        'idx79_dtb_source': args.idx79_dtb or 'internal_patch',
        'patch_status': patch_status,
        'expect_log_node': args.expect_log_node,
        'fdt_phys': hex(fdt_phys),
        'log_phys': hex(log_phys),
        'log_size': hex(L.LAYOUT['log_size']),
        'gzip_len': len(clean_gzip),
        'dtb_chain_len': len(new_chain),
        'patched_dtb_size': patched_size,
        'pad': pad,
        'pos': pos,
        'image_len_decompressed': len(image),
        'arm64_header': ah,
        'kernel_build_env': env,
        'checks': checks,
        'unexecuted': unexecuted,
    }

    atomic_write(output, out)
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'))
    print('BOOTIMG_BUILD_OK status=' + status + ' pass=' + str(npass) + '/' + str(len(checks)) + ' out=' + str(output) + ' sha256=' + report['sha256'] + ' size=' + str(len(out)) + ' gzip_len=' + str(len(clean_gzip)) + ' dtb_chain_len=' + str(len(new_chain)) + ' pad=' + str(pad) + ' log_phys=' + hex(log_phys))
    print('BOOTIMG_REPORT_OK out=' + str(report_path))
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
