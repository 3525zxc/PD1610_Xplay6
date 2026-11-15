# -*- coding: utf-8 -*-
"""步骤 3：验证 aboot 在 unlocked 状态下是否跳过 boot 签名校验。

用 9008 读回的整块 boot 分区构造两份镜像，只差首扇区 cmdline 标记：
  boot_stock.img    —— 原样，vivo DER 签名完整
  boot_patched.img  —— cmdline 中 PD1610_D_7.13.15 -> CFWTEST_9008，签名必然失效

用法:
  py boot_sig_test.py --build       生成并校验两份镜像（不碰设备）
  py boot_sig_test.py --info        打印镜像摘要
"""
import argparse
import hashlib
import os
import pathlib

EXP = pathlib.Path(r"C:\qfilx\exp")
FULL = EXP / "boot_full.bin"
ORIG4K = EXP / "boot_page0_orig.bin"
PATCH4K = EXP / "boot_page0_patched.bin"
STOCK = EXP / "boot_stock.img"
PATCHED = EXP / "boot_patched.img"

SS = 4096
# 镜像内容 0xE30000 + DER 证书链 0x2000
IMG_END = 0xE32000
OLD = b"PD1610_D_7.13.15"
NEW = b"CFWTEST_9008"


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def build():
    full = FULL.read_bytes()
    print("boot_full.bin: %d 字节  sha=%s" % (len(full), sha(full)))
    assert len(full) == 24576 * SS, "整分区长度不对"
    assert full[:8] == b"ANDROID!", "boot magic 不对"

    o4 = ORIG4K.read_bytes()
    p4 = PATCH4K.read_bytes()
    assert len(o4) == SS and len(p4) == SS
    assert o4 == full[:SS], "原始首扇区备份与当前分区不一致，禁止继续"
    print("首扇区原始备份与分区一致")

    diff = [i for i in range(SS) if o4[i] != p4[i]]
    assert diff, "改动版与原始版完全相同"
    assert all(64 <= i < 576 for i in diff), "改动溢出 cmdline 区: %s" % diff[:10]
    assert OLD in bytes(o4[64:576]) and NEW in bytes(p4[64:576])
    print("首扇区差异 %d 字节，全部落在 cmdline 区 [0x40,0x240)：%s -> %s"
          % (len(diff), OLD.decode(), NEW.decode()))

    head = full[:IMG_END]
    stock = head
    patched = p4 + full[SS:IMG_END]
    assert len(stock) == len(patched) == IMG_END
    d2 = [i for i in range(len(stock)) if stock[i] != patched[i]]
    assert d2 == diff, "整镜像差异与首扇区不一致"
    assert stock[0xE30000:0xE30004] == b"\x30\x82\x04\xfc", "DER 证书头缺失"
    assert patched[0xE30000:] == stock[0xE30000:], "签名区被改动"

    STOCK.write_bytes(stock)
    PATCHED.write_bytes(patched)
    print("\n已生成:")
    print("  %s  %d B  sha=%s" % (STOCK, len(stock), sha(stock)))
    print("  %s  %d B  sha=%s" % (PATCHED, len(patched), sha(patched)))
    print("  两份仅 %d 字节不同，签名区(0xE30000+)完全一致" % len(d2))
    print("\n对照测试（设备须在 fastboot）:")
    print("  fastboot boot %s" % STOCK)
    print("  fastboot boot %s" % PATCHED)
    print("若两者都返回 OKAY 并重启 -> 签名校验被跳过；若改动版被拒 -> 校验仍生效")


def info():
    for p in (STOCK, PATCHED):
        if p.exists():
            b = p.read_bytes()
            print("%s  %d B  sha=%s" % (p, len(b), sha(b)))
        else:
            print("%s  不存在" % p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--info", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
    else:
        info()
