import sys,struct
# usage: mkpe.py out.exe entry_va imagebase file1@va1 [file2@va2 ...]
# Wraps raw ARM blobs into a PE32 (machine 0x1c0, ARM LE) so PE-only analysers
# (REA's Windows Ghidra provider) map them at their real virtual addresses.
out=sys.argv[1]; entry=int(sys.argv[2],16); ib=int(sys.argv[3],16)
blobs=[]
for a in sys.argv[4:]:
    f,v=a.rsplit('@',1); blobs.append((f,int(v,16),open(f,'rb').read()))
blobs.sort(key=lambda x:x[1])
FA,SA=0x200,0x1000
al=lambda x,a:(x+a-1)//a*a
ns=len(blobs)
hdr_size=al(0x80+4+20+0xE0+40*ns,FA)
raw=[]; pos=hdr_size
for f,v,d in blobs:
    raw.append(pos); pos+=al(len(d),FA)
last=blobs[-1]; size_img=al(last[1]-ib+len(last[2]),SA)
dos=bytearray(0x80); dos[0:2]=b'MZ'; struct.pack_into('<I',dos,0x3c,0x80)
coff=struct.pack('<HHIIIHH',0x1c0,ns,0,0,0,0xE0,0x0102)
opt=struct.pack('<HBBIIIIIIIIIHHHHHHIIIIHHIIIIII',0x10b,1,0,
    sum(al(len(d),FA) for f,v,d in blobs),0,0,entry-ib,blobs[0][1]-ib,0,ib,SA,FA,
    4,0,0,0,4,0,0,size_img,hdr_size,0,1,0,0x100000,0x1000,0x100000,0x1000,0,16)
opt+=b'\0'*(16*8)
secs=b''
for i,((f,v,d),r) in enumerate(zip(blobs,raw)):
    name=(b'.s%x'%(v>>24))[:8].ljust(8,b'\0')
    secs+=struct.pack('<8sIIIIIIHHI',name,len(d),v-ib,al(len(d),FA),r,0,0,0,0,0xE0000020)
h=bytes(dos)+b'PE\0\0'+coff+opt+secs
h=h.ljust(hdr_size,b'\0')
body=b''.join(d.ljust(al(len(d),FA),b'\0') for f,v,d in blobs)
open(out,'wb').write(h+body); print('wrote',out,hex(size_img))
