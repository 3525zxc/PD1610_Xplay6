#!/usr/bin/env python3
"""Create a full, verifiable archive of the BLM project for cold storage.

Reads the project read-only. Produces:
  archive/manifest.json        - every file with size + sha256
  archive/blm_full.tar.zst     - compressed tar (zstd, level 6)
  archive/volumes/*.vol        - split volumes sized for upload
  archive/SHA256SUMS           - checksums of the volumes + manifest
  archive/RESTORE.md           - how to reassemble and verify

Excludes the publish/ and archive/ directories themselves to avoid recursion.
Encryption: optional --password, applied with `openssl enc -aes-256-cbc -pbkdf2`
on each volume (produces .enc files). Without a password the archive is NOT
encrypted - make sure the destination is private.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

try:
    from compression import zstd
except ImportError:
    zstd = None


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="Cold-storage archive of the BLM project")
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", help="defaults to <root>/archive")
    ap.add_argument("--volume-mb", type=int, default=900,
                    help="volume size in MiB (default 900, safe for most cloud disks)")
    ap.add_argument("--password", default="", help="if set, AES-256 encrypt each volume")
    ap.add_argument("--no-tar", action="store_true", help="skip tar, only refresh manifest")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    out = Path(a.out).resolve() if a.out else root / "archive"
    if out == root or out in root.parents:
        print("OUTPUT_MUST_BE_A_SUBDIRECTORY_OF_ROOT")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    vol_dir = out / "volumes"
    if vol_dir.exists():
        for p in vol_dir.iterdir():
            if p.is_file():
                p.unlink()
    vol_dir.mkdir(exist_ok=True)

    skip_top = {"publish", "publish_sanitized", "archive", "__pycache__", ".git"}
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts[0] in skip_top:
            continue
        if p.suffix == ".pyc":
            continue
        st = p.stat()
        files.append({"path": str(rel).replace("\\", "/"), "bytes": st.st_size,
                      "sha256": sha256_file(p)})

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(root),
        "file_count": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "note": "Full cold-storage archive. Contains third-party binaries and "
                "device-unique identifiers - store privately, do not publish.",
        "files": files,
    }
    mf = out / "manifest.json"
    mf.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MANIFEST files=%d bytes=%d (%.2f GiB)" % (
        len(files), manifest["total_bytes"], manifest["total_bytes"] / 2**30), flush=True)

    if a.no_tar:
        return 0

    tar_path = out / "blm_full.tar.zst"
    if zstd is None:
        print("NO_ZSTD_SUPPORT (Python 3.14+ required)")
        return 3

    print("TAR_START -> %s" % tar_path.name, flush=True)
    tfile = out / "blm_full.tar"
    with tarfile.open(tfile, "w", format=tarfile.GNU_FORMAT) as tf:
        for f in files:
            p = root / f["path"]
            tf.add(p, arcname=f["path"], recursive=False)
        tf.add(mf, arcname="manifest.json")
    print("TAR_DONE bytes=%d" % tfile.stat().st_size, flush=True)

    print("ZSTD_START level=6", flush=True)
    with open(tfile, "rb") as src, zstd.open(tar_path, "wb", level=6) as dst:
        while True:
            chunk = src.read(4 << 20)
            if not chunk:
                break
            dst.write(chunk)
    tfile.unlink()
    zipped = tar_path.stat().st_size
    print("ZSTD_DONE bytes=%d ratio=%.3f" % (
        zipped, zipped / manifest["total_bytes"]), flush=True)

    vol_bytes = a.volume_mb * 1024 * 1024
    print("SPLIT_START volume=%d MiB" % a.volume_mb, flush=True)
    sums = []
    with open(tar_path, "rb") as src:
        idx = 0
        while True:
            chunk = src.read(vol_bytes)
            if not chunk:
                break
            idx += 1
            vp = vol_dir / ("blm_full.tar.zst.part%02d" % idx)
            vp.write_bytes(chunk)
            final = vp
            if a.password:
                enc = vol_dir / (vp.name + ".enc")
                cmd = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt",
                       "-in", str(vp), "-out", str(enc), "-pass", "env:BLM_ARCHIVE_PW"]
                env = dict(os.environ, BLM_ARCHIVE_PW=a.password)
                r = subprocess.run(cmd, capture_output=True, env=env)
                if r.returncode != 0:
                    print("ENCRYPT_FAIL", r.stderr.decode("utf-8", "replace")[:300])
                    return 4
                vp.unlink()
                final = enc
            sums.append((final.name, final.stat().st_size, sha256_file(final)))
            print("  volume %02d %-36s %8.1f MiB" % (
                idx, final.name, final.stat().st_size / 1048576), flush=True)
    tar_path.unlink()

    with open(out / "SHA256SUMS", "w", encoding="utf-8", newline="\n") as sf:
        for n, _, h in sums:
            sf.write("%s  volumes/%s\n" % (h, n))
        sf.write("%s  manifest.json\n" % sha256_file(mf))

    enc_note = ("AES-256-CBC encrypted (password required)"
                if a.password else "NOT encrypted")
    restore = f"""# Restore the BLM cold-storage archive

Volumes: {len(sums)} files, {a.volume_mb} MiB each. Encryption: {enc_note}.

1. Download every `volumes/*` file plus `manifest.json` and `SHA256SUMS`
   into one empty directory, preserving the `volumes/` subfolder.
2. Verify: `sha256sum -c SHA256SUMS` (every line must say OK).
3. Decrypt if `.enc` volumes were produced:

       for f in volumes/*.enc; do
         openssl enc -d -aes-256-cbc -pbkdf2 -in "$f" \\
           -out "${{f%.enc}}" -pass env:BLM_ARCHIVE_PW
       done

4. Reassemble and extract (Python 3.14+ has built-in zstd):

       cat volumes/blm_full.tar.zst.part* > blm_full.tar.zst
       python -c "from compression import zstd; import tarfile; \\
         f=zstd.open('blm_full.tar.zst','rb'); \\
         tarfile.open(fileobj=f,mode='r|').extractall('restored')"

   Any zstd-capable tool works, e.g. `zstd -d` then `tar -xf`.
5. Verify every restored file against `manifest.json` (path -> sha256).
6. For the WSL build environment, see `offline/11_wsl_rebuild_guide.md`,
   route B. This archive contains `wsl_rebuild/` (1.6 GiB minimal
   reproducible build set) with its own `SHA256SUMS`.
7. Read `AI_HANDOFF_INDEX.md` in the GitHub repository for what each
   resource is for and which ones to hand to an AI when resuming work.

Notes:
- The archive contains third-party boot images, DTBs, firmware-derived
  data and device-unique identifiers. Publishing the volumes publicly is
  a separate decision from publishing the text-only GitHub repository.
- If encrypted, the password is NOT stored in the archive. Keep it
  separately or you will not be able to restore.
"""
    (out / "RESTORE.md").write_text(restore, encoding="utf-8")

    print("ARCHIVE_DONE volumes=%d encrypted=%s" % (len(sums), bool(a.password)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
