import struct, hashlib, sys, os
sys.path.insert(0,'.')
from bootsig import tlv, pub_from_cert, parse_sig_block, recover

def hdr(d):
    k=struct.unpack_from('<I',d,8)[0]; r=struct.unpack_from('<I',d,16)[0]
    s=struct.unpack_from('<I',d,24)[0]; p=struct.unpack_from('<I',d,36)[0]
    return k,r,s,p

def al(x,p): return (x+p-1)//p*p

def analyze(path, deroff=None):
    d=open(path,'rb').read()
    k,r,s,p=hdr(d)
    L = p+al(k,p)+al(r,p)+al(s,p)
    if deroff is None: deroff=L
    blk=d[deroff:deroff+0x1500]
    cert,sig,params,kids=parse_sig_block(blk)
    n,e=pub_from_cert(cert)
    mode,m,dig=recover(n,e,sig)
    # params contents
    pinfo=""
    if params:
        # find printable string & integer
        po=params
        t,o,l=tlv(params,0)
        kids2=[]; q=o
        while q<o+l:
            tt,oo,ll=tlv(params,q); kids2.append((tt,oo,ll)); q=oo+ll
        for tt,oo,ll in kids2:
            if tt==0x13: pinfo+=repr(params[oo:oo+ll])+" "
            if tt==0x02: pinfo+="INT="+hex(int.from_bytes(params[oo:oo+ll],'big'))+" "
    print(f"--- {path}")
    print(f"    size={len(d):#x} k={k:#x} r={r:#x} sec={s:#x} pg={p:#x} L={L:#x} der@{deroff:#x}")
    print(f"    params: {pinfo}")
    print(f"    cert={len(cert)}B sig={len(sig)}B mode={mode} digest={dig.hex() if dig else None}")
    cands={
      "img[:L]": d[:L],
      "img[pg:L]": d[p:L],
      "img[:L]+der": d[:L]+blk[:0x1500],
      "der+img[:L]": blk[:0x1500]+d[:L],
    }
    for name,data in cands.items():
        hh=hashlib.sha256(data).hexdigest()
        print(f"      {name:14s} {hh}  {'MATCH' if dig and hh==dig.hex() else ''}")
    return dict(path=path,d=d,L=L,p=p,k=k,r=r,deroff=deroff,dig=dig,cert=cert,sig=sig,blk=blk)

for p in ["C:/qfilx/exp/boot_stock.img","C:/qfilx/firmware/81916/boot.img"]:
    if os.path.exists(p):
        try: analyze(p)
        except Exception as ex: print("ERR",p,ex)
