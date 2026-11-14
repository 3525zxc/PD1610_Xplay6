#!/usr/bin/env python3
"""Extract the valuable text results from the 40 GiB prebuilt-route workspace.

D:/16/PD1610_81 is the "prebuilt kernel + vendor blobs + borrowed device tree"
project that predates the BLM self-compiled-kernel work. Almost all of its
value is in ~10 MiB of text; the other ~40 GiB is dump images, ROM zips and
duplicate uploads. This script copies the text layer into two publish-ready
trees and writes a binary-asset manifest (does NOT copy the binaries).

Usage:
  python tools/blm_prebuilt_extract.py --src D:/16/PD1610_81 --out <dir>
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TEXT_SUFFIX = {
    ".md", ".txt", ".json", ".sh", ".py", ".ps1", ".bat", ".mk", ".prop",
    ".xml", ".diff", ".patch", ".log", ".fstab", ".rc", ".yaml", ".yml",
    ".csv", ".dts", ".dtsi", ".html", ".qcom", ".kl", ".h", ".cpp",
    ".c", ".bp", ".mk", ".ini", ".conf",
}
MAX_TEXT = 3 * 1024 * 1024

# Directories that are pure duplication / historic upload snapshots
SKIP_PARTS = {"upload_by_mtime", "upload_20261111-0027", "upload",
              "__pycache__", ".git", "_repo-src", "_repo-src-full"}
SKIP_SUFFIX = {".pyc", ".img", ".bin", ".zip", ".tar", ".gz", ".png",
               ".jpg", ".jpeg", ".elf", ".ko", ".so", ".o", ".a"}

CORE = {
    "evidence": "逆向取证报告：aboot 失败路径、ROUND3–5 状态机、GPL/移植路线、blob 提取",
    "refs": "PD1619 移植笔记（1042 行）、BoardConfig、mk、fstab、extract-files.sh",
    "scripts": "87 个自研工具：boot.img 拆包/打包、DTB 补丁、vendor 提取、ELF 依赖分析",
    "build": "WSL 供给、repo sync、LOS16 构建、EDL 刷机脚本",
    "device_tree": "反编译 DTS 基线与 README",
    "blobs": "vendor 清单：1824 文件 inventory、211 符号链接、1041 条 proprietary-files、ELF 依赖闭包",
    "work": "实机实验日志与判读报告",
    "release": "发布包内的 flash_all.sh / sha256sums.txt 等文本",
}

REDACTIONS = [
    (re.compile(r"(?i)(serialno[=:\s\[\]]+)([0-9a-f]{6,})"), r"\1[REDACTED_SERIAL]"),
    (re.compile(r"(?i)(securebootkeyhash[=:\s\[\]]+)([0-9a-f]{8,})"), r"\1[REDACTED_KEYHASH]"),
    (re.compile(r"(?i)(imei[=:\s\[\]]+)([0-9]{8,})"), r"\1[REDACTED_IMEI]"),
    (re.compile(r"(?<![0-9a-f])[0-9a-f]{8}(?=\s+(?:device|fastboot)\b)"),
     "[DEVICE_SERIAL]"),
    (re.compile(r"(?i)(-s\s+)[0-9a-f]{8}\b"), r"\1[DEVICE_SERIAL]"),
]

# Binary assets worth keeping in private cold storage, with their role.
BINARY_GROUPS = [
    ("sys13_good_baseline", "out/system.img",
     "sys13 = WiFi 修通后的已知良好 system.img，sha 686de5de…；修 bug 的对照基线"),
    ("sys13_release_copy", "release/PD1610_LOS16_20261112/images/system.img",
     "发布包内的同版 system.img（1.85 GiB）"),
    ("prebuilt_kernel", "device_tree/device/vivo/pd1610/prebuilt/kernel",
     "prebuilt 路线核心：原厂内核镜像 56 MB，TARGET_PREBUILT_KERNEL 指向它"),
    ("rollback_base", "release/PD1610_LOS16_20261112/images/boot.img",
     "原厂 boot 回滚基线 sha 929fda99…"),
    ("device_tree_ref", "refs/device_PD1619.tar.gz",
     "借用的 PD1619 设备树打包副本（5 MiB）"),
    ("vendor_blob_archive", "blobs/_vendor.tar",
     "设备端 /system/vendor 原始归档（493 MiB，权威副本）"),
    ("kernel_modules", "blobs/modules", "13 个 .ko（712 KiB），含 wlan.ko"),
    ("partition_dumps", "backup", "48 个分区原始 dump（含 aboot/modem/devinfo 等）"),
    ("rom_output", "release/PD1610_LOS16_20261112_UNOFFICIAL.zip",
     "prebuilt 路线最终可刷 ROM"),
    ("compat_libs", "release/PD1610_LOS16_20261112/patches/compat_libs",
     "8.1 兼容库 .so（camera/GNSS/wifi 私有实现，修相机 TODO 要用）"),
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def du(path):
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src = Path(a.src).resolve()
    out = Path(a.out).resolve()
    if not src.is_dir():
        print("SRC_NOT_FOUND", src)
        return 2

    verbatim = out / "prebuilt_verbatim"
    sanitized = out / "prebuilt_sanitized"
    for d in (verbatim, sanitized):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    records = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        parts = set(rel.parts)
        if parts & SKIP_PARTS:
            continue
        top = rel.parts[0]
        if top not in CORE:
            continue
        # The final patched sources live under release/.../patches/. They are
        # the sys13 WiFi fix and are the single most valuable set for future
        # bug fixing, so never drop them on suffix grounds.
        is_final_patch = "patches" in rel.parts and top == "release"
        if not is_final_patch:
            if p.suffix.lower() in SKIP_SUFFIX or p.suffix.lower() not in TEXT_SUFFIX:
                continue
            if p.stat().st_size > MAX_TEXT:
                continue
            # blobs/: only the top-level manifest files, not the 1824 extracted files
            if top == "blobs" and len(rel.parts) > 2:
                continue
            # work/: only top-level reports, skip nested ramdisk/extract trees
            if top == "work" and len(rel.parts) > 2:
                continue
            # build/: skip the repo tool's vendored subdirs
            if top == "build" and any(x.startswith("_") for x in rel.parts[1:]):
                continue
            # device_tree/: keep the full text tree, drop the 56 MB prebuilt kernel
            if top == "device_tree" and p.name == "kernel":
                continue
        else:
            # patches/ contains small .so/.png too; only text-ish sources matter
            if p.suffix.lower() not in TEXT_SUFFIX:
                continue
            if p.stat().st_size > MAX_TEXT:
                continue
        data = p.read_bytes()
        clean = data
        for pat, repl in REDACTIONS:
            clean = pat.sub(repl, clean.decode("utf-8", "replace")).encode("utf-8")
        for target, payload in ((verbatim, data), (sanitized, clean)):
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
        records.append({"path": str(rel).replace("\\", "/"), "bytes": len(data),
                        "sha256": sha256(data)})

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "source": str(src),
        "source_total_bytes": du(src),
        "extracted_files": len(records),
        "extracted_bytes": sum(r["bytes"] for r in records),
        "groups": CORE,
        "files": records,
        "binary_assets": [],
        "open_todos": [
            "相机 Number of camera devices: 0（116 chromatix / 136 mmcamera 库都在，"
            "provider 已注册，需查 mm-qcamera-daemon 日志与权限）",
            "xtwifi-inet-agent 缺 libcurl.so（XTRA 辅助下载，非致命）",
            "发布前清理诊断代码：init.cpp PD1610 DIAG、init.qcom.rc kmsg 标记、"
            "PD_WD_SECONDS 100000、init.rc 的 pd1610-crypto-fix、printk 7 7 7 7；"
            "清理后须重编 boot+system 复测首启",
            "sepolicy 仍 permissive；configstore-hal-1-0 被 seccomp getdents64 拦截"
            "，每 5 s SIGSYS 重启",
            "未产出可刷 ROM zip / TWRP 包",
        ],
        "wifi_fix_files": [
            "device/vivo/pd1610/device.mk",
            "device/vivo/pd1610/BoardConfig.mk",
            "device/vivo/pd1610/rootdir/init.pd1610.rc",
            "vendor/vivo/pd1610/pd1610-vendor.mk",
            "vendor/vivo/pd1610/proprietary/vendor/etc/init/hw/init.qcom.rc",
            "system/core/rootdir/init.rc",
            "system/core/init/init.cpp",
        ],
    }
    for key, rel, note in BINARY_GROUPS:
        p = src / rel
        manifest["binary_assets"].append({
            "key": key, "path": rel, "note": note,
            "exists": p.exists(),
            "bytes": du(p) if p.exists() else None,
        })

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    readme = f"""# Prebuilt-route workspace: extracted results

