"""
LoginView (updated) – màn hình đăng nhập cho HPH Meeting.
- Username: chỉ chữ/số/._- (3–20 ký tự), không khoảng trắng.
- Email: đúng định dạng; tự chuyển về chữ thường.
- Nút Tiếp tục tự khóa/mở theo trạng thái hợp lệ; Enter để submit.
- Tải logo HPH nếu có Client/assets/hph_logo.png.
"""
import os
import re
import tkinter as tk
from tkinter import ttk
from typing import Optional

PALETTE = {
    "muted": "#9ca3af",
    "success": "#10b981",
    "danger": "#ef4444",
}
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SMALL = ("Segoe UI", 10)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


class ValidEntry(ttk.Frame):
    """Entry có kiểm tra hợp lệ realtime + icon trạng thái + callback khi hợp lệ thay đổi."""
    def __init__(self, parent, label: str, pattern: Optional[re.Pattern] = None,
                 placeholder: str = "", help_text: str = "",
                 on_valid_change: Optional[callable] = None):
        super().__init__(parent)
        self.configure(style="TFrame")
        self.pattern = pattern
        self.on_valid_change = on_valid_change
        ttk.Label(self, text=label, style="TLabel").pack(anchor=tk.W)
        inner = ttk.Frame(self, style="Panel.TFrame")
        inner.pack(fill=tk.X, pady=4)
        self.var = tk.StringVar()
        self.entry = ttk.Entry(inner, textvariable=self.var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
        self.status = ttk.Label(inner, text="⦿", style="TLabel", foreground=PALETTE["muted"])
        self.status.pack(side=tk.RIGHT, padx=8)
        if placeholder:
            self.entry.insert(0, placeholder)
        if help_text:
            ttk.Label(self, text=help_text, style="Muted.TLabel").pack(anchor=tk.W)
        self.var.trace_add("write", lambda *_: self._recheck())

    def value(self) -> str:
        return self.var.get().strip()

    def _recheck(self) -> None:
        val = self.value()
        if not val:
            self.status.configure(text="⦿", foreground=PALETTE["muted"])  # idle
            if self.on_valid_change:
                self.on_valid_change(False)
            return
        ok = True
        if self.pattern is not None:
            ok = bool(self.pattern.fullmatch(val))
        self.status.configure(text="✔" if ok else "✖",
                              foreground=PALETTE["success"] if ok else PALETTE["danger"]) 
        if self.on_valid_change:
            self.on_valid_change(ok)

    def valid(self) -> bool:
        val = self.value()
        return bool(val and (self.pattern.fullmatch(val) if self.pattern else True))


class LoginView(ttk.Frame):
    USER_PAT = re.compile(r"^[A-Za-z0-9_.-]{3,20}$")
    EMAIL_PAT = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app

        wrap = ttk.Frame(self, style="TFrame")
        wrap.pack(expand=True)

        card = ttk.Frame(wrap, style="Panel.TFrame", padding=24)
        card.pack()

        top = ttk.Frame(card, style="Panel.TFrame")
        top.pack(fill=tk.X)

        logo = self._load_logo()
        if logo is not None:
            lbl = ttk.Label(top, image=logo)
            lbl.image = logo
            lbl.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(top, text="HPH Meeting", font=FONT_TITLE).pack(side=tk.LEFT)
        ttk.Label(card, text="Đăng nhập để tiếp tục", style="Muted.TLabel").pack(anchor=tk.W, pady=(6, 12))

        self.btn_ok = ttk.Button(card, text="Tiếp tục", style="Primary.TButton", command=self._submit)
        # entries
        self.ent_user = ValidEntry(card, "Tên đăng nhập",
                                   pattern=self.USER_PAT,
                                   placeholder="vd: minhdo",
                                   on_valid_change=self._sync_btn)
        self.ent_user.pack(fill=tk.X)

        self.ent_mail = ValidEntry(card, "Email",
                                   pattern=self.EMAIL_PAT,
                                   placeholder="name@example.com",
                                   on_valid_change=self._sync_btn)
        self.ent_mail.pack(fill=tk.X, pady=(8, 0))

        self.btn_ok.pack(fill=tk.X, pady=(16, 4))
        self.btn_ok.state(["disabled"])  # disabled by default

        self.status = ttk.Label(card, text=" ", style="Muted.TLabel")
        self.status.pack(anchor=tk.W)

        # bindings
        self.ent_user.entry.bind("<Return>", lambda e: self._submit())
        self.ent_mail.entry.bind("<Return>", lambda e: self._submit())
        self.after(50, lambda: self.ent_user.entry.focus_set())

    # --- helpers ---
    def _load_logo(self):
        import os
        paths = (
            os.path.join(ASSETS_DIR, "hph_logo.png"),
            os.path.join(os.path.dirname(__file__), "hph_logo.png"),
        )
        for p in paths:
            if not os.path.exists(p):
                continue
            try:
                # Ưu tiên Pillow để resize mượt
                try:
                    from PIL import Image, ImageTk  # pip install pillow
                    im = Image.open(p).convert("RGBA")
                    max_side = 128
                    w, h = im.size
                    if max(w, h) > max_side:
                        scale = max_side / float(max(w, h))
                        im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
                    return ImageTk.PhotoImage(im)
                except Exception:
                    # Fallback không cần Pillow: dùng subsample của PhotoImage
                    img = tk.PhotoImage(file=p)
                    max_side = 128
                    w, h = img.width(), img.height()
                    if max(w, h) > max_side:
                        # subsample chỉ nhận số nguyên
                        step = max(1, int(max(w, h) / max_side))
                        img = img.subsample(step, step)
                    return img
            except Exception:
                pass
        return None


    def _sync_btn(self, *_):
        if self.ent_user.valid() and self.ent_mail.valid():
            self.btn_ok.state(["!disabled"])  # enable
        else:
            self.btn_ok.state(["disabled"])  # disable

    def _submit(self) -> None:
        if not (self.ent_user.valid() and self.ent_mail.valid()):
            self.set_status("Vui lòng nhập đúng tên đăng nhập và email.", ok=False)
            self._sync_btn()
            return
        # chuẩn hóa email
        email = self.ent_mail.value().lower()
        self.app.do_login(self.ent_user.value(), email)

    def set_status(self, text: str, ok: Optional[bool]) -> None:
        color = PALETTE["muted"] if ok is None else ("#10b981" if ok else "#ef4444")
        self.status.configure(text=text, foreground=color)
