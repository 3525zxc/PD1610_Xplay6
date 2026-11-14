#!/usr/bin/env python3
"""Build a sanitised, GitHub-safe publish tree from the BLM project.

Reads the project read-only and writes a separate ``publish/`` directory.
Binary assets, build artifacts and WSL exports are excluded; text files that
contain device-unique identifiers are redacted in the copy (originals intact).
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {
    "images", "build", "wsl_rebuild", "publish", "publish_sanitized", "archive",
    "prebuilt_extract", "__pycache__", ".git", "edl_probe", "proxy_probe",
}
SKIP_SUFFIX = {
    ".img", ".bin", ".dtb", ".gz", ".asm", ".tar", ".ko", ".elf",
    ".pyc", ".vhdx", ".o", ".a", ".so", ".zip", ".7z",
}
SKIP_NAMES = {"SHA256SUMS", "stock_kallsyms.txt", "stock_kallsyms_addr.txt"}

REDACTIONS = [
    (re.compile(r"(?i)(serialno[=:\s\[\]]+)([0-9a-f]{6,})"), r"\1[REDACTED_SERIAL]"),
    (re.compile(r"(?i)(securebootkeyhash[=:\s\[\]]+)([0-9a-f]{8,})"), r"\1[REDACTED_KEYHASH]"),
    (re.compile(r"(?i)(androidboot\.serialno=)([^\s\[\]]+)"), r"\1[REDACTED_SERIAL]"),
    (re.compile(r"(?i)(ro\.boot\.serialno\]:\s*\[)([^\]]+)"), r"\1[REDACTED_SERIAL]"),
    (re.compile(r"(?i)((?:wifi|bt|eth)macaddr[=:\s\[\]]+)([0-9a-f:]{12,})"), r"\1[REDACTED_MAC]"),
    (re.compile(r"(?i)(imei[=:\s\[\]]+)([0-9]{8,})"), r"\1[REDACTED_IMEI]"),
    # Device serial appears as `adb devices` output, `-s <serial> flash`, and
    # `device=adb <serial>`. Match by shape only: no serial is hardcoded here.
    (re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{8}(?=\s+(?:device|fastboot)\b)"),
     "[DEVICE_SERIAL]"),
    (re.compile(r"(?i)(-s\s+)[0-9a-f]{8}\b"), r"\1[DEVICE_SERIAL]"),
    (re.compile(r"(?i)(device=adb\s+)[0-9a-f]{8}\b"), r"\1[DEVICE_SERIAL]"),
    (re.compile(r"(?i)(transport_id:)(\d+)"), r"\1[N]"),
    (re.compile(r"(?i)(baseband[=:\s\[\]]+)([A-Za-z0-9._-]{6,})"), r"\1[REDACTED_BASEBAND]"),
]

TEXT_SUFFIX = {".txt", ".md", ".json", ".py", ".sh", ".c", ".h", ".csv",
               ".log", ".env", ".patch", ".diff", ".yml", ".yaml", ".bat", ".ps1"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def redact(data, serial=None):
    text = data.decode("utf-8", "replace")
    hits = 0
    if serial:
        text, n = re.subn(re.escape(serial), "[DEVICE_SERIAL]", text, flags=re.I)
        hits += n
    for pat, repl in REDACTIONS:
        text, n = pat.subn(repl, text)
        hits += n
    return text.encode("utf-8"), hits


def main():
    ap = argparse.ArgumentParser(description="Prepare a sanitised GitHub publish tree")
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", help="defaults to <root>/publish")
    ap.add_argument("--serial", default="",
                    help="device serial to redact exactly; passed in, never stored in this file")
    ap.add_argument("--no-redact", action="store_true",
                    help="publish full detail verbatim (no identifier redaction)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    out = Path(a.out).resolve() if a.out else root / "publish"
    if out == root or out in root.parents:
        print("OUTPUT_MUST_BE_A_SUBDIRECTORY_OF_ROOT (use <root>/publish)")
        return 2

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    manifest = {"generated": datetime.now().isoformat(timespec="seconds"),
                "source_root": str(root), "files": [], "redacted_files": [],
                "excluded_count": 0, "bytes": 0}
    excluded = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            excluded += 1
            continue
        if p.suffix.lower() in SKIP_SUFFIX or p.name in SKIP_NAMES:
            excluded += 1
            continue
        data = p.read_bytes()
        hits = 0
        if p.suffix.lower() in TEXT_SUFFIX and not a.no_redact:
            data2, hits = redact(data, a.serial or None)
            if hits:
                data = data2
                manifest["redacted_files"].append({"path": str(rel), "replacements": hits})
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest["files"].append({"path": str(rel), "bytes": len(data),
                                 "sha256": sha256(data)})
        manifest["bytes"] += len(data)

    manifest["excluded_count"] = excluded
    manifest["file_count"] = len(manifest["files"])
    (out / "PUBLISH_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    gitignore = """# BLM project - GitHub publish tree
