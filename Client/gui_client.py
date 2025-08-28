# filename: gui_client.py
import asyncio, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from client_core import ChatClient, FileAssembler

class GUIApp:
    def __init__(self, root):
        self.root = root
        root.title("All‑in‑One Meeting — Client")
        root.geometry("1100x720")

        # State
        self.client: ChatClient | None = None
        self.assembler = FileAssembler()
        self.current_room_code = tk.StringVar(value="")
        self.mic_on = tk.BooleanVar(value=False)
        self.cam_on = tk.BooleanVar(value=False)

        # Top: Login
        top = ttk.Frame(root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Server:").pack(side=tk.LEFT)
        self.ent_host = ttk.Entry(top, width=16); self.ent_host.insert(0, "127.0.0.1"); self.ent_host.pack(side=tk.LEFT, padx=4)
        self.ent_port = ttk.Entry(top, width=6); self.ent_port.insert(0, "9000"); self.ent_port.pack(side=tk.LEFT)
        ttk.Label(top, text="Username:").pack(side=tk.LEFT, padx=(12,0))
        self.ent_user = ttk.Entry(top, width=12); self.ent_user.pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="Gmail:").pack(side=tk.LEFT)
        self.ent_gmail = ttk.Entry(top, width=22); self.ent_gmail.pack(side=tk.LEFT, padx=4)
        self.btn_connect = ttk.Button(top, text="Connect & Login", command=self.on_connect_login)
        self.btn_connect.pack(side=tk.LEFT, padx=8)

        # Middle: Columns
        mid = ttk.Frame(root, padding=8); mid.pack(fill=tk.BOTH, expand=True)

        # Left: Rooms + Create/Join by code
        left = ttk.Frame(mid); left.pack(side=tk.LEFT, fill=tk.Y, padx=(0,8))
        ttk.Label(left, text="Rooms").pack(anchor=tk.W)
        self.lst_rooms = tk.Listbox(left, height=12); self.lst_rooms.pack(fill=tk.Y)
        btns = ttk.Frame(left); btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="Refresh", command=self.req_rooms).pack(side=tk.LEFT)
        ttk.Button(btns, text="Join (select)", command=self.join_selected).pack(side=tk.LEFT, padx=4)

        # Create room
        frm_create = ttk.LabelFrame(left, text="Create Room", padding=8)
        frm_create.pack(fill=tk.X, pady=6)
        self.ent_room_name = ttk.Entry(frm_create); self.ent_room_name.insert(0, "Team A"); self.ent_room_name.pack(fill=tk.X, pady=2)
        self.ent_room_pwd = ttk.Entry(frm_create); self.ent_room_pwd.insert(0, ""); self.ent_room_pwd.pack(fill=tk.X, pady=2)
        ttk.Button(frm_create, text="Create", command=self.create_room).pack(fill=tk.X)

        # Join by code
        frm_join = ttk.LabelFrame(left, text="Join by Code", padding=8)
        frm_join.pack(fill=tk.X, pady=6)
        self.ent_room_code = ttk.Entry(frm_join); self.ent_room_code.insert(0, ""); self.ent_room_code.pack(fill=tk.X, pady=2)
        self.ent_join_pwd = ttk.Entry(frm_join); self.ent_join_pwd.insert(0, ""); self.ent_join_pwd.pack(fill=tk.X, pady=2)
        ttk.Button(frm_join, text="Join", command=self.join_by_code).pack(fill=tk.X)

        # Right: Users
        right = ttk.Frame(mid); right.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Label(right, text="Users in room").pack(anchor=tk.W)
        self.lst_users = tk.Listbox(right, height=12); self.lst_users.pack(fill=tk.Y)
        ttk.Button(right, text="Refresh", command=self.req_users).pack(pady=4)

        # Center: Chat
        center = ttk.Frame(mid); center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_chat = tk.Text(center, state=tk.DISABLED, height=28)
        self.txt_chat.pack(fill=tk.BOTH, expand=True)
        bottom = ttk.Frame(center); bottom.pack(fill=tk.X)
        self.ent_msg = ttk.Entry(bottom); self.ent_msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(bottom, text="Send", command=self.send_chat).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="Send File", command=self.send_file).pack(side=tk.LEFT)

        # Media controls & video placeholder
        media = ttk.Frame(root, padding=8); media.pack(fill=tk.X)
        ttk.Checkbutton(media, text="Mic", variable=self.mic_on, command=self.toggle_mic).pack(side=tk.LEFT)
        ttk.Checkbutton(media, text="Camera", variable=self.cam_on, command=self.toggle_cam).pack(side=tk.LEFT)
        ttk.Label(media, text="Video: (placeholder — integrate OpenCV/UDP later)").pack(side=tk.LEFT, padx=12)

        self.log("Ready.")

    # -------------- UI helpers --------------
    def log(self, line: str):
        self.txt_chat.configure(state=tk.NORMAL)
        self.txt_chat.insert(tk.END, line+"\n")
        self.txt_chat.configure(state=tk.DISABLED)
        self.txt_chat.see(tk.END)

    def on_event(self, e: dict):
        t = e.get("type")
        if t == "local" and e.get("event") == "connected":
            self.log("[i] Connected.")
            self.req_rooms()
        elif t == "local" and e.get("event") == "disconnected":
            self.log("[i] Disconnected.")
        elif t == "error":
            self.log("[!] Error: "+e.get("error",""))
        elif t == "room" and "rooms" in e:
            self.lst_rooms.delete(0, tk.END)
            for r in e["rooms"]:
                label = f"{r['name']} ({r.get('count','?')}) code={r.get('code','?')}"
                self.lst_rooms.insert(tk.END, label)
        elif t == "users":
            self.lst_users.delete(0, tk.END)
            for u in e.get("users", []):
                self.lst_users.insert(tk.END, u)
        elif t == "presence":
            self.log(f"[*] {e['user']} {e['event']} {e['room_code']}")
            self.req_users()
        elif t == "chat":
            self.log(f"[{e.get('room_code')}] {e.get('from')}: {e.get('text')}")
        elif t == "dm":
            self.log(f"[DM] {e.get('from')} → {e.get('to')}: {e.get('text')}")
        elif t == "file":
            out = self.assembler.handle(e)
            if out:
                self.log(f"[✓] File saved: {out}")
        elif t == "local" and e.get("event") == "file_progress":
            sent, total = e["sent"], e["total"]
            pct = (sent/total)*100 if total else 0
            self.log(f"[upload] {e['filename']}: {pct:.1f}%")

    # -------------- Actions --------------
    def on_connect_login(self):
        host = self.ent_host.get().strip()
        port = int(self.ent_port.get().strip())
        user = self.ent_user.get().strip()
        gmail = self.ent_gmail.get().strip()
        if not user or not gmail:
            messagebox.showwarning("Login", "Enter username and gmail")
            return
        self.client = ChatClient(host, port, on_event=lambda e: self.root.after(0, self.on_event, e))
        threading.Thread(target=self._async_connect_and_login, args=(user, gmail), daemon=True).start()

    def _async_connect_and_login(self, user, gmail):
        asyncio.run(self._connect_and_login(user, gmail))

    async def _connect_and_login(self, user, gmail):
        await self.client.connect()
        await self.client.login(user, gmail)

    def req_rooms(self):
        if self.client:
            asyncio.run_coroutine_threadsafe(self.client.list_rooms(), asyncio.get_event_loop())

    def join_selected(self):
        sel = self.lst_rooms.curselection()
        if not sel or not self.client:
            return
        label = self.lst_rooms.get(sel[0])
        # extract code=XXXX at the end
        parts = label.split("code=")
        if len(parts) >= 2:
            code = parts[-1].strip()
            self.current_room_code.set(code)
            asyncio.run_coroutine_threadsafe(self.client.join_by_code(code, ""), asyncio.get_event_loop())
            self.log(f"[i] Joined {code}")
            self.req_users()

    def create_room(self):
        if not self.client:
            return
        name = self.ent_room_name.get().strip()
        pwd = self.ent_room_pwd.get().strip()
        asyncio.run_coroutine_threadsafe(self.client.create_room(name, pwd), asyncio.get_event_loop())

    def join_by_code(self):
        if not self.client:
            return
        code = self.ent_room_code.get().strip()
        pwd = self.ent_join_pwd.get().strip()
        self.current_room_code.set(code)
        asyncio.run_coroutine_threadsafe(self.client.join_by_code(code, pwd), asyncio.get_event_loop())
        self.log(f"[i] Joined {code}")
        self.req_users()

    def req_users(self):
        if self.client and self.current_room_code.get():
            asyncio.run_coroutine_threadsafe(self.client.list_users(self.current_room_code.get()), asyncio.get_event_loop())

    def send_chat(self):
        txt = self.ent_msg.get().strip()
        if not txt or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self.client.send_chat(txt), asyncio.get_event_loop())
        self.ent_msg.delete(0, tk.END)

    def send_file(self):
        if not self.client:
            return
        path = filedialog.askopenfilename()
        if path:
            asyncio.run_coroutine_threadsafe(self.client.send_file(path), asyncio.get_event_loop())

    def toggle_mic(self):
        self.log(f"[media] Mic: {'ON' if self.mic_on.get() else 'OFF'} (stub)")

    def toggle_cam(self):
        self.log(f"[media] Camera: {'ON' if self.cam_on.get() else 'OFF'} (stub)")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    root = tk.Tk()
    app = GUIApp(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    threading.Thread(target=loop.run_forever, daemon=True).start()
    root.mainloop()
    loop.call_soon_threadsafe(loop.stop)
