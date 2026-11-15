# -*- coding: utf-8 -*-
"""用 fh_loader 按 GPT 解析出的坐标导出指定分区。只读操作。"""
import io
import os
import subprocess
import sys

FH = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5\fh_loader.exe"
PORT = r"\\.\COM5"
XMLDIR = r"C:\qfilx\xml"
OUTDIR = r"C:\qfilx\dumps"
SS = 4096

# (name, lun, start_sector, num_sectors)
TARGETS = [
    ("devinfo",  4, 882954, 1),
    ("modemst1", 5, 6, 512),
    ("modemst2", 5, 518, 512),
    ("fsg",      4, 1542, 512),
    ("fsc",      5, 1030, 1),
    ("persist",  0, 8, 8192),
    ("misc",     0, 73736, 256),
]


def make_xml(name, lun, start, count):
    xml = ('<?xml version="1.0" ?>\n<data>\n'
           '<read SECTOR_SIZE_IN_BYTES="%d" filename="%s.bin" label="%s" '
           'num_partition_sectors="%d" physical_partition_number="%d" '
           'start_sector="%d"/>\n</data>\n' % (SS, name, name, count, lun, start))
    p = os.path.join(XMLDIR, name + ".xml")
    io.open(p, "w", encoding="utf-8", newline="\n").write(xml)
    return p


def main():
    os.makedirs(XMLDIR, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)
    ok, bad = [], []
    for name, lun, start, count in TARGETS:
        xml = make_xml(name, lun, start, count)
        want = count * SS
        print("[>] %-10s LUN%d start=%-8d %8.2f MB ... " %
              (name, lun, start, want / 1048576.0), end="", flush=True)
        r = subprocess.run(
            [FH, "--port=" + PORT, "--memoryname=ufs", "--sendxml=" + xml,
             "--noprompt", "--zlpawarehost=1"],
            cwd=OUTDIR, capture_output=True, text=True, errors="ignore", timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        path = os.path.join(OUTDIR, name + ".bin")
        if not os.path.isfile(path):
            print("失败（无文件）")
            print("    " + " | ".join(l.strip() for l in out.splitlines()
                                      if "TARGET SAID" in l and ("ERROR" in l or "Failed" in l))[:300])
            bad.append(name)
            continue
        have = os.path.getsize(path)
        flag = "OK" if have == want else "尺寸不符(期望%d)" % want
        print("%d 字节 %s" % (have, flag))
        (ok if have == want else bad).append(name)

    print("\n[=] 成功 %d 个: %s" % (len(ok), ", ".join(ok)))
    if bad:
        print("[!] 失败 %d 个: %s" % (len(bad), ", ".join(bad)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
