"""Patch Nord Grand 2 OS image A (decompressed CODE @0xC0000000) so that MIDI
channels 1-4 drive the four layers directly:

    ch1 -> Piano A (dedicated slot 11)    ch2 -> Piano B (slot 12)
    ch3 -> Synth A (dedicated slot 13)    ch4 -> Synth B (slot 14)

Mechanism: the firmware already has per-layer "dedicated slots" that every layer
engine subscribes to and enables together with the layer.  Only the MIDI channel
-> slot maps of the two MIDI receivers (R1 = notes/all-notes-off at param+0xfc,
R2 = pedals/PB/AT/PC at param+0x100) never point at them, because the global
MIDI channel handler (param 0x47, case in FUN_c00d4fe4) gives them the global
channel, where slot 1 always wins.  We hook the end of that case and pin
slotToChan[11+k] = k and chanToSlot[k] = 11+k in both receivers.

Space for the hook comes from the last unrolled 17-store chanToSlot rebuild of
the case (0xc00d656c..0xc00d6680), which is replaced by an equivalent loop.

usage: patch_layers.py <A_CODE.bin> <A_CODE_patched.bin>
"""
import sys, struct, re
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0xC0000000
src, dst = sys.argv[1], sys.argv[2]
img = bytearray(open(src, 'rb').read())
ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)
cs = Cs(CS_ARCH_ARM, CS_MODE_ARM)

def word(a): return struct.unpack_from('<I', img, a - BASE)[0]
def asm(code, addr):
    # keystone hangs on trailing comments: strip '//' comments first
    code = '\n'.join(re.sub(r'//.*', '', l) for l in code.split('\n'))
    enc, _ = ks.asm(code, addr)
    return bytes(enc)
def put(addr, data, expect=None):
    o = addr - BASE
    if expect is not None:
        cur = bytes(img[o:o + len(expect)])
        assert cur == expect, f'unexpected bytes at {addr:#x}: {cur.hex()} != {expect.hex()}'
    img[o:o + len(data)] = data
def dis(addr, n):
    for i in cs.disasm(bytes(img[addr - BASE:addr - BASE + n]), addr):
        print(f'  {i.address:08x}: {i.bytes.hex():8}  {i.mnemonic} {i.op_str}')

# ---- original code we rely on (sanity checks) --------------------------------
EPILOGUE      = 0xc00d66e0   # add sp,#0x2c ; pop {r4-r11,pc}  (shared switch exit)
SAVE_SITE     = 0xc00d6520   # ldr r4,[r4,#0xfc]   (r4: param_1 -> R1)
SAVE_RET      = 0xc00d6524
REBUILD_START = 0xc00d656c   # first of 17 unrolled chanToSlot stores (R1, slot-14 block)
REBUILD_END   = 0xc00d6680   # ldr r3,[r7,#0x2c]  (continuation)
BEQ1          = 0xc00d66a4   # beq EPILOGUE
BEQ2          = 0xc00d66d0   # beq EPILOGUE
REL_CALL      = 0xc00d66dc   # bl FUN_c00b0d0c (falls through into EPILOGUE)
FUN_RELEASE   = 0xc00b0d0c

assert asm('ldr r4, [r4, #0xfc]', SAVE_SITE) == bytes(img[SAVE_SITE-BASE:SAVE_SITE-BASE+4])
assert asm(f'beq #{EPILOGUE:#x}', BEQ1) == bytes(img[BEQ1-BASE:BEQ1-BASE+4])
assert asm(f'beq #{EPILOGUE:#x}', BEQ2) == bytes(img[BEQ2-BASE:BEQ2-BASE+4])
assert asm(f'bl #{FUN_RELEASE:#x}', REL_CALL) == bytes(img[REL_CALL-BASE:REL_CALL-BASE+4])
assert bytes(img[EPILOGUE-BASE:EPILOGUE-BASE+8]) == asm('add sp, sp, #0x2c; pop {r4, r5, r6, r7, r8, sb, sl, fp, pc}', EPILOGUE)
# the region we overwrite must be exactly the 17 unrolled stores we expect
expect_rebuild = []
for s in range(0x11, 0, -1):
    expect_rebuild.append((0x80 + 4 * s, s))
