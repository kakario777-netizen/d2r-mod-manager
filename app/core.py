"""모드 분석·분류·적용·백업 핵심 로직 (GUI와 분리 — 테스트 가능)."""
import datetime
import json
import os
import shutil
import subprocess

from stormlib import MpqArchive

DEFAULT_GAME_DIR = r"C:\Program Files (x86)\Diablo II Resurrected"

# ───────────────────────── 분류 ─────────────────────────
# kind: lock(잠금·끌 수 없음) / func(기능) / gfx(그래픽) / warn(조심) / sound
CATEGORIES = {
    "modinfo":   ("필수 파일", "lock", "모드가 켜지는 데 꼭 필요한 파일이에요. 끌 수 없어요."),
    "data":      ("기능 · 게임 데이터", "lock", "드랍·아이템·룬워드·스킬 수치 같은 실제 기능이에요. 빼면 캐릭터·아이템이 깨질 수 있어 잠가 뒀어요."),
    "maps":      ("기능 · 맵 구조", "lock", "맵 배치 데이터예요. 빼면 지역이 깨질 수 있어 잠가 뒀어요."),
    "lang":      ("글자 · 아이템 이름/색(필터)", "warn", "아이템 이름·색깔·설명 글자예요. 빼면 아이템 필터 표시가 원래대로 돌아가요."),
    "layout":    ("UI 배치", "warn", "창·버튼 위치를 정하는 파일이에요. 빼면 모드 전용 창이 깨질 수 있어요."),
    "gfx_items": ("그래픽 · 아이템 그림", "gfx", "아이템 모양(룩변)이에요. 빼면 원래 디아2 아이템 모양으로 보여요."),
    "gfx_char":  ("그래픽 · 캐릭터·몬스터", "gfx", "캐릭터·몬스터·NPC 모양이에요. 빼면 원래 모양으로 보여요."),
    "gfx_fx":    ("그래픽 · 스킬·이펙트", "gfx", "스킬 효과·투사체·오라 같은 이펙트예요. 그래픽 메모리를 가장 많이 먹는 쪽이에요."),
    "gfx_env":   ("그래픽 · 지형·오브젝트", "gfx", "바닥·벽·상자 같은 배경 그림이에요."),
    "gfx_ui":    ("그래픽 · UI 그림", "warn", "창·버튼·아이콘 그림이에요. 빼면 UI 모양이 어색해질 수 있어 일괄 끄기에서는 빠져요."),
    "gfx_etc":   ("그래픽 · 기타", "gfx", "분류되지 않은 HD 그래픽이에요."),
    "font":      ("글꼴", "warn", "모드 글꼴이에요. 아이템 필터 기호가 이 글꼴을 쓸 수 있어 일괄 끄기에서는 빠져요."),
    "legacy":    ("그래픽 · 클래식(레거시) 모드", "gfx", "레거시(옛날 그래픽) 화면에서만 쓰는 그림이에요. HD로만 하시면 빼도 돼요."),
    "sound":     ("사운드", "sound", "효과음·음악이에요. 그래픽 메모리와는 상관없어요."),
    "etc":       ("기타", "warn", "어디에 쓰이는지 분류되지 않은 파일이에요."),
}
CAT_ORDER = ["modinfo", "data", "maps", "lang", "layout", "gfx_fx", "gfx_char", "gfx_items",
             "gfx_env", "gfx_etc", "legacy", "gfx_ui", "font", "sound", "etc"]

GFX_EXT = (".texture", ".sprite", ".model", ".particles", ".dds", ".png", ".dc6", ".dcc", ".cof", ".pl2", ".dat")
VRAM_EXT = (".texture", ".sprite", ".dds", ".png", ".dc6", ".dcc")
SOUND_EXT = (".flac", ".wav", ".ogg", ".mp3")

FOLDER_KO = {
    "weapon": "무기", "armor": "방어구", "misc": "기타 아이템", "monster": "몬스터", "player": "플레이어",
    "npc": "NPC", "missiles": "투사체", "particles": "파티클", "overlays": "오버레이", "skills": "스킬",
    "act1": "액트1", "act2": "액트2", "act3": "액트3", "act4": "액트4", "act5": "액트5", "act6": "액트6",
    "charm": "참", "ring": "반지", "amulet": "목걸이", "rune": "룬", "gem": "보석", "jewel": "주얼",
    "helmet": "투구", "shield": "방패", "belt": "벨트", "boots": "신발", "gloves": "장갑",
    "axe": "도끼", "sword": "검", "bow": "활", "crossbow": "석궁", "staff": "지팡이", "wand": "완드",
    "mace": "둔기", "spear": "창", "polearm": "장창", "dagger": "단검", "javelin": "투창",
    "orb": "오브", "scepter": "셉터", "club": "곤봉", "hammer": "망치", "knife": "칼", "claw": "클로",
    "panel": "창(패널)", "hud": "HUD", "spells": "스킬 아이콘", "items": "아이템", "ui": "UI",
}


