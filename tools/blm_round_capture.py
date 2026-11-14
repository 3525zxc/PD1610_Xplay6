#!/usr/bin/env python3
"""One-shot evidence capture for a Tier-3 candidate kernel.

Produces snapshots in the exact formats consumed by blm_tier3_coverage.py,
plus a manifest with sha256 of every artifact. No device partition is written.

Usage:
  python tools/blm_round_capture.py --tag roundA --image <path/to/boot.img>
  python tools/blm_round_capture.py --tag roundA --image <img> --score

Event captures (touch / nav keys) are separate because they need a human to
interact with the device; run with --touch-secs / --nav-secs to include them.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADB = r"D:/xplay6/tools/platform-tools/adb.exe"
FLASH_LOG = ROOT / "flash_log"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return (e.stdout or b"") + b"\n[CAPTURE_TIMEOUT]\n"
    out = r.stdout + (b"\n[STDERR]\n" + r.stderr if r.returncode != 0 else b"")
    return out.replace(b"\r\n", b"\n")


def adb_shell(adb, script, timeout=120):
    return run([adb, "shell", script], timeout)


def save(path, data):
    path.write_bytes(data)
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def wait_boot(adb, tries=60):
    for _ in range(tries):
        out = run([adb, "shell", "getprop sys.boot_completed"], timeout=20)
        if out.strip() == b"1":
            return True
        time.sleep(2)
    return False


CAPTURES = [
    ("input_devices", "cat /proc/bus/input/devices"),
    ("i2c_bindings", 'for d in /sys/bus/i2c/devices/*; do echo "DEV $(basename $d): name=$(cat $d/name 2>/dev/null) driver=$(readlink $d/driver 2>/dev/null) modalias=$(cat $d/modalias 2>/dev/null)"; done'),
    ("props", "getprop"),
    ("dmesg", "dmesg"),
    ("getevent_i", "getevent -i"),
    ("uname", "uname -a; echo ---CMDLINE---; cat /proc/cmdline; echo ---UPTIME---; uptime"),
    ("interrupts", "cat /proc/interrupts"),
    ("lsmod", "lsmod"),
    ("input_names", 'for d in /sys/class/input/input*; do echo "$(basename $d) $(cat $d/name 2>/dev/null)"; done'),
    ("dev_input", "ls -l /dev/input/"),
    ("firmware_loads", "dmesg | grep -iE 'firmware|loading' | head -100"),
    ("i2c_drivers", 'for dr in /sys/bus/i2c/drivers/*; do echo "== $(basename $dr)"; ls -l $dr 2>/dev/null | head -20; done'),
]


def main():
    ap = argparse.ArgumentParser(description="One-shot Tier-3 evidence capture")
    ap.add_argument("--tag", required=True, help="e.g. roundA")
    ap.add_argument("--image", help="candidate boot.img for hash / preflight lookup")
    ap.add_argument("--adb", default=DEFAULT_ADB)
    ap.add_argument("--out-dir", default=str(FLASH_LOG))
    ap.add_argument("--touch-secs", type=int, default=0)
    ap.add_argument("--nav-secs", type=int, default=0)
    ap.add_argument("--touch-dev", default="/dev/input/event4")
    ap.add_argument("--nav-dev", default="/dev/input/event3")
    ap.add_argument("--score", action="store_true", help="run coverage meter afterwards")
    ap.add_argument("--baseline-input", default=str(FLASH_LOG / "stock_baseline_input_devices.txt"))
    ap.add_argument("--baseline-i2c", default=str(FLASH_LOG / "stock_baseline_i2c_bindings.txt"))
    ap.add_argument("--inventory", default=str(ROOT / "offline" / "03_firmware_inventory.csv"))
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    adb = a.adb
    manifest = {
        "tag": a.tag,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "adb": adb,
        "files": {},
    }

    online = run([adb, "devices", "-l"], timeout=30).decode("utf-8", "replace")
    manifest["devices"] = online.strip()
    if "device " not in online and "\tdevice" not in online:
        print("NO_ADB_DEVICE; abort without writing snapshots")
        return 2

    if not wait_boot(adb):
        print("WARN: sys.boot_completed != 1 within 120s; capturing anyway")

    kernel = adb_shell(adb, "uname -r").decode("utf-8", "replace").strip()
    manifest["kernel"] = kernel
    manifest["boot_completed"] = adb_shell(adb, "getprop sys.boot_completed").decode(
        "utf-8", "replace").strip()

    for name, script in CAPTURES:
        data = adb_shell(adb, script)
        p = out_dir / ("%s_%s.txt" % (a.tag, name))
        manifest["files"][p.name] = save(p, data)
        print("  %-40s %7d bytes" % (p.name, len(data)))

    if a.touch_secs:
        print(">>> TOUCH WINDOW %ds - interact with the screen now" % a.touch_secs)
        data = run([adb, "shell", "timeout %d getevent -l %s" % (a.touch_secs, a.touch_dev)],
                   timeout=a.touch_secs + 30)
        p = out_dir / ("%s_touch_events.txt" % a.tag)
        manifest["files"][p.name] = save(p, data)
        print("  %-40s %7d bytes, %d lines" % (p.name, len(data), len(data.splitlines())))

    if a.nav_secs:
        print(">>> NAV KEY WINDOW %ds - press back / recents now" % a.nav_secs)
        data = run([adb, "shell", "timeout %d getevent -l %s" % (a.nav_secs, a.nav_dev)],
                   timeout=a.nav_secs + 30)
        p = out_dir / ("%s_nav_events.txt" % a.tag)
        manifest["files"][p.name] = save(p, data)
        print("  %-40s %7d bytes, %d lines" % (p.name, len(data), len(data.splitlines())))

    if a.image:
        ip = Path(a.image)
        if ip.exists():
            manifest["boot_image"] = {"path": str(ip), "sha256": sha256_file(ip),
                                      "bytes": ip.stat().st_size}
            pf = ROOT / "images" / (ip.stem + ".preflight.json")
            if pf.exists():
                manifest["preflight"] = str(pf)

    mp = out_dir / ("%s_manifest.json" % a.tag)
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("manifest:", mp)

    if a.score:
        cmd = [sys.executable, str(ROOT / "tools" / "blm_tier3_coverage.py"),
               "--baseline-input", a.baseline_input,
               "--baseline-i2c", a.baseline_i2c,
               "--current-input", str(out_dir / ("%s_input_devices.txt" % a.tag)),
               "--current-i2c", str(out_dir / ("%s_i2c_bindings.txt" % a.tag)),
               "--props", str(out_dir / ("%s_props.txt" % a.tag)),
               "--inventory", a.inventory,
               "--report", str(out_dir / ("tier3_coverage_%s.json" % a.tag))]
        if (out_dir / ("%s_touch_events.txt" % a.tag)).exists():
            cmd += ["--touch-events", str(out_dir / ("%s_touch_events.txt" % a.tag))]
        if (out_dir / ("%s_nav_events.txt" % a.tag)).exists():
            cmd += ["--nav-events", str(out_dir / ("%s_nav_events.txt" % a.tag))]
        pf = manifest.get("preflight")
        if pf:
            cmd += ["--preflight", pf]
        print("\n=== COVERAGE ===")
        r = subprocess.run(cmd, capture_output=False)
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