txt = [f'{i.mnemonic} {i.op_str}' for i in cs.disasm(bytes(img[REBUILD_START-BASE:REBUILD_END-BASE]), REBUILD_START)]
assert len(txt) == (REBUILD_END - REBUILD_START) // 4, 'rebuild region does not disassemble cleanly'
assert txt[0] == 'ldr r3, [r4, #0xc4]' and txt[-1] == 'str r2, [r3, #0x3c]', txt[:2] + txt[-2:]
assert 'add r7, r4, r7, lsl r2' in txt   # side effect we must reproduce (r2 == 2 there)
assert sum(1 for t in txt if t == 'str r2, [r3, #0x3c]') == 17

# ---- new code placed in the freed rebuild region ------------------------------
rebuild = f'''
    mov   r3, #0x11
rb_loop:
    add   r2, r4, r3, lsl #2
    ldr   r2, [r2, #0x80]   // ch = R1.slotToChan[s]
    add   r2, r4, r2, lsl #2
    str   r3, [r2, #0x3c]   // R1.chanToSlot[ch] = s   (s = 17..1, slot 1 wins)
    subs  r3, r3, #1
    bne   rb_loop
    add   r7, r4, r7, lsl #2   // original side effect: r7 = &R1[ch+4]
    mov   r2, #1   // original leaves r2 = 1
    b     #{REBUILD_END:#x}
'''
code = asm(rebuild, REBUILD_START)
cave = REBUILD_START + len(code)

save_stub = cave
code_save = asm(f'''
    str   r4, [sp, #0x28]   // keep param_1 in an unused frame slot
    ldr   r4, [r4, #0xfc]
    b     #{SAVE_RET:#x}
''', save_stub)

rel_stub = save_stub + len(code_save)
hook = rel_stub + 8
code_rel = asm(f'''
    bl    #{FUN_RELEASE:#x}
    b     #{hook:#x}
''', rel_stub)

apply_fn = hook + 9 * 4
code_hook = asm(f'''
    ldr   r0, [sp, #0x28]
    ldr   r0, [r0, #0xfc]   // R1 (NoteOn/NoteOff/AllNotesOff receiver)
    add   r0, r0, #0x3c   // &R1.chanToSlot[0]
    bl    #{apply_fn:#x}
    ldr   r0, [sp, #0x28]
    ldr   r0, [r0, #0x100]   // R2 (pedal/PB/AT/PC receiver)
    add   r0, r0, #0x54   // &R2.chanToSlot[0]
    bl    #{apply_fn:#x}
    b     #{EPILOGUE:#x}
''', hook)
assert len(code_hook) == 9 * 4
code_apply = asm('''
    mov   r1, #0   // k   (MIDI channel 0..3 = ch1..4)
    mov   r2, #11   // slot 11..14 = Piano A, Piano B, Synth A, Synth B
ap_loop:
    add   r3, r0, r2, lsl #2
    str   r1, [r3, #0x44]   // slotToChan[slot] = k
    str   r2, [r0, r1, lsl #2]   // chanToSlot[k]   = slot
    add   r1, r1, #1
    add   r2, r2, #1
    cmp   r1, #4
    bne   ap_loop
    bx    lr
''', apply_fn)

blob = code + code_save + code_rel + code_hook + code_apply
assert REBUILD_START + len(blob) <= REBUILD_END, f'cave overflow: {len(blob):#x} > {REBUILD_END-REBUILD_START:#x}'
put(REBUILD_START, blob)
pad = REBUILD_END - (REBUILD_START + len(blob))   # unused tail of the region: NOPs, never reached
put(REBUILD_START + len(blob), asm('mov r0, r0', 0) * (pad // 4))

# ---- redirect the original control flow ----------------------------------------
put(SAVE_SITE, asm(f'b #{save_stub:#x}', SAVE_SITE))
put(BEQ1, asm(f'beq #{hook:#x}', BEQ1))
put(BEQ2, asm(f'beq #{hook:#x}', BEQ2))
put(REL_CALL, asm(f'b #{rel_stub:#x}', REL_CALL))

open(dst, 'wb').write(img)
print(f'cave used {len(blob):#x} of {REBUILD_END-REBUILD_START:#x} bytes; hook @ {hook:#x}, apply @ {apply_fn:#x}')
print('patched region:'); dis(REBUILD_START, len(blob))
print('redirects:')
for a in (SAVE_SITE, BEQ1, BEQ2, REL_CALL): dis(a, 4)
