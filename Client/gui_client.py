# filename: gui_client_pages.py
# GUI đa màn hình cho Huy: Login → Lobby → Room (không DB)
# Yêu cầu sửa: BỎ hàng Server/Port ở màn Login và thêm hiệu ứng hover cho các nút.
# Phụ thuộc: client_core.py (ChatClient, FileAssembler)

import asyncio, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional
from client_core import ChatClient, FileAssembler

# ----------------------------- Pages -----------------------------
class LoginView(ttk.Frame):
    def __init__(self, app: "App", master=None):
        super().__init__(master)
        self.app = app
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="HPH class", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(12, 16))

        # (ĐÃ BỎ) Server & Port — dùng mặc định từ App: 127.0.0.1:9000
        ttk.Label(self, text="Username").grid(row=1, column=0, sticky=tk.W, padx=6)
        self.ent_user = ttk.Entry(self); self.ent_user.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=4)
        ttk.Label(self, text="Gmail").grid(row=2, column=0, sticky=tk.W, padx=6)
        self.ent_gmail = ttk.Entry(self); self.ent_gmail.grid(row=2, column=1, sticky=tk.EW, padx=6, pady=4)

        self.btn = ttk.Button(self, text="Connect & Login", command=self.on_login)
        self.btn.grid(row=3, column=0, columnspan=2, pady=12)
        self.app.stylize_button(self.btn)

        self.status = ttk.Label(self, text="", foreground="#888")
        self.status.grid(row=4, column=0, columnspan=2)

    def on_login(self):
        user = self.ent_user.get().strip()
        gmail = self.ent_gmail.get().strip()
        if not user or not gmail:
            messagebox.showwarning("Login", "Nhập username và gmail")
            return
        self.status.configure(text=f"Đang kết nối tới {self.app.default_host}:{self.app.default_port}…")
        self.app.connect_and_login(self.app.default_host, self.app.default_port, user, gmail)

    def set_status(self, text: str):
        self.status.configure(text=text)

