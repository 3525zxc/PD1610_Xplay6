"""只读分析 Xplay6 aboot：签名区结构、验签函数定位、跳过条件。
不写设备、不修改任何分区。输出 C:\\qfilx\\aboot_verify_probe.txt
"""
import pathlib
import struct
import sys

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

SRC = pathlib.Path(r"C:\qfilx\probe\aboot.bin")
OUT = pathlib.Path(r"C:\qfilx\aboot_verify_probe.txt")
D = SRC.read_bytes()

# ELF seg3: off 0x8000 -> va 0x91800000
BASE = 0x917F8000
CODE_OFF, CODE_END = 0x8000, 0x391558

lines = []


def log(s=""):
    lines.append(s)
    print(s)


def off2va(o):
    return BASE + o


def strings(lo, hi, minlen=4):
    out = []
    cur = b""
    for x in D[lo:hi]:
        if 32 <= x < 127:
            cur += bytes([x])
        else:
            if len(cur) >= minlen:
                out.append(cur.decode("ascii", "ignore"))
            cur = b""
    if len(cur) >= minlen:
        out.append(cur.decode("ascii", "ignore"))
    return out


def imm16(w):
    return (((w >> 16) & 0xF) << 12) | (w & 0xFFF)


log("=== aboot.bin 概览 ===")
log("size %d  ELF %s  BASE %s" % (len(D), D[:4] == b"\x7fELF", hex(BASE)))
log("")
log("=== 0x1000 段（seg1，疑似 MBN 签名/证书区）===")
for o in range(0x1000, 0x1060, 16):
    c = D[o:o + 16]
    log("  %06X  %s  %s" % (o, " ".join("%02X" % b for b in c),
                             "".join(chr(b) if 32 <= b < 127 else "." for b in c)))
log("  可打印串(0x1000-0x29a8): " + (" | ".join(strings(0x1000, 0x29a8)))[:1400])
log("")
log("=== 段外尾部非零分布 ===")
nz = [i for i, b in enumerate(D[CODE_END:], CODE_END) if b]
runs = []
if nz:
    st = pr = nz[0]
    for x in nz[1:]:
        if x - pr > 64:
            runs.append((st, pr))
            st = x
        pr = x
    runs.append((st, pr))
log("  非零字节 %d，区间 %d" % (len(nz), len(runs)))
for a, b in runs[:16]:
    log("   %s..%s (%d B)" % (hex(a), hex(b), b - a + 1))
log("")

KEYS = [
    b"Device is unlocked! Skipping verification",
    b"authorized_kernel",
    b"bootimage",
    b"incomplete or not signed",
    b"verification",
    b"verify",
    b"signature",
    b"rsa",
    b"RSA",
    b"hash",
    b"authenticat",
    b"securebootkey",
    b"Device tampered",
    b"ANDROID-BOOT!",
    b"unknown command or device is lock",
]

log("=== 验签相关字符串 ===")
targets = []
for k in KEYS:
    offs = []
    i = 0
    while True:
        i = D.find(k, i)
        if i < 0:
            break
        offs.append(i)
        i += 1
        if len(offs) >= 8:
            break
    log("  %-42s count>=%d" % (k.decode("ascii", "ignore")[:42], len(offs)))
    for o in offs[:3]:
        ctx = " | ".join(strings(max(0, o - 90), o + 110))[:200]
        log("     off=%s va=%s ctx=%s" % (hex(o), hex(off2va(o)), ctx))
        if CODE_OFF <= o < CODE_END:
            targets.append((k, o, off2va(o)))
log("")

# 交叉引用：字面池 + MOVW/MOVT
log("=== 交叉引用（字面池 / MOVW+MOVT）===")
refs = {}
for k, o, va in targets:
    lits = []
    for p in range(CODE_OFF, CODE_END - 3, 4):
        w = struct.unpack_from("<I", D, p)[0]
        if va - 0x100 <= w <= va + 0x100:
            lits.append((p, w))
    hits = []
    for p in range(CODE_OFF, CODE_END - 28, 4):
        w = struct.unpack_from("<I", D, p)[0]
        if (w & 0x0FF00000) != 0x03000000:
            continue
        reg = (w >> 12) & 0xF
        lo = imm16(w)
        for j in range(1, 6):
            w2 = struct.unpack_from("<I", D, p + 4 * j)[0]
            if (w2 & 0x0FF00000) == 0x03400000 and ((w2 >> 12) & 0xF) == reg:
                val = (imm16(w2) << 16) | lo
                if abs(val - va) <= 0x100:
                    hits.append((p, reg, val))
                break
    refs[k] = (lits, hits)
    log("  %-42s 字面池 %d  MOVW/MOVT %d" % (k.decode("ascii", "ignore")[:42], len(lits), len(hits)))
    for p, w in lits[:4]:
        log("     LIT  file=%s va=%s value=%s" % (hex(p), hex(off2va(p)), hex(w)))
    for p, reg, val in hits[:4]:
        log("     MOVT file=%s va=%s r%d=%s" % (hex(p), hex(off2va(p)), reg, hex(val)))
log("")

# 反汇编关键引用点附近
log("=== 关键引用点反汇编 ===")
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = True
SHOW = ("ldr", "ldrb", "movw", "movt", "bl", "blx", "cmp", "cmn", "beq", "bne",
        "b", "bx", "cbz", "cbnz", "tst", "teq", "str", "strb", "add", "sub", "mov", "mvn")
for k in [b"Device is unlocked! Skipping verification", b"authorized_kernel",
          b"incomplete or not signed", b"Device tampered"]:
    if k not in refs:
        continue
    lits, hits = refs[k]
    points = [p for p, _ in lits[:2]] + [p for p, _, _ in hits[:2]]
    if not points:
        continue
    log("--- %s ---" % k.decode("ascii", "ignore"))
    for p in points[:2]:
        st = max(CODE_OFF, p - 0x180)
        log("  引用点 file=%s va=%s，反汇编 %s..%s" % (hex(p), hex(off2va(p)), hex(st), hex(p + 0x60)))
        cnt = 0
        for ins in md.disasm(D[st:p + 0x60], off2va(st)):
            if ins.mnemonic in SHOW:
                mark = "  <<<" if off2va(p) - 0x20 <= ins.address <= off2va(p) + 0x20 else ""
                log("    %s %-8s %s%s" % (hex(ins.address), ins.mnemonic, ins.op_str, mark))
                cnt += 1
                if cnt > 60:
                    break
log("")
log("DONE")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n[written] %s  lines=%d" % (OUT, len(lines)))
