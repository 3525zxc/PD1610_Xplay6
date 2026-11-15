# -*- coding: utf-8 -*-
"""在已装载 firehose 的 9008 端口上做一次握手探测（只读，不发写命令）。"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
BAUD = 115200


def send(ser, xml, wait=3.0):
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    ser.reset_input_buffer()
    ser.write(xml)
    ser.flush()
    print("  >> %s" % xml.decode("utf-8", "replace"))
    buf = b""
    t0 = time.time()
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if buf.rstrip().endswith(b"</data>"):
                break
        else:
            time.sleep(0.05)
    print("  << %d 字节: %s" % (len(buf), buf[:400].decode("utf-8", "replace")))
    return buf


def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1, write_timeout=5)
    except Exception as e:
        print("[x] 打不开 %s: %s" % (PORT, e))
        return 1

    print("[*] 已打开 %s" % PORT)
    try:
        print("\n[1] 空白应答测试")
        send(ser, "<?xml version=\"1.0\" encoding=\"UTF-8\" ?><data></data>", wait=2.0)

        print("\n[2] getStorageInfo")
        send(ser, "<?xml version=\"1.0\" encoding=\"UTF-8\" ?><data><getStorageInfo/></data>", wait=3.0)

        print("\n[3] 读 GPT 头（LUN0, 第0扇区，1个扇区）")
        send(ser,
             '<?xml version="1.0" encoding="UTF-8" ?><data>'
             '<read SECTOR_SIZE_IN_BYTES="4096" num_partitions="6" '
             'physical_partition_number="0" start_sector="0" NUM_SECTORS="1"/></data>',
             wait=3.0)
    finally:
        ser.close()
        print("\n[*] 端口已关闭")
    return 0


if __name__ == "__main__":
    sys.exit(main())
