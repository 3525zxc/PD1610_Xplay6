#!/usr/bin/env python3
"""Zero-context evidence ledger for this project.

Borrows the *method* from ARIS integrity-forensics (span-anchored evidence
ledger + rules-only reporter, never invent a value) but implements it locally:
no external reviewer backend, no paper assumptions. Checks that every hash
mentioned in the reports actually exists among the delivered images, that
observations/hypotheses are labelled, and that completion gates have evidence.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "images"
DOC_DIRS = [ROOT, ROOT / "offline"]
REPORTS = sorted(set(
    [p for d in DOC_DIRS for p in d.glob("ROUND*.md")]
    + [p for p in (ROOT / "offline").glob("0*.md")]
))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    images = {}
    for p in sorted(IMG_DIR.glob("*.img")):
        images[sha256(p)] = p.name
    # reports also quote hashes of evidence binaries / DTBs, not just boot.img
    for d in (ROOT / "flash_log", ROOT / "offline", ROOT / "fixtures"):
        for p in sorted(list(d.glob("*.bin")) + list(d.glob("*.dtb"))):
            images[sha256(p)] = p.name
    stock = Path("D:/16/PD1610_81/release/PD1610_LOS16_20261112/images/boot.img")
    if stock.exists():
        images[sha256(stock)] = "stock_boot.img"
    # intermediate kernel builds are quoted by their recorded sha, not kept as .img
    for env in sorted((ROOT / "build").glob("*/kernel_build.env")):
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("IMAGE_SHA256="):
                images[line.split("=", 1)[1].strip()] = env.parent.name + "/Image.gz-dtb"
    findings = []

    # 1. hash mentions in reports must match a delivered image (prefix or full)
    mentioned = 0
    unresolved = []
    for doc in REPORTS:
        text = doc.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\b([0-9a-f]{8,64})(?:\u2026|\.\.\.)?\b", text):
            frag = m.group(1)
            if len(frag) < 8:
                continue
            # decimal byte counts and the device serial are not hashes
            if frag.isdigit() or frag == "5fccbfeb":
                continue
            # only treat as a hash if context hints at it
            ctx = text[max(0, m.start() - 40):m.start()].lower()
            if not any(k in ctx for k in ("sha", "hash", "镜像", "镜像", "img")):
                continue
            mentioned += 1
            if not any(full.startswith(frag) for full in images):
                unresolved.append({"doc": doc.name, "fragment": frag})
    findings.append({
        "id": "hash_ledger",
        "images_indexed": len(images),
        "hash_mentions_checked": mentioned,
        "unresolved": unresolved[:20],
        "state": "PASS" if not unresolved else "WARN",
    })

    # 2. observation / hypothesis separation in the new offline reports
    labels = {}
    for p in sorted((ROOT / "offline").glob("0*.md")):
        if p.name.startswith("05_"):
            continue  # experiment queue is a plan, not an observation report
        t = p.read_text(encoding="utf-8", errors="replace")
        labels[p.name] = {"O": len(re.findall(r"\[O\]", t)),
                          "H": len(re.findall(r"\[H\]", t))}
    unlabelled = [n for n, v in labels.items() if v["O"] == 0 and v["H"] == 0]
    findings.append({
        "id": "observation_hypothesis_labels",
        "reports": labels,
        "reports_without_labels": unlabelled,
        "state": "PASS" if not unlabelled else "WARN",
    })

    # 3. completion meter gate evidence
    cov = ROOT / "flash_log" / "tier3_coverage_roundA_final_strict.json"
    if not cov.exists():
        cov = ROOT / "flash_log" / "tier3_coverage_offline.json"
    if not cov.exists():
        cov = ROOT / "flash_log" / "tier3_coverage_round24.json"
    gate_summary = None
    if cov.exists():
        j = json.loads(cov.read_text(encoding="utf-8"))
        gate_summary = {
            "score_lower": j.get("score_lower"),
            "score_upper": j.get("score_upper"),
            "unverified": [g["id"] for g in j.get("gates", []) if g["state"] == "UNVERIFIED"],
            "failed": [g["id"] for g in j.get("gates", []) if g["state"] == "FAIL"],
        }
    findings.append({"id": "completion_gates", "state": "INFO", "detail": gate_summary})

    # 4. firmware inventory must be non-empty and parseable
    inv = ROOT / "offline" / "03_firmware_inventory.csv"
    n = 0
    if inv.exists():
        n = max(0, len(inv.read_text(encoding="utf-8").splitlines()) - 1)
    findings.append({"id": "firmware_inventory", "entries": n,
                     "state": "PASS" if n > 0 else "FAIL"})

    result = {
        "scope": "offline evidence ledger (local, no cross-model reviewer)",
        "reports_scanned": [p.name for p in REPORTS],
        "findings": findings,
        "verdict": "BLOCK" if any(f["state"] == "FAIL" for f in findings)
                   else ("WARN" if any(f["state"] == "WARN" for f in findings) else "NO_NEW_BLOCKER"),
        "note": "A clean sweep is recorded as NO_NEW_BLOCKER, not an acquittal.",
    }
    out = ROOT / "offline" / "04_evidence_audit.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("=== EVIDENCE AUDIT ===")
    for f in findings:
        print(" ", f["id"], f["state"],
              {k: v for k, v in f.items() if k not in ("id", "state", "reports")})
    print("verdict:", result["verdict"], "| report:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
