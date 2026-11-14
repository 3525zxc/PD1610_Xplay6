# -*- coding: utf-8 -*-
"""Round-5 实验：构建 boot 分区刷写载荷与 rawprogram XML（纯文件操作，不接触设备）

分区事实（来自 restore_81_all.xml，11-10 审计通过）：
  label=boot  physical_partition_number=4  start_sector=47370  num_partition_sectors=24576
  SECTOR_SIZE=4096  → 分区大小 24576*4096 = 100663296 B
"""
import hashlib, os, shutil, struct, sys

WORK = r'D:\16\PD1610_81\work'
BACK = r'D:\16\PD1610_81\backup'
SCR  = r'D:\16\PD1610_81\scripts'

PART_SECTORS = 24576
SECTOR = 4096
PART_SIZE = PART_SECTORS * SECTOR          # 100663296
START_SECTOR = 47370
LUN = 4

img_a = os.path.join(WORK, 'boot_81_official.img')      # A 官方 96MB 分区备份中的镜像部分
img_d = os.path.join(WORK, 'boot_81_D_footerless.img')  # D 等长清零签名尾部
part_official = os.path.join(BACK, '81_boot_LUN4.bin')  # 整分区官方备份

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

a = open(img_a, 'rb').read()
d = open(img_d, 'rb').read()
po = open(part_official, 'rb').read()

print('A image      : %d B  sha256=%s' % (len(a), sha256(img_a)))
print('D image      : %d B  sha256=%s' % (len(d), sha256(img_d)))
print('part backup  : %d B  sha256=%s' % (len(po), sha256(part_official)))

assert len(a) == len(d), 'A/D 长度必须相同'
assert len(po) == PART_SIZE, '官方分区备份大小与 GPT 不符: %d' % len(po)

# --- D 的精确变更：只有 [L, end) 被清零 ---
L = 58724352
tail_start, tail_end = L, len(d)
assert a[:L] == d[:L], 'D 的 [0:L] 与 A 不同（不应发生）'
assert set(d[L:]) == {0}, 'D 的签名尾部并非全零'
assert set(a[L:]) != {0}, 'A 的签名尾部本应非零'
print('\n[D 变更核验] [0:%d) 与 A 完全一致；[%d:%d) 全零（A 侧非零）→ 单一变量成立' % (L, L, len(d)))
print('  被清零区间长度 = %d B (与 manifest tail_region 一致: %s)' % (tail_end - tail_start, (tail_end - tail_start) == 5376))

# --- 官方整分区备份 前 58729728 B 应与 A 镜像一致 ---
if po[:len(a)] == a:
    print('  官方分区备份前段与 A 镜像一致 ✓（分区 = 镜像 + 尾部填充）')
else:
    # 允许差异（分区里镜像区可能非全等），做首个差异定位
    n = min(len(po), len(a))
    diff = next((i for i in range(n) if po[i] != a[i]), None)
    print('  官方分区备份前段与 A 镜像首个差异 @0x%X（将按镜像覆盖）' % (diff if diff is not None else -1))

# --- 构造整分区载荷 ---
payload_d = bytearray(po)                       # 以官方整分区为底
payload_d[:len(d)] = d                          # 覆盖镜像区为 D（仅签名尾被清零）
payload_o = bytearray(po)                       # 官方还原载荷 = 原备份
out_d = os.path.join(WORK, 'flash_boot_D_full.bin')
out_o = os.path.join(WORK, 'flash_boot_official_full.bin')
with open(out_d, 'wb') as f: f.write(payload_d)
with open(out_o, 'wb') as f: f.write(payload_o)

# 不变量校验
chk = open(out_d, 'rb').read()
assert len(chk) == PART_SIZE
assert chk[:len(d)] == d, '载荷镜像区与 D 不一致'
assert chk[len(d):] == po[len(d):], '载荷尾段与官方分区不一致'
delta = [i for i in range(PART_SIZE) if chk[i] != po[i]]
nonzero_tail = sum(1 for i in range(L, tail_end) if po[i] != 0)
print('\n[载荷不变量] flash_boot_D_full.bin 大小 %d；与官方整分区备份的差异字节数 = %d，区间 = [0x%X, 0x%X)'
      % (PART_SIZE, len(delta), delta[0], delta[-1] + 1))
print('  官方签名尾部非零字节数 = %d（尾部共 %d B，其余本就是 0x00 填充）' % (nonzero_tail, tail_end - L))
assert len(delta) == nonzero_tail, '差异字节数(%d) != 尾部非零字节数(%d)' % (len(delta), nonzero_tail)
assert delta[0] >= L and delta[-1] + 1 <= tail_end, '差异越出签名尾部区间'
print('  ✓ 差异完全落在 [0x%X, 0x%X)（签名尾部）内，字节数与尾部非零数一致 → 相对官方分区仅此一处变量'
      % (L, tail_end))
print('  flash_boot_D_full.bin      sha256=%s' % sha256(out_d))
print('  flash_boot_official_full.bin sha256=%s' % sha256(out_o))

# --- XML ---
def xml(path, filename, label):
    body = (
 '<?xml version="1.0" ?>\n'
 '<data>\n'
 '  <program SECTOR_SIZE_IN_BYTES="4096" file_sector_offset="0" filename="%s" label="%s" '
 'num_partition_sectors="%d" partofsingleimage="false" physical_partition_number="%d" '
 'readbackverify="false" size_in_KB="98304.0" sparse="false" start_sector="%d"/>\n'
 '</data>\n') % (filename, label, PART_SECTORS, LUN, START_SECTOR)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    print('\n写 XML: %s\n%s' % (path, body))

xml(os.path.join(SCR, 'flash_boot_D.xml'), 'flash_boot_D_full.bin', 'boot')
xml(os.path.join(SCR, 'restore_boot_only.xml'), 'flash_boot_official_full.bin', 'boot')
print('\n还原载荷 = 11-10 官方整分区备份逐字节副本（81_boot_LUN4.bin）')
