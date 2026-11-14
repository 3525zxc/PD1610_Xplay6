#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
解析 vendor 目录下所有 ELF 的 DT_NEEDED，求依赖闭包边界。

目的：PD1610 是非 Treble，vendor 在 /system/vendor。移植类原生时必须知道
      哪些 /system/lib(64) 里的库是 vivo/qcom 私有、必须一起当 blob 带走，
      哪些是 AOSP 会自己编出来的。

输出：blobs/elf_deps.json  +  控制台摘要
"""
import json
import os
import struct
import sys

BASE = r"D:\16\PD1610_81\blobs"
VENDOR = os.path.join(BASE, "vendor")
SYS32 = os.path.join(BASE, "_syslib32.txt")
SYS64 = os.path.join(BASE, "_syslib64.txt")

PT_LOAD, PT_DYNAMIC = 1, 2
DT_NULL, DT_NEEDED, DT_STRTAB, DT_SONAME = 0, 1, 5, 14

# AOSP 会自己编译的库（移植时不需要从原厂带）
AOSP_PREFIX = (
    "libc.so", "libm.so", "libdl.so", "libstdc++.so", "liblog.so", "libcutils.so",
    "libutils.so", "libbinder.so", "libui.so", "libgui.so", "libhardware.so",
    "libhardware_legacy.so", "libsync.so", "libion.so", "libEGL.so", "libGLESv1_CM.so",
    "libGLESv2.so", "libGLESv3.so", "libc++.so", "libc++_shared.so", "libz.so",
    "libexpat.so", "libpng.so", "libjpeg.so", "libsqlite.so", "libselinux.so",
    "libcrypto.so", "libssl.so", "libnativehelper.so", "libnetutils.so", "libnl.so",
    "libpower.so", "libsuspend.so", "libsysutils.so", "libtinyxml.so", "libspeexresampler.so",
    "libstagefright.so", "libstagefright_foundation.so", "libstagefright_omx.so",
    "libmedia.so", "libmediaplayerservice.so", "libaudioutils.so", "libnbaio.so",
    "libsonivox.so", "libpdfium.so", "libharfbuzz_ng.so", "libft2.so", "libminikin.so",
    "libhwui.so", "libskia.so", "libRS.so", "librs_jni.so", "libRScpp.so",
    "libwpa_client.so", "lib_domain_socket.so", "libmemtrack.so", "libqdMetaData.so",
)


def read_elf(path):
    """返回 (class_bits, machine, needed[], soname, error)"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        return None, None, [], None, "open:%s" % e
    if len(data) < 64 or data[:4] != b"\x7fELF":
        return None, None, [], None, "not-elf"
    ei_class = data[4]
    ei_data = data[5]
    if ei_data != 1:
        return None, None, [], None, "big-endian"
    if ei_class == 2:
        bits = 64
        e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
        e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
        e_phnum = struct.unpack_from("<H", data, 0x38)[0]
        e_machine = struct.unpack_from("<H", data, 0x12)[0]
    elif ei_class == 1:
        bits = 32
        e_phoff = struct.unpack_from("<I", data, 0x1C)[0]
        e_phentsize = struct.unpack_from("<H", data, 0x2A)[0]
        e_phnum = struct.unpack_from("<H", data, 0x2C)[0]
        e_machine = struct.unpack_from("<H", data, 0x12)[0]
    else:
        return None, None, [], None, "bad-class"

    loads = []
    dyn = None
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + e_phentsize > len(data):
            break
        if bits == 64:
            p_type, _flags, p_offset, p_vaddr, _pp, p_filesz, _pm, _al = \
                struct.unpack_from("<IIQQQQQQ", data, off)
        else:
            p_type, p_offset, p_vaddr, _pp, p_filesz, _pm, _fl, _al = \
                struct.unpack_from("<IIIIIIII", data, off)
        if p_type == PT_LOAD:
            loads.append((p_vaddr, p_offset, p_filesz))
        elif p_type == PT_DYNAMIC:
            dyn = (p_offset, p_filesz)

    if not dyn:
        return bits, e_machine, [], None, "no-PT_DYNAMIC"

    esz = 16 if bits == 64 else 8
    fmt = "<qQ" if bits == 64 else "<iI"
    entries = []
    base = dyn[0]
    end = min(len(data), base + dyn[1])
    p = base
    while p + esz <= end:
        tag, val = struct.unpack_from(fmt, data, p)
        if tag == DT_NULL:
            break
        entries.append((tag, val))
        p += esz

    strtab_va = next((v for t, v in entries if t == DT_STRTAB), None)
    if strtab_va is None:
        return bits, e_machine, [], None, "no-DT_STRTAB"

    strtab_off = None
    for vaddr, offset, filesz in loads:
        if vaddr <= strtab_va < vaddr + filesz:
            strtab_off = offset + (strtab_va - vaddr)
            break
    if strtab_off is None:
        return bits, e_machine, [], None, "strtab-not-in-load"

    def cstr(o):
        if o is None or o >= len(data):
            return None
        e = data.find(b"\x00", o)
        if e < 0:
            return None
        return data[o:e].decode("utf-8", "replace")

    needed = [cstr(strtab_off + v) for t, v in entries if t == DT_NEEDED]
    soname = next((cstr(strtab_off + v) for t, v in entries if t == DT_SONAME), None)
    return bits, e_machine, [n for n in needed if n], soname, None


