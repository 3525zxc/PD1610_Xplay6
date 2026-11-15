# -*- coding: utf-8 -*-
"""
vivo Xplay6 (PD1610 / MSM8996) 基带与 NV 数据备份/恢复工具

依赖: pip install edlclient   (提供命令行 edl)

用法:
  # 0. 探测哪一个 firehose 能握手（手机关机 -> 音量上+下 -> 插线，进 9008 后执行）
  python baseband_backup.py probe --pkg <解压出来的固件目录>

  # 1. 只打印命令，不动设备（先看清楚要干什么）
  python baseband_backup.py plan  --loader prog_ufs_firehose_8996_ddr.elf --memory ufs

  # 2. 真机 dump（probe 成功后可省略 --loader，自动读 loader.json）
  python baseband_backup.py dump

  # 3. 校验 dump 完整性，生成 manifest.sha256
  python baseband_backup.py verify --dir dumps

  # 4. 恢复（必须显式加 --yes-i-know，且只允许本机 dump）
  python baseband_backup.py restore --dir dumps --loader prog_ufs_firehose_8996_ddr.elf --memory ufs --yes-i-know

注意:
  - modemst1/modemst2/fsg 是配对的，必须一起备份、一起恢复。
  - 恢复只允许用这台机器自己 dump 出来的文件；写入别机的 NV 会掉信号并改写别人 IMEI。
  - 本脚本不替你判断 loader 是否正确，写错 loader 的后果是 9006 硬砖。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

# 基带 / NV 关键分区。skip=True 表示默认不 dump（体积大，可按需开启）
NV_PARTS = [
    ("modemst1", False, "NV 数据区 1（IMEI/射频校准，最关键）"),
    ("modemst2", False, "NV 数据区 2（modemst1 的镜像）"),
    ("fsg",      False, "NV golden backup，恢复 modemst 时的底板"),
    ("fsc",      False, "modem 文件系统缓存（很小）"),
    ("persist",  False, "传感器校准 / WiFi-BT MAC / 部分 DRM"),
    ("misc",     False, "启动标志位、root flag"),
    ("devinfo",  False, "BL 解锁标志（改坏时可回滚）"),
    ("modem",    True,  "基带固件本体，约 100MB，跨版本降级时才有用"),
]

MANIFEST = "manifest.sha256"
META = "backup_meta.json"
LOADER_CACHE = "loader.json"

# 固件包里 4 个 firehose 的组合，按「先大概率、后兜底」排序
LOADER_CANDIDATES = [
    ("prog_ufs_firehose_8996_ddr.elf",  "ufs"),
    ("prog_ufs_firehose_8996_lite.elf", "ufs"),
    ("prog_emmc_firehose_8996_ddr.elf", "emmc"),
    ("prog_emmc_firehose_8996_lite.elf","emmc"),
]

# 判断 edl 是否真的读到了分区表（成功标志）
GPT_MARKERS = ("devinfo", "modemst1", "system")
# 判断这次失败是不是「压根没连上手机」
NODEV_MARKERS = ("no device", "devicenotfound", "no suitable", "device not found")


def ensure_loader(args):
    """--loader 没给就从 loader.json 取，都没有就报错退出。"""
    if args.loader:
        if not args.memory:
            args.memory = "ufs" if "ufs" in os.path.basename(args.loader).lower() else "emmc"
        return
    if os.path.isfile(LOADER_CACHE):
        with open(LOADER_CACHE, encoding="utf-8") as f:
            cfg = json.load(f)
        args.loader = cfg["loader"]
        args.memory = cfg["memory"]
        if args.lun is None:
            args.lun = cfg.get("lun")
        print("[*] 读 loader.json -> %s (--memory %s)" %
              (os.path.basename(args.loader), args.memory))
        return
    sys.exit("[x] 没指定 --loader，也没有 %s。\n"
             "    先跑: python baseband_backup.py probe --pkg <解压出来的固件目录>" % LOADER_CACHE)


def which_edl(required=True):
    for name in ("edl", "edl.py"):
        p = shutil.which(name)
        if p:
            return p
    if required:
        sys.exit("[x] 找不到 edl 命令。先跑: pip install edlclient")
    return "edl"


def base_cmd(args, required=True):
    cmd = [which_edl(required), "--loader", args.loader, "--memory", args.memory]
    if args.lun is not None:
        cmd += ["--lun", str(args.lun)]
    return cmd


def build_plan(args):
    cmds = []
    for part, skip, _desc in NV_PARTS:
        if skip and not args.with_modem:
            continue
        cmds.append(("r", part, os.path.join(args.dir, part + ".bin")))
    return cmds


def cmd_probe(args):
    d = args.pkg
    if not os.path.isdir(d):
        sys.exit("[x] 目录不存在: %s\n    指到解压后放着 prog_*.elf 的那一层。" % d)

    print("[*] 固件目录: %s" % os.path.abspath(d))
    print("[!] 手机关机 -> 音量上+下同时按住 -> 插线，确认设备管理器有")
    print("    Qualcomm HS-USB QDLoader 9008\n")

    present = [c for c in LOADER_CANDIDATES if os.path.isfile(os.path.join(d, c[0]))]
    if not present:
        sys.exit("[x] 这个目录里没有 prog_*_firehose_8996_*.elf，路径指错了？")

    print("[*] 找到 %d 个 firehose，开始逐个试 printgpt（只读，不写任何分区）\n" % len(present))

    for idx, (name, mem) in enumerate(present, 1):
        path = os.path.join(d, name)
        print("[%d/%d] %s   --memory %s" % (idx, len(present), name, mem))
        cmd = [which_edl(required=False), "--loader", path, "--memory", mem, "printgpt"]
        if args.dry_run:
            print("      $ %s" % " ".join(cmd))
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=args.timeout)
        except FileNotFoundError:
            sys.exit("[x] 找不到 edl 命令。先跑: pip install edlclient")
        except subprocess.TimeoutExpired:
            print("      -> 超时，跳过\n")
            continue

        out = ((r.stdout or "") + (r.stderr or "")).strip()
        low = out.lower()

        if any(m in low for m in NODEV_MARKERS):
            print("      -> 没连上手机。先让设备进 9008 再重跑，不是 loader 的问题。")
            return 1

        hit = r.returncode == 0 and any(m in low for m in GPT_MARKERS)
        if hit:
            print("      -> 成功，拿到分区表\n")
            cfg = {"loader": path, "memory": mem, "lun": args.lun}
            with open(LOADER_CACHE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print("[+] 已写入 %s:" % LOADER_CACHE)
            print(json.dumps(cfg, ensure_ascii=False, indent=2))
            print("\n下一步直接跑备份（不用再带 --loader）:")
            print("  python baseband_backup.py dump")
            return 0

        tail = "\n".join(out.splitlines()[:3]) or "(无输出)"
        print("      -> 失败: %s\n" % tail.replace("\n", " | "))
        if idx < len(present) and not args.dry_run and not args.no_wait:
            try:
                input("      失败后设备可能掉出 9008。重新插拔数据线回到 9008 后按回车继续...")
            except EOFError:
                pass
            print()

    if args.dry_run:
        print("\n[=] 干跑结束，没有连接设备。去掉 --dry-run 才会真去握手。")
        return 0

    print("[x] 4 个 firehose 全部失败，说明问题不在文件选择上。按这个顺序查:")
    print("    1. 驱动装的是不是 Qualcomm HS-USB QDLoader 9008（不是 9006/900E）")
    print("    2. 手机是真关机还是重启中（音量上+下要一直按住再插线）")
    print("    3. 换一根数据线 / 换 USB 2.0 口（前置面板口经常不行）")
    print("    4. package 本身损坏，重新解压一次")
    return 1


def cmd_plan(args):
    ensure_loader(args)
    print("[*] loader : %s" % args.loader)
    print("[*] memory : %s%s" % (args.memory, "" if args.lun is None else "  lun=%s" % args.lun))
    print("[*] 输出   : %s\n" % os.path.abspath(args.dir))
    print("将执行以下命令（顺序即执行顺序）:")
    base = " ".join(base_cmd(args, required=False))
    for op, part, out in build_plan(args):
        print("  %s %s %s %s" % (base, op, part, out))
    print("\n先跑 printgpt 确认分区名与设备对得上:")
    print("  %s printgpt" % base)
    print("\n回滚用（改 devinfo 出问题）:")
    print("  %s w devinfo %s" % (base, os.path.join(args.dir, "devinfo.bin")))
    return 0


def run(cmd, dry=False):
    print("  $ %s" % " ".join(cmd))
    if dry:
        return 0
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        sys.exit("[x] edl 无法执行，确认 PATH 里有 edl 或 edl.py")


def cmd_dump(args):
    ensure_loader(args)
    os.makedirs(args.dir, exist_ok=True)
    plan = build_plan(args)
    print("[!] 确认手机已进入 9008 模式（设备管理器出现 Qualcomm HS-USB QDLoader 9008）")
    print("[!] 确认 loader 与本机闪存类型一致: %s\n" % args.loader)

    print("[1/3] 读分区表")
    rc = run(base_cmd(args, required=not args.dry_run) + ["printgpt"], dry=args.dry_run)
    if rc != 0 and not args.dry_run:
        print("[x] printgpt 失败，loader / 驱动 / 9008 状态有问题，已停止（未写入任何分区）")
        return 1

    print("\n[2/3] dump %d 个分区" % len(plan))
    failed = []
    for op, part, out in plan:
        rc = run(base_cmd(args, required=not args.dry_run) + [op, part, out], dry=args.dry_run)
        if rc != 0:
            failed.append(part)
        elif not args.dry_run and os.path.isfile(out):
            print("      -> %d 字节" % os.path.getsize(out))

    if args.dry_run:
        print("\n[=] 干跑结束，未对设备做任何读写。")
        return 0

    print("\n[3/3] 校验")
    vrc = cmd_verify(argparse.Namespace(dir=args.dir))
    if failed:
        print("[!] 以下分区 dump 失败，重跑一次: %s" % ", ".join(failed))
        return 1
    return vrc


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_verify(args):
    d = args.dir
    if not os.path.isdir(d):
        sys.exit("[x] 目录不存在: %s" % d)

    print("[*] 校验目录: %s" % os.path.abspath(d))
    rows, bad, lines = [], [], []
    for part, _skip, _desc in NV_PARTS:
        p = os.path.join(d, part + ".bin")
        if not os.path.isfile(p):
            rows.append((part, "-", "-", "缺失（可选）" if _skip else "缺失"))
            if not _skip:
                bad.append(part)
            continue
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            head = f.read(1 << 16)
        if size == 0:
            rows.append((part, "0", "-", "空文件"))
            bad.append(part)
            continue
        if head and len(set(head)) == 1 and head[0] in (0x00, 0xFF):
            rows.append((part, str(size), "-", "疑似全 0x%02X" % head[0]))
            bad.append(part)
            continue
        h = sha256_of(p)
        rows.append((part, str(size), h[:16], "OK"))
        lines.append("%s  %s" % (h, part + ".bin"))

    w = max(len(r[0]) for r in rows)
    print("\n  %-*s  %12s  %-16s  %s" % (w, "分区", "字节", "sha256前16", "状态"))
    for part, size, h, st in rows:
        print("  %-*s  %12s  %-16s  %s" % (w, part, size, h, st))

    if lines:
        mp = os.path.join(d, MANIFEST)
        with open(mp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print("\n[+] 已写入 %s" % mp)

    with open(os.path.join(d, META), "w", encoding="utf-8") as f:
        json.dump({"device": "vivo Xplay6 PD1610 / MSM8996",
                   "partitions": [r[0] for r in rows if r[3] == "OK"]}, f,
                  ensure_ascii=False, indent=2)

    if bad:
        print("\n[!] 有问题的分区: %s  —— 不要拿这些文件去做恢复" % ", ".join(bad))
        return 1
    print("\n[=] 备份集完整。把整个 dumps 目录复制到两个不同位置保存。")
    return 0


def cmd_restore(args):
    ensure_loader(args)
    if not args.yes_i_know:
        sys.exit("[x] 恢复会覆盖本机 NV。确认无误后加 --yes-i-know 再跑。\n"
                 "    前提: 文件必须来自这台机器本身的 dump，不是网上下的、不是别机的。")
    if not os.path.isfile(os.path.join(args.dir, MANIFEST)):
        sys.exit("[x] 目录里没有 %s，先跑 verify。拒绝恢复来源不明的 dump。" % MANIFEST)

    # 只恢复 NV 三件套 + persist，modem 默认不动
    targets = [p for p, _s, _d in NV_PARTS if p in ("modemst1", "modemst2", "fsg", "fsc", "persist")]
    missing = [t for t in targets if not os.path.isfile(os.path.join(args.dir, t + ".bin"))]
    if missing:
        sys.exit("[x] 缺文件，拒绝恢复（modemst/fsg 必须成套）: %s" % ", ".join(missing))

    print("即将写回: %s" % ", ".join(targets))
    for t in targets:
        if run(base_cmd(args) + ["w", t, os.path.join(args.dir, t + ".bin")]) != 0:
            print("[x] %s 写入失败，停止。不要再往下写。" % t)
            return 1
    print("\n[+] 写完。执行 reset 重启:")
    print("  %s reset" % " ".join(base_cmd(args)))
    print("[!] 重启后 *#06# 核对 IMEI，插卡确认有信号。")
    return 0


def main():
    p = argparse.ArgumentParser(description="Xplay6 基带 / NV 备份恢复")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, need_loader=True):
        sp.add_argument("--dir", default="dumps")
        if need_loader:
            sp.add_argument("--loader", default=None,
                            help="9008 包里的 firehose；不给就自动读 loader.json")
            sp.add_argument("--memory", default=None, choices=["ufs", "emmc", "sdcc"])
            sp.add_argument("--lun", type=int, default=None)

    sp = sub.add_parser("probe", help="逐个试 firehose，找出能握手的那一个")
    sp.add_argument("--pkg", required=True, help="解压后放着 prog_*.elf 的目录")
    sp.add_argument("--lun", type=int, default=None)
    sp.add_argument("--timeout", type=int, default=90)
    sp.add_argument("--dry-run", action="store_true", help="只打印会跑的命令")
    sp.add_argument("--no-wait", action="store_true", help="失败后不暂停等插拔")
    sp.set_defaults(func=cmd_probe)

    sp = sub.add_parser("plan", help="只打印命令")
    common(sp)
    sp.add_argument("--with-modem", action="store_true", help="连 modem 固件一起 dump")
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("dump", help="执行备份")
    common(sp)
    sp.add_argument("--with-modem", action="store_true")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_dump)

    sp = sub.add_parser("verify", help="校验备份")
    common(sp, need_loader=False)
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("restore", help="恢复 NV")
    common(sp)
    sp.add_argument("--yes-i-know", action="store_true")
    sp.set_defaults(func=cmd_restore)

    args = p.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
