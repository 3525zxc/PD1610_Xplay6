# -*- coding: utf-8 -*-
"""分析 boot / recovery / sec 的签名结构，判断能否刷入未签名镜像。纯读取。"""
import os
import struct
import subprocess
import sys

FH = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5\fh_loader.exe"
PORT = r"\\.\COM5"
SS = 4096
WORK = r"C:\qfilx\probe"

# (名字, LUN, start, 总扇区数)
PARTS = {
    "boot":     (4, 47370, 24576),
    "recovery": (4, 858378, 24576),
    "sec":      (4, 2054, 4),
    "aboot":    (4, 39178, 4096),
}


def read_range(name, lun, start, count, tag):
    xml = ('<?xml version="1.0" ?>\n<data>\n'
           '<read SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="x" '
           'num_partition_sectors="%d" physical_partition_number="%d" '
           'start_sector="%d"/>\n</data>\n' % (SS, tag, count, lun, start))
    p = os.path.join(WORK, tag + ".xml")
    open(p, "w", encoding="utf-8", newline="\n").write(xml)
    r = subprocess.run([FH, "--port=" + PORT, "--memoryname=ufs",
                        "--sendxml=" + p, "--noprompt", "--zlpawarehost=1"],
                       cwd=WORK, capture_output=True, text=True,
                       errors="ignore", timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    path = os.path.join(WORK, tag)
    if not os.path.isfile(path):
        bad = [l for l in out.splitlines() if "ERROR" in l or "Failed" in l]
        raise RuntimeError("%s 读取失败: %s" % (tag, " | ".join(bad[:2])[:200]))
    return open(path, "rb").read()


def parse_boot_hdr(d, label):
    if d[:8] != b"ANDROID!":
        print("  [!] 不是标准 ANDROID! 头，前 8 字节: %r" % d[:8])
        return
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
     second_size, second_addr, tags_addr, page_size,
     hdr_ver, os_ver) = struct.unpack_from("<10I", d, 8)
    name = d[48:64].split(b"\x00")[0].decode("ascii", "ignore")
    cmdline = d[64:576].split(b"\x00")[0].decode("ascii", "ignore")
    extra = d[608:1632].split(b"\x00")[0].decode("ascii", "ignore")
    print("  header_version : %d" % hdr_ver)
    print("  page_size      : %d" % page_size)
    print("  kernel_size    : %d" % kernel_size)
    print("  ramdisk_size   : %d" % ramdisk_size)
    print("  name           : %s" % name)
    print("  cmdline        : %s" % (cmdline or "(空)"))
    if extra:
        print("  extra_cmdline  : %s" % extra)
    full = (cmdline + " " + extra).lower()
    for kw in ("verity", "dm-verity", "verifiedboot", "selinux"):
        if kw in full:
            print("  >> cmdline 里出现 '%s'" % kw)


def tail_info(d, label, total):
    print("  最后 64 字节: %s" % " ".join("%02X" % b for b in d[-64:]))
    for magic, desc in ((b"AVBf", "AVB 签名尾（AVB 2.0）"),
                        (b"SEANDROIDENFORCE", "Android 强制验证标记"),
                        (b"QC_BOOT", "Qualcomm boot 标记")):
        idx = d.rfind(magic)
        if idx >= 0:
            print("  + 发现 %s @ 0x%X" % (desc, idx))
    if b"AVBf" not in d:
        print("  - 没有 AVBf 尾巴")


def main():
    os.makedirs(WORK, exist_ok=True)
    print("=" * 66)
    print("第二步：读 boot / recovery 头尾，判断签名机制")
    print("=" * 66)

    for name in ("boot", "recovery"):
        lun, start, cnt = PARTS[name]
        print("\n[%s]  LUN%d start=%d 共 %d 扇区 (%.0f MB)" %
              (name, lun, start, cnt, cnt * SS / 1048576.0))
        head = read_range(name, lun, start, 2, name + "_head.bin")
        print("  头 8KB 已读")
        parse_boot_hdr(head, name)

        tail_start = start + cnt - 2
        tail = read_range(name, lun, tail_start, 2, name + "_tail.bin")
        print("  尾 8KB 已读")
        tail_info(tail, name, cnt)

    lun, start, cnt = PARTS["sec"]
    print("\n[sec]  LUN%d start=%d (%d 扇区)" % (lun, start, cnt))
    sec = read_range("sec", lun, start, cnt, "sec.bin")
    nz = sum(1 for b in sec if b)
    print("  大小 %d, 非零字节 %d" % (len(sec), nz))
    print("  前 64 字节: %s" % " ".join("%02X" % b for b in sec[:64]))

    print("\n" + "=" * 66)
    print("完成。判断标准：")
    print("  boot 尾部有 AVBf  -> 改 boot 会被拒，Magisk 走不通")
    print("  boot 尾部无 AVBf  -> 可能只靠 dm-verity，关掉即可")
    print("  header_version=0  -> 老式 boot，无 dtbo，兼容第三方内核")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
