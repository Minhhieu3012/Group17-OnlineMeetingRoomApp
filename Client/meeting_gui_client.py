"""
HPH Meeting – GUI Wrapper (modular views)

Chạy bằng:
    python -m Client.meeting_gui_client
"""
from __future__ import annotations

import base64
import json
import queue
import socket
import struct
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

# --- imports view (ổn định khi chạy -m) ---
try:
    from Client.gui_login import LoginView
    from Client.gui_lobby import LobbyView
    from Client.gui_room import RoomView
except Exception:  # fallback khi chạy trực tiếp file
    from gui_login import LoginView
    from gui_lobby import LobbyView
    from gui_room import RoomView

# --- config & crypto helpers ---
from advanced_feature import config_client
from server.utils import aes_encrypt, aes_decrypt, CRYPTO_AVAILABLE, recvall

# ============================ TCP JSON CLIENT ============================= #
class TCPJsonClient:
    """Length‑prefixed JSON over TCP; AES‑GCM after login_ok."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.aes_key: Optional[bytes] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rx_queue: "queue.Queue[dict]" = queue.Queue()
        self._alive = False

    # --- send ---
    def _send_plain(self, obj: dict) -> None:
        data = json.dumps(obj).encode("utf-8")
        header = struct.pack("!I", len(data))
        assert self.sock is not None
        self.sock.sendall(header + data)

    def _send_secure(self, obj: dict) -> None:
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Cryptography not installed")
        assert self.aes_key is not None and self.sock is not None
        blob = aes_encrypt(json.dumps(obj).encode("utf-8"), self.aes_key)
        header = struct.pack("!I", len(blob))
        self.sock.sendall(header + blob)

    def send(self, obj: dict) -> None:
        if self.aes_key is None or obj.get("type") == "login":
            self._send_plain(obj)
        else:
            self._send_secure(obj)

    # --- recv ---
    def _read_plain(self) -> dict:
        assert self.sock is not None
        (length,) = struct.unpack("!I", recvall(self.sock, 4))
        raw = recvall(self.sock, length)
        return json.loads(raw.decode("utf-8"))

    def _read_secure(self) -> dict:
        assert self.sock is not None and self.aes_key is not None
        (length,) = struct.unpack("!I", recvall(self.sock, 4))
        blob = recvall(self.sock, length)
        plain = aes_decrypt(blob, self.aes_key)
        return json.loads(plain.decode("utf-8"))

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(2)
        self._alive = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def close(self) -> None:
        self._alive = False
        try:
            if self.sock:
                self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def _rx_loop(self) -> None:
        while self._alive and self.sock is not None:
            try:
                msg = self._read_secure() if self.aes_key else self._read_plain()
                if isinstance(msg, dict) and msg.get("type") == "login_ok":
                    key_b64 = msg.get("aes_key_b64")
                    if key_b64:
                        try:
                            self.aes_key = base64.b64decode(key_b64)
                        except Exception:
                            self.aes_key = None
                self._rx_queue.put(msg)
            except socket.timeout:
                continue
            except Exception:
                self._alive = False
                break

    def get_message_nowait(self) -> Optional[dict]:
        try:
            return self._rx_queue.get_nowait()
        except queue.Empty:
            return None


# ================================ THEME ================================== #
PALETTE = {
    "bg": "#0f172a",
    "panel": "#111827",
    "panel2": "#0b1220",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
    "primary": "#6c63ff",
    "success": "#10b981",
    "danger": "#ef4444",
}
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_H1 = ("Segoe UI", 16, "bold")
FONT_BASE = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 10)


# ============================== MAIN APP ================================= #
class MeetingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("HPH Meeting – Client")
        self.geometry("1080x680")
        self.minsize(960, 600)
        self.configure(bg=PALETTE["bg"])

        # Networking
        self.client = TCPJsonClient(config_client.SERVER_HOST, config_client.TCP_PORT)
        self.username: Optional[str] = None
        self.room: Optional[str] = None

        # Optional media clients
        self.voice = None
        self.video = None
        self.mic_on = False
        self.cam_on = False

        # Styles
        self._init_style()

        # View container
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)

        # Init views
        self.views: dict[str, tk.Frame] = {}
        self.views["LoginView"] = LoginView(self.container, app=self)
        self.views["LobbyView"] = LobbyView(self.container, app=self)
        self.views["RoomView"] = RoomView(self.container, app=self)
        for v in self.views.values():
            v.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.show("LoginView")
        self.after(60, self._pump_network)

    # --------------------- Styling --------------------- #
    def _init_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=PALETTE["bg"]) 
        style.configure("Panel.TFrame", background=PALETTE["panel"]) 
        style.configure("Panel2.TFrame", background=PALETTE["panel2"]) 
        style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=FONT_BASE)
        style.configure("Heading.TLabel", font=FONT_H1)
        style.configure("Muted.TLabel", foreground=PALETTE["muted"], font=FONT_SMALL)
        style.configure("TButton", font=FONT_BASE, padding=8)
        style.map("TButton", background=[("active", PALETTE["primary"])])
        style.configure("Primary.TButton", background=PALETTE["primary"], foreground="#fff")
        style.map("Primary.TButton", background=[("active", "#5a54e6")])
        style.configure("Danger.TButton", background=PALETTE["danger"], foreground="#fff")
        style.configure("Success.TButton", background=PALETTE["success"], foreground="#062a24")
        style.configure("TEntry", fieldbackground="#1f2937", foreground=PALETTE["text"], insertcolor=PALETTE["text"], padding=6)
        style.configure("Card.TLabelframe", background=PALETTE["panel"], foreground=PALETTE["text"], borderwidth=0)
        style.configure("Card.TLabelframe.Label", background=PALETTE["panel"], foreground=PALETTE["muted"], font=FONT_SMALL)

    # --------------------- View switch --------------------- #
    def show(self, name: str) -> None:
        frame = self.views[name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            try:
                frame.on_show()
            except Exception:
                pass

    # --------------------- Networking pump --------------------- #
    def _pump_network(self) -> None:
        while True:
            msg = self.client.get_message_nowait()
            if msg is None:
                break
            self._handle_message(msg)
        self.after(60, self._pump_network)

    def _handle_message(self, msg: dict) -> None:
        t = msg.get("type")
        p = msg.get("payload", {})
        if t == "login_ok":
            if "LoginView" in self.views and hasattr(self.views["LoginView"], "set_status"):
                self.views["LoginView"].set_status("Đăng nhập thành công!", ok=True)
            self.show("LobbyView")
            self.client.send({"type": "list_rooms", "payload": {}})
        elif t == "rooms":
            if "LobbyView" in self.views and hasattr(self.views["LobbyView"], "populate_rooms"):
                self.views["LobbyView"].populate_rooms(msg.get("rooms", []))
        elif t == "join_room_ok":
            self.room = msg.get("room")
            if "RoomView" in self.views:
                rv = self.views["RoomView"]
                if hasattr(rv, "set_room"):
                    rv.set_room(self.room)
                if hasattr(rv, "set_participants"):
                    rv.set_participants(msg.get("users", []))
                if hasattr(rv, "append_chat"):
                    rv.append_chat(f"— joined room {self.room} —")
            self.show("RoomView")
        elif t == "participant_joined":
            rv = self.views.get("RoomView")
            if rv and hasattr(rv, "user_joined"):
                rv.user_joined(msg.get("from"))
        elif t == "participant_left":
            rv = self.views.get("RoomView")
            if rv and hasattr(rv, "user_left"):
                rv.user_left(msg.get("from"))
        elif t == "chat":
            rv = self.views.get("RoomView")
            if rv and hasattr(rv, "append_chat"):
                rv.append_chat(f"{msg.get('from')}: {p.get('text','')}")
        elif not msg.get("ok", True):
            messagebox.showerror("Server", msg.get("error", "Unknown error"))

    # --------------------- App actions (called by views) ------------------ #
    def do_login(self, username: str, email: str) -> None:
        if self.client.sock is None:
            try:
                self.client.connect()
            except Exception as e:
                if "LoginView" in self.views and hasattr(self.views["LoginView"], "set_status"):
                    self.views["LoginView"].set_status(f"Không kết nối được server: {e}", ok=False)
                return
        self.username = username
        self.client.send({"type": "login", "payload": {"username": username, "password": email or "nopass"}})
        if "LoginView" in self.views and hasattr(self.views["LoginView"], "set_status"):
            self.views["LoginView"].set_status("Đang đăng nhập…", ok=None)

    def refresh_rooms(self) -> None:
        if self.client.sock and self.client.aes_key:
            self.client.send({"type": "list_rooms", "payload": {}})

    def create_room(self, room: str) -> None:
        self.client.send({"type": "create_room", "payload": {"room": room}})
        self.join_room(room)

    def join_room(self, room: str) -> None:
        self.client.send({"type": "join_room", "payload": {"room": room}})

    def leave_room(self) -> None:
        self.client.send({"type": "leave_room", "payload": {}})
        self.room = None
        self.show("LobbyView")

    def send_chat(self, text: str) -> None:
        self.client.send({"type": "chat", "payload": {"text": text}})

    # Media toggles (dùng advanced_feature.voice_chat/video_call)
    def toggle_mic(self) -> bool:
        try:
            from advanced_feature.voice_chat import VoiceChatClient
        except Exception:
            messagebox.showwarning("Audio", "Chưa cài PyAudio hoặc voice client.")
            return False
        if not self.room:
            messagebox.showwarning("Audio", "Hãy tham gia phòng trước.")
            return False
        if not self.mic_on:
            self.voice = VoiceChatClient(config_client.SERVER_HOST, config_client.UDP_PORT_VOICE)
            self.voice.start(self.room, self.username or "user")
            self.mic_on = True
        else:
            try:
                if self.voice:
                    self.voice.stop()
            finally:
                self.mic_on = False
        return self.mic_on

    def toggle_cam(self, show_window: bool = False) -> bool:
        try:
            from advanced_feature.video_call import VideoCallClient
        except Exception:
            messagebox.showwarning("Video", "Chưa cài OpenCV hoặc video client.")
            return False
        if not self.room:
            messagebox.showwarning("Video", "Hãy tham gia phòng trước.")
            return False
        if not self.cam_on:
            self.video = VideoCallClient(config_client.SERVER_HOST, config_client.UDP_PORT_VIDEO)
            self.video.start(self.room, self.username or "user")
            self.cam_on = True
        else:
            try:
                if self.video:
                    self.video.stop()
            finally:
                self.cam_on = False
        return self.cam_on


# --------------------------------- MAIN ---------------------------------- #
if __name__ == "__main__":
    app = MeetingApp()
    app.mainloop()
