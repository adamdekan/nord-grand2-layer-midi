import sys,struct
from capstone import *
# usage: vcalls.py <vtable-offset-hex> [ctx]  -> list "ldr rN,[rM,#off]; ... blx rN" sites in image A code
import os
seg=os.environ.get('NORD_SEGMENTS','work')   # folder with A_CODE.bin / A_SRAM.bin (build_layers.py work dir)
d=open(os.path.join(seg,'A_CODE.bin'),'rb').read(); B=0xC0000000; END=0xc01a5000
off=int(sys.argv[1],16); ctx=int(sys.argv[2]) if len(sys.argv)>2 else 6
md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
ins={}
for a in range(B,END,4):
    g=list(md.disasm(d[a-B:a-B+4],a))
    ins[a]=g[0] if g else None
pat='#0x%x]'%off
for a in range(B,END,4):
    i=ins[a]
    if not i or i.mnemonic!='ldr' or not i.op_str.endswith(pat) or '[pc' in i.op_str: continue
    r=i.op_str.split(',')[0]
    for k in range(1,16):
        j=ins.get(a+4*k)
        if j and j.mnemonic=='blx' and j.op_str==r:
            print('-----',hex(a))
            for q in range(a-4*ctx,a+4*k+4,4):
                x=ins.get(q); print('  %x: %s %s'%(q,x.mnemonic,x.op_str) if x else '  %x: ??'%q)
            break
