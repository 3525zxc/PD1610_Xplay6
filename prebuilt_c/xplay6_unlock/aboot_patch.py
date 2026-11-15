"""aboot 单扇区实验：验证 SBL 是否校验 aboot 分区签名。

用法：
  py aboot_patch.py --prepare                 只生成扇区镜像（不碰设备）
  py aboot_patch.py --test                   全自动：进 9008 -> 写测试扇区 -> 回读 -> reset -> 读 oem device-info
  py aboot_patch.py --restore                全自动：进 9008 -> 写回原扇区 -> 回读 -> reset
  py aboot_patch.py --write NAME             仅写（firehose 已就绪时用）
  py aboot_patch.py --check                  只读：进 fastboot 读 oem device-info

测试原理：把 aboot 里 "Device tampered: %s" 的首字母 t 改成 T。
不影响任何执行代码，但落在 ELF 代码段内 —— 若 SBL 校验 aboot 的
MBN hash / RSA 签名，设备会拒绝启动；若启动成功且 oem device-info
显示 "Device Tampered:"，即证明 aboot 可被自由 patch。
回滚只需写回同一 4KB 扇区，原片 C:\\qfilx\\probe\\aboot.bin 完好。
"""
import argparse
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import cycle_helper as cyc  # noqa: E402

QFIL = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5"
FH = os.path.join(QFIL, "fh_loader.exe")
FB = r"C:\qfilx\fastboot\fastboot.exe"
SRC = pathlib.Path(r"C:\qfilx\probe\aboot.bin")
WORK = pathlib.Path(r"C:\qfilx\aboot")
WORK.mkdir(parents=True, exist_ok=True)

LUN = 4
ABOOT_START = 39178
SS = 4096
STR_OFF = 0x8875D                      # "Device tampered: %s" 在 aboot.bin 中的文件偏移
REL_SECTOR = STR_OFF // SS             # 136
ABS_SECTOR = ABOOT_START + REL_SECTOR  # 39314
INNER = STR_OFF % SS                   # 0x75D
PATCH_OFF = INNER + 7                  # 'Device ' 之后的首字母 t
EXPECT = b"Device tampered: %s"

FILES = {
    "orig": WORK / "aboot_s136_orig.bin",
    "test": WORK / "aboot_s136_test.bin",
}


def log(*a):
    print(*a, flush=True)


def run(cmd, timeout=300, label="", cwd=None):
    log("  $", " ".join(str(x) for x in cmd[:4]), "...", label)
    r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore",
                       timeout=timeout, cwd=cwd)
    out = (r.stdout or "") + (r.stderr or "")
    if out.strip():
        log("   ", out.strip()[-600:].replace("\n", " | "))
    return r.returncode, out


def prepare():
    d = SRC.read_bytes()
    s = d[REL_SECTOR * SS:(REL_SECTOR + 1) * SS]
    assert s[INNER:INNER + len(EXPECT)] == EXPECT, "字符串位置不符，拒绝生成"
    assert s[PATCH_OFF] == ord("t"), "目标字节不是 t，拒绝生成"
    FILES["orig"].write_bytes(s)
    t = bytearray(s)
    t[PATCH_OFF] = ord("T")
    FILES["test"].write_bytes(t)
    diff = [i for i in range(SS) if s[i] != t[i]]
    log("原扇区", FILES["orig"], "测试扇区", FILES["test"])
    log("  扇区坐标 LUN%d / %d (aboot 内相对 %d)，内偏移 %s" %
        (LUN, ABS_SECTOR, REL_SECTOR, hex(PATCH_OFF)))
    log("  差异字节数", len(diff), "位置", [hex(x) for x in diff])
    log("  原串", s[INNER:INNER + 24])
    log("  新串", bytes(t[INNER:INNER + 24]))
    assert diff == [PATCH_OFF], "护栏失败：差异不止 1 字节"
    return True


def xml_write(path, filename, tag):
    path.write_text(
        '<?xml version="1.0" ?>\n<data>\n'
        '<program SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="aboot" '
        'num_partition_sectors="1" physical_partition_number="%d" start_sector="%d"/>\n'
        '</data>\n' % (SS, os.path.basename(filename), LUN, ABS_SECTOR), encoding="ascii")
    return str(path)


def xml_read(path, filename, tag):
    path.write_text(
        '<?xml version="1.0" ?>\n<data>\n'
        '<read SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="aboot" '
        'num_partition_sectors="1" physical_partition_number="%d" start_sector="%d"/>\n'
        '</data>\n' % (SS, os.path.basename(filename), LUN, ABS_SECTOR), encoding="ascii")
    return str(path)


def fh(xml, tag, timeout=300):
    log("  fh_loader", tag)
    rc, out = run([FH, "--port=" + cyc.PORT, "--memoryname=ufs",
                   "--sendxml=" + xml, "--noprompt", "--zlpawarehost=1"],
                  timeout=timeout, label=tag, cwd=str(WORK))
    ok = rc == 0 and "FAIL" not in out.upper()
    log("  ->", "OK" if ok else "FAIL", tag)
    return ok


