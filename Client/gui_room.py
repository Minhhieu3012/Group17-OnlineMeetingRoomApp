import tkinter as tk
from tkinter import ttk
from typing import List
from PIL import Image, ImageTk
import cv2
import numpy as np
from advanced_feature.video_call import VideoCallClient

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
        ttk.Button(self.hdr, text="Rời phòng", style="Danger.TButton",
                   command=self.app.leave_room).pack(side=tk.RIGHT)

        # Body
        body = ttk.Frame(self, style="TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        # Participants
        left = ttk.Labelframe(body, text="Người tham gia", style="Card.TLabelframe", padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y)
        self.lst_users = tk.Listbox(
            left, height=18, width=26, bg="#0f172a", fg="#e5e7eb",
            highlightthickness=0, selectbackground="#6c63ff"
        )
        self.lst_users.pack(fill=tk.Y)

        # Center: video area
        center = ttk.Frame(body, style="TFrame")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        self.canvas = tk.Canvas(center, bg="#0b1220", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        ctrls = ttk.Frame(center, style="Panel.TFrame")
        ctrls.pack(fill=tk.X, pady=(8, 0))
        self.btn_mic = ttk.Button(ctrls, text="🎙  Mic OFF", command=self._toggle_mic)
        self.btn_cam = ttk.Button(ctrls, text="🎥  Cam OFF", command=self._toggle_cam)
        self.btn_mic.pack(side=tk.LEFT)
        self.btn_cam.pack(side=tk.LEFT, padx=6)

        # Chat
        right = ttk.Labelframe(body, text="Chat", style="Card.TLabelframe", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_chat = tk.Text(
            right, height=18, bg="#0f172a", fg="#e5e7eb",
            insertbackground="#e5e7eb", wrap=tk.WORD
        )
        self.txt_chat.pack(fill=tk.BOTH, expand=True)
        self.txt_chat.configure(state=tk.DISABLED)
        row = ttk.Frame(right, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=(6, 0))
        self.ent_chat = ttk.Entry(row)
        self.ent_chat.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Gửi", style="Primary.TButton",
                   command=self._send_chat).pack(side=tk.LEFT, padx=6)

        # Video state
        self.vclient: VideoCallClient = None
        self._local_imgtk = None
        self._remote_imgtk = None
        self.cam_visible = False

    # ------------------- Video rendering -------------------
    def _draw_local(self, frame: np.ndarray):
        if self.canvas.winfo_width() < 50 or self.canvas.winfo_height() < 50:
            return
        # PiP local nhỏ
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb).resize((200, 120))
        self._local_imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.delete("local")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.create_image(w - 10, h - 10, anchor=tk.SE,
                                 image=self._local_imgtk, tags="local")

    def _draw_remote(self, payload: bytes):
        arr = np.frombuffer(payload, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return
        if self.canvas.winfo_width() < 50 or self.canvas.winfo_height() < 50:
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        img = Image.fromarray(rgb).resize((w, h))
        self._remote_imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.delete("remote")
        self.canvas.create_image(0, 0, anchor=tk.NW,
                                 image=self._remote_imgtk, tags="remote")

    # ------------------- Camera toggle -------------------
    def _toggle_cam(self) -> None:
        if not self.vclient:
            self.vclient = VideoCallClient(
                self.app.client.host if hasattr(self.app, "client") else "127.0.0.1",
                getattr(self.app.client, "port", 5000),
                on_remote_frame=self._draw_remote,
                on_local_frame=self._draw_local
            )
            self.vclient.start(self.app.room or "hp-meeting",
                               self.app.username or "guest")

        # toggle hiển thị/gửi frame
        self.cam_visible = not self.cam_visible
        if self.vclient:
            self.vclient.cam_visible = self.cam_visible

        if self.cam_visible:
            self.btn_cam.configure(text="🎥  Cam ON", style="Success.TButton")
        else:
            # xoá hình đang hiển thị local/remote
            self.canvas.delete("local")
            self.btn_cam.configure(text="🎥  Cam OFF", style="TButton")

    # ------------------- Mic toggle -------------------
    def _toggle_mic(self) -> None:
        on = self.app.toggle_mic()
        self.btn_mic.configure(
            text="🎙  Mic ON" if on else "🎙  Mic OFF",
            style="Success.TButton" if on else "TButton"
        )

    # ------------------- Chat & room info -------------------
    def _title_text(self) -> str:
        return f"{self._room_name}  •  {self._count} người"

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

    def _send_chat(self) -> None:
        text = self.ent_chat.get().strip()
        if not text:
            return
        self.app.send_chat(text)
        if getattr(self.app, "username", None):
            self.append_chat(f"{self.app.username}: {text}")
        self.ent_chat.delete(0, tk.END)
