# -*- coding: utf-8 -*-
"""Xplay6 devinfo 分组实验的模式切换助手。

用法:
  py cycle_helper.py --to-edl          # fastboot -> Android -> adb reboot edl -> 上传 firehose
  py cycle_helper.py --write UL        # 调 devinfo_scan.py --write UL
  py cycle_helper.py --to-fastboot     # firehose reset -> Android -> adb reboot bootloader -> --check
  py cycle_helper.py --status          # 只读查看当前模式/端口
  py cycle_helper.py --restore         # 写回原始 devinfo（需 firehose 就绪）
"""
import argparse
import os
import subprocess
import sys
import time

QFIL = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5"
SAHARA = os.path.join(QFIL, "QSaharaServer.exe")
PROG = r"C:\qfilx\prog_ufs_firehose_8996_ddr.elf"
PORT = r"\\.\COM5"
FASTBOOT = r"C:\qfilx\fastboot\fastboot.exe"
ADB = r"C:\Users\Tse\Downloads\MiFlash20220507\Source\ThirdParty\Google\Android\adb.exe"
SCAN = r"C:\Users\Tse\WorkBuddy\寒霜刷机\xplay6_unlock\devinfo_scan.py"


def run(cmd, timeout=60, label=None):
    tag = label or " ".join(str(x) for x in cmd[:2])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           errors="ignore", timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        print("  [%s] rc=%d %s" % (tag, r.returncode, out[-400:]))
        return r.returncode, out
    except subprocess.TimeoutExpired:
        print("  [%s] 超时 %ds" % (tag, timeout))
        return -1, ""


def ports():
    import serial.tools.list_ports as l
    return [(p.device, p.description) for p in l.comports()]


def is_edl():
    return any("9008" in d or "QDLoader" in d or dev == "COM5"
               for dev, d in ports())


def wait_edl(seconds=30):
    for i in range(seconds):
        if is_edl():
            print("  9008 已出现 (%ds): %s" % (i, ports()))
            return True
        time.sleep(1)
    print("  9008 未出现: %s" % ports())
    return False


def wait_adb(seconds=90):
    for i in range(seconds):
        rc, out = run([ADB, "get-state"], timeout=8, label="adb")
        if rc == 0 and out.strip() == "device":
            print("  adb 在线 (%ds)" % i)
            return True
        time.sleep(1)
    print("  adb 未上线")
    return False


def wait_fastboot(seconds=60):
    for i in range(seconds):
        rc, out = run([FASTBOOT, "devices"], timeout=8, label="fastboot")
        if rc == 0 and "fastboot" in out:
            print("  fastboot 在线 (%ds)" % i)
            return True
        time.sleep(1)
    print("  fastboot 未上线")
    return False


def upload():
    print("上传 firehose programmer ...")
    rc, out = run([SAHARA, "-p", PORT, "-s", "13:" + PROG], timeout=120,
                  label="QSaharaServer")
    ok = ("Sahara" in out or "Image Loaded" in out or "470032" in out
          or "Done" in out or rc == 0)
    print("  programmer %s" % ("上传成功" if ok else "结果需检查"))
    return ok


def scan(arg):
    parts = arg.split()
    rc, _ = run(["py", SCAN] + parts, timeout=300, label="devinfo_scan " + arg)
    return rc


def cmd_to_edl():
    print("1) fastboot reboot -> Android")
    run([FASTBOOT, "reboot"], timeout=30)
    print("2) 等 adb 上线")
    if not wait_adb():
        print("!! adb 未上线。若屏幕停在「数据损坏/需要清除数据」，先按提示清数据再继续。")
        return 1
    print("3) adb shell reboot edl")
    run([ADB, "shell", "reboot", "edl"], timeout=25)
    print("4) 等 9008")
    if not wait_edl(30):
        return 1
    print("5) 立即上传 programmer（不做任何端口探测）")
    return 0 if upload() else 1


def cmd_to_edl_oem():
    """解锁后 OEM 命令可能放行：先试 fastboot oem reboot-edl，失败再走 adb 路线。"""
    print("0) 试 fastboot oem reboot-edl")
    rc, out = run([FASTBOOT, "oem", "reboot-edl"], timeout=20)
    if rc == 0 and "FAILED" not in out and wait_edl(20):
        print("  OEM 通道成功，立即上传 programmer")
        return 0 if upload() else 1
    print("  OEM 通道不可用/未进 9008，回退 fastboot reboot -> adb reboot edl")
    return cmd_to_edl()


def cmd_to_fastboot():
    print("1) firehose power reset")
    rc = scan("--reset")
    if rc != 0:
        print("!! reset 未确认，停止")
        return 1
    print("2) 等 Android/adb 上线")
    if not wait_adb(120):
        print("!! adb 未上线，需要人工按键进 fastboot")
        return 1
    print("3) adb reboot bootloader")
    run([ADB, "reboot", "bootloader"], timeout=30)
    print("4) 等 fastboot")
    if not wait_fastboot(60):
        return 1
    print("5) 读 oem device-info")
    return scan("--check")


def quiet(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           errors="ignore", timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


def mode_snapshot():
    m = []
    if "fastboot" in quiet([FASTBOOT, "devices"]):
        m.append("FASTBOOT")
    # 注意 "error: no devices/emulators found" 里也含 device，必须精确匹配状态行
    adb_state = quiet([ADB, "get-state"]).strip().splitlines()
    if adb_state and adb_state[-1].strip() == "device":
        m.append("ADB")
    if is_edl():
        m.append("9008")
    return ",".join(m) or "无"


def cmd_reset_probe(seconds=75):
    print("1) firehose power reset")
    scan("--reset")
    print("2) 轮询设备落点（每 3s）")
    last = None
    for i in range(0, seconds, 3):
        s = mode_snapshot()
        if s != last:
            print("  %3ds -> %s" % (i, s))
            last = s
        time.sleep(3)
    print("最终落点: %s" % last)
    return 0


def cmd_status():
    print("PORTS:", ports())
    run([FASTBOOT, "devices"], timeout=8, label="fastboot")
    run([ADB, "devices"], timeout=8, label="adb")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to-edl", action="store_true")
    ap.add_argument("--to-edl-oem", action="store_true")
    ap.add_argument("--to-fastboot", action="store_true")
    ap.add_argument("--write", metavar="GROUP")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset-probe", action="store_true")
    a = ap.parse_args()
    if a.reset_probe:
        return cmd_reset_probe()
    if a.status:
        return cmd_status()
    if a.to_edl_oem:
        return cmd_to_edl_oem()
    if a.to_edl:
        return cmd_to_edl()
    if a.write:
        return scan("--write " + a.write)
    if a.restore:
        return scan("--restore")
    if a.to_fastboot:
        return cmd_to_fastboot()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
