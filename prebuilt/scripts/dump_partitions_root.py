#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Root 基线备份：通过 adb (su) 直接 dd 读取块设备，流式落盘到 PC。
- 不再依赖 EDL / fh_loader，不需要短接
- 每个分区：本地流式 sha256 + 设备端 sha256sum 双向比对 + 长度校验
- userdata 过大（112.7 GB）只采样头部 16 MB
输出目录：D:\\16\\PD1610_81\\backup\\root_20261111
"""
import hashlib
import json
import os
import subprocess
import sys
import time

ADB = r"C:\UnlockTool\Binaries\adb.exe"
SIZES = r"D:\16\PD1610_81\work\part_sizes.txt"
OUT = r"D:\16\PD1610_81\backup\root_20261111"
BDEV = "/dev/block/bootdevice/by-name/"
CHUNK = 1 << 20

# 全量备份，但这些分区只做头部采样
SAMPLE_HEAD = {"userdata": 16 << 20}
# 直接跳过（不产生文件）
SKIP = set()


def adb(args, timeout=None):
    return subprocess.run([ADB] + args, capture_output=True, timeout=timeout)


def load_sizes():
    rows = []
    with open(SIZES, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.split()
            if len(p) != 2:
                continue
            name, sz = p[0], p[1]
            if name == "*" or not sz.isdigit():
                continue
            rows.append((name, int(sz)))
    return rows


def dev_sha(name, limit=None):
    # toybox dd 把统计行写到 stdout，先 head -c 精确截断再算 sha
    cmd = "sha256sum " + BDEV + name
    if limit:
        cmd = ("dd if=%s%s bs=1048576 count=%d 2>/dev/null | head -c %d | sha256sum"
               % (BDEV, name, (limit + (1 << 20) - 1) // (1 << 20), limit))
    r = adb(["shell", cmd], timeout=900)
    out = r.stdout.decode("ascii", "replace").strip()
    tok = out.split()
    return tok[0] if tok and len(tok[0]) == 64 else None


def dump(name, size, sample=None):
    target_bytes = sample if sample else size
    path = os.path.join(OUT, "%s.bin" % name)
    t0 = time.time()
    if sample is None:
        # adb pull 比 exec-out dd 快约 3 倍
        r = adb(["pull", BDEV + name, path], timeout=3600)
        rc = r.returncode
        if rc != 0 or not os.path.exists(path):
            msg = r.stderr.decode("utf-8", "replace").strip()[:200]
            raise RuntimeError("adb pull failed rc=%d %s" % (rc, msg))
        h = hashlib.sha256()
        got = 0
        with open(path, "rb") as f:
            while True:
                buf = f.read(CHUNK * 4)
                if not buf:
                    break
                h.update(buf)
                got += len(buf)
        return path, got, h.hexdigest(), time.time() - t0

    cmd = [ADB, "exec-out",
           "dd if=%s%s bs=1048576 count=%d" % (BDEV, name, (sample + (1 << 20) - 1) // (1 << 20))]
    h = hashlib.sha256()
    got = 0
    with open(path, "wb") as f:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, bufsize=CHUNK * 4)
        # toybox dd 的统计行会污染 stdout，这里只取精确的 target_bytes
        while got < target_bytes:
            want = min(CHUNK, target_bytes - got)
            buf = p.stdout.read(want)
            if not buf:
                break
            f.write(buf)
            h.update(buf)
            got += len(buf)
        try:
            p.kill()
        except Exception:
            pass
        try:
            p.wait(timeout=10)
        except Exception:
            pass
        try:
            p.stdout.close()
        except Exception:
            pass
    dt = time.time() - t0
    return path, got, h.hexdigest(), dt


def main():
    only = sys.argv[1:] or None
    os.makedirs(OUT, exist_ok=True)
    rows = load_sizes()
    if only:
        rows = [r for r in rows if r[0] in only]

    total = sum(SAMPLE_HEAD.get(n, s) for n, s in rows)
    print("[i] partitions=%d  planned bytes=%.2f GB" % (len(rows), total / 1e9))
    sys.stdout.flush()

    manifest = []
    ok = fail = 0
    for idx, (name, size) in enumerate(rows, 1):
        if name in SKIP:
            continue
        sample = SAMPLE_HEAD.get(name)
        need = sample if sample else size
        free = None
        try:
            import shutil
            free = shutil.disk_usage(OUT).free
        except Exception:
            pass
        if free is not None and free < need + (200 << 20):
            print("[!] %-14s SKIP: free space %d MB < need %d MB" %
                  (name, free >> 20, need >> 20))
            manifest.append({"name": name, "status": "skipped_nospace",
                             "expected": size})
            fail += 1
            continue

        print("[%2d/%2d] %-14s %10d B%s ..." %
              (idx, len(rows), name, need, " (sample)" if sample else ""))
        sys.stdout.flush()
        try:
            path, got, lsha, dt = dump(name, size, sample)
        except Exception as e:
            print("    FAIL dump: %s" % e)
            manifest.append({"name": name, "status": "error", "error": str(e)})
            fail += 1
            continue

        dsha = dev_sha(name, sample)
        size_ok = (got == need)
        sha_ok = (dsha == lsha)
        status = "ok" if (size_ok and sha_ok) else "mismatch"
        if status == "ok":
            ok += 1
        else:
            fail += 1
        print("    -> %d B in %.1fs (%.1f MB/s) size_ok=%s sha_ok=%s" %
              (got, dt, got / dt / 1e6 if dt else 0, size_ok, sha_ok))
        if not sha_ok:
            print("    local=%s dev=%s" % (lsha, dsha))
        sys.stdout.flush()

        manifest.append({
            "name": name,
            "file": os.path.basename(path),
            "status": status,
            "partition_bytes": size,
            "dumped_bytes": got,
            "sampled": bool(sample),
            "sha256": lsha,
            "sha256_device": dsha,
            "size_ok": size_ok,
            "sha_ok": sha_ok,
            "seconds": round(dt, 2),
        })

    mpath = os.path.join(OUT, "_manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "adb": ADB, "count": len(manifest),
                   "ok": ok, "fail": fail, "partitions": manifest},
                  f, ensure_ascii=False, indent=1)
    print("\n[done] ok=%d fail=%d  manifest=%s" % (ok, fail, mpath))


if __name__ == "__main__":
    main()
