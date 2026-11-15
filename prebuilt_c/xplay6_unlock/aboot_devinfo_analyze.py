# -*- coding: utf-8 -*-
"""静态解析 Xplay6 aboot(ELF32 ARM)：定位 device_info 结构体字段偏移。

思路：
  1. 解析 ELF program header，建立 文件偏移 <-> 运行时虚拟地址 映射
  2. 找 "Device tampered" / "Device unlocked" 等字符串，算出 VA
  3. 在代码段里找指向这些字符串的字面池(literal pool)项，反推引用它们的 LDR
  4. 在引用附近反汇编，找 LDRB/LDR [rX, #imm] —— imm 即结构体字段偏移
只读，不接触设备。
"""
import struct
import pathlib
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_MEM, ARM_OP_REG, ARM_OP_IMM

BIN = pathlib.Path(r"C:\qfilx\probe\aboot.bin")
D = BIN.read_bytes()

phoff = struct.unpack_from("<I", D, 0x1C)[0]
phentsz = struct.unpack_from("<H", D, 0x2A)[0]
phnum = struct.unpack_from("<H", D, 0x2C)[0]
SEGS = []
for i in range(phnum):
    o = phoff + i * phentsz
    typ, off, va, pa, fsz, msz, flg, al = struct.unpack_from("<IIIIIIII", D, o)
    if typ == 1 and fsz > 0x10000:
        SEGS.append((off, va, pa, fsz))
    print("PH%d type=%d off=%s va=%s pa=%s filesz=%s" %
          (i, typ, hex(off), hex(va), hex(pa), hex(fsz)))

SEG_OFF, SEG_VA, SEG_PA, SEG_SIZE = SEGS[0]
DELTA_VA = SEG_VA - SEG_OFF
DELTA_PA = SEG_PA - SEG_OFF
print("\n主段 off=%s va=%s pa=%s delta_va=%s delta_pa=%s" %
      (hex(SEG_OFF), hex(SEG_VA), hex(SEG_PA), hex(DELTA_VA), hex(DELTA_PA)))


def off2va(o, base=DELTA_VA):
    return base + o


def va2off(v, base=DELTA_VA):
    return v - base


def printable(b):
    return len(b) >= 4 and all(32 <= x < 127 for x in b)


STRINGS = [
    b"Device tampered", b"Device unlocked", b"critical unlocked",
    b"Charger screen", b"ANDROID-BOOT!", b"Device is unlocked! Skipping verification",
    b"No devinfo partition", b"Cannot read device info", b"reset_device_info",
    b"device is locked. Cannot erase", b"get_unlock_ability", b"oem device-info",
]
print("\n--- 字符串与候选指针 ---")
targets = {}
for s in STRINGS:
    offs = []
    i = 0
    while True:
        i = D.find(s, i)
        if i < 0:
            break
        offs.append(i)
        i += 1
    print("%-45s offs=%s" % (s.decode("ascii", "ignore"),
                             [hex(x) for x in offs[:6]]))
    for o in offs[:2]:
        targets[DELTA_VA + o] = (s.decode("ascii", "ignore"), o)
        if DELTA_PA != DELTA_VA:
            targets[DELTA_PA + o] = (s.decode("ascii", "ignore"), o)

# 扫描整个段内的 4 字节字面，找指向已知字符串的指针
hits = []
for o in range(SEG_OFF, min(SEG_OFF + SEG_SIZE, len(D)) - 3, 4):
    w = struct.unpack_from("<I", D, o)[0]
    if w in targets:
        hits.append((o, w, targets[w][0], targets[w][1]))
print("\n--- 字面池命中 (%d) ---" % len(hits))
for o, w, name, so in hits[:60]:
    print("  literal@%s -> %s [%s] string@%s" % (hex(o), hex(w), name, hex(so)))

if not hits:
    print("!! 未直接命中，用字面集合反推运行时基址")
    words = set()
    for o in range(SEG_OFF, min(SEG_OFF + SEG_SIZE, len(D)) - 3, 4):
        words.add(struct.unpack_from("<I", D, o)[0])
    fos = [D.find(s) for s in STRINGS[:4] if D.find(s) > 0]
    print("  不同字面数=%d  目标偏移=%s" % (len(words), [hex(x) for x in fos]))
    bases = []
    if fos:
        for w in words:
            k = w - fos[0]
            if 0x70000000 <= k <= 0xB0000000 and all((k + f) in words for f in fos[1:]):
                bases.append(k)
    print("  一致基址差候选:", [hex(k) for k in bases[:8]])
    if bases:
        DELTA_VA = bases[0]
        print("  采用基址差 %s" % hex(DELTA_VA))
        for s in STRINGS:
            fo = D.find(s)
            if fo > 0:
                targets[DELTA_VA + fo] = (s.decode("ascii", "ignore"), fo)
        for o in range(SEG_OFF, min(SEG_OFF + SEG_SIZE, len(D)) - 3, 4):
            w = struct.unpack_from("<I", D, o)[0]
            if w in targets:
                hits.append((o, w, targets[w][0], targets[w][1]))
        print("  重新命中字面池 %d 处" % len(hits))


