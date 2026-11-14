#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Root 分区回写 / 校验工具（PD1610，需 BL 解锁 + adb root）

用法：
  python scripts/restore_partition_root.py list
  python scripts/restore_partition_root.py verify  boot
  python scripts/restore_partition_root.py restore boot  backup/root_20261111/boot.bin

行为：
  - verify ：把设备分区回读并与本地文件比对 sha256（不写设备）
  - restore：先校验本地文件，push 到 /data/local/tmp，dd 回分区，再回读校验
  - 长度必须严格等于分区字节数；boot 之类的小镜像需先补齐到分区大小
  - userdata 的采样文件（16 MB）禁止 restore，脚本会拒绝
安全：
  - 默认 dry-run，加 --yes 才真正写入
"""
import hashlib
import os
import subprocess
import sys

ADB = r"C:\UnlockTool\Binaries\adb.exe"
BDEV = "/dev/block/bootdevice/by-name/"
TMP = "/data/local/tmp/wb_restore.bin"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def adb(args, timeout=3600, binary=False):
    if binary:
        return subprocess.run([ADB, "exec-out"] + args,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=timeout)
    return subprocess.run([ADB] + args, capture_output=True, timeout=timeout)


def sh(cmd, timeout=3600):
    return adb(["shell", cmd], timeout=timeout)


def part_size(name):
    r = sh("blockdev --getsize64 " + BDEV + name)
    out = r.stdout.decode("ascii", "replace").strip().split()
    return int(out[0]) if out and out[0].isdigit() else None


def dev_sha(name, size):
    r = sh("dd if=%s%s bs=1048576 2>/dev/null | head -c %d | sha256sum" % (BDEV, name, size))
    tok = r.stdout.decode("ascii", "replace").split()
    return tok[0] if tok and len(tok[0]) == 64 else None


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def do_list():
    r = sh("ls /dev/block/bootdevice/by-name")
    names = r.stdout.decode().split()
    for n in names:
        print("%-16s %s" % (n, part_size(n)))


def do_verify(name):
    size = part_size(name)
    if size is None:
        print("no such partition: %s" % name)
        return 1
    path = os.path.join(BASE, "backup", "root_20261111", name + ".bin")
    if not os.path.exists(path):
        print("local backup missing: %s" % path)
        return 1
    ls = os.path.getsize(path)
    if ls != size:
        print("尺寸不一致：本地 %d / 分区 %d —— 本地为采样文件，无法比对" % (ls, size))
        return 1
    a = file_sha(path)
    b = dev_sha(name, size)
    print("%-12s local=%s\n             device=%s\n             %s" %
          (name, a, b, "一致" if a == b else "不一致"))
    return 0 if a == b else 1


def do_restore(name, path, yes=False):
    if name == "userdata":
        print("拒绝：userdata 只有 16 MB 采样，不允许回写")
        return 1
    size = part_size(name)
    if size is None:
        print("no such partition: %s" % name)
        return 1
    if not os.path.exists(path):
        print("file missing: %s" % path)
        return 1
    fs = os.path.getsize(path)
    if fs != size:
        print("拒绝：文件 %d B 与分区 %d B 不一致（小镜像请先补齐/或用 fastboot flash）" % (fs, size))
        return 1
    lsha = file_sha(path)
    print("partition=%s size=%d sha256=%s" % (name, size, lsha))
    if not yes:
        print("[dry-run] 未写入。确认无误后加 --yes")
        return 0
    print("pushing ...")
    r = adb(["push", path, TMP])
    if r.returncode != 0:
        print("push failed:", r.stderr.decode("utf-8", "replace")[:300])
        return 1
    print("writing ...")
    r = sh("dd if=%s of=%s%s bs=1048576 2>&1; sync" % (TMP, BDEV, name))
    print(r.stdout.decode("utf-8", "replace").strip()[-300:])
    dsha = dev_sha(name, size)
    print("回读 sha256=%s  %s" % (dsha, "一致" if dsha == lsha else "不一致！"))
    sh("rm -f " + TMP)
    return 0 if dsha == lsha else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "list":
        do_list()
    elif cmd == "verify" and len(sys.argv) >= 3:
        sys.exit(do_verify(sys.argv[2]))
    elif cmd == "restore" and len(sys.argv) >= 4:
        sys.exit(do_restore(sys.argv[2], sys.argv[3], "--yes" in sys.argv))
    else:
        print(__doc__)
