import sys,struct
# usage: refsin.py <start-hex> <end-hex> [margin-hex]  -> any word in image A (CODE+SRAM) pointing into [start-margin,end)
import os
seg=os.environ.get('NORD_SEGMENTS','work')   # folder with A_CODE.bin / A_SRAM.bin (build_layers.py work dir)
imgs=[(open(os.path.join(seg,'A_CODE.bin'),'rb').read(),0xC0000000),(open(os.path.join(seg,'A_SRAM.bin'),'rb').read(),0x80000000)]
s,e=int(sys.argv[1],16),int(sys.argv[2],16); m=int(sys.argv[3],16) if len(sys.argv)>3 else 0
for d,b in imgs:
    for al in (0,):
        n=(len(d)-al)//4
        for i,v in enumerate(struct.unpack_from('<%dI'%n,d,al)):
            if s-m<=v<e: print(f'{b+al+4*i:#x} -> {v:#x}')
