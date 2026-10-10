import sys,struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
# usage: pedis.py <pe> <va-hex> [count]  -> x64 disassembly at a virtual address
pe=open(sys.argv[1],'rb').read()
e=struct.unpack_from('<I',pe,0x3c)[0]
nsec=struct.unpack_from('<H',pe,e+6)[0]; opt=struct.unpack_from('<H',pe,e+20)[0]
ib=struct.unpack_from('<Q',pe,e+24+24)[0]
secs=[]
for i in range(nsec):
    o=e+24+opt+40*i
    vs,va,rs,ro=struct.unpack_from('<IIII',pe,o+8)
    secs.append((va,max(vs,rs),ro))
def off(v):
    r=v-ib
    for va,sz,ro in secs:
        if va<=r<va+sz: return ro+r-va
va=int(sys.argv[1+1],16); n=int(sys.argv[3]) if len(sys.argv)>3 else 30
md=Cs(CS_ARCH_X86,CS_MODE_64)
o=off(va)
for k,i in enumerate(md.disasm(pe[o:o+n*15],va)):
    if k>=n: break
    print(f'{i.address:x}: {i.mnemonic} {i.op_str}')
    if i.mnemonic=='ret': break