def disasm_around(fo, before=0x120, after=0x40, mode="arm"):
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM if mode == "arm" else CS_MODE_THUMB)
    md.detail = True
    start = max(SEG_OFF, fo - before)
    code = D[start:fo + after]
    va = off2va(start)
    out = []
    for ins in md.disasm(code, va):
        out.append((ins.address, ins.mnemonic, ins.op_str, ins))
    return out


print("\n--- 引用 device-info 字符串附近的代码 ---")
for lo, w, name, so in hits[:8]:
    if "tampered" not in name and "unlocked" not in name and "Charger" not in name:
        continue
    print("\n### literal@%s -> %s" % (hex(lo), name))
    ins = disasm_around(lo, before=0xA0, after=0x20)
    for addr, mn, op, _ in ins[-36:]:
        print("  %s  %-8s %s" % (hex(addr), mn, op))

# 快速指令编码扫描：ARM 模式下 LDRB/LDR/STRB 立即数小偏移
# 位 27-20: LDRB=01011101(0x5D) LDR=01011001(0x59) STRB=01011100(0x5C)
print("\n--- 快速模式扫描：ARM LDRB/LDR/STRB 小偏移指令 ---")
PAT = {0x05D00000: "LDRB", 0x05900000: "LDR", 0x05C00000: "STRB"}
small = []
for o in range(SEG_OFF, min(SEG_OFF + SEG_SIZE, len(D)) - 3, 4):
    w = struct.unpack_from("<I", D, o)[0]
    k = w & 0x0FF00000
    if k in PAT and 0x0D <= (w & 0xFFF) <= 0x20:
        small.append((o, w, PAT[k], w & 0xFFF, (w >> 16) & 0xF))
print("命中 %d 条" % len(small))
from collections import Counter
for imm, n in sorted(Counter(x[3] for x in small).items()):
    print("  imm=0x%02X : %d 条" % (imm, n))
for o, w, m, imm, rn in small[:60]:
    print("  off=%s word=%s %-5s r%d,[r%d,#0x%X]" %
          (hex(o), hex(w), m, (w >> 12) & 0xF, rn, imm))

# LK 用 MOVW/MOVT 构造绝对地址，不是字面池：按立即数配对定位字符串引用
print("\n--- MOVW/MOVT 配对定位字符串引用 ---")
BASE = 0x917F8000  # p_vaddr - segment file offset
str_vas = {}
for s in STRINGS:
    fo = D.find(s)
    if fo > 0:
        str_vas[BASE + fo] = s.decode("ascii", "ignore")
print("字符串 VA(前 6):", [(hex(v), n) for v, n in list(str_vas.items())[:6]])


def imm16(w):
    return (((w >> 16) & 0xF) << 12) | (w & 0xFFF)


mv = []
for o in range(SEG_OFF, min(SEG_OFF + SEG_SIZE, len(D)) - 20, 4):
    w = struct.unpack_from("<I", D, o)[0]
    if (w & 0x0FF00000) != 0x03000000:      # MOVW
        continue
    reg = (w >> 12) & 0xF
    lo = imm16(w)
    for j in range(1, 5):
        w2 = struct.unpack_from("<I", D, o + 4 * j)[0]
        if (w2 & 0x0FF00000) == 0x03400000 and ((w2 >> 12) & 0xF) == reg:  # MOVT
            val = (imm16(w2) << 16) | lo
            if val in str_vas:
                mv.append((o, reg, val, str_vas[val]))
            break
print("命中 %d 处:" % len(mv))
for o, reg, val, name in mv[:40]:
    print("  off=%s r%d -> %s [%s]" % (hex(o), reg, hex(val), name))

# 把命中点附近的代码反汇编出来，看结构体字段加载偏移
print("\n--- 命中点附近反汇编 (每处 ±0x140) ---")
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = True
for o, reg, val, name in mv[:6]:
    print("\n### %s  @file %s" % (name, hex(o)))
    st = max(SEG_OFF, o - 0x140)
    code = D[st:o + 0x80]
    ins = list(md.disasm(code, off2va(st)))
    for x in ins:
        if x.address < off2va(o) - 0xC0:
            continue
        mark = ""
        for op in x.operands:
            if op.type == ARM_OP_MEM and 0x08 <= op.mem.disp <= 0x24:
                mark = "   <<< 字段 #0x%02X" % op.mem.disp
        if x.mnemonic in ("ldrb", "ldr", "strb", "str", "cmp", "mov", "movw", "movt", "bl", "tst", "beq", "bne"):
            print("  %s  %-8s %s%s" % (hex(x.address), x.mnemonic, x.op_str, mark))

