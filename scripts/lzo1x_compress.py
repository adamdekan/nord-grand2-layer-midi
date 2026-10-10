"""LZO1X compressor restricted to the instruction forms found in Clavia's
original OS images (LZO1X-1 style): literal runs (state 0), M2, M3, M4 with
0-3 trailing literals and the standard M4 end marker.  It never emits M1
matches or the initial-literal opcode, so any lzo1x_decompress that handled the
shipped image will handle this output.

usage: lzo1x_compress.py <in> <out>
"""
import sys, array

M2_MAX_OFFSET, M3_MAX_OFFSET, M4_MAX_OFFSET = 0x0800, 0x4000, 0xbfff
MIN_MATCH, MAX_CHAIN = 3, 48

def _len_ext(out, n):
    # n >= 1: emit (n-1)//255 zero bytes worth of 255 and a final non-zero byte
    while n > 255:
        out.append(0); n -= 255
    out.append(n)

def _emit_literals(out, data, start, n):
    # literal run instruction (only valid in state 0); n >= 4
    if n - 3 <= 15:
        out.append(n - 3)
    else:
        out.append(0); _len_ext(out, n - 3 - 15)
    out += data[start:start + n]

def _emit_match(out, dist, mlen):
    """Returns index of the byte whose low 2 bits carry the trailing-literal count."""
    if mlen <= 8 and dist <= M2_MAX_OFFSET:
        d = dist - 1
        out.append(((mlen - 1) << 5) | ((d & 7) << 2)); out.append(d >> 3)
        return len(out) - 2
    if dist <= M3_MAX_OFFSET:
        d = dist - 1
        if mlen - 2 <= 31:
            out.append(0x20 | (mlen - 2))
        else:
            out.append(0x20); _len_ext(out, mlen - 2 - 31)
        out.append((d & 0x3f) << 2); out.append(d >> 6)
        return len(out) - 2
    d = dist - 0x4000
    assert 1 <= d <= 0x7fff
    h = (d & 0x4000) >> 11
    low = d & 0x3fff
    if mlen - 2 <= 7:
        out.append(0x10 | h | (mlen - 2))
    else:
        out.append(0x10 | h); _len_ext(out, mlen - 2 - 7)
    out.append((low & 0x3f) << 2); out.append(low >> 6)
    return len(out) - 2

def _match_len(data, a, b, limit):
    n = 0
    while n + 32 <= limit and data[a + n:a + n + 32] == data[b + n:b + n + 32]:
        n += 32
    while n < limit and data[a + n] == data[b + n]:
        n += 1
    return n

def compress(data):
    data = bytes(data); n = len(data)
    out = bytearray()
    head = {}
    prev = array.array('i', [-1]) * n
    lit_start = 0          # start of pending literals
    last_tr_idx = None     # byte of last match that can take 1..3 trailing literals
    i = 0

    def insert(p):
        if p + 3 <= n:
            k = data[p:p + 3]
            prev[p] = head.get(k, -1); head[k] = p

    while i < n:
        best_len, best_dist = 0, 0
        # the very first instruction must be a literal run of >= 4 bytes (no initial-literal opcode)
        if i + MIN_MATCH <= n and not (last_tr_idx is None and i - lit_start < 4):
            cand = head.get(data[i:i + 3], -1); chain = 0
            limit = n - i
            while cand >= 0 and chain < MAX_CHAIN:
                dist = i - cand
                if dist > M4_MAX_OFFSET: break
                l = _match_len(data, cand, i, limit)
                if l > best_len and l >= MIN_MATCH:
                    best_len, best_dist = l, dist
                    if l >= 264: break
                cand = prev[cand]; chain += 1
        if best_len >= MIN_MATCH:
            # flush pending literals
            nlit = i - lit_start
            if nlit:
                if 1 <= nlit <= 3 and last_tr_idx is not None:
                    out[last_tr_idx] |= nlit
                    out += data[lit_start:i]
                else:
                    assert nlit >= 4, (i, nlit)
                    _emit_literals(out, data, lit_start, nlit)
            last_tr_idx = _emit_match(out, best_dist, best_len)
            for p in range(i, i + best_len): insert(p)
            i += best_len
            lit_start = i
        else:
            insert(i); i += 1
    # trailing literals
    nlit = n - lit_start
    if nlit:
        if 1 <= nlit <= 3 and last_tr_idx is not None:
            out[last_tr_idx] |= nlit; out += data[lit_start:]
        else:
            assert nlit >= 4
            _emit_literals(out, data, lit_start, nlit)
    out += bytes([0x11, 0x00, 0x00])     # M4 end-of-stream marker
    return bytes(out)

if __name__ == '__main__':
    src = open(sys.argv[1], 'rb').read()
    c = compress(src)
    open(sys.argv[2], 'wb').write(c)
    print(f'{sys.argv[1]}: {len(src)} -> {len(c)} bytes')
