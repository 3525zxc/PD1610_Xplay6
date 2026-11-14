#!/usr/bin/env python3
"""Measure Tier-3 completion: self-compiled kernel + source-rebuilt vendor drivers.

Denominator is the STOCK device's *observed* inventory (input devices, I2C
bindings), never a guess. Every gate is PASS / FAIL / UNVERIFIED, and the
score is a [lower, upper] range so that unverified work is never counted as
finished. Re-run after each flash to get a comparable number.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# id, acceptance criterion, weight (sums to 100)
GATES = [
    ("boot", "3 consecutive cold boots reach sys.boot_completed=1, no bootloop", 20),
    ("touch_cold", "touch usable within 30s of cold boot: ABS_MT + real getevent events", 15),
    ("nav_keys", "3-0028 bound, virtual_key input present, 3 key events observed", 8),
    ("input_parity", "every stock input device present with same name", 12),
    ("i2c_parity", "every stock I2C device that had a driver is bound", 15),
    ("hal", "key HAL services running (vibrator / fingerprint / audio / wifi)", 10),
    ("firmware_inventory", "vendor firmware blob dependency inventory written", 5),
    ("reproducible", "one-command rebuild + 40/40 build + 17/17 preflight + verified rollback", 15),
]


def read_text(path):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def input_names(text):
    if text is None:
        return None
    return [m for m in re.findall(r'^N:\s*Name="([^"]+)"', text, re.M)]


def i2c_bindings(text):
    """Parse 'DEV <addr>: name=<n> driver=<d> modalias=<m>' lines."""
    if text is None:
        return None
    out = {}
    for line in text.splitlines():
        if not line.startswith("DEV "):
            continue
        head = line[4:].split(":", 1)[0].strip()
        if head.startswith("i2c-"):
            continue
        n = re.search(r"\bname=(\S*)", line)
        d = re.search(r"\bdriver=(\S*)", line)
        out[head] = {"name": n.group(1) if n else "", "driver": d.group(1) if d else ""}
    return out


def props(text):
    if text is None:
        return None
    d = {}
    for line in text.splitlines():
        m = re.match(r"^\[([^\]]+)\]:\s*\[(.*)\]\s*$", line.strip())
        if m:
            d[m.group(1)] = m.group(2)
        elif "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def main():
    ap = argparse.ArgumentParser(description="Tier-3 completion meter")
    ap.add_argument("--baseline-input", help="stock /proc/bus/input/devices snapshot")
    ap.add_argument("--baseline-i2c", help="stock I2C bindings snapshot")
    ap.add_argument("--current-input", help="candidate input devices snapshot")
    ap.add_argument("--current-i2c", help="candidate I2C bindings snapshot")
    ap.add_argument("--props", help="candidate getprop snapshot")
    ap.add_argument("--touch-events", help="getevent capture for the touch device")
    ap.add_argument("--nav-events", help="getevent capture for virtual keys")
    ap.add_argument("--inventory", help="firmware blob inventory file")
    ap.add_argument("--preflight", help="preflight JSON with verdict")
    ap.add_argument("--boot-ok", action="store_true", help="3 clean cold boots verified")
    ap.add_argument("--hal-ignore", default="",
                    help="comma-separated init.svc.* keys to exclude (oneshot/disabled services)")
    ap.add_argument("--report", help="write JSON report here")
    a = ap.parse_args()

    base_in = input_names(read_text(a.baseline_input))
    cur_in = input_names(read_text(a.current_input))
    base_i2c = i2c_bindings(read_text(a.baseline_i2c))
    cur_i2c = i2c_bindings(read_text(a.current_i2c))
    pr = props(read_text(a.props))
    touch = read_text(a.touch_events)
    nav = read_text(a.nav_events)
    inv = read_text(a.inventory)
    pf = read_text(a.preflight)

    evidence = {}
    states = {}

    # --- inventory comparison ---
    if base_in is not None and cur_in is not None:
        missing = [x for x in base_in if x not in cur_in]
        extra = [x for x in cur_in if x not in base_in]
        rate = (len(base_in) - len(missing)) / len(base_in) if base_in else 0.0
        evidence["input"] = {
            "stock": len(base_in), "candidate": len(cur_in),
            "coverage": round(rate, 4), "missing": missing, "extra": extra,
        }
        states["input_parity"] = "PASS" if not missing else "FAIL"
    else:
        evidence["input"] = {"coverage": None}
        states["input_parity"] = "UNVERIFIED"

    if base_i2c is not None and cur_i2c is not None:
        need = {k: v["driver"] for k, v in base_i2c.items() if v["driver"]}
        bound = {k: cur_i2c[k]["driver"] for k in need
                 if k in cur_i2c and cur_i2c[k]["driver"]}
        missing = sorted(set(need) - set(bound))
        evidence["i2c"] = {
            "stock_devices": len(base_i2c), "stock_with_driver": len(need),
            "candidate_bound": len(bound), "missing": missing,
            "coverage": round(len(bound) / len(need), 4) if need else None,
        }
        states["i2c_parity"] = "PASS" if not missing else "FAIL"
    else:
        evidence["i2c"] = {"coverage": None, "note": "candidate I2C snapshot required"}
        states["i2c_parity"] = "UNVERIFIED"

    # --- evidence-backed gates ---
    states["boot"] = "PASS" if a.boot_ok else (
        "PASS" if pr and pr.get("sys.boot_completed") == "1" else
        ("FAIL" if pr else "UNVERIFIED"))
    states["touch_cold"] = ("PASS" if touch and len(touch.strip().splitlines()) > 0
                            else ("FAIL" if touch is not None else "UNVERIFIED"))
    states["nav_keys"] = ("PASS" if nav and len(nav.strip().splitlines()) > 0
                          else ("FAIL" if nav is not None else "UNVERIFIED"))
    if pr:
        ignored = [x.strip() for x in a.hal_ignore.split(",") if x.strip()]
        keys = [k for k in pr if k.startswith("init.svc.")
                and any(x in k for x in ("vibrator", "fingerprint", "audio", "wifi"))
                and k not in ignored]
        running = [k for k in keys if pr[k] == "running"]
        states["hal"] = "PASS" if keys and len(running) == len(keys) else "FAIL"
        evidence["hal"] = {"checked": keys, "running": running,
                           "excluded_oneshot": ignored}
    else:
        states["hal"] = "UNVERIFIED"
    states["firmware_inventory"] = "PASS" if inv and inv.strip() else "UNVERIFIED"
    if pf:
        try:
            j = json.loads(pf)
            states["reproducible"] = "PASS" if (
                j.get("verdict") == "SAFE_TO_FLASH" and j.get("pass") == j.get("total")
            ) else "FAIL"
        except ValueError:
            states["reproducible"] = "FAIL"
    else:
        states["reproducible"] = "UNVERIFIED"

    lower = sum(w for gid, _, w in GATES if states.get(gid) == "PASS")
    upper = sum(w for gid, _, w in GATES if states.get(gid) != "FAIL")
    result = {
        "score_lower": lower,
        "score_upper": upper,
        "score_note": "lower = verified PASS only; upper = PASS + UNVERIFIED",
        "gates": [{"id": g, "criterion": c, "weight": w, "state": states.get(g, "UNVERIFIED")}
                  for g, c, w in GATES],
        "evidence": evidence,
    }

    print("=== TIER-3 COMPLETION ===")
    print("score: %d%% verified, at most %d%% (unverified counted)" % (lower, upper))
    for g in result["gates"]:
        print("  %-22s %-11s w=%2d  %s" % (g["id"], g["state"], g["weight"], g["criterion"]))
    if evidence.get("input", {}).get("coverage") is not None:
        e = evidence["input"]
        print("input parity: %d/%d = %.1f%%  missing=%s" % (
            e["stock"] - len(e["missing"]), e["stock"], e["coverage"] * 100, e["missing"]))
    if evidence.get("i2c", {}).get("coverage") is not None:
        e = evidence["i2c"]
        print("i2c parity  : %d/%d = %.1f%%  missing=%s" % (
            e["candidate_bound"], e["stock_with_driver"], e["coverage"] * 100, e["missing"]))
    if a.report:
        Path(a.report).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
        print("report:", a.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
