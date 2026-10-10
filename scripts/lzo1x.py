import sys

def lzo1x_decompress(src, ip=0):
    """Pure-python LZO1X decompressor. Returns (output, input_bytes_consumed_until_end_marker)."""
    out = bytearray(); n = len(src); start = ip
    state = 0  # 0 none, 1..3 trailing literals after a match, 4 after long literal run
    t = src[ip]
    if t > 17:
        ip += 1; t -= 17
        out += src[ip:ip+t]; ip += t
        state = 4 if t >= 4 else t
    while True:
        t = src[ip]; ip += 1
        if t < 16:
            if state == 0:
                if t == 0:
                    while src[ip] == 0: t += 255; ip += 1
                    t += 15 + src[ip]; ip += 1
                out += src[ip:ip+t+3]; ip += t + 3
                state = 4
                continue
            if state == 4:
                dist = 1 + 0x800 + (t >> 2) + (src[ip] << 2); ln = 3
            else:
                dist = 1 + (t >> 2) + (src[ip] << 2); ln = 2
            ip += 1
            tr = t & 3
        else:
            if t >= 64:
                dist = ((t >> 2) & 7) + 1 + (src[ip] << 3); ip += 1
                ln = (t >> 5) - 1 + 2; tr = t & 3
            elif t >= 32:
                t &= 31
                if t == 0:
                    while src[ip] == 0: t += 255; ip += 1
                    t += 31 + src[ip]; ip += 1
                ln = t + 2
                dist = 1 + ((src[ip] >> 2) | (src[ip+1] << 6)); tr = src[ip] & 3; ip += 2
            else:
                h = (t & 8) << 11
                t &= 7
                if t == 0:
                    while src[ip] == 0: t += 255; ip += 1
                    t += 7 + src[ip]; ip += 1
                ln = t + 2
                d = (src[ip] >> 2) | (src[ip+1] << 6); tr = src[ip] & 3; ip += 2
                if h + d == 0:
                    return bytes(out), ip - start
                dist = h + d + 0x4000
        if dist > len(out): raise ValueError(f'bad dist {dist:#x} at out={len(out):#x} in={ip:#x}')
        p = len(out) - dist
        for _ in range(ln): out.append(out[p]); p += 1
        if tr: out += src[ip:ip+tr]; ip += tr
        state = tr

if __name__ == '__main__':
    src = open(sys.argv[1],'rb').read(); skip = int(sys.argv[2],0)
    out, used = lzo1x_decompress(src, skip)
    open(sys.argv[3],'wb').write(out)
    print(f'{sys.argv[1]}: consumed {used:#x} of {len(src):#x} (from {skip:#x}), output {len(out):#x} ({len(out)} bytes)')
