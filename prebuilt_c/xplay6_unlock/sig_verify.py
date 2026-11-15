# -*- coding: utf-8 -*-
"""步骤 3（签名校验）+ 步骤 2（ULC）的 9008 侧操作。

步骤 3 复刻上次失败实验：只写 boot 首扇区（cmdline 打标记使签名失效），
devinfo 保持 UL 不变。上次锁着时这样写会卡 logo 无限重启；
现在 unlocked=true 若能进到「要启动Android，请输入您的密码」，即证明校验被跳过。

用法（设备须已在 9008 且已上传 firehose programmer）:
  py sig_verify.py --patch       写改动 boot 扇区 + 回读校验
  py sig_verify.py --restore     写回原始 boot 扇区 + 回读校验
  py sig_verify.py --ulc         写 devinfo ULC（0x10+0x18）
  py sig_verify.py --reset       firehose power reset
  py sig_verify.py --probe 90    轮询设备落点
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FH = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5\fh_loader.exe"
EXP = r"C:\qfilx\exp"
SS = 4096
BOOT_LUN, BOOT_START = 4, 47370
PORT = r"\\.\COM5"


def fh(xml, cwd=EXP):
    cmd = [FH, "--port=" + PORT, "--memoryname=ufs",
           "--sendxml=" + xml, "--noprompt", "--zlpawarehost=1"]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       errors="ignore", timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    ok = "All Finished Successfully" in out or "Finished programming" in out
    print("  %s : %s" % (os.path.basename(xml), "OK" if ok else "失败/需检查"))
    if not ok:
        print(out[-500:])
    return ok, out


def xml_for(tag, filename, read=False):
    p = os.path.join(EXP, "%s_%s.xml" % ("r" if read else "w", tag))
    op = "read" if read else "program"
    open(p, "w", encoding="utf-8", newline="\n").write(
        '<?xml version="1.0" ?>\n<data>\n'
        '<%s SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="boot" '
        'num_partition_sectors="1" physical_partition_number="%d" '
        'start_sector="%d"/>\n</data>\n' % (op, SS, filename, BOOT_LUN, BOOT_START))
    return p


def write_sector(filename, tag):
    ok, _ = fh(xml_for(tag, filename))
    if not ok:
        return 1
    chk = "chk_" + tag + ".bin"
    ok, _ = fh(xml_for("chk_" + tag, chk, read=True))
    if not ok:
        return 1
    want = open(os.path.join(EXP, filename), "rb").read()
    got = open(os.path.join(EXP, chk), "rb").read()
    same = got == want
    print("  回读 %s: %s" % ("一致" if same else "不一致", chk))
    return 0 if same else 1


def cmd_patch():
    print("写 boot 首扇区（改动版）：仅 LUN4 / %d 一个 4KB 扇区" % BOOT_START)
    print("  devinfo 保持 UL 不动，boot 其余部分、签名区、基带全不动")
    return write_sector("boot_page0_patched.bin", "boot_patch")


def cmd_restore():
    print("写回 boot 原始首扇区")
    return write_sector("boot_page0_orig.bin", "boot_restore")


def cmd_ulc():
    r = subprocess.run(["py", os.path.join(HERE, "devinfo_scan.py"),
                        "--write", "ULC"], timeout=300)
    return r.returncode


def cmd_reset():
    r = subprocess.run(["py", os.path.join(HERE, "devinfo_scan.py"), "--reset"],
                       timeout=300)
    return r.returncode


def cmd_probe(seconds):
    sys.path.insert(0, HERE)
    import cycle_helper as c
    last = None
    for i in range(0, seconds, 3):
        s = c.mode_snapshot()
        if s != last:
            print("  %3ds -> %s" % (i, s))
            last = s
        time.sleep(3)
    print("最终落点: %s  (无 = 已进 Android，停在加密密码界面)" % last)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--ulc", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--probe", type=int, metavar="SECONDS")
    a = ap.parse_args()
    if a.patch:
        sys.exit(cmd_patch())
    if a.restore:
        sys.exit(cmd_restore())
    if a.ulc:
        sys.exit(cmd_ulc())
    if a.reset:
        sys.exit(cmd_reset())
    if a.probe:
        sys.exit(cmd_probe(a.probe))
    ap.print_help()