def write_sector(name):
    src = FILES[name]
    assert src.exists(), "先跑 --prepare"
    xml = xml_write(WORK / ("w_%s.xml" % name), str(src), name)
    if not fh(xml, "write " + name):
        return False
    chk = WORK / ("chk_%s.bin" % name)
    if chk.exists():
        chk.unlink()
    xr = xml_read(WORK / ("r_%s.xml" % name), str(chk), name)
    if not fh(xr, "readback " + name):
        return False
    if not chk.exists() or chk.read_bytes() != src.read_bytes():
        log("  !! 回读不一致")
        return False
    log("  回读逐字节一致")
    return True


def reset():
    p = WORK / "reset.xml"
    p.write_text('<?xml version="1.0" ?>\n<data>\n<power value="reset"/>\n</data>\n',
                 encoding="ascii")
    return fh(str(p), "reset", timeout=180)


def to_edl():
    log("  自动进 9008")
    if "ADB" not in cyc.mode_snapshot():
        log("  adb 不在线，尝试 fastboot reboot 后等待 adb")
        run([FB, "reboot"], 30, "fastboot reboot")
        for _ in range(90):
            if "ADB" in cyc.mode_snapshot():
                break
            time.sleep(1)
    cyc.run([cyc.ADB, "shell", "reboot", "edl"], 25, "adb reboot edl")
    ok = cyc.wait_edl(40) and cyc.upload()
    log("  READY", ok)
    return ok


def check():
    if "FASTBOOT" not in cyc.mode_snapshot():
        if "ADB" in cyc.mode_snapshot():
            run([cyc.ADB, "reboot", "bootloader"], 30, "adb reboot bootloader")
            for _ in range(45):
                if "FASTBOOT" in cyc.mode_snapshot():
                    break
                time.sleep(1)
    rc, out = run([FB, "oem", "device-info"], 25, "oem device-info")
    hit = "Device Tampered:" in out
    log("  === 标记检测:", "命中 -> aboot 已被替换且在运行" if hit else "未命中")
    log(out.strip()[:600])
    return hit


def cmd_rescue(timeout=1200):
    """后台监听 9008，一旦出现立即上传 programmer 并写回原始扇区。
    动态识别 COM 号，不写死 COM5（拆机 test point 后可能枚举成别的端口）。
    """
    import serial.tools.list_ports as lp
    log("  等待 9008（最多 %d 秒）；端口一出现立即自动回滚" % timeout)
    dev = None
    desc = ""
    for i in range(timeout):
        for p in lp.comports():
            d = p.description or ""
            if "9008" in d or "QDLoader" in d or "QUSB" in d or "QC DIAG" in d:
                dev, desc = p.device, d
                break
        if dev:
            log("  9008 已出现 (%ds): %s / %s" % (i, dev, desc))
            break
        time.sleep(1)
    if not dev:
        log("  !! 超时：未看到 9008 端口，最后端口表", [(p.device, p.description) for p in lp.comports()])
        return 1
    cyc.PORT = "\\\\.\\" + dev
    log("  覆盖端口为", cyc.PORT, "，立刻上传 programmer")
    if not cyc.upload():
        log("  !! programmer 上传失败")
        return 1
    prepare()
    if not write_sector("orig"):
        log("  !! 写回原扇区失败")
        return 2
    reset()
    log("  原扇区已写回并回读一致，等待系统启动")
    for i in range(0, 91, 3):
        m = cyc.mode_snapshot()
        if m != "无":
            log("   %3ds -> %s" % (i, m))
        if "ADB" in m or "FASTBOOT" in m:
            break
        time.sleep(3)
    log("  RESCUE DONE")
    return 0


def cmd_auto(name, do_check=False):
    prepare()
    if not to_edl():
        log("!! 进 9008 失败，未写任何分区")
        return 1
    if not write_sector(name):
        log("!! 写入/回读失败，请用 --restore 回滚")
        return 2
    reset()
    log("  轮询启动落点")
    last = None
    for i in range(0, 61, 3):
        m = cyc.mode_snapshot()
        if m != last:
            log("   %3ds -> %s" % (i, m))
            last = m
        time.sleep(3)
    log("  最终模式", last)
    if do_check and name == "test":
        check()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--write", metavar="NAME", choices=["orig", "test"])
    ap.add_argument("--direct", metavar="NAME", choices=["orig", "test"],
                    help="firehose 已就绪时：写扇区 + 回读 + reset，不尝试进 9008")
    ap.add_argument("--reset-only", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rescue", action="store_true", help="后台监听 9008 并自动写回原扇区")
    a = ap.parse_args()
    if a.prepare:
        return 0 if prepare() else 1
    if a.test:
        return cmd_auto("test", do_check=True)
    if a.restore:
        return cmd_auto("orig")
    if a.write:
        prepare()
        return 0 if write_sector(a.write) else 2
    if a.direct:
        prepare()
        if not write_sector(a.direct):
            return 2
        reset()
        return 0
    if a.reset_only:
        return 0 if reset() else 2
    if a.check:
        return 0 if check() else 3
    if a.rescue:
        return cmd_rescue()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
