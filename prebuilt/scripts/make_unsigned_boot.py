import struct, hashlib, os

SRC = r'D:\16\PD1610_81\backup\81_boot_LUN4.bin'   # 8.1 真实 boot 分区回读
OUT_OFFICIAL = r'D:\16\PD1610_81\work\boot_81_official.img'
OUT_TEST = r'D:\16\PD1610_81\work\boot_81_unsigned_test.img'
IMG = 58729728                                      # 官方 boot.img 实际大小


def align(x, a):
    return (x + a - 1) // a * a


with open(SRC, 'rb') as f:
    d = bytearray(f.read(IMG))
assert len(d) == IMG, len(d)
assert d[:8] == b'ANDROID!', d[:8]

(kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
 second_size, second_addr, tags_addr, page_size) = struct.unpack_from('<8I', d, 8)
header_version, os_version = struct.unpack_from('<2I', d, 40)

sig_off = d.find(b'AndroidVerifiedBootSignature')
print('=== 8.1 boot header ===')
print('  magic          :', bytes(d[:8]).decode())
print('  page_size      :', page_size)
print('  kernel_size    :', kernel_size)
print('  ramdisk_size   :', ramdisk_size)
print('  second_size    :', second_size)
print('  header_version :', header_version)
print('  os_version     : 0x%08X' % os_version)
print('  signature magic @', sig_off)

k_start = page_size
k_end = k_start + kernel_size
k_pad_end = k_start + align(kernel_size, page_size)
r_start = k_pad_end
r_end = r_start + ramdisk_size
r_pad_end = r_start + align(ramdisk_size, page_size)
L = page_size + align(kernel_size, page_size) + align(ramdisk_size, page_size)
print('  kernel  [%d, %d)  padding -> %d' % (k_start, k_end, k_pad_end))
print('  ramdisk [%d, %d)  padding -> %d' % (r_start, r_end, r_pad_end))
print('  signed length L =', L, '(%.2f MB)' % (L / 1048576))

# 选一个位于已签名范围 L 内、但不属于任何被加载内容的对齐填充字节
if k_pad_end > k_end:
    target, region = k_end, 'kernel alignment padding'
elif r_pad_end > r_end and r_end < L:
    target, region = r_end, 'ramdisk alignment padding'
else:
    raise SystemExit('[X] 没有可用的对齐填充字节，停止（不做破坏性改动）')

assert target < L, (target, L)
assert d[target] == 0, ('padding 不是 0', target, d[target])
h_before = hashlib.sha256(d[:L]).hexdigest()
print('  chosen byte    : offset %d (%s), 原值 0x%02X' % (target, region, d[target]))

with open(OUT_OFFICIAL, 'wb') as f:
    f.write(d)

d[target] = 0x01
h_after = hashlib.sha256(d[:L]).hexdigest()
with open(OUT_TEST, 'wb') as f:
    f.write(d)

diff = sum(1 for a, b in zip(open(OUT_OFFICIAL, 'rb').read(), open(OUT_TEST, 'rb').read()) if a != b)
print('=== 结果 ===')
print('  签名输入 SHA256 前 :', h_before)
print('  签名输入 SHA256 后 :', h_after)
print('  验签必然失败       :', h_before != h_after)
print('  两镜像差异字节数   :', diff, '(应为 1)')
print('  kernel/ramdisk/签名 DER 均未改动')
print('  官方还原镜像       :', OUT_OFFICIAL)
print('  测试镜像           :', OUT_TEST)
