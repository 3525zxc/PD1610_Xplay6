# -*- coding: utf-8 -*-
"""无损实验：fastboot boot 内存启动 stock / patched 镜像，区分校验路径。

判据：
  A(stock) 能启动、B(patched) 被 fastboot 拒绝      -> aboot 统一校验（内存路径也验签/完整性）
  A、B 都能启动并进系统                              -> 只有分区启动路径校验，fastboot boot 路径不校验
  B 能启动且 kernel cmdline 含 CFWTEST_9008          -> 决定性：签名失效的 boot 被实际加载

不写任何分区。用法:
  py boot_ram_test.py --baseline     读当前系统属性与 /proc/cmdline 可读性
  py boot_ram_test.py --case A       fastboot boot boot_stock.img
  py boot_ram_test.py --case B       fastboot boot boot_patched.img
"""
import argparse
import pathlib
import subprocess
import sys
import time

FB = r"C:\qfilx\fastboot\fastboot.exe"
ADB = r"C:\Users\Tse\Downloads\MiFlash20220507\Source\ThirdParty\Google\Android\adb.exe"
EXP = pathlib.Path(r"C:\qfilx\exp")
IMGS = {"A": EXP / "boot_stock.img", "B": EXP / "boot_patched.img"}
LOG = EXP / "ram_test.log"


def q(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           errors="ignore", timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT %ds]" % timeout
    except Exception as e:
        return "[ERR %s]" % e


def log(line):
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8", errors="ignore") as f:
        f.write(line + "\n")


def fb_online():
    return "fastboot" in q([FB, "devices"], 6)


def adb_online():
    out = q([ADB, "get-state"], 6).strip().splitlines()
    return bool(out) and out[-1].strip() == "device"


def edl_online():
    import serial.tools.list_ports as lp
    return any("9008" in p.description or "QDLoader" in p.description
               or p.device == "COM5" for p in lp.comports())


def mode():
    m = []
    if fb_online():
        m.append("FASTBOOT")
    if adb_online():
        m.append("ADB")
    if edl_online():
        m.append("9008")
    return ",".join(m) or "无"


def wait(pred, seconds):
    for i in range(seconds):
        if pred():
            return i
        time.sleep(1)
    return None


def to_fastboot():
    if fb_online():
        log("  已在 fastboot")
        return True
    if adb_online():
        log("  adb reboot bootloader")
        q([ADB, "reboot", "bootloader"], 25)
    else:
        log("  !! 当前既不在 adb 也不在 fastboot：%s，需人工进 fastboot" % mode())
        return False
    n = wait(fb_online, 60)
    log("  fastboot 在线: %s" % ("%ds" % n if n is not None else "超时"))
    return n is not None


def read_result(tag):
    """adb 上线后尽可能读出 kernel cmdline 与启动状态。"""
    out = []
    n = wait(adb_online, 120)
    if n is None:
        out.append("adb 未在 120s 上线；最终落点=%s" % mode())
        return out
    out.append("adb 上线 (%ds)" % n)
    cmds = [
        ("verifiedbootstate", [ADB, "shell", "getprop", "ro.boot.verifiedbootstate"]),
        ("veritymode", [ADB, "shell", "getprop", "ro.boot.veritymode"]),
        ("flash.locked", [ADB, "shell", "getprop", "ro.boot.flash.locked"]),
        ("build", [ADB, "shell", "getprop", "ro.build.version.release"]),
        ("cat /proc/cmdline", [ADB, "shell", "cat", "/proc/cmdline"]),
        ("toybox cat", [ADB, "shell", "toybox", "cat", "/proc/cmdline"]),
        ("sh -c cat", [ADB, "shell", "sh", "-c", "cat /proc/cmdline"]),
        ("ls -l", [ADB, "shell", "ls", "-l", "/proc/cmdline"]),
        ("dmesg cmdline", [ADB, "shell", "dmesg | grep -i 'Kernel command line' | head -3"]),
        ("getprop 标记", [ADB, "shell", "getprop | grep -i 'CFWTEST\\|PD1610_D_7\\|7.13.15'"]),
    ]
    for name, cmd in cmds:
        r = q(cmd, 20).replace("\n", " ")
        out.append("  %-20s : %s" % (name, r[:700]))
    return out


def baseline():
    log("=== BASELINE 当前系统 ===")
    log("mode=%s" % mode())
    for line in read_result("baseline"):
        log(line)


def run_case(name):
    img = IMGS[name]
    label = {"A": "A_STOCK (签名有效)", "B": "B_PATCHED (cmdline 改动, 签名失效)"}[name]
    log("\n=== %s : %s (%d B) ===" % (label, img, img.stat().st_size))
    if not to_fastboot():
        return 1
    log("  >>> fastboot boot %s" % img)
    r = q([FB, "boot", str(img)], 180)
    for line in r.splitlines():
        log("  | " + line)
    log("  启动命令结束，落点=%s" % mode())
    for line in read_result(name):
        log(line)
    log("  最终落点=%s" % mode())
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--case", choices=["A", "B"])
    a = ap.parse_args()
    if a.baseline:
        baseline()
    elif a.case:
        sys.exit(run_case(a.case))
    else:
        ap.print_help()
