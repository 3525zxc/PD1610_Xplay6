#!/usr/bin/env python3
"""Verify that a rebuilt boot.img differs from its baseline ONLY in the
kernel gzip payload (instrumentation code), while DTB chain, ramdisk,
signature and all header fields except the recomputed id stay identical.

Used as the offline release gate for the Round 17 candidate.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_build_bootimg as B


def parse(path):
    d = Path(path).read_bytes()
    page, ks, rs, ss, align, sig_off = B.layout(d)
    ramdisk_off = page + align(ks)
    kernel = d[page:page + ks]
    gz_end = B.first_dtb(kernel)
    chain = kernel[gz_end:]
    dtbs = B.count_dtbs(chain, 0)
    chain_end = gz_end + (dtbs[-1][0] + dtbs[-1][1] if dtbs else len(chain))
    return {
        'data': d, 'page': page, 'ks': ks, 'rs': rs, 'ss': ss,
        'sig_off': sig_off, 'kernel': kernel, 'gz_end': gz_end,
        'chain_used': kernel[gz_end:chain_end], 'chain_end': chain_end,
        'pad': kernel[chain_end:],
        'ramdisk': d[ramdisk_off:ramdisk_off + rs],
        'sig': d[sig_off:sig_off + B.SIG_LEN],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--new', required=True)
    ap.add_argument('--report', default='')
    args = ap.parse_args()

    a, b = parse(args.base), parse(args.new)
    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})

    chk('file size equal', len(a['data']) == len(b['data']),
        '%d / %d' % (len(a['data']), len(b['data'])))
    chk('header equal except id',
        a['data'][:0x240] == b['data'][:0x240]
        and a['data'][0x254:a['page']] == b['data'][0x254:b['page']])
    chk('header id recomputed', b['data'][0x240:0x254] == B.compute_id(b['kernel'], b['ramdisk']))
    chk('kernel_size fixed', a['ks'] == b['ks'] == 56551493, str(b['ks']))
    chk('ramdisk identical', a['ramdisk'] == b['ramdisk'], str(len(b['ramdisk'])))
    chk('signature identical', a['sig'] == b['sig'], str(len(b['sig'])))
    chk('DTB chain identical', a['chain_used'] == b['chain_used'],
        '%d / %d bytes' % (len(a['chain_used']), len(b['chain_used'])))
    chk('tail padding all zero', set(b['pad']) <= {0}, str(len(b['pad'])))
    chk('gzip payload changed (kernel recompiled)',
        a['kernel'][:a['gz_end']] != b['kernel'][:b['gz_end']],
        '%d -> %d bytes' % (a['gz_end'], b['gz_end']))
    gz_ok = False
    try:
        import zlib
        z = zlib.decompressobj(16 + zlib.MAX_WBITS)
        img = z.decompress(b['kernel'][:b['gz_end']]) + z.flush()
        hdr = B.arm64_header(img)
        gz_ok = bool(z.eof and hdr and hdr['magic'] == B.ARM64_MAGIC)
    except Exception:
        pass
    chk('new gzip decompresses to ARM64 Image', gz_ok)

    npass = sum(1 for c in checks if c['ok'])
    status = 'PASS' if npass == len(checks) else 'FAIL'
    out = {
        'status': status, 'pass': npass, 'total': len(checks),
        'base': args.base, 'new': args.new,
        'base_sha256': hashlib.sha256(a['data']).hexdigest(),
        'new_sha256': hashlib.sha256(b['data']).hexdigest(),
        'base_gzip_len': a['gz_end'], 'new_gzip_len': b['gz_end'],
        'dtb_chain_len': len(b['chain_used']),
        'checks': checks,
    }
    print('KERNEL_ONLY_VERIFY status=%s pass=%d/%d' % (status, npass, len(checks)))
    for c in checks:
        print('  %s %s %s' % ('OK' if c['ok'] else 'FAIL', c['name'], c['detail']))
    if args.report:
        Path(args.report).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print('REPORT_OK ' + args.report)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