def main():
    sys32 = set(open(SYS32, encoding="utf-8", errors="replace").read().split()) \
        if os.path.exists(SYS32) else set()
    sys64 = set(open(SYS64, encoding="utf-8", errors="replace").read().split()) \
        if os.path.exists(SYS64) else set()

    vendor32 = set()
    vendor64 = set()
    for root, _dirs, files in os.walk(os.path.join(VENDOR, "lib")):
        vendor32 |= {f for f in files if f.endswith(".so")}
    for root, _dirs, files in os.walk(os.path.join(VENDOR, "lib64")):
        vendor64 |= {f for f in files if f.endswith(".so")}

    results = []
    all_needed = {"32": set(), "64": set()}
    errors = []
    for root, _dirs, files in os.walk(VENDOR):
        for fn in files:
            path = os.path.join(root, fn)
            try:
                with open(path, "rb") as f:
                    if f.read(4) != b"\x7fELF":
                        continue
            except Exception:
                continue
            bits, machine, needed, soname, err = read_elf(path)
            rel = os.path.relpath(path, VENDOR).replace("\\", "/")
            if err:
                errors.append({"path": "vendor/" + rel, "error": err})
                continue
            key = "64" if bits == 64 else "32"
            all_needed[key] |= set(needed)
            results.append({
                "path": "vendor/" + rel,
                "bits": bits,
                "machine": machine,
                "soname": soname,
                "needed": needed,
            })

    # 边界分析：vendor 未满足的依赖落到 system lib
    report = {"elf_count": len(results), "errors": errors,
              "unresolved": {"32": [], "64": []},
              "system_needed": {"32": [], "64": []}}
    for key, vset, sset in (("32", vendor32, sys32), ("64", vendor64, sys64)):
        for name in sorted(all_needed[key] - vset):
            if name in sset:
                report["system_needed"][key].append(
                    {"name": name, "aosp": name in AOSP_PREFIX})
            else:
                report["unresolved"][key].append(name)

    with open(os.path.join(BASE, "elf_deps.json"), "w", encoding="utf-8") as f:
        json.dump({"elfs": results, "report": report}, f, ensure_ascii=False, indent=0)

    print("ELF 文件 %d 个（解析失败 %d）" % (len(results), len(errors)))
    for key in ("32", "64"):
        sn = report["system_needed"][key]
        un = report["unresolved"][key]
        aosp = [x["name"] for x in sn if x["aosp"]]
        priv = [x["name"] for x in sn if not x["aosp"]]
        print("\n[%s 位] 依赖 vendor 之外的库 %d 个：AOSP 自带 %d，疑似私有 %d，完全找不到 %d"
              % (key, len(sn), len(aosp), len(priv), len(un)))
        if priv:
            print("  私有(需带走)：", ", ".join(priv[:24]) + (" ..." if len(priv) > 24 else ""))
        if un:
            print("  找不到     ：", ", ".join(un[:16]) + (" ..." if len(un) > 16 else ""))
    if errors:
        print("\n解析失败样例：", errors[:3])


if __name__ == "__main__":
    sys.exit(main())
