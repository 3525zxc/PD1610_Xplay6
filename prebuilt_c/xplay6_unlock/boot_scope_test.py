# -*- coding: utf-8 -*-
"""boot 分区校验范围对照实验（单扇区、可回滚、不动基带）。

D 组：改纯填充扇区 1 字节 —— 镜像内容与 DER 签名都不变
C 组：改 DER 签名区 1 字符 —— kernel/ramdisk/cmdline 全不变，只让签名失效

判据：
  D 能进系统 + C 卡 logo  -> 签名校验确实作用于 boot，cmdline 实验的卡 logo 是验签失败
  D 卡 logo               -> aboot 校验整块分区/另有完整性机制
  C 也能进系统            -> 签名校验可绕过（重大发现，可刷未签名 boot）

用法（9008 且已上传 programmer 时可写设备）:
  py boot_scope_test.py --prepare
  py boot_scope_test.py --write pad_patched       # 写 D 改动扇区 + 回读
  py boot_scope_test.py --write sig_patched       # 写 C 改动扇区 + 回读
  py boot_scope_test.py --restore pad             # 写回 pad_orig
  py boot_scope_test.py --restore sig             # 写回 sig_orig
  py boot_scope_test.py --reset
  py boot_scope_test.py --wait-system 120
"""
import argparse
import os
import pathlib
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FH = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5\fh_loader.exe"
ADB = r"C:\Users\Tse\Downloads\MiFlash20220507\Source\ThirdParty\Google\Android\adb.exe"
EXP = pathlib.Path(r"C:\qfilx\exp")
FULL = EXP / "boot_full.bin"
LOG = EXP / "scope_test.log"
SS = 4096
BOOT_LUN, BOOT_START = 4, 47370
PORT = r"\\.\COM5"

# D: 纯填充区（12968 扇区之后全零）
PAD_SECTOR = 20000
PAD_INNER = 0
# C: DER 证书链 subject "SHENZHEN" 的首字母 @0xE30056
SIG_SECTOR = 0xE30000 // SS          # 3632
SIG_INNER = 0x56
# E: kernel 数据之后的页对齐填充（0x9C8DD8..0x9C9000，552B 全零）
#    改这里不动任何被执行代码、不动 header/cmdline，只改变镜像内容 hash
KRN_OFF = 0x9C8EEC
KRN_SECTOR = KRN_OFF // SS           # 2504
KRN_INNER = KRN_OFF % SS             # 0xEEC

FILES = {
    "pad_orig": (PAD_SECTOR, None),
    "pad_patched": (PAD_SECTOR, (PAD_INNER, 0xA5)),
    "sig_orig": (SIG_SECTOR, None),
    "sig_patched": (SIG_SECTOR, (SIG_INNER, 0x58)),  # 'S'(0x53) -> 'X'(0x58)
    "krn_orig": (KRN_SECTOR, None),
    "krn_patched": (KRN_SECTOR, (KRN_INNER, 0xA5)),
}


def log(s):
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8", errors="ignore") as f:
        f.write(s + "\n")


