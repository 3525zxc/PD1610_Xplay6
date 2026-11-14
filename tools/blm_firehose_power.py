#!/usr/bin/env python3
"""Send one Firehose <power value="..."/> command on an existing 9008 session.

Used after a read-only peek to move the device from Firehose straight into
fastboot, so the stock boot image can be restored without waiting for the
candidate bootloop to fall back by itself. No partition is written.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blm_firehose_peek as P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--com', type=int, required=True)
    ap.add_argument('--mode', default='fastboot',
                    help='firehose power value: fastboot / reset / off / reset_to_edl')
    ap.add_argument('--workdir', default='')
    ap.add_argument('--timeout', type=int, default=60)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    workdir = Path(args.workdir) if args.workdir else root / 'edl_probe'
    workdir.mkdir(parents=True, exist_ok=True)
    if not P.FH.is_file():
        print('TOOL_MISSING ' + str(P.FH))
        return 2

    pt = workdir / 'port_trace.txt'
    if pt.is_file():
        pt.unlink()
    xml = workdir / 'power_cmd.xml'
    body = '<power value="%s" />' % args.mode
    xml.write_text('<?xml version="1.0" ?>\n<data>\n  %s\n</data>\n' % body, encoding='ascii')

    cmd = [str(P.FH), '--port=\\\\.\\COM%d' % args.com,
           '--sendxml=' + str(xml),
           '--search_path=' + str(workdir),
           '--mainoutputdir=' + str(workdir),
           '--memoryname=ufs', '--noprompt', '--zlpawarehost=1']
    rc, txt = P.run(cmd, workdir, timeout=args.timeout)
    text = P.collect_text(workdir, txt)
    ack = 'ACK' in text
    nak = 'NAK' in text
    print('POWER_CMD mode=%s rc=%s ack=%s nak=%s' % (args.mode, rc, ack, nak))
    print(text[-900:])
    return 0 if rc == 'OK' and ack and not nak else 1


if __name__ == '__main__':
    sys.exit(main())
