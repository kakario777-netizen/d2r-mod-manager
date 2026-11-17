"""빌드 서버(Windows)에서 StormLib/CascLib DLL이 제대로 동작하는지 확인하는 자체 시험."""
import ctypes
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stormlib  # noqa: E402
import casclib  # noqa: E402
import core  # noqa: E402

L = stormlib.lib()
L.SFileCreateArchive.argtypes = [ctypes.c_wchar_p if os.name == "nt" else ctypes.c_char_p, ctypes.c_uint32,
                                 ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
L.SFileCreateArchive.restype = ctypes.c_bool
L.SFileAddFileEx.argtypes = [ctypes.c_wchar_p if os.name == "nt" else ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
L.SFileAddFileEx.argtypes = [ctypes.c_void_p] + L.SFileAddFileEx.argtypes
L.SFileAddFileEx.restype = ctypes.c_bool

d = os.path.join(tempfile.gettempdir(), "dmm 테스트 한글")
os.makedirs(os.path.join(d, "game", "mods", "t"), exist_ok=True)
mpq = os.path.join(d, "game", "mods", "t", "t.mpq")
if os.path.exists(mpq):
    os.remove(mpq)
h = ctypes.c_void_p()
assert L.SFileCreateArchive(stormlib._path_arg(mpq), 0x00300000, 64, ctypes.byref(h)), "create"
names = ["modinfo.json", "data\\global\\excel\\weapons.txt", "data\\hd\\items\\weapon\\axe\\axe.texture",
         "data\\hd\\missiles\\fb\\fb.particles"]
for n in names:
    src = os.path.join(d, n.replace("\\", "_"))
    with open(src, "wb") as f:
        f.write(b"x" * 1000)
    assert L.SFileAddFileEx(h, stormlib._path_arg(src), n.encode(), 0x80000200, 2, 2), n
L.SFileCloseArchive(h)

os.environ["USERPROFILE"] = os.path.join(d, "home")
os.environ["HOME"] = os.path.join(d, "home")
g = os.path.join(d, "game")
ents, st = core.read_mod_files(g, "t")
assert len(ents) == 4, [e.n for e in ents]
for e in ents:
    if e.bulk_offable():
        e.enabled = False
assert core.apply_mod(g, "t", ents, compact=True) == []
with stormlib.MpqArchive(mpq) as a:
    left = sorted(core.norm(r) for r, _, _ in a.list_files())
assert left == ["data/global/excel/weapons.txt", "modinfo.json"], left
core.restore_original(g, "t")
with stormlib.MpqArchive(mpq) as a:
    assert len(a.list_files()) == 4
casclib._load()  # DLL 로드 확인
print("SELFTEST OK")