def norm(name):
    if isinstance(name, bytes):
        try:
            name = name.decode("utf-8")
        except UnicodeDecodeError:
            name = name.decode("cp949", "replace")
    return name.replace("\\", "/").lower().lstrip("/")


def classify(n):
    """n: 정규화된 경로 → (카테고리, 카테고리 기준 루트)"""
    ext = os.path.splitext(n)[1]
    if "/" not in n or n.endswith("modinfo.json"):
        return "modinfo", ""
    if ext in SOUND_EXT or n.startswith(("data/hd/global/sfx/", "data/hd/global/music/", "data/global/sfx/", "data/global/music/")):
        return "sound", "data/hd/global/" if n.startswith("data/hd/") else "data/global/"
    if n.startswith("data/global/excel/"):
        return "data", "data/global/excel/"
    if n.startswith("data/global/tiles/"):
        return "maps", "data/global/tiles/"
    if n.startswith("data/local/lng/") or n.startswith("data/local/"):
        return "lang", "data/local/"
    if n.startswith("data/global/ui/layouts/"):
        return "layout", "data/global/ui/layouts/"
    if n.startswith(("data/hd/ui/fonts/", "data/hd/global/ui/fonts/")) or ext in (".ttf", ".otf"):
        return "font", "data/hd/"
    if n.startswith("data/hd/items/"):
        return "gfx_items", "data/hd/items/"
    if n.startswith("data/hd/character/"):
        return "gfx_char", "data/hd/character/"
    for p in ("data/hd/missiles/", "data/hd/vfx/", "data/hd/overlays/"):
        if n.startswith(p):
            return "gfx_fx", "data/hd/"
    for p in ("data/hd/env/", "data/hd/objects/", "data/hd/global/tiles/"):
        if n.startswith(p):
            return "gfx_env", "data/hd/"
    if n.startswith(("data/hd/global/ui/", "data/hd/local/", "data/hd/ui/")):
        return "gfx_ui", "data/hd/"
    if n.startswith("data/hd/"):
        return "gfx_etc", "data/hd/"
    if n.startswith("data/global/") and ext in (".dc6", ".dcc", ".cof", ".dt1", ".pl2", ".dat"):
        return "legacy", "data/global/"
    return "etc", ""


def group_of(n, root):
    rel = n[len(root):] if root and n.startswith(root) else n
    parts = rel.split("/")[:-1]
    return "/".join(parts[:2]) if parts else "(바로 아래)"


def group_label(g):
    return " / ".join(FOLDER_KO.get(p, p) + (f" ({p})" if p in FOLDER_KO else "") for p in g.split("/"))


class FileEntry:
    __slots__ = ("raw", "n", "size", "cat", "group", "ext", "is_new", "enabled")

    def __init__(self, raw, size):
        self.raw = raw
        self.n = norm(raw)
        self.size = size
        self.cat, root = classify(self.n)
        self.group = group_of(self.n, root)
        self.ext = os.path.splitext(self.n)[1]
        self.is_new = None  # True=새 파일, False=원본 덮어쓰기, None=확인 불가
        self.enabled = True

    @property
    def kind(self):
        return CATEGORIES[self.cat][1]

    @property
    def locked(self):
        return self.kind == "lock"

    @property
    def vram(self):
        return self.size if self.ext in VRAM_EXT and self.cat.startswith(("gfx", "legacy")) else 0

    @property
    def is_link_json(self):
        # 그래픽 폴더 안 json = 어떤 그림을 쓸지 연결하는 파일
        return self.ext == ".json" and self.cat.startswith("gfx")

    def bulk_offable(self):
        """'그래픽 전부 끄기'에 포함되는지"""
        if self.kind != "gfx" or self.is_link_json:
            return False
        if self.is_new is True:
            return False
        return True

    def warning(self):
        if self.locked:
            return "잠금"
        if self.is_link_json:
            return "그림 연결 파일 — 빼면 모드 그림 연결이 풀려요"
        if self.is_new and self.cat.startswith("gfx"):
            return "새로 추가된 그림 — 빼면 해당 대상이 안 보이거나 튕길 수 있어요"
        if self.kind == "warn":
            return "조심"
        return ""


