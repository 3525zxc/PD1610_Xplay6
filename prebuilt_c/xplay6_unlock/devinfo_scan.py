# -*- coding: utf-8 -*-
"""devinfo 单变量分组实验：只改 devinfo 标志字节，绝不碰 boot / 基带。

来源线索：酷安 feed/74915679 —— vivo 系机型改 devinfo 特定字节即可解 BL。
本机 Xplay6 真机 devinfo: 0x00-0x0C = ANDROID-BOOT!, 0x0D-0xDF 全 00,
0xE0 起为充电屏 ARM 代码。上一轮只试过 0x0D/0x0E，本脚本逐组排查其余候选。

用法（设备须按提示进入对应模式）:
  py devinfo_scan.py --plan                 生成全部候选镜像并打印差异，不碰设备
  py devinfo_scan.py --write G1             写一组并自动回读校验（需 firehose 就绪）
  py devinfo_scan.py --verify G1            仅回读 devinfo 与期望镜像比对
  py devinfo_scan.py --check                在 fastboot 模式读 oem device-info
  py devinfo_scan.py --reset                发 power reset 让设备重启（需 firehose 就绪）
  py devinfo_scan.py --restore              写回原始 devinfo.bin 并回读校验

9008 铁律：断电重插进 9008 -> 立刻 QSaharaServer 上传 programmer -> fh_loader。
不要先用 pyserial 探测端口。QSaharaServer 僵尸进程要先清掉。
"""
import argparse
import datetime
import os
import subprocess
import sys

QFIL = r"D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5"
FH = os.path.join(QFIL, "fh_loader.exe")
SAHARA = os.path.join(QFIL, "QSaharaServer.exe")
PROG = r"C:\qfilx\prog_ufs_firehose_8996_ddr.elf"
FASTBOOT = r"C:\qfilx\fastboot\fastboot.exe"
DUMP = r"C:\qfilx\dumps"
WORK = r"C:\qfilx\scan"
LOG = os.path.join(WORK, "logs")
ORIG = os.path.join(DUMP, "devinfo.bin")

PORT = r"\\.\COM5"
SS = 4096
LUN = 4
START = 882954
MAGIC = b"ANDROID-BOOT!"

# 只允许改 magic 之后、充电屏代码之前的标志区
SAFE_LO, SAFE_HI = 0x0D, 0x20

# list = 全部置 01；dict = 写入指定值
GROUPS = {
    "G0":    [0x0D, 0x0E],                              # 标准 LK 位，上一轮已试，作对照
    "G1":    [0x14, 0x15],                              # 酷安「第二排第 5/6」16 字节行 1-based
    "G2":    [0x15, 0x16],                              # 同上 0-based 列号解释
    "G3":    [0x10, 0x11],
    "G4":    [0x18, 0x19],
    "G5":    [0x1C, 0x1D],
    "G6":    [0x0D, 0x0F],                              # 跳过疑似 is_tampered 的 0x0E
    "G7":    [0x0D, 0x14, 0x15],                        # 标准位 + 酷安位
    "TAIL":  {0x14: 0x01, 0x15: 0x01,                   # 模拟酷安尾部 21 01 01 01 标记
              0x1C: 0x21, 0x1D: 0x01, 0x1E: 0x01, 0x1F: 0x01},
    "BROAD": [i for i in range(0x0D, 0x20) if i != 0x0E],  # 宽筛，避开疑似 tampered 位
    # aboot 静态反汇编确认（oem device-info @0x91837F40，字段为 32 位字）：
    #   0x10=is_unlocked  0x14=is_tampered  0x18=is_unlock_critical
    #   0x1C=charger_screen_enabled  0x20=display_panel
    # 启动校验 @0x91839958 读 [struct+0x10]，非零则跳过签名校验
    "UL":    {0x10: 0x01},                              # 首选：只置 is_unlocked
    "ULC":   {0x10: 0x01, 0x18: 0x01},                 # 同时置 critical unlocked
}

