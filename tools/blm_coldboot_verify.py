#!/usr/bin/env python3
"""Verify N consecutive cold boots reach sys.boot_completed=1 without bootloop.

Uses `adb reboot` (plain reboot; `reboot bootloader` is known broken on the
candidate kernel). Each cycle waits for the device to go offline and come back,
then polls the boot_completed property. Writes a JSON ledger.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_ADB = r"D:/xplay6/tools/platform-tools/adb.exe"


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.stdout.decode("utf-8", "replace").replace("\r", "").strip()
    except subprocess.TimeoutExpired:
        return ""


def online(adb):
    out = run([adb, "devices"], timeout=20)
    return any("\tdevice" in l for l in out.splitlines())


def prop(adb, key):
    return run([adb, "shell", "getprop " + key], timeout=20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", default=DEFAULT_ADB)
    ap.add_argument("--cycles", type=int, default=3)
    ap.add_argument("--settle-timeout", type=int, default=240)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()

    cycles = []
    verdict = "PASS"
    for i in range(1, a.cycles + 1):
        rec = {"cycle": i, "started_at": datetime.now().isoformat(timespec="seconds")}
        if not online(a.adb):
            rec["result"] = "NO_ADB_BEFORE_REBOOT"
            verdict = "FAIL"
            cycles.append(rec)
            break
        rec["kernel_before"] = run([a.adb, "shell", "uname -r"], timeout=20)
        print("cycle %d: rebooting (%s)" % (i, rec["kernel_before"]), flush=True)
        run([a.adb, "reboot"], timeout=30)

        # wait for offline (avoid counting the pre-reboot adb session)
        t0 = time.time()
        went_offline = False
        while time.time() - t0 < 60:
            if not online(a.adb):
                went_offline = True
                break
            time.sleep(2)
        rec["went_offline"] = went_offline

        t1 = time.time()
        booted = False
        while time.time() - t1 < a.settle_timeout:
            if online(a.adb) and prop(a.adb, "sys.boot_completed") == "1":
                # second enumeration guard: stale adb session can answer once
                time.sleep(3)
                if online(a.adb) and prop(a.adb, "sys.boot_completed") == "1":
                    booted = True
                    break
            time.sleep(3)
        rec["boot_seconds"] = round(time.time() - t1, 1)
        rec["boot_completed"] = prop(a.adb, "sys.boot_completed") if online(a.adb) else "<offline>"
        rec["kernel_after"] = run([a.adb, "shell", "uname -r"], timeout=20)
        rec["uptime"] = run([a.adb, "shell", "uptime"], timeout=20)
        rec["result"] = "PASS" if booted else "FAIL"
        if not booted:
            verdict = "FAIL"
        print("  -> %s in %ss kernel=%s" % (rec["result"], rec["boot_seconds"],
                                            rec["kernel_after"]), flush=True)
        cycles.append(rec)
        if verdict == "FAIL":
            break

    out = {
        "verdict": verdict,
        "cycles_requested": a.cycles,
        "cycles_run": len(cycles),
        "cycles_passed": sum(1 for c in cycles if c["result"] == "PASS"),
        "method": "adb reboot; offline->online; poll sys.boot_completed=1 twice",
        "note": "single reboot per cycle; no partition writes",
        "cycles": cycles,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    Path(a.report).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print("VERDICT=%s (%d/%d)" % (verdict, out["cycles_passed"], a.cycles))
    print("report:", a.report)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