# ───────────────────────── 경로·저장소 ─────────────────────────
def store_dir():
    base = os.path.join(os.path.expanduser("~"), "Documents")
    if not os.path.isdir(base):
        base = os.path.expanduser("~")
    d = os.path.join(base, "D2R Mod Manager")
    os.makedirs(d, exist_ok=True)
    return d


def mod_store(mod):
    d = os.path.join(store_dir(), mod)
    os.makedirs(d, exist_ok=True)
    return d


def list_mods(game_dir):
    out = []
    for mods in ("mods", "Mods"):
        p = os.path.join(game_dir, mods)
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                mp = os.path.join(p, name, name + ".mpq")
                if os.path.exists(mp) and name not in out:
                    out.append(name)
            break
    return out


def mods_root(game_dir):
    for mods in ("mods", "Mods"):
        p = os.path.join(game_dir, mods)
        if os.path.isdir(p):
            return p
    return os.path.join(game_dir, "mods")


def game_version(game_dir):
    """.build.info에서 활성 버전 문자열"""
    try:
        with open(os.path.join(game_dir, ".build.info"), encoding="utf-8", errors="replace") as f:
            lines = [l.rstrip("\n") for l in f if l.strip()]
        cols = [c.split("!")[0] for c in lines[0].split("|")]
        for row in lines[1:]:
            vals = row.split("|")
            d = dict(zip(cols, vals))
            if d.get("Active", "1") == "1" and d.get("Version"):
                return d["Version"]
    except Exception:
        pass
    return ""


def mod_target_version(game_dir, mod):
    p = os.path.join(mods_root(game_dir), mod, "d2rloader", "metadata.json")
    try:
        with open(p, encoding="utf-8") as f:
            md = json.load(f)
        bins = md.get("d2rloader", {}).get("bins", {})
        meta = md.get("metadata", {})
        return {"gameVersion": bins.get("gameVersion", ""), "gameBuild": str(bins.get("gameBuild", "")),
                "modVersion": meta.get("modVersion", ""), "author": meta.get("author", ""),
                "loader": md.get("d2rloader", {}).get("version", "")}
    except Exception:
        return {}


def version_match(game_ver, target):
    if not game_ver or not target.get("gameBuild"):
        return None
    return game_ver.split(".")[-1] == target["gameBuild"]


def is_game_running():
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq D2R.exe"], capture_output=True, text=True,
                             creationflags=0x08000000).stdout
        return "D2R.exe" in out
    except Exception:
        return False


def file_sig(p):
    st = os.stat(p)
    return {"size": st.st_size, "mtime": int(st.st_mtime)}


# ───────────────────────── 상태 저장 ─────────────────────────
def load_state(mod):
    p = os.path.join(mod_store(mod), "상태.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"disabled": [], "plugins_disabled": [], "history": []}


def save_state(mod, st):
    p = os.path.join(mod_store(mod), "상태.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def original_path(mod):
    return os.path.join(mod_store(mod), "원본", mod + ".mpq")


def copy_with_progress(src, dst, progress=None, chunk=8 * 1024 * 1024):
    total = os.path.getsize(src)
    done = 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".copying"
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        while True:
            b = fi.read(chunk)
            if not b:
                break
            fo.write(b)
            done += len(b)
            if progress:
                progress(done, total)
    os.replace(tmp, dst)


def original_status(game_dir, mod):
    """원본 상태: 'none'(원본 백업 없음), 'ours'(우리가 수정한 상태), 'original'(원본 그대로), 'changed'(모드가 새로 바뀜)"""
    cur = os.path.join(mods_root(game_dir), mod, mod + ".mpq")
    orig = original_path(mod)
    if os.path.isdir(cur):
        return "folder"
    if not os.path.exists(orig):
        return "none"
    st = load_state(mod)
    sig = file_sig(cur)
    if st.get("applied") and sig == st["applied"]:
        return "ours"
    if sig == st.get("original"):
        return "original"
    return "changed"


def ensure_original(game_dir, mod, progress=None, force_new=False):
    cur = os.path.join(mods_root(game_dir), mod, mod + ".mpq")
    orig = original_path(mod)
    status = original_status(game_dir, mod)
    if status in ("none",) or (status == "changed" and force_new):
        copy_with_progress(cur, orig, progress)
        st = load_state(mod)
        st["original"] = file_sig(cur)
        st["applied"] = None
        st["disabled"] = []
        st.setdefault("history", []).append({"time": now(), "note": "원본 저장", "disabled": []})
        save_state(mod, st)
    return orig


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ───────────────────────── 모드 읽기 ─────────────────────────
def read_mod_files(game_dir, mod):
    """모드 안 파일 목록. 원본 백업이 있으면 원본 기준(꺼둔 파일도 보이도록)."""
    cur = os.path.join(mods_root(game_dir), mod, mod + ".mpq")
    entries = []
    if os.path.isdir(cur):
        for root, _, files in os.walk(cur):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, cur).replace(os.sep, "/")
                entries.append(FileEntry(rel.encode("utf-8"), os.path.getsize(full)))
        # 꺼둔 파일(저장소로 옮긴 것)도 목록에 표시
        off_dir = os.path.join(mod_store(mod), "꺼둔 파일")
        if os.path.isdir(off_dir):
            for root, _, files in os.walk(off_dir):
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, off_dir).replace(os.sep, "/")
                    e = FileEntry(rel.encode("utf-8"), os.path.getsize(full))
                    e.enabled = False
                    entries.append(e)
        return entries, "folder"
    status = original_status(game_dir, mod)
    src = original_path(mod) if status in ("ours", "original") else cur
    with MpqArchive(src) as a:
        for raw, size, _ in a.list_files():
            entries.append(FileEntry(raw, size))
    st = load_state(mod)
    if status in ("ours", "original"):
        off = set(st.get("disabled", []))
        for e in entries:
            if e.n in off:
                e.enabled = False
    return entries, status