NOTE = {
    "G0": "对照组：上一轮已验证无效，不必重复",
    "G1": "首选：酷安动态指向的位置",
    "G2": "首选备择：列号从 0 数的解释",
    "G6": "避开 0x0E（LK 里通常是 is_tampered）",
    "TAIL": "按 iQOO 尾部标记重建结构",
    "BROAD": "宽筛：一次覆盖全部候选，命中后再二分定位；仍有误触断言风险",
    "UL": "已由 aboot 反汇编确认：0x10 是 is_unlocked 32 位字，0x14 保持 0 避免 tampered",
    "ULC": "UL 基础上再置 0x18=is_unlock_critical，对应酷安截图两项均为 true",
}


def orig_bytes():
    d = open(ORIG, "rb").read()
    assert len(d) == SS, "原始 devinfo 不是 4096 字节: %d" % len(d)
    assert d[:13] == MAGIC, "原始 devinfo magic 不对"
    return d


def patch_of(name):
    if name not in GROUPS:
        raise KeyError("未知分组 %s，可用: %s" % (name, ", ".join(GROUPS)))
    g = GROUPS[name]
    return dict((i, 1) for i in g) if isinstance(g, list) else dict(g)


def build(name, base=None):
    d = bytearray(base if base is not None else orig_bytes())
    for off, val in patch_of(name).items():
        assert SAFE_LO <= off < SAFE_HI, "偏移越界: 0x%X" % off
        d[off] = val
    return bytes(d)


def guard(base, new, name):
    """硬护栏：magic 不变、标志区之外不变、差异集合与预期完全一致。"""
    assert len(new) == SS
    assert new[:13] == MAGIC
    assert new[SAFE_HI:] == base[SAFE_HI:], "标志区之外被改动，拒绝"
    want = set(patch_of(name).items())
    got = set((i, new[i]) for i in range(len(new)) if new[i] != base[i])
    assert got == want, "差异集合与预期不符: got=%s want=%s" % (got, want)


def ensure_work():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(LOG, exist_ok=True)


