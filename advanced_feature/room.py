from client_base import ChatClientGUI, NetworkThread, HOST, PORT
import tkinter as tk

class FeatureChatClient(ChatClientGUI):
    def _build_widgets(self):
        super()._build_widgets()

        # Thêm nút Kick user
        self.btn_kick = tk.Button(self.root, text="Kick User", command=self.kick_user, state="disabled")
        # Đặt cạnh danh sách user (UI trực quan hơn)
        self.btn_kick.pack(side="right", fill="y")

    def _handle(self, m):
        super()._handle(m)

        # Khi bạn là owner phòng (server báo event room_created)
        if m.get("type") == "ok" and m.get("event") == "room_created":
            self.btn_kick.config(state="normal")

        # Nếu server gửi thông tin phòng (có owner)
        elif m.get("type") == "room_info":
            if m.get("owner") == self.username:
                self.btn_kick.config(state="normal")
            else:
                self.btn_kick.config(state="disabled")

        # Nếu bị kick khỏi phòng
        elif m.get("type") == "system" and m.get("event") == "kicked":
            self._append("🚪 Bạn đã bị kick khỏi phòng.")
            self.btn_kick.config(state="disabled")

        # Server phản hồi sau khi gửi lệnh kick
        elif m.get("type") == "ok" and m.get("event") == "kick_success":
            self._append(f"✅ Kick {m['target']} thành công")
        elif m.get("type") == "error" and m.get("event") == "kick_failed":
            self._append(f"❌ Kick thất bại: {m.get('message','Lỗi không rõ')}")

    def kick_user(self):
        try:
            target = self.list_users.get(self.list_users.curselection())
        except:
            self._append("⚠️ Chọn user trong danh sách để kick")
            return

        if target == self.username:
            self._append("⚠️ Không thể tự kick mình")
            return

        # Gửi lệnh kick lên server
        self.net.send({"type": "kick", "target": target})
        self._append(f"👉 Gửi yêu cầu kick {target}")


if __name__=="__main__":
    tk.Tk().withdraw()
    root = tk.Tk()
    FeatureChatClient(root)
    root.mainloop()