Source: `{src}` ({du(src)/2**30:.1f} GiB)
Extracted text: **{len(records)} files / {manifest['extracted_bytes']/1048576:.1f} MiB**
Generated: {manifest['created']}

## What this project was

The **prebuilt route** (2026-11-10 → 11-12): vivo never released kernel
source for PD1610/PD1619, so this line of work rebuilt a LOS16 ROM using
the stock prebuilt kernel + vendor blobs + a borrowed LeEco s2 / PD1619
device tree. It is the predecessor of the BLM self-compiled-kernel work.
Key results are in `evidence/GPL_AND_PORTING_ROADMAP.md` and
`refs/PD1619_PORTING_NOTES.md`.

## Two publish trees

- `prebuilt_verbatim/` — full detail, no redaction (matches the user's
  decision to publish everything on GitHub).
- `prebuilt_sanitized/` — same files with device identifiers redacted.

Pick one as the repository root. Both contain a copy of this README.

## Binary assets (private cold storage only)

The binaries are **not copied here**. Upload them to the private netdisk
from the original paths listed in `manifest.json` -> `binary_assets`.
Priority 1: the `boot.img` rollback baseline, `refs/device_PD1619.tar.gz`,
`blobs/_vendor.tar`, `blobs/modules/`, and the `backup/` partition dumps.

