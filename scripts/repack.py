"""Rebuild the Nord OS container (resource BIN/101 of the Nord Update Tool).

Container layout (big-endian):
  0x00  up to 4 x (offset, size) block entries ("CAB" table; unused = 0,0)
  block header (0x2d4 bytes):
    +0 version u16, +2 0x0100, +4 build u16, +6 ~bytesum16(header[8:0x2d4])
    +0x10 segment count, +0x14 + i*0x2c: tag, offset, size, load, ~bytesum32(data),
                                       packed size, ~bytesum32(packed), 0...
  segments follow the header back to back (offsets relative to the block start)

usage:
  repack.py <orig bin101> <out bin101> [--code <unpacked CODE> <packed CODE>]
Without --code the original is rebuilt unchanged (self-test).
"""
import sys, struct

def be32(b, o): return struct.unpack_from('>I', b, o)[0]
def nsum(b): return (~sum(b)) & 0xffffffff
HDR = 0x2d4

def parse_block(blk):
    nseg = be32(blk, 0x10)
    segs = []
    for i in range(nseg):
        o = 0x14 + i * 0x2c
        tag = blk[o:o + 4].decode()
        off, size, load, ck, psize, pck = struct.unpack_from('>6I', blk, o + 4)
        data = blk[off:off + (psize or size)]
        segs.append(dict(tag=tag, off=off, size=size, load=load, ck=ck, psize=psize, pck=pck, data=data, desc=o))
    return segs

def build_block(blk, segs):
    hdr = bytearray(blk[:HDR])
    pos = HDR; body = b''
    for s in segs:
        o = s['desc']
        struct.pack_into('>6I', hdr, o + 4, pos, s['size'], s['load'], s['ck'], s['psize'], s['pck'])
        body += s['data']; pos += len(s['data'])
    struct.pack_into('>H', hdr, 6, (~sum(hdr[8:HDR])) & 0xffff)
    return bytes(hdr) + body

def main():
    orig = open(sys.argv[1], 'rb').read()
    out = sys.argv[2]
    entries = [struct.unpack_from('>II', orig, 8 * i) for i in range(4)]
    blocks = [orig[o:o + n] for o, n in entries if n]
    segsA = parse_block(blocks[0])
    if '--code' in sys.argv:
        k = sys.argv.index('--code')
        unpacked = open(sys.argv[k + 1], 'rb').read(); packed = open(sys.argv[k + 2], 'rb').read()
        code = next(s for s in segsA if s['tag'] == 'CODE')
        assert len(unpacked) == code['size'], 'unpacked CODE size must not change'
        code.update(ck=nsum(unpacked), psize=len(packed), pck=nsum(packed), data=packed)
    newA = build_block(blocks[0], segsA)
    newblocks = [newA] + blocks[1:]
    top = bytearray(0x20); pos = 0x20
    for i, b in enumerate(newblocks):
        struct.pack_into('>II', top, 8 * i, pos, len(b)); pos += len(b)
    res = bytes(top) + b''.join(newblocks)
    open(out, 'wb').write(res)
    print(f'wrote {out}: {len(res)} bytes (orig {len(orig)}); identical to original: {res == orig}')

if __name__ == '__main__':
    main()
