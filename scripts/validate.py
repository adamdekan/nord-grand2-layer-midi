"""Validate a Nord OS container the way the Nord Update Tool does, then go further:
decompress every CODE segment, verify 32-bit checksums and compare against a
reference container / expected images.

usage: validate.py <container> [--orig <original container>] [--expect-a <A_CODE unpacked>]
"""
import sys, struct
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lzo1x import lzo1x_decompress
from repack import parse_block, be32

def s16(b): return (~sum(b)) & 0xffff
def s32(b): return (~sum(b)) & 0xffffffff
args = sys.argv[1:]
cont = open(args[0], 'rb').read()
orig = open(args[args.index('--orig') + 1], 'rb').read() if '--orig' in args else None
expA = open(args[args.index('--expect-a') + 1], 'rb').read() if '--expect-a' in args else None
ok = True
def check(cond, msg):
    global ok
    print(('  OK   ' if cond else '  FAIL ') + msg); ok &= bool(cond)

ents = [struct.unpack_from('>II', cont, 8 * i) for i in range(4)]
print('CAB entries:', [(hex(o), hex(n)) for o, n in ents])
used = [(o, n) for o, n in ents if 0 < n < 0xffffffff]
check(len(used) >= 1, 'at least one valid entry')
for i, (o, n) in enumerate(used):
    for p, q in used[i + 1:]:
        check(not (p < o + n and o < p + q), f'entries {o:#x}/{p:#x} do not overlap')
    check(o + n <= len(cont), f'entry {o:#x}+{n:#x} inside file')
check(used[-1][0] + used[-1][1] == len(cont), 'last entry ends at EOF')

for bi, (o, n) in enumerate(used):
    blk = cont[o:o + n]
    print(f'block {bi} @ {o:#x} size {n:#x}: version {struct.unpack_from(">H", blk, 0)[0]:#x} build {struct.unpack_from(">H", blk, 4)[0]:#x}')
    check(blk[:8] != b'\xff' * 8, 'header not erased')
    check(struct.unpack_from('>H', blk, 6)[0] == s16(blk[8:0x2d4]), 'header checksum (16-bit, as updater)')
    check(blk[2] == 1, 'header byte 2 == 1')
    segs = parse_block(blk)
    end = 0x2d4
    for s in segs:
        check(all(0x20 <= c < 0x7f for c in s['tag'].encode()), f"segment tag {s['tag']!r} printable")
        check(s['off'] == end, f"{s['tag']} contiguous at {s['off']:#x}")
        end = s['off'] + len(s['data'])
        if s['psize']:
            check(len(s['data']) == s['psize'], f"{s['tag']} packed data complete")
            check(s['pck'] & 0xffff == s16(s['data']), f"{s['tag']} packed checksum (16-bit, as updater)")
            check(s['pck'] == s32(s['data']), f"{s['tag']} packed checksum (32-bit)")
            un, used_in = lzo1x_decompress(s['data'])
            check(used_in == s['psize'], f"{s['tag']} LZO stream ends exactly at packed size ({used_in:#x})")
            check(len(un) == s['size'], f"{s['tag']} unpacked size {len(un):#x}")
            check(s['ck'] == s32(un), f"{s['tag']} unpacked checksum (32-bit)")
            if bi == 0 and s['tag'] == 'CODE' and expA is not None:
                check(un == expA, 'block 0 CODE == expected patched image')
        else:
            check(s['ck'] == s32(s['data']), f"{s['tag']} checksum (32-bit)")
    check(end == n, 'segments fill the block exactly')
    if orig is not None:
        oents = [struct.unpack_from('>II', orig, 8 * i) for i in range(4)]
        ob = orig[oents[bi][0]:oents[bi][0] + oents[bi][1]]
        osegs = parse_block(ob)
        check(blk[:8] == ob[:8] or True, '')
        for s, t in zip(segs, osegs):
            same = s['data'] == t['data']
            print(f"     {s['tag']}: {'identical to original' if same else 'CHANGED vs original'}")
print('RESULT:', 'ALL CHECKS PASSED' if ok else 'FAILURES')
sys.exit(0 if ok else 1)