def mark_vanilla(entries, vanilla):
    if not vanilla:
        return
    for e in entries:
        e.is_new = e.n not in vanilla


def vanilla_cache_path(ver):
    return os.path.join(store_dir(), f"원본목록_{ver or 'unknown'}.txt")


def load_vanilla(game_dir, ver, progress=None):
    p = vanilla_cache_path(ver)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return set(l.strip() for l in f if l.strip())
    from casclib import list_vanilla
    names = list_vanilla(game_dir, progress)
    if names:
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(names)))
    return names


# ───────────────────────── 적용 ─────────────────────────
def apply_mod(game_dir, mod, entries, compact=False, progress=None, note="적용"):
    """원본 복사본에서 꺼둔 파일을 뺀 새 mpq를 만들어 모드 자리에 넣음."""
    cur = os.path.join(mods_root(game_dir), mod, mod + ".mpq")
    disabled = [e for e in entries if not e.enabled and not e.locked]
    if os.path.isdir(cur):
        return _apply_folder(game_dir, mod, entries, note)
    orig = ensure_original(game_dir, mod, progress)
    tmp = cur + ".dmm_tmp"
    if progress:
        progress(0, 1, "원본을 복사하는 중")
    copy_with_progress(orig, tmp, (lambda d, t: progress(d, t, "원본을 복사하는 중")) if progress else None)
    failed = []
    if disabled:
        with MpqArchive(tmp, read_only=False) as a:
            for i, e in enumerate(disabled):
                if not a.remove(e.raw):
                    failed.append(e.n)
                if progress and i % 50 == 0:
                    progress(i, len(disabled), "파일을 빼는 중")
            if compact:
                if progress:
                    progress(0, 1, "용량 줄이는 중(조금 걸려요)")
                a.compact()
            a.flush()
    os.replace(tmp, cur)
    st = load_state(mod)
    st["applied"] = file_sig(cur) if disabled else None
    if not disabled:
        # 원본 그대로 복사됨 → mtime이 바뀌었으니 원본 서명도 갱신
        st["original"] = file_sig(cur)
        st["applied"] = file_sig(cur)
    st["disabled"] = sorted(e.n for e in disabled)
    hist = st.setdefault("history", [])
    hist.append({"time": now(), "note": note, "disabled": st["disabled"]})
    st["history"] = hist[-30:]
    save_state(mod, st)
    return failed


