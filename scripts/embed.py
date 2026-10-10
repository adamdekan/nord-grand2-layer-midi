"""Write a copy of the Nord Update Tool whose BIN/101 resource (the OS container)
is replaced, then read it back to verify.

usage: embed.py <nord-fun.exe> <container> <out.exe>
"""
import sys, shutil, ctypes
from ctypes import wintypes as w

src, cont, out = sys.argv[1:4]
data = open(cont, 'rb').read()
shutil.copyfile(src, out)

k = ctypes.WinDLL('kernel32', use_last_error=True)
k.BeginUpdateResourceW.restype = w.HANDLE
k.BeginUpdateResourceW.argtypes = [w.LPCWSTR, w.BOOL]
k.UpdateResourceW.argtypes = [w.HANDLE, w.LPCWSTR, ctypes.c_void_p, w.WORD, ctypes.c_void_p, w.DWORD]
k.EndUpdateResourceW.argtypes = [w.HANDLE, w.BOOL]
h = k.BeginUpdateResourceW(out, False)
assert h, ctypes.get_last_error()
buf = ctypes.create_string_buffer(data, len(data))
assert k.UpdateResourceW(h, 'BIN', ctypes.c_void_p(101), 0x409, buf, len(data)), ctypes.get_last_error()
assert k.EndUpdateResourceW(h, False), ctypes.get_last_error()

def read_res(path, rid):
    k.LoadLibraryExW.restype = w.HMODULE; k.LoadLibraryExW.argtypes = [w.LPCWSTR, w.HANDLE, w.DWORD]
    k.FindResourceExW.restype = w.HANDLE; k.FindResourceExW.argtypes = [w.HMODULE, w.LPCWSTR, ctypes.c_void_p, w.WORD]
    k.SizeofResource.argtypes = [w.HMODULE, w.HANDLE]; k.LoadResource.restype = w.HANDLE
    k.LoadResource.argtypes = [w.HMODULE, w.HANDLE]; k.LockResource.restype = ctypes.c_void_p
    k.LockResource.argtypes = [w.HANDLE]; k.FreeLibrary.argtypes = [w.HMODULE]
    m = k.LoadLibraryExW(path, None, 0x2 | 0x20)
    r = k.FindResourceExW(m, 'BIN', ctypes.c_void_p(rid), 0x409)
    n = k.SizeofResource(m, r); p = k.LockResource(k.LoadResource(m, r))
    b = ctypes.string_at(p, n); k.FreeLibrary(m); return b

print('BIN/101 in new exe == container:', read_res(out, 101) == data)
print('BIN/105 unchanged:', read_res(out, 105) == read_res(src, 105))
