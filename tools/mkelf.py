import sys,struct
# usage: mkelf.py out.elf entry file1@base1 [file2@base2 ...]
# Wraps raw little-endian ARM blobs in a minimal ELF32 (EM_ARM, ET_EXEC) with
# one PT_LOAD + one section per blob so disassemblers pick up the load addresses.
out=sys.argv[1]; entry=int(sys.argv[2],16)
blobs=[]
for a in sys.argv[3:]:
    f,b=a.rsplit('@',1); blobs.append((f,int(b,16),open(f,'rb').read()))
n=len(blobs)
ehsz,phsz,shsz=52,32,40
shstr=b'\0'+b''.join(b'.seg%d\0'%i for i in range(n))+b'.shstrtab\0'
off=ehsz+phsz*n
data=b''; offs=[]
for f,b,d in blobs:
    pad=(-(off+len(data)))%0x1000; data+=b'\0'*pad
    offs.append(off+len(data)); data+=d
shstr_off=off+len(data); data+=shstr
sh_off=(shstr_off+len(shstr)+3)&~3; data+=b'\0'*(sh_off-(shstr_off+len(shstr)))
eh=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01\x01'+b'\0'*9,2,40,1,entry,ehsz,sh_off,0x05000000,
               ehsz,phsz,n,shsz,n+2,n+1)
ph=b''.join(struct.pack('<8I',1,o,b,b,len(d),len(d),7,0x1000) for o,(f,b,d) in zip(offs,blobs))
sh=b'\0'*shsz
for i,(o,(f,b,d)) in enumerate(zip(offs,blobs)):
    sh+=struct.pack('<10I',1+i*6,1,7,b,o,len(d),0,0,4,0)
sh+=struct.pack('<10I',1+n*6,3,0,0,shstr_off,len(shstr),0,0,1,0)
open(out,'wb').write(eh+ph+data+sh)
print('wrote',out)
