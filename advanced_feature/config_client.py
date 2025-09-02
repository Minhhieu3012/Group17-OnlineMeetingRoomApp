"""
Config cho CLIENT – chạy trên máy client (meeting_gui_client).
Cần chỉnh SERVER_HOST thành IP của máy server trong mạng LAN/VPN.
"""

# Địa chỉ IP của server:
# - Nếu chạy client trên cùng máy với server: dùng "127.0.0.1"
# - Nếu máy khác: điền IP LAN hoặc IP RadminVPN của server (ví dụ "26.45.123.10")
SERVER_HOST = "26.62.100.145" # ⚠️ Máy khác thì nhớ đổi thành IP của server

TCP_PORT = 8888
UDP_PORT_VOICE = 9999
UDP_PORT_VIDEO = 10000

UDP_PORT = UDP_PORT_VOICE

GATEWAY_PORT = 8765
WS_PORT = GATEWAY_PORT

APP_NAME = "HPH Meeting – Client"
