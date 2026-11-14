#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验 device_tree/device/vivo/pd1610 里的配置是否与实机数据一致。

比对基准全部是实测数据，不是另一份手抄的配置：
  work/boot_81_official.img   boot 头（page_size / base / offset / cmdline）
  work/part_sizes.txt         55 个分区的 blockdev --getsize64
  blobs/                      vendor 全量 + system/lib[64] 私有库
  blobs/vendor_links.json     211 条软链（Windows 无法落地，只能查表）

用法:
    python scripts/verify_device_tree.py
退出码 0 = 全通过；1 = 有 FAIL。
"""
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DT = os.path.join(ROOT, "device_tree", "device", "vivo", "pd1610")
BOOT = os.path.join(ROOT, "work", "boot_81_official.img")
PARTS = os.path.join(ROOT, "work", "part_sizes.txt")
BLOBS = os.path.join(ROOT, "blobs")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    return ok


def read_mk(path):
    """把 makefile 读成 dict，处理反斜杠续行，只保留简单赋值。"""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # 续行合并
    raw = re.sub(r"\\\s*\n", " ", raw)
    out = {}
    for line in raw.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(\+=|:=|\?=|=)\s*(.*)$", s)
        if m:
            key, op, val = m.group(1), m.group(2), m.group(3).strip()
            if op == "+=" and key in out:
                out[key] += " " + val
            else:
                out[key] = val
    return out


def boot_header():
    d = open(BOOT, "rb").read()
    ks, ka, rs, ra, ss, sa, tags, page, hv, osv = struct.unpack_from("<10I", d, 8)
    cmdline = d[0x40:0x240].split(b"\x00")[0].decode("ascii", "replace")
    return dict(data=d, ks=ks, ka=ka, rs=rs, ra=ra, ss=ss, sa=sa,
                tags=tags, page=page, hv=hv, osv=osv, cmdline=cmdline)


def part_sizes():
    out = {}
    with open(PARTS, encoding="utf-8") as f:
        for line in f:
            bits = line.split()
            if len(bits) >= 2 and bits[1].isdigit():
                out[bits[0]] = int(bits[1])
    return out


def int_mk(v):
    v = v.strip()
    try:
        return int(v, 0)
    except ValueError:
        return None


def main():
    bc = read_mk(os.path.join(DT, "BoardConfig.mk"))
    dev = read_mk(os.path.join(DT, "device.mk"))
    bh = boot_header()
    parts = part_sizes()

    # ---------------- kernel / boot header ----------------
    check("BoardConfig 存在且非空", len(bc) > 40, "%d 个变量" % len(bc))

    check("BOARD_KERNEL_PAGESIZE == boot header page_size",
          int_mk(bc.get("BOARD_KERNEL_PAGESIZE", "")) == bh["page"],
          "配置 %s / 实测 %d" % (bc.get("BOARD_KERNEL_PAGESIZE"), bh["page"]))

    base = int_mk(bc.get("BOARD_KERNEL_BASE", ""))
    args = bc.get("BOARD_MKBOOTIMG_ARGS", "")
    def arg(name, default=None):
        m = re.search(r"--%s\s+(\S+)" % name, args)
        return int(m.group(1), 0) if m else default

    check("BOARD_KERNEL_BASE + kernel_offset == header kernel_addr",
          base is not None and base + (arg("kernel_offset") or 0) == bh["ka"],
          "配置 0x%X + %s / 实测 0x%X" % (base or 0, arg("kernel_offset"), bh["ka"]))
    check("ramdisk_offset == header ramdisk_addr - base",
          base is not None and base + (arg("ramdisk_offset") or 0) == bh["ra"],
          "配置 0x%X + %s / 实测 0x%X" % (base or 0, arg("ramdisk_offset"), bh["ra"]))
    check("tags_offset == header tags_addr - base",
          base is not None and base + (arg("tags_offset") or 0) == bh["tags"],
          "配置 0x%X + %s / 实测 0x%X" % (base or 0, arg("tags_offset"), bh["tags"]))
    check("second_offset == header second_addr - base",
          base is not None and base + (arg("second_offset") or 0) == bh["sa"],
          "配置 0x%X + %s / 实测 0x%X" % (base or 0, arg("second_offset"), bh["sa"]))

    # cmdline：允许追加参数，但官方 413 字节必须一字不差做前缀
    cfg_cl = bc.get("BOARD_KERNEL_CMDLINE", "").strip()
    check("BOARD_KERNEL_CMDLINE 以官方 cmdline 为前缀",
          cfg_cl.startswith(bh["cmdline"]),
          "官方 %d B / 配置 %d B / 追加 %r" % (
              len(bh["cmdline"]), len(cfg_cl), cfg_cl[len(bh["cmdline"]):].strip()))
    check("cmdline 保留 securebootkey 三件套",
          all(k in cfg_cl for k in ("androidboot.securebootkey=beta",
                                    "androidboot.securebootkeyhash=da758fd5",
                                    "androidboot.securebootkeyver=2")))
    over = len(cfg_cl) - 512 + 1
    check("cmdline 长度不超过 boot v0 的 512 B 上限",
          len(cfg_cl) <= 511, "%d B（余量 %d）" % (len(cfg_cl), 512 - 1 - len(cfg_cl)))

    # ---------------- prebuilt kernel ----------------
    kp = os.path.join(DT, "prebuilt", "kernel")
    if check("prebuilt/kernel 存在", os.path.exists(kp)):
        k = open(kp, "rb").read()
        ref = bh["data"][bh["page"]:bh["page"] + bh["ks"]]
        check("prebuilt/kernel 与官方 boot 的 kernel 段逐字节一致",
              k == ref, "%d B / sha256 %s" % (len(k), __import__("hashlib").sha256(k).hexdigest()[:16]))
        check("prebuilt/kernel 是 gzip（Image.gz-dtb）", k[:2] == b"\x1f\x8b", k[:4].hex())
        check("prebuilt/kernel 内含 appended DTB",
              k.find(b"\xd0\x0d\xfe\xed") > 0,
              "DTB 偏移 0x%X" % k.find(b"\xd0\x0d\xfe\xed"))

    # ---------------- 分区大小 ----------------
    pairs = [("BOOT", "boot"), ("RECOVERY", "recovery"), ("SYSTEM", "system"),
             ("USERDATA", "userdata"), ("CACHE", "cache")]
    for mk_key, part in pairs:
        key = "BOARD_%sIMAGE_PARTITION_SIZE" % mk_key
        want = parts.get(part)
        got = int_mk(bc.get(key, ""))
        check("%s == %s 实际大小" % (key, part), got == want,
              "配置 %s / 实测 %s" % (got, want))

    # ---------------- 非 Treble 结构 ----------------
    check("TARGET_COPY_OUT_VENDOR := system/vendor", 
          bc.get("TARGET_COPY_OUT_VENDOR") == "system/vendor", bc.get("TARGET_COPY_OUT_VENDOR"))
    check("BOARD_ROOT_EXTRA_SYMLINKS 建 /vendor 软链",
          "/vendor:/system/vendor" in bc.get("BOARD_ROOT_EXTRA_SYMLINKS", ""),
          bc.get("BOARD_ROOT_EXTRA_SYMLINKS"))
    check("未定义 BOARD_VENDORIMAGE_PARTITION_SIZE（非 Treble 不应有 vendor 镜像）",
          "BOARD_VENDORIMAGE_PARTITION_SIZE" not in bc)
    check("HAL 加密首版关闭", bc.get("TARGET_HW_DISK_ENCRYPTION") == "false",
          bc.get("TARGET_HW_DISK_ENCRYPTION"))

    # ---------------- PRODUCT_COPY_FILES 源文件存在 ----------------
    copies = []
    for tok in dev.get("PRODUCT_COPY_FILES", "").split():
        if ":" in tok:
            copies.append(tok)
    missing = []
    for tok in copies:
        src = tok.split(":", 1)[0].replace("$(LOCAL_PATH)", DT)
        if src.startswith("frameworks/") or src.startswith("external/"):
            continue  # AOSP 侧文件，不在本仓库
        if not os.path.exists(src):
            missing.append(os.path.basename(src))
    check("device.mk 的 PRODUCT_COPY_FILES 源文件都存在", not missing,
          "%d 条，缺失 %s" % (len(copies), missing[:5]))

    dsts = [t.split(":", 1)[1] for t in copies]
    def is_vendor_etc_fstab(d):
        return ("vendor/etc/fstab.qcom" in d) or (d == "$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qcom")
    check("fstab 同时装到 ramdisk 根与 /vendor/etc",
          "root/fstab.qcom" in dsts and any(is_vendor_etc_fstab(d) for d in dsts),
          [d for d in dsts if "fstab" in d])
    check("三份 keylayout 都装到 system/usr/keylayout",
          sum(1 for d in dsts if d.startswith("system/usr/keylayout/")) == 3,
          [os.path.basename(d) for d in dsts if "keylayout" in d])

    # ---------------- fstab 引用的分区都存在 ----------------
    fstab = os.path.join(DT, "rootdir", "etc", "fstab.qcom")
    names = re.findall(r"/dev/block/bootdevice/by-name/([A-Za-z0-9_]+)", open(fstab).read())
    unknown = [n for n in names if n not in parts]
    check("fstab 引用的分区全部存在", not unknown,
          "%d 个引用，未知 %s" % (len(set(names)), unknown))

    # ---------------- proprietary-files.txt ----------------
    pf = os.path.join(DT, "proprietary-files.txt")
    links = {}
    lp = os.path.join(BLOBS, "vendor_links.json")
    if os.path.exists(lp):
        for it in json.load(open(lp, encoding="utf-8")):
            links[it["path"]] = it.get("linkname")

    miss_file, miss_link, n_file, n_link = [], [], 0, 0
    for line in open(pf, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        path = s.split(":", 1)[0]
        local = os.path.join(BLOBS, path.replace("/", os.sep))
        if ":" in s:
            n_link += 1
            if path not in links and not os.path.exists(local):
                miss_link.append(path)
        else:
            n_file += 1
            if not os.path.exists(local):
                miss_file.append(path)
    check("proprietary-files.txt 普通文件都能在 blobs 找到", not miss_file,
          "%d 个文件，缺失 %d %s" % (n_file, len(miss_file), miss_file[:5]))
    check("proprietary-files.txt 软链都能在原厂清单找到", not miss_link,
          "%d 条软链，缺失 %d %s" % (n_link, len(miss_link), miss_link[:5]))
    check("proprietary-files.txt 已剔除 vendor/etc/fstab.qcom（改用设备树版本）",
          "vendor/etc/fstab.qcom\n" not in open(pf, encoding="utf-8").read())

    # ---------------- 汇总 ----------------
    width = max(len(r[0]) for r in results)
    okc = sum(1 for r in results if r[1])
    print("=" * (width + 46))
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print("[%s] %-*s %s" % (mark, width, name, detail))
    print("=" * (width + 46))
    print("总计 %d 项：%d 通过 / %d 失败" % (len(results), okc, len(results) - okc))
    return 0 if okc == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
