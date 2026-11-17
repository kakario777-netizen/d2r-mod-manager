"""GitHub 릴리스 자동 업데이트."""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

REPO = "kakario777-netizen/d2r-mod-manager"
EXE_NAME = "D2RModManager.exe"


def latest():
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                 headers={"User-Agent": "d2r-mod-manager"})
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.load(r)
    url = None
    for a in d.get("assets", []):
        if a["name"].lower().endswith(".exe"):
            url = a["browser_download_url"]
    return {"tag": d.get("tag_name", ""), "url": url, "page": d.get("html_url", "")}


def _ver(s):
    s = s.lstrip("vV")
    out = []
    for p in s.split("."):
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return out


def is_newer(tag, cur):
    return _ver(tag) > _ver(cur)


def download_and_restart(info, progress=None):
    if not info.get("url") or not getattr(sys, "frozen", False):
        if info.get("page"):
            os.startfile(info["page"])
        return
    tmp = os.path.join(tempfile.gettempdir(), "D2RModManager_new.exe")
    req = urllib.request.Request(info["url"], headers={"User-Agent": "d2r-mod-manager"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            b = r.read(256 * 1024)
            if not b:
                break
            f.write(b)
            done += len(b)
            if progress and total:
                progress(done, total, "업데이트 받는 중")
    me = sys.executable
    bat = os.path.join(tempfile.gettempdir(), "d2rmm_update.bat")
    with open(bat, "w", encoding="cp949", errors="replace") as f:
        f.write("@echo off\r\n"
                f"set PID={os.getpid()}\r\n"
                ":wait\r\n"
                "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul && (timeout /t 1 >nul & goto wait)\r\n"
                f"move /y \"{tmp}\" \"{me}\" >nul\r\n"
                f"start \"\" \"{me}\"\r\n"
                "del \"%~f0\"\r\n")
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)
    os._exit(0)
