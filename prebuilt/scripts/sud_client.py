#!/usr/bin/env python3
"""
sud TCP root client - bypass the broken /system/bin/sh on Xplay6 8.1.

temproot-1.9.41 stages `sud` which listens on 127.0.0.1:<port> (12346 in the
21:28 log) and speaks a line protocol with requests like `SU <uid> <cmd>`.
adb forward is handled by adbd directly and never executes /system/bin/sh,
so this works even while mirror8.sh has bind-mounted sh to a 0-byte file.

Prereq (after a successful temproot escalation, DO NOT REBOOT):
    adb forward tcp:12346 tcp:12346

Usage:
    python sud_client.py "id"
    python sud_client.py "getenforce"
    python sud_client.py "dd if=/sdcard/boot.img of=/dev/block/bootdevice/by-name/boot bs=4096"

NOTE: the request framing / token format is inferred from strings in
assets/{su,sud,relayd}; it has NOT been verified against a live daemon yet.
The script prints the raw server reply so the framing can be adjusted on site.
"""
import argparse
import socket
import sys
import time

DEFAULT_CMDS = [
    ("plain", None),
    ("token-prefix", "TOKEN {token}\n"),
    ("token-suffix", None),
]


def exchange(host, port, payload, wait=3.0):
    s = socket.create_connection((host, port), timeout=8)
    s.settimeout(wait)
    s.sendall(payload)
    out = b""
    try:
        while True:
            b = s.recv(65536)
            if not b:
                break
            out += b
    except socket.timeout:
        pass
    s.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="id")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12346)
    ap.add_argument("--uid", type=int, default=0)
    ap.add_argument("--token-file", default=None)
    ap.add_argument("--wait", type=float, default=3.0)
    a = ap.parse_args()

    token = None
    if a.token_file:
        with open(a.token_file, "rb") as f:
            token = f.read().strip()

    req = ("SU %d %s\n" % (a.uid, a.cmd)).encode()

    attempts = [("plain", req)]
    if token:
        attempts.append(("TOKEN line", ("TOKEN " + token.decode("ascii", "ignore") + "\n").encode() + req))
        attempts.append(("token+cmd", token + b"\n" + req))

    for name, payload in attempts:
        try:
            out = exchange(a.host, a.port, payload, a.wait)
        except OSError as e:
            print("[%s] connect/IO error: %s" % (name, e))
            return 2
        text = out.decode("utf-8", "replace")
        print("--- %s ---" % name)
        print(text if text.strip() else "(no reply)")
        if "unauthenticated" not in text and "ERR " not in text and text.strip():
            print("[OK] usable framing: %s" % name)
            return 0
        time.sleep(0.3)
    print("[!] no usable framing; adjust protocol using the raw replies above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
