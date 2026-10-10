"""After UpdateResource on a signed PE: drop the stale certificate-table pointer
(it points past the new end of file) and recompute the PE checksum.

usage: fixpe.py <exe>
"""
import sys, struct
p = sys.argv[1]; pe = bytearray(open(p, 'rb').read())
e = struct.unpack_from('<I', pe, 0x3c)[0]; opt = struct.unpack_from('<H', pe, e + 20)[0]
dd = e + 24 + opt - 16 * 8
off, size = struct.unpack_from('<II', pe, dd + 8 * 4)
if off and off + size > len(pe):
    struct.pack_into('<II', pe, dd + 8 * 4, 0, 0)
struct.pack_into('<I', pe, e + 24 + 0x40, 0)
s = 0
for i in range(0, len(pe) // 2 * 2, 2):
    s += struct.unpack_from('<H', pe, i)[0]; s = (s & 0xffff) + (s >> 16)
if len(pe) & 1:
    s += pe[-1]; s = (s & 0xffff) + (s >> 16)
s = ((s & 0xffff) + (s >> 16)) + len(pe)
struct.pack_into('<I', pe, e + 24 + 0x40, s & 0xffffffff)
open(p, 'wb').write(pe)
print(f'{p}: certificate pointer {"cleared" if off + size > len(pe) else "kept"}, checksum {s:#x}')