def fh(xml_path, tag):
    cmd = [FH, "--port=" + PORT, "--memoryname=ufs",
           "--sendxml=" + xml_path, "--noprompt", "--zlpawarehost=1"]
    r = subprocess.run(cmd, cwd=WORK, capture_output=True, text=True,
                       errors="ignore", timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    lp = os.path.join(LOG, "%s_%s.log" % (
        datetime.datetime.now().strftime("%H%M%S"), tag))
    open(lp, "w", encoding="utf-8", errors="ignore").write(out)
    ok = ("All Finished Successfully" in out) or ("Finished programming" in out)
    print("  [%s] %s  日志=%s" % (tag, "OK" if ok else "失败/需检查", lp))
    if not ok:
        print(out[-600:])
    return ok, out


def xml_write(filename, tag):
    p = os.path.join(WORK, "w_%s.xml" % tag)
    open(p, "w", encoding="utf-8", newline="\n").write(
        '<?xml version="1.0" ?>\n<data>\n'
        '<program SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="devinfo" '
        'num_partition_sectors="1" physical_partition_number="%d" '
        'start_sector="%d"/>\n</data>\n' % (SS, filename, LUN, START))
    return p


def xml_read(filename, tag):
    p = os.path.join(WORK, "r_%s.xml" % tag)
    open(p, "w", encoding="utf-8", newline="\n").write(
        '<?xml version="1.0" ?>\n<data>\n'
        '<read SECTOR_SIZE_IN_BYTES="%d" filename="%s" label="devinfo" '
        'num_partition_sectors="1" physical_partition_number="%d" '
        'start_sector="%d"/>\n</data>\n' % (SS, filename, LUN, START))
    return p


def xml_reset():
    p = os.path.join(WORK, "reset.xml")
    open(p, "w", encoding="utf-8", newline="\n").write(
        '<?xml version="1.0" ?>\n<data>\n<power value="reset"/>\n</data>\n')
    return p


def do_write(filename, tag):
    ok, _ = fh(xml_write(filename, tag), "write_" + tag)
    return ok


def do_readback(filename, tag, expected, label):
    ok, _ = fh(xml_read(filename, tag), "read_" + tag)
    if not ok:
        return False
    p = os.path.join(WORK, filename)
    if not os.path.exists(p):
        print("  回读文件不存在: %s" % p)
        return False
    got = open(p, "rb").read()
    same = got == expected
    print("  [%s] 回读 %s: %s" % (label, "一致" if same else "不一致", filename))
    if not same:
        diffs = [i for i in range(SS) if got[i] != expected[i]]
        print("  差异字节数 %d，前 20 个: %s" % (len(diffs), [hex(i) for i in diffs[:20]]))
    return same


def cmd_plan():
    ensure_work()
    base = orig_bytes()
    print("原始 devinfo: %s  4096 字节  magic=%s" % (ORIG, MAGIC.decode()))
    print("标志区 0x%02X-0x%02X 之外一律不动（0xE0 起充电屏代码保持原样）\n" % (SAFE_LO, SAFE_HI - 1))
    for name in GROUPS:
        img = build(name, base)
        guard(base, img, name)
        fn = "devinfo_%s.bin" % name
        open(os.path.join(WORK, fn), "wb").write(img)
        diff = " ".join("%02X:%02X->%02X" % (i, base[i], img[i])
                        for i in sorted(patch_of(name)))
        print("  %-6s %-26s %s" % (name, fn, diff))
        if name in NOTE:
            print("         %s" % NOTE[name])
    open(os.path.join(WORK, "devinfo_orig.bin"), "wb").write(base)
    print("\n共 %d 组镜像已生成到 %s；未写入设备。" % (len(GROUPS), WORK))
    print("上传 programmer 命令（断电重插进 9008 后立刻执行）:")
    print('  "%s" -p %s -s 13:%s' % (SAHARA, PORT, PROG))


def cmd_write(name):
    ensure_work()
    base = orig_bytes()
    img = build(name, base)
    guard(base, img, name)
    fn = "devinfo_%s.bin" % name
    open(os.path.join(WORK, fn), "wb").write(img)
    print("准备写入 %s，改动: %s" % (
        name, " ".join("%02X->%02X" % (i, val) for i, val in sorted(patch_of(name).items()))))
    print("  仅 devinfo 单扇区 LUN%d / %d，不动 boot、不动基带" % (LUN, START))
    if not do_write(fn, name):
        print("写入未成功，终止。检查 9008 时序与 firehose 是否已上传。")
        return 1
    chk = "chk_%s.bin" % name
    do_readback(chk, name, img, "写入校验")
    print("写入完成。下一步：--reset 重启 -> 进 fastboot -> --check 看 device-info")
    return 0


def cmd_verify(name):
    ensure_work()
    img = build(name)
    return 0 if do_readback("chk_%s.bin" % name, name, img, "校验") else 1


def cmd_restore():
    ensure_work()
    base = orig_bytes()
    fn = "devinfo_orig.bin"
    open(os.path.join(WORK, fn), "wb").write(base)
    print("恢复原始 devinfo.bin（0x0D-0xDF 全 00）")
    if not do_write(fn, "restore"):
        print("恢复写入未成功，务必重试，不要直接开机使用。")
        return 1
    ok = do_readback("chk_restore.bin", "restore", base, "恢复校验")
    print("恢复 %s" % ("完成，设备可正常启动" if ok else "未确认，请重跑 --restore"))
    return 0 if ok else 1


def cmd_check():
    if not os.path.exists(FASTBOOT):
        print("fastboot 不存在: %s" % FASTBOOT)
        return 1
    r = subprocess.run([FASTBOOT, "oem", "device-info"],
                       capture_output=True, text=True, errors="ignore", timeout=60)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip())
    lo = out.lower()
    if "device unlocked: true" in lo:
        print("\n>>> 命中：BL 已解锁。记录当前分组，可继续验证 fastboot flash。")
    else:
        print("\n>>> 仍未解锁（或设备不在 fastboot）。换下一组，或执行 --restore。")
    return 0


def cmd_reset():
    ensure_work()
    ok, _ = fh(xml_reset(), "reset")
    print("重启指令 %s；之后按键或用 adb reboot bootloader 进 fastboot" % ("已发出" if ok else "未确认"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--write", metavar="GROUP")
    ap.add_argument("--verify", metavar="GROUP")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    if a.plan or not any([a.write, a.verify, a.check, a.reset, a.restore]):
        cmd_plan()
        return 0
    if a.write:
        return cmd_write(a.write)
    if a.verify:
        return cmd_verify(a.verify)
    if a.check:
        return cmd_check()
    if a.reset:
        return cmd_reset()
    if a.restore:
        return cmd_restore()
    return 0


if __name__ == "__main__":
    sys.exit(main())
