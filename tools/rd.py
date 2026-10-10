import sys,struct
# usage: rd.py <addr-hex> [count]   -> read LE words from image A (CODE @C0000000 / SRAM @80000000)
import os
seg=os.environ.get('NORD_SEGMENTS','work')   # folder with A_CODE.bin / A_SRAM.bin (build_layers.py work dir)
imgs=[(open(os.path.join(seg,'A_CODE.bin'),'rb').read(),0xC0000000),(open(os.path.join(seg,'A_SRAM.bin'),'rb').read(),0x80000000)]
def rd(a):
    for d,b in imgs:
        if b<=a<b+len(d)-3: return struct.unpack_from('<I',d,a-b)[0]
    return None
a=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 1
for i in range(n):
    v=rd(a+4*i); print(f'{a+4*i:#010x}: {v:#010x}' if v is not None else f'{a+4*i:#010x}: <unmapped>')
