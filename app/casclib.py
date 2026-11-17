"""CascLib ctypes 래퍼 — 게임 원본(CASC) 파일 목록을 읽어서
모드 그림이 '원본을 덮어쓰는 그림'인지 '새로 추가된 그림'인지 구분하는 데 사용."""
import ctypes
import os
import re
import sys

IS_WIN = os.name == "nt"
MAX_PATH = 260 if IS_WIN else 1024


def _lib_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")


def _load():
    name = "CascLib.dll" if IS_WIN else "libcasc.so"
    for d in (_lib_dir(), os.path.dirname(os.path.abspath(__file__))):
        p = os.path.join(d, name)
        if os.path.exists(p):
            L = ctypes.CDLL(p)
            P = ctypes.c_wchar_p if IS_WIN else ctypes.c_char_p
            H = ctypes.c_void_p
            L.CascOpenStorage.argtypes = [P, ctypes.c_uint32, ctypes.POINTER(H)]
            L.CascOpenStorage.restype = ctypes.c_bool
            L.CascCloseStorage.argtypes = [H]
            L.CascCloseStorage.restype = ctypes.c_bool
            L.CascFindFirstFile.argtypes = [H, ctypes.c_char_p, ctypes.c_void_p, P]
            L.CascFindFirstFile.restype = H
            L.CascFindNextFile.argtypes = [H, ctypes.c_void_p]
            L.CascFindNextFile.restype = ctypes.c_bool
            L.CascFindClose.argtypes = [H]
            L.CascFindClose.restype = ctypes.c_bool
            return L
    raise OSError("CascLib을 찾을 수 없어요")


_PREFIX = re.compile(r"^[a-z0-9_]+:")


def norm_casc_name(name):
    n = name.replace("\\", "/").lower()
    n = _PREFIX.sub("", n)
    return n.lstrip("/")


def list_vanilla(game_dir, progress=None):
    """게임 원본 파일 이름 집합(소문자, '/' 구분, 'data/...' 형태)."""
    L = _load()
    h = ctypes.c_void_p()
    arg = game_dir if IS_WIN else game_dir.encode("utf-8")
    if not L.CascOpenStorage(arg, 0, ctypes.byref(h)):
        raise OSError("게임 원본 데이터를 열 수 없어요")
    names = set()
    buf = ctypes.create_string_buffer(8192)  # CASC_FIND_DATA보다 넉넉하게
    try:
        hf = L.CascFindFirstFile(h, b"*", buf, None)
        if not hf:
            return names
        try:
            i = 0
            while True:
                raw = buf.raw[:MAX_PATH].split(b"\0", 1)[0]
                if raw:
                    names.add(norm_casc_name(raw.decode("utf-8", "replace")))
                i += 1
                if progress and i % 20000 == 0:
                    progress(i)
                if not L.CascFindNextFile(hf, buf):
                    break
        finally:
            L.CascFindClose(hf)
    finally:
        L.CascCloseStorage(h)
    return names