class LobbyView(ttk.Frame):
    def __init__(self, app: "App", master=None):
        super().__init__(master)
        self.app = app

        # Layout
        self.pack_propagate(False)
        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = ttk.Frame(container)
        hdr.pack(fill=tk.X)
        self.lbl_user = ttk.Label(hdr, text="")
        self.lbl_user.pack(side=tk.LEFT)
        self.btn_logout = ttk.Button(hdr, text="Logout", command=self.app.go_login)
        self.btn_logout.pack(side=tk.RIGHT)
        self.app.stylize_button(self.btn_logout)

        main = ttk.Frame(container)
        main.pack(fill=tk.BOTH, expand=True, pady=(8,0))

        # Rooms list
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,8))
        ttk.Label(left, text="Rooms", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.lst_rooms = tk.Listbox(left, height=16)
        self.lst_rooms.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(left); btns.pack(fill=tk.X, pady=4)
        self.btn_refresh = ttk.Button(btns, text="Refresh", command=self.req_rooms)
        self.btn_refresh.pack(side=tk.LEFT)
        self.app.stylize_button(self.btn_refresh)
        self.btn_join_select = ttk.Button(btns, text="Join (select)", command=self.join_selected)
        self.btn_join_select.pack(side=tk.LEFT, padx=6)
        self.app.stylize_button(self.btn_join_select)

        # Create / Join by Code
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        frm_create = ttk.LabelFrame(right, text="Create Room", padding=8)
        frm_create.pack(fill=tk.X)
        self.ent_room_name = ttk.Entry(frm_create)
        self.ent_room_name.insert(0, "Team A")
        self.ent_room_name.pack(fill=tk.X, pady=4)
        self.ent_room_pwd = ttk.Entry(frm_create)
        self.ent_room_pwd.insert(0, "")
        self.ent_room_pwd.pack(fill=tk.X, pady=4)
        self.btn_create = ttk.Button(frm_create, text="Create", command=self.create_room)
        self.btn_create.pack(fill=tk.X)
        self.app.stylize_button(self.btn_create)

        frm_join = ttk.LabelFrame(right, text="Join by Code", padding=8)
        frm_join.pack(fill=tk.X, pady=8)
        self.ent_room_code = ttk.Entry(frm_join)
        self.ent_room_code.pack(fill=tk.X, pady=4)
        self.ent_join_pwd = ttk.Entry(frm_join)
        self.ent_join_pwd.pack(fill=tk.X, pady=4)
        self.btn_join_code = ttk.Button(frm_join, text="Join", command=self.join_by_code)
        self.btn_join_code.pack(fill=tk.X)
        self.app.stylize_button(self.btn_join_code)

        self.info = ttk.Label(container, text="", foreground="#888")
        self.info.pack(anchor=tk.W, pady=(8,0))

    # Actions
    def activate(self):
        self.lbl_user.configure(text=f"Logged in as: {self.app.username}  •  Server: {self.app.default_host}:{self.app.default_port}")
        self.req_rooms()

    def req_rooms(self):
        self.app.aio(self.app.client.list_rooms())

    def join_selected(self):
        sel = self.lst_rooms.curselection()
        if not sel: return
        label = self.lst_rooms.get(sel[0])
        # format: name (count) code=XXXX
        parts = label.split("code=")
        if len(parts) >= 2:
            code = parts[-1].strip()
            self.app.join_room(code, "")

    def create_room(self):
        name = self.ent_room_name.get().strip() or "Room"
        pwd = self.ent_room_pwd.get().strip()
        self.app.aio(self.app.client.create_room(name, pwd))
        self.info.configure(text="Đang tạo phòng…")

    def join_by_code(self):
        code = self.ent_room_code.get().strip()
        pwd = self.ent_join_pwd.get().strip()
        if not code:
            messagebox.showwarning("Join", "Nhập room code")
            return
        self.app.join_room(code, pwd)

    # Render helpers
    def render_rooms(self, rooms):
        self.lst_rooms.delete(0, tk.END)
        for r in rooms:
            label = f"{r['name']} ({r.get('count','?')}) code={r.get('code','?')}"
            self.lst_rooms.insert(tk.END, label)
        self.info.configure(text=f"{len(rooms)} room(s)")

class RoomView(ttk.Frame):
    def __init__(self, app: "App", master=None):
        super().__init__(master)
        self.app = app
        self.assembler = FileAssembler()

        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Header with leave
        hdr = ttk.Frame(container)
        hdr.pack(fill=tk.X)
        self.lbl_room = ttk.Label(hdr, text="Room: -", font=("Segoe UI", 11, "bold"))
        self.lbl_room.pack(side=tk.LEFT)
        self.btn_leave = ttk.Button(hdr, text="Leave", command=self.leave_room)
        self.btn_leave.pack(side=tk.RIGHT)
        self.app.stylize_button(self.btn_leave)

        main = ttk.Frame(container)
        main.pack(fill=tk.BOTH, expand=True, pady=(8,0))

        # Users
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Label(right, text="Users").pack(anchor=tk.W)
        self.lst_users = tk.Listbox(right, height=16, width=22)
        self.lst_users.pack(fill=tk.Y)
        self.btn_users_refresh = ttk.Button(right, text="Refresh", command=self.req_users)
        self.btn_users_refresh.pack(pady=4)
        self.app.stylize_button(self.btn_users_refresh)

        # Chat center
        center = ttk.Frame(main)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_chat = tk.Text(center, state=tk.DISABLED, height=24)
        self.txt_chat.pack(fill=tk.BOTH, expand=True)
        bottom = ttk.Frame(center); bottom.pack(fill=tk.X)
        self.ent_msg = ttk.Entry(bottom)
        self.ent_msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_send = ttk.Button(bottom, text="Send", command=self.send_chat)
        self.btn_send.pack(side=tk.LEFT, padx=4)
        self.app.stylize_button(self.btn_send)
        self.btn_send_file = ttk.Button(bottom, text="Send File", command=self.send_file)
        self.btn_send_file.pack(side=tk.LEFT)
        self.app.stylize_button(self.btn_send_file)

        # Media controls
        media = ttk.Frame(container)
        media.pack(fill=tk.X, pady=(8,0))
        self.mic_on = tk.BooleanVar(value=False)
        self.cam_on = tk.BooleanVar(value=False)
        self.chk_mic = ttk.Checkbutton(media, text="Mic", variable=self.mic_on, command=self.toggle_mic)
        self.chk_mic.pack(side=tk.LEFT)
        self.chk_cam = ttk.Checkbutton(media, text="Camera", variable=self.cam_on, command=self.toggle_cam)
        self.chk_cam.pack(side=tk.LEFT)
        ttk.Label(media, text="Video: (placeholder — integrate OpenCV/UDP later)").pack(side=tk.LEFT, padx=12)

    # Actions
    def activate(self, room_code: str):
        self.lbl_room.configure(text=f"Room: {room_code}")
        self.req_users()

    def leave_room(self):
        self.app.aio(self.app.client.leave_room())
        self.app.current_room_code = None
        self.app.go_lobby()

    def req_users(self):
        rc = self.app.current_room_code
        if rc:
            self.app.aio(self.app.client.list_users(rc))

    def send_chat(self):
        txt = self.ent_msg.get().strip()
        if not txt: return
        self.app.aio(self.app.client.send_chat(txt))
        self.ent_msg.delete(0, tk.END)

    def send_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.app.aio(self.app.client.send_file(path))

    def append_log(self, line: str):
        self.txt_chat.configure(state=tk.NORMAL)
        self.txt_chat.insert(tk.END, line+"\n")
        self.txt_chat.configure(state=tk.DISABLED)
        self.txt_chat.see(tk.END)

    def render_users(self, users):
        self.lst_users.delete(0, tk.END)
        for u in users:
            self.lst_users.insert(tk.END, u)

    def handle_file_message(self, e: dict):
        out = self.assembler.handle(e)
        if out:
            self.append_log(f"[✓] File saved: {out}")

    def toggle_mic(self):
        self.append_log(f"[media] Mic: {'ON' if self.mic_on.get() else 'OFF'} (stub)")

    def toggle_cam(self):
        self.append_log(f"[media] Camera: {'ON' if self.cam_on.get() else 'OFF'} (stub)")

# ----------------------------- App Controller -----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HPH class")
        self.geometry("1100x720")

        # Defaults (được dùng thay cho UI server/port)
        self.default_host = "127.0.0.1"
        self.default_port = 9000

        # Styles & hover
        self.style = ttk.Style(self)
        try:
            self.style.theme_use('clam')  # theme này hỗ trợ đổi background tốt hơn
        except Exception:
            pass
        self.style.configure('App.TButton', padding=6, background='#0f131a', foreground='#eeeeee', borderwidth=1)
        self.style.configure('Hover.App.TButton', padding=6, background='#1a2230', foreground='#ffffff', borderwidth=1)

        # Async loop in background thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()

        # Network state
        self.client: Optional[ChatClient] = None
        self.username: Optional[str] = None
        self.current_room_code: Optional[str] = None

        # Pages
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.pages = {}
        self.login_view = LoginView(self, self.container)
        self.lobby_view = LobbyView(self, self.container)
        self.room_view = RoomView(self, self.container)
        self.pages["login"] = self.login_view
        self.pages["lobby"] = self.lobby_view
        self.pages["room"] = self.room_view
        for p in self.pages.values():
            p.place(x=0, y=0, relwidth=1, relheight=1)
        self.go_login()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # Styling helper: áp hiệu ứng hover cho nút ttk
    def stylize_button(self, btn: ttk.Button):
        try:
            btn.configure(style='App.TButton', cursor='hand2')
            btn.bind('<Enter>', lambda e: btn.configure(style='Hover.App.TButton'))
            btn.bind('<Leave>', lambda e: btn.configure(style='App.TButton'))
        except Exception:
            pass

    # Navigation
    def go_login(self):
        self.show_page("login")
        self.login_view.set_status("")

    def go_lobby(self):
        self.show_page("lobby")
        self.lobby_view.activate()

    def go_room(self, room_code: str):
        self.current_room_code = room_code
        self.show_page("room")
        self.room_view.activate(room_code)

    def show_page(self, name: str):
        for n, p in self.pages.items():
            if n == name:
                p.lift()

    # Async helpers
    def aio(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    # Network connect/login
    def connect_and_login(self, host: str, port: int, username: str, gmail: str):
        self.username = username
        self.client = ChatClient(host, port, on_event=lambda e: self.after(0, self.on_event, e))
        def runner():
            async def task():
                await self.client.connect()
                await self.client.login(username, gmail)
            asyncio.run(task())
        threading.Thread(target=runner, daemon=True).start()

    # Event router
    def on_event(self, e: dict):
        t = e.get("type")
        if t == "local" and e.get("event") == "connected":
            self.login_view.set_status("Đã kết nối — đang đăng nhập…")
        elif t == "error":
            messagebox.showerror("Error", e.get("error", ""))
        elif t == "auth":
            if e.get("status") == "ok":
                self.login_view.set_status("Login OK")
                self.go_lobby()
            else:
                self.login_view.set_status("Login thất bại: " + str(e.get("error")))
        elif t == "room" and "rooms" in e:
            self.lobby_view.render_rooms(e["rooms"])
        elif t == "room" and e.get("status") == "ok" and e.get("room_code"):
            # Join success → go room
            self.go_room(e["room_code"])
        elif t == "users":
            if e.get("room_code") == self.current_room_code:
                self.room_view.render_users(e.get("users", []))
        elif t == "presence":
            if e.get("room_code") == self.current_room_code:
                self.room_view.append_log(f"[*] {e['user']} {e['event']} {e['room_code']}")
                self.room_view.req_users()
        elif t == "chat":
            if e.get("room_code") == self.current_room_code:
                self.room_view.append_log(f"[{e.get('room_code')}] {e.get('from')}: {e.get('text')}")
        elif t == "dm":
            self.room_view.append_log(f"[DM] {e.get('from')} → {e.get('to')}: {e.get('text')}")
        elif t == "file":
            self.room_view.handle_file_message(e)
        elif t == "local" and e.get("event") == "file_progress":
            sent, total = e["sent"], e["total"]
            pct = (sent/total)*100 if total else 0
            self.room_view.append_log(f"[upload] {e['filename']}: {pct:.1f}%")

    # High-level actions
    def join_room(self, code: str, pwd: str):
        if not self.client:
            return
        self.aio(self.client.join_by_code(code, pwd))

    def on_close(self):
        try:
            if self.client:
                self.aio(self.client.close())
        except Exception:
            pass
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
