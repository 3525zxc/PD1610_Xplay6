# -*- coding: utf-8 -*-
"""从真机 adb 抓到的 vendor_all.txt 生成 LineageOS proprietary-files.txt。

用法:
  adb shell "find /system/vendor -type f" > vendor_all.txt
  py make_proprietary.py

规则:
  - 去掉 /system 前缀（LineageOS 以 system 根为基准）
  - 排除 vivo 运营商 overlay / CTA 资源（类原生不需要，且多为 APK 资源）
  - 排除 apk / odex / oat / 资源包，只留 lib / lib64 / etc / firmware / bin
  - 输出按目录排序，便于人工裁剪
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "vendor_all.txt"
OUT = HERE / "proprietary-files.txt"
EXCLUDE_DIRS = ("/CTA/", "/Cambodia/", "/ChinaMobile/", "/ChinaTelecom/",
                "/ChinaUnicom/", "/Indonesia", "/Latam", "/Malaysia",
                "/Thailand", "/Telefonica", "/Vodafone", "/overlay/",
                "/Philippines", "/Vietnam", "/India", "/EU", "/Turkey",
                "/Russia", "/Mexico", "/Brazil", "/Singapore", "/HongKong",
                "/Taiwan", "/Korea", "/Japan", "/Australia", "/SouthAfrica")
KEEP_EXT = (".so", ".xml", ".conf", ".ini", ".bin", ".fw", ".mbn", ".dat",
            ".txt", ".json", ".png", ".wav", ".bmd", ".elf", ".mbn", ".qcom")
KEEP_DIRS = ("/lib/", "/lib64/", "/etc/", "/firmware/", "/bin/", "/usr/")


def main():
    lines = [l.strip().replace("\r", "") for l in
             SRC.read_text(encoding="utf-8", errors="ignore").splitlines()]
    paths = sorted(set(l for l in lines if l.startswith("/system/")))
    kept, dropped = [], []
    for p in paths:
        rel = p[len("/system"):]
        if any(x in rel for x in EXCLUDE_DIRS):
            dropped.append(rel)
            continue
        if not any(x in rel for x in KEEP_DIRS):
            dropped.append(rel)
            continue
        if not rel.lower().endswith(KEEP_EXT):
            dropped.append(rel)
            continue
        kept.append(rel)
    header = [
        "# vivo Xplay6 (PD1610 / msm8996) proprietary blobs",
        "# Generated from a live device: adb shell \"find /system/vendor -type f\"",
        "# Source firmware: PD1610_D_7.13.15 (Android 7.1.1 / NMF26F)",
        "# Excluded %d carrier-overlay/resource files" % len(dropped),
        "# Review and trim before use: many blobs are Funtouch-specific",
        "",
    ]
    OUT.write_text("\n".join(header + kept) + "\n",
                   encoding="utf-8", newline="\n")
    print("input %d, kept %d, dropped %d -> %s"
          % (len(paths), len(kept), len(dropped), OUT))
    from collections import Counter
    for k, v in Counter("/".join(x.split("/")[:3]) for x in kept).most_common(12):
        print("  %-40s %d" % (k, v))


if __name__ == "__main__":
    main()