# Large / third-party binary assets are archived separately (encrypted, Baidu Netdisk / GitHub Release)
/images/
/build/
/wsl_rebuild/
/archive/
*.img
*.bin
*.dtb
*.vhdx
*.tar
*.tar.gz
*.tgz
*.vol*
*.asm
*.ko
*.elf
*.o
*.a
*.pyc
__pycache__/
stock_Image.bin
stock_kallsyms*.txt
blm_ram_round*.bin
PUBLISH_MANIFEST.json
"""
    (out / ".gitignore").write_text(gitignore, encoding="utf-8")

    readme = """# PD1610 / Xplay6 self-compiled kernel + bootloop forensics

vivo Xplay6 (MSM8996, LineageOS 16) self-compiled `3.18.120` kernel:
from bootloop to a bootable desktop with working touch, using a custom
RAM-log monitor (BLM) and Qualcomm 9008 Firehose `peek` to observe failures.

**Start here:** [`offline/12_ai_handoff_index.md`](offline/12_ai_handoff_index.md)
is a standalone index written for a resuming AI: what is stored where, which
files to fetch from cold storage, how to rebuild the WSL toolchain, and which
experiment round to pick up.

## Verified status (2026-11-14)

- Tier-3 completion meter: **50/50 strict**, `UNVERIFIED = 0`
  (report: `flash_log/tier3_coverage_roundA_final_strict.json`).
- Still FAIL: `touch_cold`, `nav_keys`, `input_parity` (5/9), `i2c_parity` (4/9).
- Device rolled back to stock `3.18.71-perf-g8a8c60dd`, `sys.boot_completed=1`.
- A round result: `offline/08_roundA_result.md`. Queue: `offline/05_experiment_queue.md`.

## Honest limitations

- Touch works only after a suspend/resume cycle; cold-boot 30 s window has
  no events. `nav_keys` has no `vivo_virtual_key` input device.
- `adb reboot bootloader` still reboots normally on the candidate kernel.
- The last navigation-key candidate `b6d5debb...` was reported as bootloop
  and rolled back; the cause was never isolated.
- Round 14/15 blamed `usb_bam`; **Round 16 fixed-slot evidence overturned
  that**. The real stall was `qpnp_vibrator_init` -> first SPMI read.
  Do not continue from the old conclusion.

## What this repository does not contain

Boot images, DTB binaries, firmware blobs, RAM dumps and the WSL build
environment are in a separate private cold-storage archive (969 MiB,
2 volumes, zstd tar). This repo is the text-only documentation layer;
see `offline/12_ai_handoff_index.md` section 2 for the restore procedure.

## Licensing

Self-written tools: MIT. Documentation: CC-BY-4.0. Kernel patches follow
the upstream LineageOS msm8996 3.18 GPL-2.0 with copyright headers intact.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    # The prebuilt-route text results live in a separate extract tree. Publish
    # exactly one copy (verbatim by default, sanitized when redaction is on)
    # under prebuilt/ so both projects ship in the same repository.
    pe = root / "prebuilt_extract"
    src_tree = pe / ("prebuilt_sanitized" if not a.no_redact else "prebuilt_verbatim")
    if src_tree.is_dir():
        dest_tree = out / "prebuilt"
        shutil.copytree(src_tree, dest_tree)
        copied = [p for p in dest_tree.rglob("*") if p.is_file()]
        for p in copied:
            rel = p.relative_to(out)
            manifest["files"].append({"path": str(rel).replace("\\", "/"),
                                      "bytes": p.stat().st_size,
                                      "sha256": sha256(p.read_bytes())})
            manifest["bytes"] += p.stat().st_size
        manifest["file_count"] = len(manifest["files"])
        (out / "PUBLISH_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("  + prebuilt/ %d files (from %s)" % (len(copied), src_tree.name))

    print("PUBLISH_READY dir=%s files=%d bytes=%d (%.2f MiB) redacted=%d excluded=%d" % (
        out, manifest["file_count"], manifest["bytes"],
        manifest["bytes"] / 1048576, len(manifest["redacted_files"]), excluded))
    for r in manifest["redacted_files"]:
        print("  redacted %-50s %d replacements" % (r["path"], r["replacements"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