# 单独看 0xF900-0xFC00 那簇连续小偏移 LDRB/STRB
print("\n--- 簇 0xF900..0xFBC0 反汇编 ---")
st = 0xF900
for x in md.disasm(D[st:0xFBC0], off2va(st)):
    if x.mnemonic in ("ldrb", "strb", "ldr", "str", "cmp", "mov", "bl", "tst", "b", "beq", "bne", "add", "sub"):
        print("  %s  %-8s %s" % (hex(x.address), x.mnemonic, x.op_str))

# 格式化串实际以 \t 开头，按 ±8 字节窗口重找引用，定位 oem device-info 处理函数
print("\n--- 扩展：格式化串 (含前导字符) 的 MOVW/MOVT 引用 ---")
FO = {"tampered": 0x8875D, "unlocked": 0x88775,
      "critical": 0x88794, "charger": 0x887AD}
for nm, fo in FO.items():
    print("  %-9s 原文: %r" % (nm, D[fo - 12:fo + 40]))
ext = {}
for nm, fo in FO.items():
    for delta in range(-8, 9):
        ext[BASE + fo + delta] = (nm, delta)
mv2 = []
for o in range(SEG_OFF, min(SEG_OFF + SEG_SIZE, len(D)) - 20, 4):
    w = struct.unpack_from("<I", D, o)[0]
    if (w & 0x0FF00000) != 0x03000000:
        continue
    reg = (w >> 12) & 0xF
    lo = imm16(w)
    for j in range(1, 5):
        w2 = struct.unpack_from("<I", D, o + 4 * j)[0]
        if (w2 & 0x0FF00000) == 0x03400000 and ((w2 >> 12) & 0xF) == reg:
            val = (imm16(w2) << 16) | lo
            if val in ext:
                mv2.append((o, reg, val, ext[val]))
            break
print("命中 %d 处:" % len(mv2))
for o, reg, val, (nm, dl) in mv2[:40]:
    print("  off=%s r%d -> %s [%s %+d]" % (hex(o), reg, hex(val), nm, dl))

print("\n--- 引用点附近反汇编（看字段加载）---")
md2 = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md2.detail = True
for o, reg, val, (nm, dl) in mv2[:8]:
    print("\n### %s @file %s" % (nm, hex(o)))
    st = max(SEG_OFF, o - 0x180)
    for x in md2.disasm(D[st:o + 0x60], off2va(st)):
        if x.address < off2va(o) - 0x150:
            continue
        mark = ""
        for op in x.operands:
            if op.type == ARM_OP_MEM and 0x0 <= op.mem.disp <= 0x30:
                mark = "   <<< #0x%02X" % op.mem.disp
        if x.mnemonic in ("ldrb", "ldr", "strb", "str", "cmp", "cmn", "tst",
                          "mov", "movw", "movt", "bl", "beq", "bne", "add", "sub"):
            print("  %s  %-8s %s%s" % (hex(x.address), x.mnemonic, x.op_str, mark))

# 全局：在代码段里找 LDRB/LDR [rX,#imm]，imm 落在 0x0D-0x20 的候选字段区
# 该段 3.6MB 全量反汇编较慢，默认跳过，加 --full 才执行
import sys
if "--full" not in sys.argv:
    print("\n--- 全段扫描已跳过（加 --full 启用）---")
    sys.exit(0)
print("\n--- 全段扫描：结构体小偏移加载指令 (imm 0x08..0x30) ---")
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
md.detail = True
found = []
start = SEG_OFF
code = D[start:start + SEG_SIZE]
for ins in md.disasm(code, off2va(start)):
    if ins.mnemonic not in ("ldrb", "ldrsb", "ldr", "strb", "str"):
        continue
    for op in ins.operands:
        if op.type == ARM_OP_MEM and op.mem.base != 0 and op.mem.disp:
            disp = op.mem.disp
            if 0x08 <= disp <= 0x30:
                found.append((ins.address, ins.mnemonic, ins.op_str, disp))
                break
print("命中 %d 条，按偏移汇总:" % len(found))
from collections import Counter
c = Counter(x[3] for x in found)
for disp, n in sorted(c.items()):
    print("  #0x%02X : %d 条" % (disp, n))
print("\n前 60 条明细:")
for a, mn, op, disp in found[:60]:
    print("  %s  %-6s %s" % (hex(a), mn, op))

# 输出 0x10-0x20 区间的指令附近上下文，方便人工判断
print("\n--- 只列偏移 0x0D..0x1F 的指令 (最多 80 条) ---")
n = 0
for a, mn, op, disp in found:
    if 0x0D <= disp <= 0x1F:
        print("  %s  %-6s %s" % (hex(a), mn, op))
        n += 1
        if n >= 80:
            break
