"""End-to-end build: stock Nord Update Tool -> modded Update Tool with the
"MIDI channels 1-4 = Piano A / Piano B / Synth A / Synth B" OS patch.

usage: build_layers.py <stock nord-fun.exe> <out dir>
"""
import sys, os, subprocess, hashlib, ctypes
from ctypes import wintypes as w

here = os.path.dirname(os.path.abspath(__file__))
src_exe, outdir = sys.argv[1], sys.argv[2]
work = os.path.join(outdir, 'work'); os.makedirs(work, exist_ok=True)
py = sys.executable
def run(*a): subprocess.run([py, *a], check=True)
def p(*n): return os.path.join(work, *n)

# 1. extract BIN/101 (OS container) from the stock updater
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.LoadLibraryExW.restype = w.HMODULE; k.LoadLibraryExW.argtypes = [w.LPCWSTR, w.HANDLE, w.DWORD]
k.FindResourceExW.restype = w.HANDLE; k.FindResourceExW.argtypes = [w.HMODULE, w.LPCWSTR, ctypes.c_void_p, w.WORD]
k.SizeofResource.argtypes = [w.HMODULE, w.HANDLE]; k.LoadResource.restype = w.HANDLE
k.LoadResource.argtypes = [w.HMODULE, w.HANDLE]; k.LockResource.restype = ctypes.c_void_p
k.LockResource.argtypes = [w.HANDLE]; k.FreeLibrary.argtypes = [w.HMODULE]
m = k.LoadLibraryExW(os.path.abspath(src_exe), None, 0x2 | 0x20)
r = k.FindResourceExW(m, 'BIN', ctypes.c_void_p(101), 0x409)
cont = ctypes.string_at(k.LockResource(k.LoadResource(m, r)), k.SizeofResource(m, r)); k.FreeLibrary(m)
STOCK_SHA256 = 'd53e41f112f52a1ee596bba7a1c572f280bbbd618b3dfd4520bac8840e6c2af3'   # Nord Grand 2 OS v1.22 (b245) container
assert hashlib.sha256(cont).hexdigest() == STOCK_SHA256, 'unexpected OS container: this patch is only for Nord Grand 2 OS v1.22'
open(p('bin101.bin'), 'wb').write(cont)

# 2. decompress image A CODE
sys.path.insert(0, here)
from repack import parse_block, be32
from lzo1x import lzo1x_decompress
import struct
o, n = struct.unpack_from('>II', cont, 0)
code = next(s for s in parse_block(cont[o:o + n]) if s['tag'] == 'CODE')
unpacked, used = lzo1x_decompress(code['data'])
assert used == code['psize'] and len(unpacked) == code['size'] and (~sum(unpacked)) & 0xffffffff == code['ck']
open(p('A_CODE.bin'), 'wb').write(unpacked)
for s in parse_block(cont[o:o + n]):          # SRAM / ARM0 for the analysis tools and tests
    if s['tag'] != 'CODE':
        open(p(f"A_{s['tag']}.bin"), 'wb').write(s['data'])

# 3. patch, 4. recompress, 5. repack, 6. validate, 7. embed
run(os.path.join(here, 'patch_layers.py'), p('A_CODE.bin'), p('A_CODE_patched.bin'))
run(os.path.join(here, 'lzo1x_compress.py'), p('A_CODE_patched.bin'), p('A_CODE_patched.lzo'))
out_bin = os.path.join(outdir, 'bin101_layers.bin')
run(os.path.join(here, 'repack.py'), p('bin101.bin'), out_bin, '--code', p('A_CODE_patched.bin'), p('A_CODE_patched.lzo'))
run(os.path.join(here, 'validate.py'), out_bin, '--orig', p('bin101.bin'), '--expect-a', p('A_CODE_patched.bin'))
out_exe = os.path.join(outdir, 'nord-fun-layers.exe')
run(os.path.join(here, 'embed.py'), src_exe, out_bin, out_exe)
run(os.path.join(here, 'fixpe.py'), out_exe)
for f in (out_bin, out_exe):
    print(f'{os.path.basename(f)}  sha256 {hashlib.sha256(open(f, "rb").read()).hexdigest()}')