def _apply_folder(game_dir, mod, entries, note):
    cur = os.path.join(mods_root(game_dir), mod, mod + ".mpq")
    off_dir = os.path.join(mod_store(mod), "꺼둔 파일")
    for e in entries:
        if e.locked:
            continue
        rel = e.n
        on_path = _find_case(cur, e.raw.decode("utf-8", "replace"))
        off_path = os.path.join(off_dir, *e.raw.decode("utf-8", "replace").split("/"))
        if not e.enabled and on_path and os.path.exists(on_path):
            os.makedirs(os.path.dirname(off_path), exist_ok=True)
            shutil.move(on_path, off_path)
        elif e.enabled and os.path.exists(off_path):
            dst = os.path.join(cur, *e.raw.decode("utf-8", "replace").split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(off_path, dst)
    st = load_state(mod)
    st["disabled"] = sorted(e.n for e in entries if not e.enabled and not e.locked)
    st.setdefault("history", []).append({"time": now(), "note": note, "disabled": st["disabled"]})
    st["history"] = st["history"][-30:]
    save_state(mod, st)
    return []


def _find_case(base, rel):
    p = os.path.join(base, *rel.split("/"))
    return p if os.path.exists(p) else None


def restore_original(game_dir, mod, progress=None):
    cur = os.path.join(mods_root(game_dir), mod, mod + ".mpq")
    if os.path.isdir(cur):
        entries, _ = read_mod_files(game_dir, mod)
        for e in entries:
            e.enabled = True
        return _apply_folder(game_dir, mod, entries, "원본으로 되돌리기")
    orig = original_path(mod)
    if not os.path.exists(orig):
        raise FileNotFoundError("저장된 원본이 없어요")
    copy_with_progress(orig, cur + ".dmm_tmp", (lambda d, t: progress(d, t, "원본을 되돌리는 중")) if progress else None)
    os.replace(cur + ".dmm_tmp", cur)
    st = load_state(mod)
    st["original"] = file_sig(cur)
    st["applied"] = file_sig(cur)
    st["disabled"] = []
    st.setdefault("history", []).append({"time": now(), "note": "원본으로 되돌리기", "disabled": []})
    save_state(mod, st)


# ───────────────────────── D2RLoader 플러그인·패치 ─────────────────────────
from plugins_kb import describe_plugin  # noqa: E402


class PluginEntry:
    def __init__(self, scope, kind, name, files, size):
        self.scope = scope      # "전체" / "모드"
        self.kind = kind        # "플러그인" / "패치"
        self.name = name        # 표시 이름(파일 이름 기준)
        self.files = files      # 이 항목에 속한 실제 경로들(dll + 같은 이름 .mpq)
        self.size = size
        self.enabled = True
        self.ptype, self.desc = describe_plugin(name, kind)

    @property
    def key(self):
        return f"{self.scope}|{self.kind}|{self.name}"


def _dir_size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    t = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return t


def plugin_dirs(game_dir, mod):
    return [("전체", os.path.join(game_dir, "d2rloader")),
            ("모드", os.path.join(mods_root(game_dir), mod, "d2rloader"))]


def disabled_plugin_store(scope, mod):
    return os.path.join(store_dir(), "꺼둔 플러그인", "전체" if scope == "전체" else mod)


def list_plugins(game_dir, mod):
    out = []
    for scope, base in plugin_dirs(game_dir, mod):
        for kind, sub in (("플러그인", "plugins"), ("패치", "patches")):
            for enabled, d in ((True, os.path.join(base, sub)),
                               (False, os.path.join(disabled_plugin_store(scope, mod), sub))):
                if not os.path.isdir(d):
                    continue
                groups = {}
                for fn in os.listdir(d):
                    stem, ext = os.path.splitext(fn)
                    if kind == "플러그인" and ext.lower() not in (".dll", ".mpq"):
                        continue
                    if kind == "패치" and ext.lower() != ".json":
                        continue
                    groups.setdefault(stem, []).append(os.path.join(d, fn))
                for stem, files in sorted(groups.items(), key=lambda x: x[0].lower()):
                    pe = PluginEntry(scope, kind, stem, files, sum(_dir_size(f) for f in files))
                    pe.enabled = enabled
                    pe.has_gfx = any(os.path.isdir(os.path.join(f, "data", "hd")) for f in files if f.lower().endswith(".mpq"))
                    out.append(pe)
    return out


def apply_plugins(game_dir, mod, plugins):
    moved = 0
    for pe in plugins:
        base = dict(plugin_dirs(game_dir, mod))[pe.scope]
        sub = "plugins" if pe.kind == "플러그인" else "patches"
        on_dir = os.path.join(base, sub)
        off_dir = os.path.join(disabled_plugin_store(pe.scope, mod), sub)
        new_files = []
        for f in pe.files:
            fn = os.path.basename(f)
            in_on = os.path.normcase(os.path.dirname(f)) == os.path.normcase(on_dir)
            if pe.enabled and not in_on:
                os.makedirs(on_dir, exist_ok=True)
                dst = os.path.join(on_dir, fn)
                shutil.move(f, dst)
                new_files.append(dst)
                moved += 1
            elif not pe.enabled and in_on:
                os.makedirs(off_dir, exist_ok=True)
                dst = os.path.join(off_dir, fn)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(f, dst)
                new_files.append(dst)
                moved += 1
            else:
                new_files.append(f)
        pe.files = new_files
    st = load_state(mod)
    st["plugins_disabled"] = sorted(pe.key for pe in plugins if not pe.enabled)
    save_state(mod, st)
    return moved
