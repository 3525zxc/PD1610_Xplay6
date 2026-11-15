import struct, hashlib, base64, sys, os

def tlv(buf, off):
    tag = buf[off]; l = buf[off+1]; o = off+2
    if l & 0x80:
        n = l & 0x7f
        l = int.from_bytes(buf[o:o+n], 'big'); o += n
    return tag, o, l

def pub_from_cert(der):
    # der = X.509 certificate
    _, o, _ = tlv(der, 0)          # tbsCertificate
    _, o2, l2 = tlv(der, o)        # [0] version or serial; walk children
    p = o
    for _ in range(1):
        pass
    # walk: optional [0] version, serial, sigalg, issuer, validity, subject, spki
    def children(buf, start, end):
        out = []
        while start < end:
            t, oo, ll = tlv(buf, start)
            out.append((t, oo, ll, start))
            start = oo + ll
        return out
    t, oo, ll = tlv(der, 0)
    kids = children(der, oo, oo+ll)
    # tbs is kids[0]
    _, to, tl, _ = kids[0]
    tk = children(der, to, to+tl)
    spki = None
    for t, oo2, ll2, _ in tk:
        if t == 0x30 and spki is None:
            try:
                sub = children(der, oo2, oo2+ll2)
                if len(sub) == 2 and sub[0][0] == 0x30 and sub[1][0] == 0x03:
                    pass
            except Exception:
                pass
    # simpler: find last SEQUENCE that has BITSTRING>SEQ>INT,INT  -> use position of "OID rsaEncryption"
    idx = der.find(b'\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01')
    if idx < 0:
        raise ValueError("no rsaEncryption OID")
    # after OID+NULL comes BITSTRING
    j = idx + 11
    if der[j] == 0x05: j += 2
    if der[j] != 0x03: raise ValueError("no bitstring after oid")
    bo, bl = tlv(der, j)[1], tlv(der, j)[2]
    inner = bo + 1
    so, sl = tlv(der, inner)[1], tlv(der, inner)[2]
    ko = so
    t1 = tlv(der, ko); n = int.from_bytes(der[t1[1]:t1[1]+t1[2]], 'big')
    t2 = tlv(der, t1[1]+t1[2]); e = int.from_bytes(der[t2[1]:t2[1]+t2[2]], 'big')
    return n, e

def parse_sig_block(blk):
    """blk = 0x1500 bytes starting at DER"""
    t, o, l = tlv(blk, 0)
    assert t == 0x30
    end = o + l
    kids = []
    p = o
    while p < end:
        tt, oo, ll = tlv(blk, p)
        kids.append((tt, oo, ll, p))
        p = oo + ll
    cert = sig = params = None
    for tt, oo, ll, start in kids:
        if tt == 0x30 and blk[oo] == 0x30 and cert is None and ll > 500:
            cert = blk[oo:oo+ll]
        if tt == 0x30:
            # params seq: PRINTABLESTRING + INTEGER
            if blk[oo] == 0x13:
                params = blk[oo:oo+ll]
        if tt == 0x04 and ll == 256 and sig is None:
            sig = blk[oo:oo+ll]
    return cert, sig, params, kids

def recover(n, e, sig):
    for name, val in (("be", int.from_bytes(sig, 'big')), ("le", int.from_bytes(sig, 'little'))):
        m = pow(val, e, n).to_bytes((n.bit_length()+7)//8, 'big')
        if m[:2] == b'\x00\x01':
            return name, m, m[-32:]
    return None, None, None
