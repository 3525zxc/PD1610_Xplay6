#!/usr/bin/env python3
"""Read-only Firehose peek client for the BLM RAM log region on PD1610.

Uses the already-proven QSaharaServer + fh_loader toolchain. The firehose
programmer reports "peek" in its Supported Functions list; peek replies are
XML <log value="0x22 0x00 ..."> text, so no USB bulk data path is needed.

No partition is written. Only <peek> commands and an optional final reset
are sent. Run --selftest for an offline parser check.
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

QFIL = Path(r'D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5')
SAHARA = QFIL / 'QSaharaServer.exe'
FH = QFIL / 'fh_loader.exe'
PROGRAMMER = Path(r'D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf')

LOG_RE = re.compile(r'<log\s+value="([^"]*)"', re.S)
HEX_RE = re.compile(r'0x([0-9a-fA-F]{2})\b')


def extract_bytes(text):
    """Pull 0xNN byte tokens out of firehose <log value=...> payloads."""
    out = bytearray()
    for m in LOG_RE.finditer(text):
        val = m.group(1)
        toks = HEX_RE.findall(val)
        if len(toks) < 4:
            continue
        nonspace = re.sub(r'\s+', '', val)
        if nonspace and len(toks) * 4 >= len(nonspace) * 0.6:
            out.extend(int(t, 16) for t in toks)
    return bytes(out)


def peek_xml(path, addr, size, fallback=False):
    if fallback:
        body = '<peek address64="%s" SizeInBytes="%s" />' % (hex(addr), hex(size))
    else:
        body = '<peek address64="%d" size_in_bytes="%d" />' % (addr, size)
    path.write_text('<?xml version="1.0" ?>\n<data>\n  %s\n</data>\n' % body, encoding='ascii')
    return body


def run(cmd, cwd, timeout=120):
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return 'TIMEOUT', (e.stdout or b'').decode('utf-8', 'replace') + (e.stderr or b'').decode('utf-8', 'replace')
    txt = p.stdout.decode('utf-8', 'replace') + '\n' + p.stderr.decode('utf-8', 'replace')
    return ('OK' if p.returncode == 0 else 'RC=%d' % p.returncode), txt


def collect_text(workdir, extra):
    parts = [extra]
    pt = workdir / 'port_trace.txt'
    if pt.is_file():
        parts.append(pt.read_text(encoding='utf-8', errors='replace'))
    return '\n'.join(parts)


def selftest():
    sample = ('<?xml version="1.0" encoding="UTF-8" ?><data>'
              '<log value="Using address 00100000" /></data>\n'
              '<?xml version="1.0" encoding="UTF-8" ?><data>'
              '<log value="0x22 0x00 0x00 0xEA 0x70 0x00 0x00 0xEA\n'
              '0x74 0x00 0x00 0xEA 0x78 0x00 0x00 0xEA" /></data>\n'
              '<response value="ACK" MaxPayloadSizeFromTargetInBytes="4096" />')
    got = extract_bytes(sample)
    want = bytes.fromhex('220000ea700000ea740000ea780000ea')
    ok = got == want
    print('PEEK_PARSE_SELFTEST ' + ('OK' if ok else 'FAIL') + ' bytes=' + str(len(got))
          + ' hex=' + got.hex())
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--com', type=int, default=0, help='9008 QDLoader COM number, e.g. 5')
    ap.add_argument('--address', type=lambda x: int(x, 0), default=0x42100000)
    ap.add_argument('--size', type=lambda x: int(x, 0), default=0x40000)
    ap.add_argument('--chunk', type=lambda x: int(x, 0), default=0x10000)
    ap.add_argument('--out', default='')
    ap.add_argument('--workdir', default='')
    ap.add_argument('--no-upload', action='store_true', help='skip Sahara upload (device already in firehose)')
    ap.add_argument('--reset', action='store_true', help='send reset after the last peek')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    root = Path(__file__).resolve().parents[1]
    workdir = Path(args.workdir) if args.workdir else root / 'edl_probe'
    workdir.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else root / 'flash_log' / 'blm_ram.bin'
    out.parent.mkdir(parents=True, exist_ok=True)

    for p in (SAHARA, FH, PROGRAMMER):
        if not p.is_file():
            print('TOOL_MISSING ' + str(p))
            return 2
    if args.com <= 0:
        print('COM_REQUIRED pass --com <number> of the 9008 QDLoader port')
        return 2
    if args.size % args.chunk:
        print('SIZE_NOT_MULTIPLE_OF_CHUNK')
        return 2

    if not args.no_upload:
        rc, txt = run([str(SAHARA), '-u', str(args.com), '-s', '13:' + str(PROGRAMMER)], workdir)
        print('SAHARA_UPLOAD ' + rc + (' OK' if 'Sahara completed' in txt or 'Upload' in txt else ''))
        if rc != 'OK':
            print(txt[-1500:])
            return 3

    n = args.size // args.chunk
    blob = bytearray()
    failures = []
    for i in range(n):
        addr = args.address + i * args.chunk
        xml = workdir / 'peek_blm.xml'
        peek_xml(xml, addr, args.chunk)
        pt = workdir / 'port_trace.txt'
        if pt.is_file():
            pt.unlink()
        cmd = [str(FH), '--port=\\\\.\\COM%d' % args.com,
               '--sendxml=' + str(xml),
               '--search_path=' + str(workdir),
               '--mainoutputdir=' + str(workdir),
               '--memoryname=ufs', '--noprompt', '--zlpawarehost=1']
        if args.reset and i == n - 1:
            cmd.append('--reset')
        rc, txt = run(cmd, workdir)
        text = collect_text(workdir, txt)
        data = extract_bytes(text)
        if len(data) < args.chunk and ('NAK' in text or 'SizeInBytes' in text or 'Invalid parameters' in text):
            peek_xml(xml, addr, args.chunk, fallback=True)
            if pt.is_file():
                pt.unlink()
            rc, txt = run(cmd, workdir)
            text = collect_text(workdir, txt)
            data = extract_bytes(text)
        good = data[:args.chunk]
        if len(good) < args.chunk:
            failures.append({'block': i, 'addr': hex(addr), 'got': len(good), 'rc': rc,
                             'tail': text[-400:]})
        blob.extend(good)
        if len(blob) < args.chunk * (i + 1):
            blob.extend(b'\x00' * (args.chunk * (i + 1) - len(blob)))
        print('PEEK_BLOCK %d/%d addr=%s got=%d rc=%s' % (i + 1, n, hex(addr), len(good), rc))

    out.write_bytes(bytes(blob))
    nonzero = sum(1 for b in blob if b)
    digest = hashlib.sha256(blob).hexdigest()
    print('PEEK_DONE out=' + str(out) + ' bytes=' + str(len(blob)) + ' nonzero=' + str(nonzero)
          + ' sha256=' + digest + ' head=' + bytes(blob[:16]).hex()
          + ' failed_blocks=' + str(len(failures)))
    for f in failures[:5]:
        print('PEEK_BLOCK_FAIL ' + repr(f))
    return 0 if not failures else 4


if __name__ == '__main__':
    sys.exit(main())
