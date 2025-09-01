"""
RoomView (updated) – màn hình trong phòng họp: participants, video placeholder, chat, mic/cam.
- Hiển thị số người tham gia & tên phòng trên header.
- Enter để gửi chat; Ctrl+M bật/tắt Mic, Ctrl+C bật/tắt Camera.
- Nút đổi style theo trạng thái.
"""
import tkinter as tk
from tkinter import ttk
from typing import List

FONT_H1 = ("Segoe UI", 16, "bold")


class RoomView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame")
        self.app = app
        self._room_name = "Phòng"
        self._count = 0

        # Header
        self.hdr = ttk.Frame(self, style="TFrame")
        self.hdr.pack(fill=tk.X, padx=16, pady=10)
        self.lbl_title = ttk.Label(self.hdr, text=self._title_text(), font=FONT_H1)
        self.lbl_title.pack(side=tk.LEFT)
        ttk.Button(self.hdr, text="Rời phòng", style="Danger.TButton", command=self.app.leave_room).pack(side=tk.RIGHT)

        # Body
        body = ttk.Frame(self, style="TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        # Participants
        left = ttk.Labelframe(body, text="Người tham gia", style="Card.TLabelframe", padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y)
        self.lst_users = tk.Listbox(
            left, height=18, width=26, bg="#0f172a", fg="#e5e7eb", highlightthickness=0, selectbackground="#6c63ff"
        )
        self.lst_users.pack(fill=tk.Y)

        # Center: video area + mic/cam bar
        center = ttk.Frame(body, style="TFrame")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        self.video_placeholder = tk.Canvas(center, bg="#0b1220", highlightthickness=0)
        self.video_placeholder.pack(fill=tk.BOTH, expand=True)
        self.video_placeholder.create_text(12, 12, anchor=tk.NW, fill="#6b7280", font=("Segoe UI", 12), text="Video view (placeholder)")

        ctrls = ttk.Frame(center, style="Panel.TFrame")
        ctrls.pack(fill=tk.X, pady=(8, 0))
        self.btn_mic = ttk.Button(ctrls, text="🎙  Mic OFF", command=self._toggle_mic)
        self.btn_cam = ttk.Button(ctrls, text="🎥  Cam OFF", command=self._toggle_cam)
        self.btn_mic.pack(side=tk.LEFT)
        self.btn_cam.pack(side=tk.LEFT, padx=6)

        # Chat
        right = ttk.Labelframe(body, text="Chat", style="Card.TLabelframe", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_chat = tk.Text(right, height=18, bg="#0f172a", fg="#e5e7eb", insertbackground="#e5e7eb", wrap=tk.WORD)
        self.txt_chat.pack(fill=tk.BOTH, expand=True)
        self.txt_chat.configure(state=tk.DISABLED)
        row = ttk.Frame(right, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=(6, 0))
        self.ent_chat = ttk.Entry(row)
        self.ent_chat.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Gửi", style="Primary.TButton", command=self._send_chat).pack(side=tk.LEFT, padx=6)

        # accelerators
        self.ent_chat.bind("<Return>", lambda e: self._send_chat())
        self.bind_all("<Control-m>", lambda e: self._toggle_mic())
        self.bind_all("<Control-M>", lambda e: self._toggle_mic())
        self.bind_all("<Control-c>", lambda e: self._toggle_cam())
        self.bind_all("<Control-C>", lambda e: self._toggle_cam())

    # Lifecycle
    def on_show(self):
        self._redraw_size()
        self.after(150, self._redraw_size)

    def _redraw_size(self):
        self.video_placeholder.delete("size")
        w = self.video_placeholder.winfo_width() or 640
        h = self.video_placeholder.winfo_height() or 360
        self.video_placeholder.create_text(w-10, h-10, anchor=tk.SE, fill="#6b7280", font=("Segoe UI", 10), text=f"{w}×{h}", tags="size")

    def _title_text(self) -> str:
        return f"{self._room_name}  •  {self._count} người"

    # Callbacks from app (network events)
    def set_room(self, name: str) -> None:
        self._room_name = f"Phòng: {name}"
        self.lbl_title.configure(text=self._title_text())

    def set_participants(self, users: List[str]) -> None:
        self._count = len(users)
        self.lst_users.delete(0, tk.END)
        for u in users:
            self.lst_users.insert(tk.END, u)
        self.lbl_title.configure(text=self._title_text())

    def user_joined(self, who: str) -> None:
        self.lst_users.insert(tk.END, who)
        self._count += 1
        self.lbl_title.configure(text=self._title_text())
        self.append_chat(f"* {who} joined *")

    def user_left(self, who: str) -> None:
        items = [self.lst_users.get(i) for i in range(self.lst_users.size())]
        self.lst_users.delete(0, tk.END)
        self._count = 0
        for name in items:
            if name != who:
                self.lst_users.insert(tk.END, name)
                self._count += 1
        self.lbl_title.configure(text=self._title_text())
        self.append_chat(f"* {who} left *")

    def append_chat(self, line: str) -> None:
        self.txt_chat.configure(state=tk.NORMAL)
        self.txt_chat.insert(tk.END, line + "\n")
        self.txt_chat.configure(state=tk.DISABLED)
        self.txt_chat.see(tk.END)

    # Local actions
    def _send_chat(self) -> None:
        text = self.ent_chat.get().strip()
        if not text:
            return
        self.app.send_chat(text)
        if getattr(self.app, "username", None):
            self.append_chat(f"{self.app.username}: {text}")
        self.ent_chat.delete(0, tk.END)

    def _toggle_mic(self) -> None:
        on = self.app.toggle_mic()
        self.btn_mic.configure(text="🎙  Mic ON" if on else "🎙  Mic OFF", style="Success.TButton" if on else "TButton")

    def _toggle_cam(self) -> None:
        on = self.app.toggle_cam(show_window=False)
        self.btn_cam.configure(text="🎥  Cam ON" if on else "🎥  Cam OFF", style="Success.TButton" if on else "TButton")
