import struct,zlib,sys
# Test checksum hypotheses for the BIN/101 container fields.
bin_=sys.argv[1]; seg=sys.argv[2]
d=open(bin_,'rb').read()
be=lambda o:struct.unpack('>I',d[o:o+4])[0]
M=0xffffffff
def cands(x):
    r={}
    r['bsum']=sum(x)&M
    r['-bsum']=(-sum(x))&M
    r['~bsum']=(~sum(x))&M
    n=len(x)//2*2
    hb=struct.unpack('>%dH'%(n//2),x[:n]); hl=struct.unpack('<%dH'%(n//2),x[:n])
    r['hsumBE']=sum(hb)&M; r['-hsumBE']=(-sum(hb))&M
    r['hsumLE']=sum(hl)&M; r['-hsumLE']=(-sum(hl))&M
    n=len(x)//4*4
    wb=struct.unpack('>%dI'%(n//4),x[:n]); wl=struct.unpack('<%dI'%(n//4),x[:n])
    r['wsumBE']=sum(wb)&M; r['-wsumBE']=(-sum(wb))&M
    r['wsumLE']=sum(wl)&M; r['-wsumLE']=(-sum(wl))&M
    r['crc32']=zlib.crc32(x)&M; r['~crc32']=(~zlib.crc32(x))&M
    return r
def test(label,x,targets):
    c=cands(x)
    hit=[(k,t) for k,v in c.items() for t in targets if v==t]
    print(f'{label:28s} len={len(x):#9x} hits={[(k,hex(t)) for k,t in hit]}  bsum={c["bsum"]:#x}')
A=0x20; B=0x16a5b8
tgts=[be(0x44),be(0x70),be(0x78),be(0x9c),be(0x24),be(B+0x20),be(B+0x50),be(B+0x58),be(B+0x7c),be(B+4)]
print('targets',[hex(t) for t in tgts])
for nm,blk in (('A',A),('B',B)):
    s=lambda n:open(f'{seg}/{nm}_{n}.bin','rb').read()
    test(nm+' SRAM',s('SRAM'),tgts)
    test(nm+' CODE unpacked',s('CODE'),tgts)
    test(nm+' CODE packed',s('CODE_packed'),tgts)
    test(nm+' ARM0',s('ARM0'),tgts)
    end=B if nm=='A' else len(d)
    test(nm+' block all',d[blk:end],tgts)
    test(nm+' block after hdr',d[blk+0x2d4:end],tgts)
    test(nm+' block from +8',d[blk+8:end],tgts)
test('whole file',d,tgts)
test('file from 0x20',d[0x20:],tgts)
