# -*- coding: utf-8 -*-
"""Check whether this machine can actually build AND flash a PD1610 ROM.

Run: py verify_prereq.py
It reports real, measured facts only. It does not pretend a build succeeded.
"""
import os
import pathlib
import shutil
import subprocess

HERE = pathlib.Path(__file__).parent
ROOT = pathlib.Path(os.environ.get("ANDROID_ROOT", r"D:\android\lineage"))
rows = []


def add(name, ok, detail):
    rows.append((name, ok, detail))


def tool(name):
    try:
        r = subprocess.run([name, "--version"], capture_output=True,
                           text=True, errors="ignore", timeout=8)
        return r.returncode == 0 or bool((r.stdout + r.stderr).strip())
    except Exception:
        return False


add("构建操作系统", os.name != "nt",
    "当前 %s；Android 必须在 Linux 编译" % ("Windows" if os.name == "nt" else os.name))
for t in ("git", "java", "make", "gcc", "repo", "python3"):
    add("工具 " + t, tool(t), "已找到" if tool(t) else "未安装")
try:
    free = shutil.disk_usage("D:\\" if os.name == "nt" else "/").free / 1024 ** 3
    add("可用磁盘 >= 200 GB", free >= 200, "当前 D: 可用 %.1f GB" % free)
except Exception:
    add("可用磁盘 >= 200 GB", False, "无法读取")

add("内核源码 kernel/vivo/msm8996", (ROOT / "kernel/vivo/msm8996").is_dir(),
    "未找到；vivo 未公开 PD1610 内核源码，需自行提供 GPL 发布包")
add("设备树 device/vivo/pd1610", (ROOT / "device/vivo/pd1610").is_dir(),
    "本目录骨架已生成，但尚未放入 LineageOS 源码树")
add("vendor blobs vendor/vivo/pd1610", (ROOT / "vendor/vivo/pd1610").is_dir(),
    "需运行 extract-files.sh 从真机提取")
add("proprietary-files.txt", (HERE / "proprietary-files.txt").exists(),
    "由 make_proprietary.py 从真机 1609 个文件生成")
add("vendor_all.txt", (HERE / "vendor_all.txt").exists(),
    "真机 /system/vendor 全量清单")

print("=== 编译前提 ===")
for n, ok, d in rows:
    print("  [%s] %-36s %s" % ("OK" if ok else "--", n, d))

print("\n=== 刷机前提（这两项与编译无关，且当前未解决）===")
print("  [!!] 门① boot 签名：量产 aboot 校验 boot [0,0xE30000) 的 vivo DER 证书链；")
print("       实测改 1 字节即每 5 秒卡 logo。自编译的 boot.img 无法通过。")
print("  [!!] 门② dm-verity：量产 boot 的 fstab.qcom 为 /system ... wait,verify；")
print("       设备信任的 /verity_key 是 vivo 私钥，与包里 AOSP verity.pk8 模数不匹配。")
print("  => 需要官方签名的工程 boot（eng.root，fstab 关闭 verify）+ 配套 system。")

bad = [n for n, ok, _ in rows if not ok]
print("\n=== 结论 ===")
print("  缺失 %d 项：%s" % (len(bad), ", ".join(bad)))
print("  即使全部补齐并编译成功，仍受上面两道门限制，产物目前刷不进去。")
print("  最短路径：拿到博主那套 boot+system 完整包，验签后整套刷。")