## Why the small text layer is the valuable part

40 GiB of the source is ROM zips, system.img, 48 partition dumps and
duplicate upload snapshots. Those are reproducible or re-dumpable from
the device. The text layer is the irreplaceable part: reverse
engineering conclusions, the 1042-line porting note, blob dependency
inventories, and 87 custom tools.

## If the goal is to FIX the remaining bugs (read this first)

`release/PD1610_LOS16_20261112/patches/` contains the **final sys13 patched
sources** (the WiFi fix) and is NOT the same as the `device_tree/` baseline.
Both are extracted; diff them before editing anything. The 7 files that
produced the working WiFi are listed in `manifest.json` -> `wifi_fix_files`.

Known-good baseline for comparison: `out/system.img` = **sys13**,
sha256 `686de5de21ad6c8837530836ba9483bd63e69ce660d2de289c4c0a2eecb88e9a`,
`Wi-Fi is enabled` / `wpa_supplicant=running` / 9 APs visible. Keep this
image in private cold storage; without it a regression cannot be told apart
from a pre-existing broken state.

Open TODOs (full text in `evidence/_log_append4.md`):

1. Camera: `Number of camera devices: 0` despite 116 chromatix + 136
   mmcamera libs present. Check `mm-qcamera-daemon` logs / SELinux perms.
2. `xtwifi-inet-agent` missing `libcurl.so` (non-fatal XTRA download).
3. Remove diagnostic code before release: `init.cpp` PD1610 DIAG,
   `init.qcom.rc` kmsg markers, `PD_WD_SECONDS 100000`,
   `init.rc` `pd1610-crypto-fix`, `printk 7 7 7 7`. Rebuild BOTH boot and
   system afterwards and re-test first boot.
4. sepolicy still permissive; `configstore-hal-1-0` killed by seccomp
   `getdents64` every 5 s (log noise).
5. No flashable ROM zip / TWRP package produced yet.

Also do NOT repeat these corrected misdiagnoses (all in
`evidence/_log_append3.md` / `_log_append4.md`):

- "device hung / kernel panic" was wrong - `logcat -v time -b all` plus
  2 s dmesg sampling proved the device stayed alive; only USB/adbd dropped.
- `WifiScanningService: wifi driver unloaded` is the normal
  `CMD_DRIVER_UNLOADED` message when WiFi is off, not missing-driver evidence.
- The "AOSP9 wifi HAL vs 8.1 libwifi-hal ABI mismatch" theory was wrong:
  the real cause was the 8.1 `libwifi-hal.so` blob **overwriting** the
  freshly built AOSP9 one. Removing that copy rule fixed the SIGSEGV.

Build command (from `build/build_pd1610.sh`, bypasses lunch because
`lunch lineage_pd1610-userdebug` hangs on this tree):

    bash ~/build_pd1610.sh systemimage     # ~75 s
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    for d in (verbatim, sanitized):
        (d / "README.md").write_text(readme, encoding="utf-8")

    print("EXTRACT_OK files=%d bytes=%d (%.2f MiB) source=%.1f GiB" % (
        len(records), manifest["extracted_bytes"],
        manifest["extracted_bytes"] / 1048576, du(src) / 2**30))
    for k, _, _ in BINARY_GROUPS:
        e = next(x for x in manifest["binary_assets"] if x["key"] == k)
        print("  binary %-22s exists=%s bytes=%s" % (k, e["exists"], e["bytes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
