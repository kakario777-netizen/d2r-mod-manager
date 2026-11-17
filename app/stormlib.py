"""StormLib(MPQ 라이브러리) ctypes 래퍼 — 모드 .mpq 파일을 읽고 파일을 빼는 데 사용."""
import ctypes
import os
import sys

IS_WIN = os.name == "nt"
MAX_PATH = 260 if IS_WIN else 1024
MPQ_OPEN_READ_ONLY = 0x00000100
SFILE_OPEN_FROM_MPQ = 0


class SFILE_FIND_DATA(ctypes.Structure):
    _fields_ = [
        ("cFileName", ctypes.c_char * MAX_PATH),
        ("szPlainName", ctypes.c_char_p),
        ("dwHashIndex", ctypes.c_uint32),
        ("dwBlockIndex", ctypes.c_uint32),
        ("dwFileSize", ctypes.c_uint32),
        ("dwFileFlags", ctypes.c_uint32),
        ("dwCompSize", ctypes.c_uint32),
        ("dwFileTimeLo", ctypes.c_uint32),
        ("dwFileTimeHi", ctypes.c_uint32),
        ("lcLocale", ctypes.c_uint32),
    ]


def _lib_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")


_lib = None


def lib():
    global _lib
    if _lib is None:
        names = ["StormLib.dll"] if IS_WIN else ["libstorm.so"]
        last = None
        for n in names:
            for d in (_lib_dir(), os.path.dirname(os.path.abspath(__file__))):
                p = os.path.join(d, n)
                if os.path.exists(p):
                    try:
                        _lib = ctypes.CDLL(p)
                        break
                    except OSError as e:
                        last = e
            if _lib:
                break
        if _lib is None:
            env = os.environ.get("STORMLIB_PATH")
            if env:
                _lib = ctypes.CDLL(env)
            else:
                raise OSError(f"StormLib을 찾을 수 없어요 ({last})")
        _setup(_lib)
    return _lib


def _path_arg(p):
    # Windows 빌드는 UNICODE(wchar_t) — 한글 경로 대응
    return p if IS_WIN else p.encode("utf-8")


def _setup(L):
    P = ctypes.c_wchar_p if IS_WIN else ctypes.c_char_p
    H = ctypes.c_void_p
    L.SFileOpenArchive.argtypes = [P, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(H)]
    L.SFileOpenArchive.restype = ctypes.c_bool
    L.SFileCloseArchive.argtypes = [H]
    L.SFileCloseArchive.restype = ctypes.c_bool
    L.SFileFlushArchive.argtypes = [H]
    L.SFileFlushArchive.restype = ctypes.c_bool
    L.SFileFindFirstFile.argtypes = [H, ctypes.c_char_p, ctypes.POINTER(SFILE_FIND_DATA), P]
    L.SFileFindFirstFile.restype = H
    L.SFileFindNextFile.argtypes = [H, ctypes.POINTER(SFILE_FIND_DATA)]
    L.SFileFindNextFile.restype = ctypes.c_bool
    L.SFileFindClose.argtypes = [H]
    L.SFileFindClose.restype = ctypes.c_bool
    L.SFileRemoveFile.argtypes = [H, ctypes.c_char_p, ctypes.c_uint32]
    L.SFileRemoveFile.restype = ctypes.c_bool
    L.SFileCompactArchive.argtypes = [H, P, ctypes.c_bool]
    L.SFileCompactArchive.restype = ctypes.c_bool
    L.SFileOpenFileEx.argtypes = [H, ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(H)]
    L.SFileOpenFileEx.restype = ctypes.c_bool
    L.SFileGetFileSize.argtypes = [H, ctypes.POINTER(ctypes.c_uint32)]
    L.SFileGetFileSize.restype = ctypes.c_uint32
    L.SFileReadFile.argtypes = [H, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    L.SFileReadFile.restype = ctypes.c_bool
    L.SFileCloseFile.argtypes = [H]
    L.SFileCloseFile.restype = ctypes.c_bool


def last_error():
    try:
        if IS_WIN:
            return ctypes.windll.kernel32.GetLastError()
        f = lib().SErrGetLastError
        f.restype = ctypes.c_uint32
        return f()
    except Exception:
        return -1


def _enc(name):
    # MPQ 내부 이름은 바이트 그대로 보존 (cp949/utf-8 혼용 대비)
    return name if isinstance(name, bytes) else name.encode("utf-8", "surrogateescape")


class MpqArchive:
    def __init__(self, path, read_only=True):
        L = lib()
        self.h = ctypes.c_void_p()
        flags = MPQ_OPEN_READ_ONLY if read_only else 0
        if not L.SFileOpenArchive(_path_arg(path), 0, flags, ctypes.byref(self.h)):
            raise OSError(f"MPQ를 열 수 없어요: {path} (오류 {last_error()})")

    def close(self):
        if self.h:
            lib().SFileCloseArchive(self.h)
            self.h = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def list_files(self):
        """[(raw_name_bytes, size, compressed_size)] — 내부 관리 파일((listfile) 등) 제외"""
        L = lib()
        fd = SFILE_FIND_DATA()
        out = []
        hf = L.SFileFindFirstFile(self.h, b"*", ctypes.byref(fd), None)
        if not hf:
            return out
        try:
            while True:
                raw = fd.cFileName
                if not raw.startswith(b"("):
                    out.append((raw, fd.dwFileSize, fd.dwCompSize))
                if not L.SFileFindNextFile(hf, ctypes.byref(fd)):
                    break
        finally:
            L.SFileFindClose(hf)
        return out

    def read(self, name):
        L = lib()
        hf = ctypes.c_void_p()
        if not L.SFileOpenFileEx(self.h, _enc(name), SFILE_OPEN_FROM_MPQ, ctypes.byref(hf)):
            return None
        try:
            size = L.SFileGetFileSize(hf, None)
            buf = ctypes.create_string_buffer(size)
            got = ctypes.c_uint32()
            L.SFileReadFile(hf, buf, size, ctypes.byref(got), None)
            return buf.raw[: got.value]
        finally:
            L.SFileCloseFile(hf)

    def remove(self, name):
        return bool(lib().SFileRemoveFile(self.h, _enc(name), 0))

    def compact(self):
        return bool(lib().SFileCompactArchive(self.h, None, False))

    def flush(self):
        return bool(lib().SFileFlushArchive(self.h))
