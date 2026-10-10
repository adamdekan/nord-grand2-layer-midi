import sys
from capstone import *
d=open(sys.argv[1],'rb').read(); base=int(sys.argv[2],0); off=int(sys.argv[3],0); n=int(sys.argv[4],0)
md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
for i in md.disasm(d[off:off+n],base+off): print(f'{i.address:08x}: {i.bytes.hex():8} {i.mnemonic} {i.op_str}')
