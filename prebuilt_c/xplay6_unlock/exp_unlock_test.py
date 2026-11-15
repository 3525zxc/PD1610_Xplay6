# -*- coding: utf-8 -*-
"""决定性实验：devinfo 置 1 + boot cmdline 打标记，验证 aboot 是否跳过 boot 校验。

步骤:
  1. 写 devinfo (0x0D=1, 0x0E=1)          —— 声明"已解锁"
  2. 读 boot 第一扇区，改 cmdline 标记     —— 使签名失效
  3. 写回 boot 第一扇区                   —— 只写 4KB
  4. 重启，检查 /proc/cmdline 是否含标记

参数:
  --plan     只生成镜像并打印差异，不写设备
  --apply    真正写入
  --restore  恢复 devinfo 与 boot 第一扇区
"""
import argparse
import os
import subprocess
import sys

FH = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5\fh_loader.exe"
WORK = r"C:\qfilx\exp"
DUMP = r"C:\qfilx\dumps"
SS = 4096

DEVINFO_LUN, DEVINFO_START = 4, 882954
BOOT_LUN, BOOT_START = 4, 47370

MARK_OLD = b"PD1610_D_7.13.15"
MARK_NEW = b"CFWTEST_9008"


def fh(xml_path, cwd):
    r = subprocess.run([FH, "--port=\\\\.\\COM5", "--memoryname=ufs",
                        "--sendxml=" + xml_path, "--noprompt", "--zlpawarehost=1"],
                       cwd=cwd, capture_output=True, text=True,
                       errors="ignore", timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    ok = "All Finished Successfully" in out or "Finished programming" in out
    return ok, out


def write_part(tag, lun, start, count, filename, cwd):
    xml = ('<?xml version="1.0" ?>\n<data>\n'
           '<program SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="%s" '
           'num_partition_sectors="%d" physical_partition_number="%d" '
           'start_sector="%d"/>\n</data>\n'
           % (SS, filename, tag, count, lun, start))
    p = os.path.join(WORK, "w_%s.xml" % tag)
    open(p, "w", encoding="utf-8", newline="\n").write(xml)
    return fh(p, cwd)


def read_part(tag, lun, start, count, filename, cwd):
    xml = ('<?xml version="1.0" ?>\n<data>\n'
           '<read SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="%s" '
           'num_partition_sectors="%d" physical_partition_number="%d" '
           'start_sector="%d"/>\n</data>\n'
           % (SS, filename, tag, count, lun, start))
    p = os.path.join(WORK, "r_%s.xml" % tag)
    open(p, "w", encoding="utf-8", newline="\n").write(xml)
    return fh(p, cwd)


def build_images():
    os.makedirs(WORK, exist_ok=True)

    dev_orig = open(os.path.join(DUMP, "devinfo.bin"), "rb").read()
    assert dev_orig[:13] == b"ANDROID-BOOT!"
    dev = bytearray(dev_orig)
    dev[0x0D] = 0x01
    dev[0x0E] = 0x01
    open(os.path.join(WORK, "devinfo_unlock.bin"), "wb").write(bytes(dev))
    print("[1] devinfo_unlock.bin 已生成: 0x0D=%02X 0x0E=%02X (原 %02X/%02X)"
          % (dev[0x0D], dev[0x0E], dev_orig[0x0D], dev_orig[0x0E]))

    head = open(r"C:\qfilx\probe\boot_head.bin", "rb").read()
    page0 = bytearray(head[:SS])
    raw_cmd = bytes(page0[64:576])
    cmd = raw_cmd.split(b"\x00")[0]
    print("    boot cmdline 长度 %d" % len(cmd))
    if MARK_OLD not in cmd:
        print("[!] cmdline 里找不到 %r，中止" % MARK_OLD)
        return None
    new_cmd = cmd.replace(MARK_OLD, MARK_NEW)
    if len(new_cmd) > 512:
        print("[!] 新 cmdline 超长，中止")
        return None
    page0[64:576] = new_cmd.ljust(512, b"\x00")
    open(os.path.join(WORK, "boot_page0_patched.bin"), "wb").write(bytes(page0))
    open(os.path.join(WORK, "boot_page0_orig.bin"), "wb").write(head[:SS])
    print("[2] boot_page0_patched.bin 已生成: %r -> %r" % (MARK_OLD, MARK_NEW))
    print("    原始扇区已另存 boot_page0_orig.bin (4KB)，回滚用")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.restore:
        os.makedirs(WORK, exist_ok=True)
        ok1, _ = write_part("devinfo", DEVINFO_LUN, DEVINFO_START, 1,
                            "devinfo.bin", DUMP)
        print("[devinfo 还原] %s" % ("OK" if ok1 else "失败"))
        ok2, _ = write_part("boot", BOOT_LUN, BOOT_START, 1,
                            "boot_page0_orig.bin", WORK)
        print("[boot 扇区还原] %s" % ("OK" if ok2 else "失败"))
        return 0 if (ok1 and ok2) else 1

    if not build_images():
        return 1
    if a.plan or not a.apply:
        print("\n[plan] 未写入设备。加 --apply 才执行。")
        print("  将写入: devinfo (LUN%d %d, 1 扇区)" % (DEVINFO_LUN, DEVINFO_START))
        print("  将写入: boot    (LUN%d %d, 1 扇区)" % (BOOT_LUN, BOOT_START))
        return 0

    ok1, out1 = write_part("devinfo", DEVINFO_LUN, DEVINFO_START, 1,
                           "devinfo_unlock.bin", WORK)
    print("[3] 写 devinfo: %s" % ("OK" if ok1 else "失败"))
    if not ok1:
        print(out1[-400:])
        return 1

    ok2, out2 = write_part("boot", BOOT_LUN, BOOT_START, 1,
                           "boot_page0_patched.bin", WORK)
    print("[4] 写 boot 扇区: %s" % ("OK" if ok2 else "失败"))
    if not ok2:
        print(out2[-400:])
        return 1

    print("\n[!] 两步都已写入。重启后若开不了机，说明校验没被跳过。")
    print("    恢复命令: py exp_unlock_test.py --restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