def prepare():
    d = FULL.read_bytes()
    assert len(d) == 24576 * SS
    log("boot_full.bin %d B，扇区 %d" % (len(d), len(d) // SS))
    for name, (sector, patch) in FILES.items():
        b = bytearray(d[sector * SS:(sector + 1) * SS])
        if patch:
            inner, val = patch
            old = b[inner]
            assert old != val, "改动值与原值相同"
            b[inner] = val
            log("  %-12s 扇区 %d 内 0x%02X: %02X -> %02X"
                % (name, sector, inner, old, val))
        p = EXP / (name + ".bin")
        p.write_bytes(bytes(b))
        log("  %-12s -> %s (%d B, sha前8=%s)"
            % (name, p.name, len(b), __import__("hashlib").sha256(bytes(b)).hexdigest()[:8]))
    o = (EXP / "pad_orig.bin").read_bytes()
    p = (EXP / "pad_patched.bin").read_bytes()
    assert [i for i in range(SS) if o[i] != p[i]] == [PAD_INNER]
    o = (EXP / "sig_orig.bin").read_bytes()
    p = (EXP / "sig_patched.bin").read_bytes()
    assert [i for i in range(SS) if o[i] != p[i]] == [SIG_INNER]
    assert o[SIG_INNER:SIG_INNER + 8] == b"SHENZHEN", o[SIG_INNER:SIG_INNER + 8]
    o = (EXP / "krn_orig.bin").read_bytes()
    p = (EXP / "krn_patched.bin").read_bytes()
    assert [i for i in range(SS) if o[i] != p[i]] == [KRN_INNER]
    assert d[KRN_OFF] == 0, "kernel 页填充区不是全零，禁止继续"
    log("  护栏通过：每组仅 1 字节差异；签名区原串 SHENZHEN；kernel 填充区原值 00")


def fh(xml_path):
    cmd = [FH, "--port=" + PORT, "--memoryname=ufs",
           "--sendxml=" + xml_path, "--noprompt", "--zlpawarehost=1"]
    r = subprocess.run(cmd, cwd=str(EXP), capture_output=True, text=True,
                       errors="ignore", timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    ok = "All Finished Successfully" in out or "Finished programming" in out
    log("  %s : %s" % (os.path.basename(xml_path), "OK" if ok else "失败"))
    if not ok:
        log(out[-400:])
    return ok


def xml_write(filename, sector, tag):
    p = EXP / ("w_%s.xml" % tag)
    p.write_text('<?xml version="1.0" ?>\n<data>\n'
                 '<program SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="boot" '
                 'num_partition_sectors="1" physical_partition_number="%d" '
                 'start_sector="%d"/>\n</data>\n'
                 % (SS, filename, BOOT_LUN, BOOT_START + sector),
                 encoding="utf-8", newline="\n")
    return str(p)


def xml_read(filename, sector, tag):
    p = EXP / ("r_%s.xml" % tag)
    p.write_text('<?xml version="1.0" ?>\n<data>\n'
                 '<read SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="boot" '
                 'num_partition_sectors="1" physical_partition_number="%d" '
                 'start_sector="%d"/>\n</data>\n'
                 % (SS, filename, BOOT_LUN, BOOT_START + sector),
                 encoding="utf-8", newline="\n")
    return str(p)


def write_sector(name):
    sector, _ = FILES[name]
    fn = name + ".bin"
    want = (EXP / fn).read_bytes()
    log("写 %s -> LUN%d / %d (= boot 分区内扇区 %d)，单 4KB"
        % (fn, BOOT_LUN, BOOT_START + sector, sector))
    if not fh(xml_write(fn, sector, name)):
        return 1
    chk = "chk_%s.bin" % name
    if not fh(xml_read(chk, sector, "chk_" + name)):
        return 1
    got = (EXP / chk).read_bytes()
    same = got == want
    log("  回读 %s：%s" % ("一致" if same else "不一致", chk))
    if not same:
        log("  差异: %s" % [i for i in range(SS) if got[i] != want[i]][:20])
    return 0 if same else 1


def q(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           errors="ignore", timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return "[ERR %s]" % e


def adb_online():
    out = q([ADB, "get-state"], 6).strip().splitlines()
    return bool(out) and out[-1].strip() == "device"


def reset():
    p = EXP / "scope_reset.xml"
    p.write_text('<?xml version="1.0" ?>\n<data>\n<power value="reset"/>\n</data>\n',
                 encoding="utf-8", newline="\n")
    return 0 if fh(str(p)) else 1


def recover_all():
    """等 9008 -> 上传 -> 三个改动扇区全部写回原片 -> reset -> 确认进系统。"""
    sys.path.insert(0, HERE)
    import cycle_helper as c
    log("等待 9008（最多 40s）...")
    if not c.wait_edl(40):
        log("NEED_USER_9008：设备未进 9008，请断电重插进 QDLoader 9008 后重跑 --recover-all")
        return 2
    if not c.upload():
        log("上传失败")
        return 1
    for name in ("pad_orig", "sig_orig", "krn_orig"):
        if write_sector(name):
            log("!! 恢复 %s 失败" % name)
            return 1
    if reset():
        return 1
    return wait_system(90)


def wait_system(seconds):
    log("等系统上线（最多 %ds）..." % seconds)
    for i in range(seconds):
        if adb_online():
            log("  adb 上线 (%ds) <<< 启动成功" % i)
            break
        time.sleep(1)
    else:
        log("  adb 未上线 <<< 启动失败/卡 logo")
        return 1
    time.sleep(2)
    cmdline = q([ADB, "shell", "dmesg | grep -i 'Kernel command line' | head -1"], 20)
    log("  dmesg cmdline: %s" % cmdline[:900])
    for prop in ("ro.boot.verifiedbootstate", "ro.boot.veritymode"):
        log("  %s = %s" % (prop, q([ADB, "shell", "getprop", prop])))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--write", metavar="NAME", choices=list(FILES))
    ap.add_argument("--restore", metavar="KIND", choices=["pad", "sig", "krn"])
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--wait-system", type=int, metavar="SECONDS")
    ap.add_argument("--recover-all", action="store_true")
    a = ap.parse_args()
    if a.recover_all:
        sys.exit(recover_all())
    if a.prepare:
        prepare()
    elif a.write:
        sys.exit(write_sector(a.write))
    elif a.restore:
        sys.exit(write_sector(a.restore + "_orig"))
    elif a.reset:
        sys.exit(reset())
    elif a.wait_system:
        sys.exit(wait_system(a.wait_system))
    else:
        ap.print_help()
