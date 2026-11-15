# -*- coding: utf-8 -*-
"""读 aboot 并搜索 unlock / secureboot 相关字符串，判断解锁代码是否存在。"""
import os
import re
import subprocess

FH = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5\fh_loader.exe"
SS = 4096
WORK = r"C:\qfilx\probe"
LUN, START, COUNT = 4, 39178, 4096

os.makedirs(WORK, exist_ok=True)
xml = ('<?xml version="1.0" ?>\n<data>\n'
       '<read SECTOR_SIZE_IN_BYTES="%d" filename="aboot.bin" label="aboot" '
       'num_partition_sectors="%d" physical_partition_number="%d" '
       'start_sector="%d"/>\n</data>\n' % (SS, COUNT, LUN, START))
p = os.path.join(WORK, "read_aboot.xml")
open(p, "w", encoding="utf-8", newline="\n").write(xml)

print("[>] 读取 aboot (%d 扇区, %.1f MB) ..." % (COUNT, COUNT * SS / 1048576.0))
r = subprocess.run([FH, "--port=\\\\.\\COM5", "--memoryname=ufs", "--sendxml=" + p,
                    "--noprompt", "--zlpawarehost=1"],
                   cwd=WORK, capture_output=True, text=True, errors="ignore", timeout=600)
out = (r.stdout or "") + (r.stderr or "")
path = os.path.join(WORK, "aboot.bin")
if not os.path.isfile(path):
    print("[x] 读取失败")
    print("\n".join([l for l in out.splitlines() if "ERROR" in l or "Failed" in l][:4]))
    raise SystemExit(1)

d = open(path, "rb").read()
print("[+] 已读 %d 字节" % len(d))

KEYS = [
    b"flashing unlock", b"unlock_critical", b"is_unlocked", b"Device unlocked",
    b"Device tampered", b"oem unlock", b"fastboot", b"securebootkey",
    b"ANDROID-BOOT!", b"devinfo", b"unlock",
]

print("\n=== 命中统计 ===")
for k in KEYS:
    n = d.count(k)
    hits = [m.start() for m in re.finditer(re.escape(k), d)][:3]
    flag = "OK " if n else "-- "
    print("  %s %-20s %4d 次  %s" % (flag, k.decode(), n,
                                     " ".join("0x%X" % h for h in hits)))

print("\n=== 所有含 unlock 的可见字符串（去重前 40 条）===")
seen = set()
for m in re.finditer(rb"[\x20-\x7e]{6,}", d):
    s = m.group()
    if b"unlock" in s.lower():
        t = s.decode("ascii", "ignore")
        if t not in seen:
            seen.add(t)
            print("  0x%06X  %s" % (m.start(), t[:120]))
        if len(seen) >= 40:
            break
if not seen:
    print("  （aboot 里没有任何含 unlock 的字符串）")
