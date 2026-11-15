# -*- coding: utf-8 -*-
"""试探这个 firehose 支持哪些标签（只读探测，不发写命令）"""
import time

import serial

PORT = "COM5"
ser = serial.Serial(PORT, 115200, timeout=1, write_timeout=10)


def exchange(inner, wait=4.0, expect_raw=0):
    xml = ('<?xml version="1.0" encoding="UTF-8" ?><data>%s</data>' % inner).encode()
    ser.reset_input_buffer()
    ser.write(xml)
    ser.flush()
    buf = b""
    t0 = time.time()
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if buf.rstrip().endswith(b"</data>"):
                break
        else:
            time.sleep(0.02)
    text = buf.decode("utf-8", "replace")
    raw = b""
    if 'rawmode="true"' in text and expect_raw:
        t0 = time.time()
        while len(raw) < expect_raw and time.time() - t0 < 30:
            n = ser.in_waiting
            if n:
                raw += ser.read(min(n, expect_raw - len(raw)))
            else:
                time.sleep(0.01)
        try:
            tail = b""
            t0 = time.time()
            while time.time() - t0 < 5:
                n = ser.in_waiting
                if n:
                    tail += ser.read(n)
                    if tail.rstrip().endswith(b"</data>"):
                        break
                else:
                    time.sleep(0.02)
            text += " | TAIL:" + tail.decode("utf-8", "replace")
        except Exception as e:
            text += " | TAIL ERR:%s" % e
    tag = inner.split()[0].rstrip("/>")
    ok = 'value="ACK"' in text
    print("[%-6s] %-52s -> %s %s" % ("ACK" if ok else "NAK/无", inner[:52],
                                     "raw=%d" % len(raw) if raw else "",
                                     "| " + text.replace("\n", " ")[:150]))
    return ok, raw, text


tests = [
    ('<configure MemoryName="ufs" />', 0),
    ('<configure MemoryName="emmc" />', 0),
    ('<configure />', 0),
    ('<read SECTOR_SIZE_IN_BYTES="4096" num_partitions="6" physical_partition_number="0" start_sector="0" NUM_SECTORS="1" />', 4096),
    ('<read SECTOR_SIZE_IN_BYTES="512" num_partitions="6" physical_partition_number="0" start_sector="0" NUM_SECTORS="2" />', 1024),
]

for inner, rawlen in tests:
    try:
        exchange(inner, wait=5.0, expect_raw=rawlen)
    except Exception as e:
        print("[ERR  ] %s -> %s" % (inner[:52], e))
    time.sleep(0.5)

ser.close()
print("done")
