"""D2R 모드 정리기 — 설치된 모드의 기능/그래픽을 한눈에 보고 켜고 끄는 프로그램."""
import os
import sys
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

import core
import updater
from version import __version__

BG = "#14161b"
PANEL = "#1d2128"
PANEL2 = "#252a33"
FG = "#d9dee7"
DIM = "#7b8494"
GOLD = "#d4a531"
ON = "#4ade80"
OFF = "#6b7280"
WARN = "#facc15"
LOCK = "#f87171"
BLUE = "#60a5fa"
FONT = ("Malgun Gothic", 10)
FONT_B = ("Malgun Gothic", 10, "bold")
FONT_BIG = ("Malgun Gothic", 13, "bold")

FILTERS = ["전체 보기", "기능만", "그래픽만", "조심·잠금만", "꺼진 것만"]


def mb(n):
    if n >= 1024 * 1024 * 1024:
        return f"{n / 1024 / 1024 / 1024:.2f}GB"
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f}MB"
    if n >= 1024:
        return f"{n / 1024:.0f}KB"
    return f"{n}B"


def bar(v, mx, width=10):
    if mx <= 0 or v <= 0:
        return ""
    k = max(1, round(v / mx * width))
    return "█" * k + "░" * (width - k)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"D2R 모드 정리기 v{__version__}")
        self.geometry("1280x820")
        self.minsize(1000, 640)
        self.configure(bg=BG)
        self.game_dir = tk.StringVar(value=core.DEFAULT_GAME_DIR)
        self.mod = tk.StringVar()
        self.filter = tk.StringVar(value=FILTERS[0])
        self.search = tk.StringVar()
        self.compact = tk.BooleanVar(value=False)
        self.entries = []
        self.saved_off = set()
        self.plugins = []
        self.saved_plugins_off = set()
        self.vanilla_ok = None
        self.busy = False
        self.node_entries = {}
        self._style()
        self._build()
        self.after(100, self.refresh_mods)
        self.after(1500, self.check_update)

    # ───────────── 스타일 ─────────────
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=FONT, fieldbackground=PANEL2, bordercolor=PANEL2)
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Panel.TLabel", background=PANEL, foreground=FG)
        s.configure("Dim.TLabel", background=BG, foreground=DIM)
        s.configure("Title.TLabel", background=BG, foreground=GOLD, font=("Malgun Gothic", 16, "bold"))
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=DIM, padding=(16, 6), font=FONT_B)
        s.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", GOLD)])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=PANEL2, foreground=GOLD, font=FONT_B, relief="flat")
        s.map("Treeview", background=[("selected", "#334155")])
        s.configure("TButton", background=PANEL2, foreground=FG, padding=(10, 5), borderwidth=0)
        s.map("TButton", background=[("active", "#323845"), ("disabled", PANEL)], foreground=[("disabled", OFF)])
        s.configure("Gold.TButton", background="#5a4614", foreground="#ffe9a8", font=FONT_B)
        s.map("Gold.TButton", background=[("active", "#6e5618")])
        s.configure("Go.TButton", background="#166534", foreground="#eafff0", font=FONT_BIG, padding=(18, 8))
        s.map("Go.TButton", background=[("active", "#15803d"), ("disabled", PANEL)])
        s.configure("Red.TButton", background="#5b1d1d", foreground="#ffd6d6")
        s.map("Red.TButton", background=[("active", "#7a2626")])
        s.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=FG, arrowcolor=GOLD)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", GOLD)],
              background=[("readonly", PANEL2)])
        s.configure("TEntry", fieldbackground=PANEL2, foreground=FG, insertcolor=FG)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        s.configure("Horizontal.TProgressbar", background=GOLD, troughcolor=PANEL2, borderwidth=0)
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.font", FONT)

    # ───────────── 화면 구성 ─────────────
    def _build(self):
        top = ttk.Frame(self, padding=(14, 10, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text="D2R 모드 정리기", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text=f"  v{__version__}", style="Dim.TLabel").pack(side="left", pady=(6, 0))
        self.update_btn = ttk.Button(top, text="", style="Gold.TButton", command=self.do_update)

        row = ttk.Frame(self, padding=(14, 4))
        row.pack(fill="x")
        ttk.Label(row, text="게임 폴더").pack(side="left")
        ttk.Entry(row, textvariable=self.game_dir, width=52).pack(side="left", padx=6)
        ttk.Button(row, text="변경", command=self.pick_game_dir).pack(side="left")
        ttk.Label(row, text="     모드").pack(side="left")
        self.mod_box = ttk.Combobox(row, textvariable=self.mod, state="readonly", width=26)
        self.mod_box.pack(side="left", padx=6)
        self.mod_box.bind("<<ComboboxSelected>>", lambda e: self.load_mod())
        ttk.Button(row, text="다시 읽기", command=self.load_mod).pack(side="left")

        # 정보 카드
        info = tk.Frame(self, bg=PANEL, padx=14, pady=8)
        info.pack(fill="x", padx=14, pady=(6, 4))
        self.lbl_ver = tk.Label(info, bg=PANEL, fg=FG, font=FONT_B, anchor="w")
        self.lbl_ver.grid(row=0, column=0, sticky="w")
        self.lbl_orig = tk.Label(info, bg=PANEL, fg=DIM, font=FONT, anchor="w")
        self.lbl_orig.grid(row=1, column=0, sticky="w")
        self.lbl_sum = tk.Label(info, bg=PANEL, fg=FG, font=FONT_BIG, anchor="e")
        self.lbl_sum.grid(row=0, column=1, sticky="e", padx=(20, 0))
        self.meter = tk.Canvas(info, height=16, bg=PANEL2, highlightthickness=0)
        self.meter.grid(row=1, column=1, sticky="ew", padx=(20, 0))
        info.columnconfigure(0, weight=1)
        info.columnconfigure(1, weight=1)
        self.meter.bind("<Configure>", lambda e: self.update_summary())

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=14, pady=4)
        self._build_files_tab()
        self._build_plugins_tab()
        self._build_history_tab()

        srow = ttk.Frame(self, padding=(14, 2, 14, 0))
        srow.pack(fill="x")
        self.prog = ttk.Progressbar(srow, length=260, mode="determinate")
        self.prog.pack(side="left")
        self.lbl_status = tk.Label(srow, bg=BG, fg=DIM, font=FONT, anchor="w")
        self.lbl_status.pack(side="left", padx=10, fill="x", expand=True)
        bottom = ttk.Frame(self, padding=(14, 4, 14, 12))
        bottom.pack(fill="x")
        self.apply_btn = ttk.Button(bottom, text="변경사항 적용하기", style="Go.TButton", command=self.apply)
        self.apply_btn.pack(side="right")
        ttk.Checkbutton(bottom, text="모드 파일 용량도 줄이기 (느림)", variable=self.compact).pack(side="right", padx=12)
        self.lbl_pending = tk.Label(bottom, bg=BG, fg=WARN, font=FONT_B)
        self.lbl_pending.pack(side="right", padx=12)

    def _build_files_tab(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="  모드 내용  ")
        bar_ = ttk.Frame(f)
        bar_.pack(fill="x", pady=(0, 6))
        ttk.Button(bar_, text="그래픽 전부 끄기 (기능만 살리기)", style="Gold.TButton",
                   command=self.bulk_gfx_off).pack(side="left")
        ttk.Button(bar_, text="전부 켜기 (원본대로)", command=self.all_on).pack(side="left", padx=6)
        ttk.Button(bar_, text="적용 전 상태로", command=self.revert_pending).pack(side="left")
        ttk.Label(bar_, text="   보기").pack(side="left")
        cb = ttk.Combobox(bar_, textvariable=self.filter, values=FILTERS, state="readonly", width=12)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill_tree())
        ttk.Label(bar_, text="  찾기").pack(side="left")
        en = ttk.Entry(bar_, textvariable=self.search, width=24)
        en.pack(side="left", padx=4)
        en.bind("<Return>", lambda e: self.fill_tree())
        ttk.Button(bar_, text="찾기", command=self.fill_tree).pack(side="left")

        legend = tk.Frame(f, bg=BG)
        legend.pack(fill="x", pady=(0, 4))
        for txt, col in (("■ 켜짐", ON), ("□ 꺼짐", OFF), ("▣ 일부 꺼짐", BLUE), ("! 조심", WARN), ("잠금(기능 보호)", LOCK)):
            tk.Label(legend, text=txt, bg=BG, fg=col, font=FONT_B).pack(side="left", padx=(0, 16))
        tk.Label(legend, text="줄을 더블클릭하거나 스페이스를 누르면 켜고 꺼져요. 여러 줄을 골라 한 번에 바꿀 수도 있어요.",
                 bg=BG, fg=DIM, font=FONT).pack(side="left")

        cols = ("state", "kind", "count", "size", "vram", "type", "note")
        wrap = ttk.Frame(f)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=cols, selectmode="extended")
        heads = {"#0": ("이름", 380), "state": ("상태", 90), "kind": ("구분", 90), "count": ("파일", 60),
                 "size": ("용량", 80), "vram": ("그래픽 메모리 부담", 190), "type": ("원본 비교", 90), "note": ("알림", 330)}
        for c, (t, w) in heads.items():
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, minwidth=40, stretch=(c in ("#0", "note")))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, col in (("on", ON), ("off", OFF), ("part", BLUE), ("warn", WARN), ("lock", LOCK)):
            self.tree.tag_configure(tag, foreground=col)
        self.tree.tag_configure("cat", font=FONT_B)
        self.tree.bind("<Double-1>", self.on_toggle)
        self.tree.bind("<space>", self.on_toggle)
        self.tree.bind("<<TreeviewOpen>>", self.on_open)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.detail = tk.Label(f, bg=PANEL, fg=FG, font=FONT, anchor="w", justify="left", padx=10, pady=8, wraplength=1150)
        self.detail.pack(fill="x", pady=(6, 0))

    def _build_plugins_tab(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="  D2RLoader 플러그인·패치  ")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 6))
        ttk.Button(b, text="그래픽 플러그인 끄기", style="Gold.TButton", command=self.plugins_gfx_off).pack(side="left")
        ttk.Button(b, text="전부 켜기", command=self.plugins_all_on).pack(side="left", padx=6)
        tk.Label(b, text="플러그인은 모드와 따로 게임에 끼워 넣는 기능이에요. 끄면 파일을 '문서\\D2R Mod Manager\\꺼둔 플러그인'으로 옮겨 두고, 켜면 다시 가져와요.",
                 bg=BG, fg=DIM, font=FONT).pack(side="left", padx=10)
        cols = ("state", "ptype", "scope", "kind", "size", "desc")
        self.ptree = ttk.Treeview(f, columns=cols, show="headings", selectmode="extended")
        for c, t, w in (("state", "상태", 80), ("ptype", "종류", 120), ("scope", "범위", 60), ("kind", "형태", 70),
                        ("size", "용량", 80), ("desc", "설명", 600)):
            self.ptree.heading(c, text=t)
            self.ptree.column(c, width=w, stretch=(c == "desc"))
        self.ptree.column("#0", width=0, stretch=False)
        self.ptree["show"] = ("tree", "headings")
        self.ptree.heading("#0", text="이름")
        self.ptree.column("#0", width=300, stretch=False)
        self.ptree.pack(fill="both", expand=True)
        for tag, col in (("on", ON), ("off", OFF), ("warn", WARN), ("lock", LOCK)):
            self.ptree.tag_configure(tag, foreground=col)
        self.ptree.bind("<Double-1>", self.on_ptoggle)
        self.ptree.bind("<space>", self.on_ptoggle)

    def _build_history_tab(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="  백업·변경 기록  ")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 6))
        ttk.Button(b, text="고른 시점으로 되돌리기", style="Gold.TButton", command=self.restore_history).pack(side="left")
        ttk.Button(b, text="원본으로 완전히 되돌리기", style="Red.TButton", command=self.restore_original).pack(side="left", padx=6)
        ttk.Button(b, text="백업 폴더 열기", command=self.open_store).pack(side="left")
        tk.Label(f, text="처음 적용할 때 원본 모드를 '문서\\D2R Mod Manager\\(모드 이름)\\원본'에 통째로 저장해요. 그 뒤로는 바꿀 때마다 무엇을 껐는지 기록만 남겨서, 어느 시점으로든 똑같이 되돌릴 수 있어요.",
                 bg=BG, fg=DIM, font=FONT, wraplength=1150, justify="left").pack(fill="x", pady=(0, 6))
        self.htree = ttk.Treeview(f, columns=("time", "note", "off"), show="headings", selectmode="browse")
        for c, t, w in (("time", "시각", 180), ("note", "내용", 220), ("off", "꺼둔 파일 수", 120)):
            self.htree.heading(c, text=t)
            self.htree.column(c, width=w, stretch=(c == "note"))
        self.htree.pack(fill="both", expand=True)

    # ───────────── 공통 ─────────────
    def status(self, txt, color=DIM):
        self.lbl_status.config(text=txt, fg=color)

    def progress(self, done, total, label=""):
        def f():
            self.prog["maximum"] = max(total, 1)
            self.prog["value"] = done
            if label:
                pct = f" {done * 100 // max(total, 1)}%" if total > 1 else ""
                self.status(label + pct, GOLD)
        self.after(0, f)

    def run_bg(self, work, done=None, label="작업 중"):
        if self.busy:
            return
        self.busy = True
        self.apply_btn.state(["disabled"])
        self.status(label + "...", GOLD)

        def t():
            try:
                r = work()
                self.after(0, lambda: self._bg_done(done, r, None))
            except Exception as e:
                tb = traceback.format_exc()
                self.after(0, lambda: self._bg_done(done, None, (e, tb)))
        threading.Thread(target=t, daemon=True).start()

    def _bg_done(self, done, r, err):
        self.busy = False
        self.apply_btn.state(["!disabled"])
        self.prog["value"] = 0
        if err:
            self.status("오류가 났어요", LOCK)
            messagebox.showerror("오류", f"{err[0]}\n\n{err[1][-1500:]}")
            return
        if done:
            done(r)

    def pick_game_dir(self):
        d = filedialog.askdirectory(initialdir=self.game_dir.get(), title="Diablo II Resurrected 폴더 선택")
        if d:
            self.game_dir.set(os.path.normpath(d))
            self.refresh_mods()

    def open_store(self):
        p = core.mod_store(self.mod.get()) if self.mod.get() else core.store_dir()
        if os.name == "nt":
            os.startfile(p)

    # ───────────── 모드 불러오기 ─────────────
    def refresh_mods(self):
        g = self.game_dir.get()
        if not os.path.isdir(g):
            self.status("게임 폴더를 찾을 수 없어요. [변경]으로 골라 주세요.", LOCK)
            return
        mods = core.list_mods(g)
        self.mod_box["values"] = mods
        if not mods:
            self.status("mods 폴더에 설치된 모드가 없어요.", WARN)
            return
        if self.mod.get() not in mods:
            self.mod.set(mods[0])
        self.load_mod()

    def load_mod(self):
        g, m = self.game_dir.get(), self.mod.get()
        if not m:
            return
        st = core.original_status(g, m)
        if st == "changed":
            if messagebox.askyesno("모드가 바뀌었어요",
                                   f"'{m}' 모드 파일이 저장해 둔 원본과 달라요.\n(모드를 새로 설치하거나 업데이트한 것 같아요)\n\n"
                                   "지금 설치된 파일을 새 원본으로 저장할까요?\n[아니요]를 누르면 지금 파일 그대로 보여 드려요."):
                self.run_bg(lambda: core.ensure_original(g, m, lambda d, t: self.progress(d, t, "새 원본 저장 중"), force_new=True),
                            lambda r: self.load_mod(), "새 원본 저장 중")
                return

        def work():
            entries, status = core.read_mod_files(g, m)
            ver = core.game_version(g)
            vanilla = None
            try:
                vanilla = core.load_vanilla(g, ver, lambda n: self.progress(n % 100000, 100000, f"게임 원본 목록 읽는 중 ({n:,}개)"))
            except Exception:
                vanilla = None
            core.mark_vanilla(entries, vanilla)
            plugins = core.list_plugins(g, m)
            return entries, status, ver, bool(vanilla), plugins

        self.run_bg(work, self._loaded, "모드를 읽는 중")

    def _loaded(self, r):
        entries, status, ver, vanilla_ok, plugins = r
        g, m = self.game_dir.get(), self.mod.get()
        self.entries = entries
        self.saved_off = {e.n for e in entries if not e.enabled}
        self.plugins = plugins
        self.saved_plugins_off = {p.key for p in plugins if not p.enabled}
        self.vanilla_ok = vanilla_ok
        tv = core.mod_target_version(g, m)
        match = core.version_match(ver, tv)
        if match is None:
            vt, col = f"게임 버전 {ver or '?'}  ·  모드 기준 버전 정보 없음", FG
        elif match:
            vt, col = f"게임 버전 {ver}  ·  모드 기준 {tv['gameVersion']} ({tv['gameBuild']})  —  버전 맞음", ON
        else:
            vt, col = (f"게임 버전 {ver}  ·  모드 기준 {tv['gameVersion']} ({tv['gameBuild']})  —  버전 다름! "
                       "플러그인이 튕김 원인일 수 있어요. 모드·D2RLoader 업데이트를 권해요."), LOCK
        self.lbl_ver.config(text=vt, fg=col)
        st_txt = {"none": "원본 백업: 아직 없음 (처음 적용할 때 자동 저장)", "ours": "원본 백업: 있음 · 지금 모드는 이 프로그램으로 수정된 상태",
                  "original": "원본 백업: 있음 · 지금 모드는 원본 그대로", "changed": "원본 백업: 있음 · 지금 모드 파일이 원본과 달라요",
                  "folder": "폴더형 모드 · 끈 파일은 '문서\\D2R Mod Manager'로 옮겨 보관"}.get(status, "")
        if tv.get("modVersion"):
            st_txt = f"모드 버전 {tv['modVersion']} · " + st_txt
        if not vanilla_ok:
            st_txt += "   ·   게임 원본 비교 불가 → 새 그림/덮어쓰기 구분 없이 표시"
        self.lbl_orig.config(text=st_txt)
        self.fill_tree()
        self.fill_plugins()
        self.fill_history()
        self.update_summary()
        self.status(f"{m} — 파일 {len(entries):,}개 · 플러그인·패치 {len(plugins)}개", ON)

    # ───────────── 트리 ─────────────
    def _visible(self, e):
        f = self.filter.get()
        q = self.search.get().strip().lower()
        if q and q not in e.n:
            return False
        if f == "기능만":
            return not (e.cat.startswith("gfx") or e.cat == "legacy")
        if f == "그래픽만":
            return e.cat.startswith("gfx") or e.cat == "legacy"
        if f == "조심·잠금만":
            return bool(e.warning())
        if f == "꺼진 것만":
            return not e.enabled
        return True

    def fill_tree(self):
        t = self.tree
        t.delete(*t.get_children())
        self.node_entries = {}
        by_cat = {}
        for e in self.entries:
            if self._visible(e):
                by_cat.setdefault(e.cat, {}).setdefault(e.group, []).append(e)
        self.max_vram = max([sum(x.vram for gs in by_cat.get(c, {}).values() for x in gs) for c in by_cat] + [1])
        for cat in core.CAT_ORDER:
            if cat not in by_cat:
                continue
            label = core.CATEGORIES[cat][0]
            all_e = [x for gs in by_cat[cat].values() for x in gs]
            cid = t.insert("", "end", text=label, open=False)
            self.node_entries[cid] = all_e
            for g, es in sorted(by_cat[cat].items(), key=lambda kv: -sum(x.size for x in kv[1])):
                gid = t.insert(cid, "end", text=core.group_label(g))
                self.node_entries[gid] = es
                t.insert(gid, "end", text="…")  # 펼칠 때 채움
            self.paint(cid)
            for gid in t.get_children(cid):
                self.paint(gid)

    def on_open(self, _e=None):
        t = self.tree
        node = t.focus()
        kids = t.get_children(node)
        if len(kids) == 1 and t.item(kids[0], "text") == "…":
            t.delete(kids[0])
            for e in sorted(self.node_entries[node], key=lambda x: -x.size):
                iid = t.insert(node, "end", text=e.n.rsplit("/", 1)[-1])
                self.node_entries[iid] = [e]
                self.paint(iid)

    def node_state(self, es):
        changeable = [e for e in es if not e.locked]
        if not changeable:
            return "lock"
        on = sum(1 for e in changeable if e.enabled)
        if on == len(changeable):
            return "on"
        if on == 0:
            return "off"
        return "part"

    def paint(self, iid):
        es = self.node_entries.get(iid, [])
        stt = self.node_state(es)
        state_txt = {"on": "■ 켜짐", "off": "□ 꺼짐", "part": "▣ 일부", "lock": "잠금"}[stt]
        cats = {e.cat for e in es}
        kind = core.CATEGORIES[next(iter(cats))][1] if len(cats) == 1 else "-"
        kind_txt = {"lock": "기능(잠금)", "func": "기능", "gfx": "그래픽", "warn": "조심", "sound": "사운드"}.get(kind, "-")
        size = sum(e.size for e in es)
        vram = sum(e.vram for e in es if e.enabled)
        vram_all = sum(e.vram for e in es)
        if vram_all:
            vtxt = f"{bar(vram, self.max_vram)} {mb(vram)}" + (f" / {mb(vram_all)}" if vram != vram_all else "")
        else:
            vtxt = ""
        news = [e for e in es if e.is_new is True and e.cat.startswith("gfx")]
        olds = [e for e in es if e.is_new is False and e.cat.startswith("gfx")]
        if len(es) == 1:
            e = es[0]
            typ = "" if not e.cat.startswith(("gfx", "legacy")) else ("새 파일" if e.is_new else "덮어쓰기" if e.is_new is False else "?")
            note = e.warning() if e.warning() not in ("조심", "잠금") else core.CATEGORIES[e.cat][2]
        else:
            typ = f"새 {len(news)}·덮 {len(olds)}" if (news or olds) else ""
            note = core.CATEGORIES[next(iter(cats))][2] if len(cats) == 1 else ""
            if news and self.tree.parent(iid) != "":
                note = f"새로 추가된 그림 {len(news)}개 포함 — 일괄 끄기에서는 보호돼요"
        tags = [stt if stt != "on" or kind not in ("warn",) else "warn"]
        if self.tree.parent(iid) == "":
            tags.append("cat")
        self.tree.item(iid, values=(state_txt, kind_txt, f"{len(es):,}", mb(size), vtxt, typ, note), tags=tags)

    def repaint_all(self):
        t = self.tree

        def walk(n):
            for c in t.get_children(n):
                if c in self.node_entries:
                    self.paint(c)
                    walk(c)
        walk("")
        self.update_summary()

    def on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        es = self.node_entries.get(sel[0], [])
        if len(es) == 1:
            e = es[0]
            txt = f"{e.n}\n{core.CATEGORIES[e.cat][0]} · {mb(e.size)} · {core.CATEGORIES[e.cat][2]}"
            if e.warning() and e.warning() not in ("조심", "잠금"):
                txt += f"\n주의: {e.warning()}"
        else:
            cats = {e.cat for e in es}
            txt = " · ".join(core.CATEGORIES[c][2] for c in cats)[:600]
        self.detail.config(text=txt)

    def on_toggle(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return "break"
        es = []
        for iid in sel:
            es.extend(self.node_entries.get(iid, []))
        changeable = [e for e in es if not e.locked]
        if not changeable:
            self.status("잠긴 항목이에요. 기능이 깨지지 않게 보호하고 있어요.", LOCK)
            return "break"
        turn_off = any(e.enabled for e in changeable)
        if turn_off and len(changeable) > 1:
            risky = [e for e in changeable if e.enabled and (e.is_new and e.cat.startswith("gfx") or e.is_link_json)]
            if risky:
                ans = messagebox.askyesnocancel(
                    "조심할 파일이 섞여 있어요",
                    f"고른 항목에 '새로 추가된 그림' 또는 '그림 연결 파일'이 {len(risky)}개 있어요.\n"
                    "이걸 빼면 해당 아이템·몬스터가 안 보이거나 튕길 수 있어요.\n\n"
                    "[예] 전부 끄기\n[아니요] 안전한 것만 끄기 (추천)\n[취소] 그만두기")
                if ans is None:
                    return "break"
                if ans is False:
                    rs = set(id(e) for e in risky)
                    changeable = [e for e in changeable if id(e) not in rs]
        for e in changeable:
            e.enabled = not turn_off
        self.repaint_all()
        return "break"

    # ───────────── 일괄 ─────────────
    def bulk_gfx_off(self):
        n = 0
        for e in self.entries:
            if e.enabled and e.bulk_offable():
                e.enabled = False
                n += 1
        skipped = sum(1 for e in self.entries if e.enabled and e.cat.startswith("gfx") and not e.bulk_offable())
        self.repaint_all()
        msg = f"그래픽 {n:,}개를 껐어요."
        if skipped:
            msg += f"  새로 추가된 그림·그림 연결 파일·UI 그림 {skipped:,}개는 안전하게 남겨 뒀어요."
        self.status(msg + "  [변경사항 적용하기]를 눌러야 실제로 반영돼요.", GOLD)

    def all_on(self):
        for e in self.entries:
            e.enabled = True
        self.repaint_all()

    def revert_pending(self):
        for e in self.entries:
            e.enabled = e.n not in self.saved_off
        for p in self.plugins:
            p.enabled = p.key not in self.saved_plugins_off
        self.repaint_all()
        self.fill_plugins()

    # ───────────── 요약 ─────────────
    def update_summary(self):
        total = sum(e.size for e in self.entries)
        vram_all = sum(e.vram for e in self.entries)
        vram_on = sum(e.vram for e in self.entries if e.enabled)
        vram_saved = sum(e.vram for e in self.entries if e.n in self.saved_off)
        self.lbl_sum.config(text=f"모드 {mb(total)}  ·  그래픽 {mb(vram_on)} / {mb(vram_all)} 사용")
        c = self.meter
        c.delete("all")
        w = c.winfo_width() or 400
        if vram_all:
            c.create_rectangle(0, 0, w * vram_on / vram_all, 16, fill=GOLD, width=0)
            c.create_text(6, 8, anchor="w", fill="#111", font=("Malgun Gothic", 8, "bold"),
                          text=f"그래픽 남김 {vram_on * 100 // vram_all}%")
        pend = sum(1 for e in self.entries if (not e.enabled) != (e.n in self.saved_off))
        pend += sum(1 for p in self.plugins if (not p.enabled) != (p.key in self.saved_plugins_off))
        self.lbl_pending.config(text=f"적용 안 된 변경 {pend:,}개" if pend else "")
        _ = vram_saved

    # ───────────── 플러그인 탭 ─────────────
    def fill_plugins(self):
        t = self.ptree
        t.delete(*t.get_children())
        self.pmap = {}
        for p in self.plugins:
            st = "■ 켜짐" if p.enabled else "□ 꺼짐"
            ptype = p.ptype + (" +그림" if getattr(p, "has_gfx", False) else "")
            tag = "on" if p.enabled else "off"
            if p.ptype in ("필수", "안정성") and p.enabled:
                tag = "lock"
            iid = t.insert("", "end", text=p.name, values=(st, ptype, p.scope, p.kind, mb(p.size), p.desc), tags=(tag,))
            self.pmap[iid] = p
        self.update_summary()

    def on_ptoggle(self, _e=None):
        sel = self.ptree.selection()
        ps = [self.pmap[i] for i in sel if i in self.pmap]
        if not ps:
            return "break"
        turn_off = any(p.enabled for p in ps)
        crit = [p for p in ps if p.enabled and p.ptype in ("필수", "안정성")]
        if turn_off and crit:
            if not messagebox.askyesno("확인", "필수·안정성 플러그인이 포함돼 있어요.\n끄면 다른 플러그인이 멈추거나 오히려 더 튕길 수 있어요.\n그래도 끌까요?"):
                return "break"
        for p in ps:
            p.enabled = not turn_off
        self.fill_plugins()
        return "break"

    def plugins_gfx_off(self):
        n = 0
        for p in self.plugins:
            if p.enabled and p.ptype == "그래픽":
                p.enabled = False
                n += 1
        self.fill_plugins()
        self.status(f"그래픽 플러그인 {n}개를 껐어요. [변경사항 적용하기]를 눌러야 반영돼요.", GOLD)

    def plugins_all_on(self):
        for p in self.plugins:
            p.enabled = True
        self.fill_plugins()

    # ───────────── 기록 탭 ─────────────
    def fill_history(self):
        t = self.htree
        t.delete(*t.get_children())
        self.hmap = {}
        st = core.load_state(self.mod.get())
        for h in reversed(st.get("history", [])):
            iid = t.insert("", "end", values=(h["time"], h["note"], f"{len(h.get('disabled', [])):,}개"))
            self.hmap[iid] = h

    def restore_history(self):
        sel = self.htree.selection()
        if not sel:
            messagebox.showinfo("안내", "되돌릴 시점을 목록에서 골라 주세요.")
            return
        h = self.hmap[sel[0]]
        off = set(h.get("disabled", []))
        for e in self.entries:
            e.enabled = e.locked or e.n not in off
        self.repaint_all()
        self.nb.select(0)
        self.status(f"{h['time']} 상태로 맞췄어요. [변경사항 적용하기]를 누르면 반영돼요.", GOLD)

    def restore_original(self):
        g, m = self.game_dir.get(), self.mod.get()
        if core.is_game_running():
            messagebox.showwarning("게임 실행 중", "디아블로2를 끈 다음에 해 주세요.")
            return
        if not messagebox.askyesno("확인", f"'{m}' 모드를 처음 받은 원본 그대로 되돌릴까요?"):
            return
        self.run_bg(lambda: core.restore_original(g, m, self.progress), lambda r: self.load_mod(), "원본으로 되돌리는 중")

    # ───────────── 적용 ─────────────
    def apply(self):
        g, m = self.game_dir.get(), self.mod.get()
        if not m or self.busy:
            return
        if core.is_game_running():
            messagebox.showwarning("게임 실행 중", "디아블로2가 켜져 있어요. 게임을 끈 다음에 적용해 주세요.")
            return
        files_changed = any((not e.enabled) != (e.n in self.saved_off) for e in self.entries)
        plug_changed = any((not p.enabled) != (p.key in self.saved_plugins_off) for p in self.plugins)
        if not files_changed and not plug_changed:
            self.status("바뀐 게 없어요.", DIM)
            return
        off_n = sum(1 for e in self.entries if not e.enabled)
        first = core.original_status(g, m) == "none"
        msg = f"꺼둘 파일 {off_n:,}개로 모드를 다시 만들어요."
        if first:
            msg += "\n\n처음이라 원본 모드를 먼저 통째로 백업해요. (용량만큼 시간이 조금 걸려요)"
        if not messagebox.askyesno("적용할까요?", msg):
            return

        def work():
            failed = []
            if files_changed:
                failed = core.apply_mod(g, m, self.entries, self.compact.get(), self.progress)
            if plug_changed:
                core.apply_plugins(g, m, self.plugins)
            return failed

        def done(failed):
            if failed:
                messagebox.showwarning("일부 실패", f"{len(failed)}개 파일은 빼지 못했어요.\n" + "\n".join(failed[:15]))
            self.load_mod()
            self.after(300, lambda: self.status("적용 완료! 게임을 켜서 확인해 보세요.", ON))

        self.run_bg(work, done, "적용하는 중")

    # ───────────── 업데이트 ─────────────
    def check_update(self):
        def work():
            return updater.latest()

        def done(info):
            if info and updater.is_newer(info["tag"], __version__):
                self.update_info = info
                self.update_btn.config(text=f"새 버전 {info['tag']} 받기")
                self.update_btn.pack(side="right")

        def t():
            try:
                r = work()
                self.after(0, lambda: done(r))
            except Exception:
                pass
        threading.Thread(target=t, daemon=True).start()

    def do_update(self):
        info = getattr(self, "update_info", None)
        if not info:
            return
        if not messagebox.askyesno("업데이트", f"{info['tag']} 버전으로 업데이트할까요?\n프로그램이 잠깐 꺼졌다가 다시 켜져요."):
            return
        self.run_bg(lambda: updater.download_and_restart(info, self.progress), None, "업데이트 받는 중")


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
