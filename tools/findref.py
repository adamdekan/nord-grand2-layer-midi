import sys,struct
# usage: findref.py <target-hex> ...   -> BL/B instructions and literal words referencing targets
import os
seg=os.environ.get('NORD_SEGMENTS','work')   # folder with A_CODE.bin / A_SRAM.bin (build_layers.py work dir)
imgs=[(open(os.path.join(seg,'A_CODE.bin'),'rb').read(),0xC0000000),(open(os.path.join(seg,'A_SRAM.bin'),'rb').read(),0x80000000)]
for t in sys.argv[1:]:
    tgt=int(t,16)
    for d,base in imgs:
        n=len(d)//4
        w=struct.unpack('<%dI'%n,d[:n*4])
        for i,x in enumerate(w):
            pc=base+i*4
            if x==tgt: print(f'{tgt:#x}: word @ {pc:#x}')
            if (x>>25)&7==5 and x>>28!=0xF:  # B/BL
                off=x&0xffffff
                if off&0x800000: off-=0x1000000
                if pc+8+off*4==tgt: print(f'{tgt:#x}: {"BL" if x&(1<<24) else "B "} @ {pc:#x} cond={x>>28:x}')
