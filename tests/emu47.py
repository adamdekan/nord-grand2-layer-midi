"""Emulate the Nord Grand 2 system-parameter handler FUN_c00d4fe4 for parameter
0x47 (Edt_Sys_kMIDIGlobal) on the original and the patched image and print the
resulting MIDI channel->slot maps of both MIDI receivers.

usage: emu47.py <A_CODE.bin> [value value ...]   (value: 0=Off, 1..16)
"""
import sys, struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UcError
from unicorn.arm_const import *

CODE_BASE, SRAM_BASE = 0xC0000000, 0x80000000
HEAP, STACK = 0x10000000, 0x20000000
FUN = 0xc00d4fe4
STUBS = {0xc00b18e0: 'R2.releaseSlot', 0xc00b0d0c: 'R1.releaseSlot', 0xc00886f0: 'timer.cancel'}
RET_MAGIC = 0x30000000

img = open(sys.argv[1], 'rb').read()
sram = open(sys.argv[1].replace('A_CODE_patched.bin', 'A_SRAM.bin').replace('A_CODE.bin', 'A_SRAM.bin'), 'rb').read()
values = [int(v) for v in sys.argv[2:]] or [1]

mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
mu.mem_map(CODE_BASE, 0x400000)            # image + BSS
mu.mem_write(CODE_BASE, img)
mu.mem_map(SRAM_BASE, 0x20000)
mu.mem_write(SRAM_BASE, sram)
mu.mem_map(HEAP, 0x100000)
mu.mem_map(STACK - 0x10000, 0x10000)
mu.mem_map(RET_MAGIC, 0x1000)

brk = [HEAP]
def alloc(n, fill=0):
    a = brk[0]; brk[0] += (n + 15) & ~15
    mu.mem_write(a, bytes([fill]) * n); return a
w32 = lambda a, v: mu.mem_write(a, struct.pack('<I', v & 0xffffffff))
r32 = lambda a: struct.unpack('<I', mu.mem_read(a, 4))[0]

# --- receivers -------------------------------------------------------------
R1 = alloc(0x140)               # NoteOn/NoteOff receiver: chanToSlot @0x3c, slotToChan @0x80
R2 = alloc(0x140)               # pedal/PB/AT/PC receiver: chanToSlot @0x54, slotToChan @0x98
for s in range(18):
    w32(R1 + 0x80 + 4 * s, 0x10)
    w32(R2 + 0x98 + 4 * s, 0x10)
for s in (1, 6, 7, 8, 11, 12, 13, 14):     # slot objects
    w32(R1 + 0xcc + 4 * s, alloc(0x20c))
    w32(R2 + 0xe4 + 4 * s, alloc(0x80))
# objects touched by the MIDI-out part of the case (param+0x104 / +0x108)
def obj_with_d4():
    o = alloc(0x400); inner = alloc(0x400)
    w32(o + 0xd4, 0); w32(o + 0xd4, 0)          # index 0 -> entry at o+0xd4 itself
    w32(o + 0xd4 + 0 * 4, 0)
    # *(o + idx*4 + 0xd4) with idx=*(o+0xd4)=0 -> *(o+0xd4) must be a pointer: make idx 1
    w32(o + 0xd4, 1); w32(o + 0xd8, inner)
    return o
P = alloc(0x200)
w32(P + 0xfc, R1); w32(P + 0x100, R2)
w32(P + 0x104, obj_with_d4()); w32(P + 0x108, obj_with_d4())
# parameter value chain: ***(T[0x47]) where T = **(P+0x34)
T = alloc(0x400); PP = alloc(4); w32(PP, T); w32(P + 0x34, PP)
VAL = alloc(4); X = alloc(4); Y = alloc(4)
w32(X, VAL); w32(T + 0x47 * 4, X)   # value = **(T[0x47])
PID = alloc(4); w32(PID, 0x47)

calls = []
def hook(uc, addr, size, _):
    if addr in STUBS:
        calls.append((STUBS[addr], uc.reg_read(UC_ARM_REG_R1)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
mu.hook_add(UC_HOOK_CODE, hook)

def run(value):
    w32(VAL, value)
    calls.clear()
    mu.reg_write(UC_ARM_REG_SP, STACK - 0x100)
    mu.reg_write(UC_ARM_REG_R0, P); mu.reg_write(UC_ARM_REG_R1, 0); mu.reg_write(UC_ARM_REG_R2, PID)
    mu.reg_write(UC_ARM_REG_LR, RET_MAGIC)
    for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
              UC_ARM_REG_R10, UC_ARM_REG_R11):
        mu.reg_write(r, 0xdead0000 + r)
    mu.emu_start(FUN, RET_MAGIC, count=200000)
    regs_ok = all(mu.reg_read(r) == 0xdead0000 + r for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                  UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11))
    sp_ok = mu.reg_read(UC_ARM_REG_SP) == STACK - 0x100
    def maps(R, c2s, s2c):
        cmap = [r32(R + c2s + 4 * c) for c in range(16)]
        smap = {s: r32(R + s2c + 4 * s) for s in (1, 7, 8, 11, 12, 13, 14)}
        return cmap, smap
    print(f'--- global MIDI channel param = {value} ({"Off" if value == 0 else value})  callee-saved ok={regs_ok} sp ok={sp_ok}')
    for name, R, c2s, s2c in (('R1 notes ', R1, 0x3c, 0x80), ('R2 ctrl  ', R2, 0x54, 0x98)):
        cmap, smap = maps(R, c2s, s2c)
        print(f'  {name} chanToSlot[ch1..16] = {cmap}')
        print(f'  {name} slotToChan(+1)      = ' + ', '.join(f'{s}:{"-" if v == 0x10 else v + 1}' for s, v in smap.items()))
    print('  releases:', calls)

for v in values:
    try: run(v)
    except UcError as e:
        print('EMULATION ERROR', e, hex(mu.reg_read(UC_ARM_REG_PC))); raise
