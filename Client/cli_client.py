# filename: cli_client.py
import asyncio, sys
from client_core import ChatClient, FileAssembler

HELP = """
Commands:
  /login <username> <gmail>
  /rooms
  /create <room_name> <password_or_empty>
  /joincode <room_code> <password_or_empty>
  /leave
  /users [room_code]
  /msg <text>
  /dm <user> <text>
  /sendfile <path>
  /help
  /quit
"""

assembler = FileAssembler()

def print_event(e: dict):
    t = e.get("type")
    if t == "local" and e.get("event") == "connected":
        print("[i] Connected.")
    elif t == "local" and e.get("event") == "disconnected":
        print("[i] Disconnected.")
    elif t == "error":
        print("[!] Error:", e.get("error"))
    elif t == "room" and "rooms" in e:
        print("Rooms:")
        for r in e["rooms"]:
            print(f" - {r['name']} ({r.get('count','?')}) code={r.get('code','?')}")
    elif t == "users":
        print(f"Users in {e.get('room_code')}: {', '.join(e.get('users', []))}")
    elif t == "presence":
        print(f"[*] {e['user']} {e['event']} {e['room_code']}")
    elif t == "chat":
        print(f"[{e.get('room_code')}] {e.get('from')}: {e.get('text')}")
    elif t == "dm":
        print(f"[DM] {e.get('from')} → {e.get('to')}: {e.get('text')}")
    elif t == "file":
        out = assembler.handle(e)
        if out:
            print(f"[✓] File saved: {out}")
    elif t == "local" and e.get("event") == "file_progress":
        sent, total = e["sent"], e["total"]
        pct = (sent/total)*100 if total else 0
        print(f"[upload] {e['filename']}: {pct:.1f}%")

async def user_input_loop(client: ChatClient):
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        if line == "/help":
            print(HELP)
        elif line == "/quit":
            await client.close()
            break
        elif line.startswith("/login "):
            try:
                _, u, g = line.split(" ", 2)
            except ValueError:
                print("Usage: /login <username> <gmail>")
                continue
            await client.login(u, g)
        elif line == "/rooms":
            await client.list_rooms()
        elif line.startswith("/create "):
            parts = line.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /create <room_name> <password_or_empty>")
                continue
            name, pwd = parts[1], parts[2]
            await client.create_room(name, pwd)
        elif line.startswith("/joincode "):
            parts = line.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /joincode <room_code> <password_or_empty>")
                continue
            code, pwd = parts[1], parts[2]
            await client.join_by_code(code, pwd)
        elif line == "/leave":
            await client.leave_room()
        elif line.startswith("/users"):
            parts = line.split(" ", 1)
            rc = parts[1] if len(parts) == 2 else None
            await client.list_users(rc)
        elif line.startswith("/msg "):
            _, text = line.split(" ", 1)
            await client.send_chat(text)
        elif line.startswith("/dm "):
            try:
                _, to_user, text = line.split(" ", 2)
            except ValueError:
                print("Usage: /dm <user> <text>")
                continue
            await client.send_dm(to_user, text)
        elif line.startswith("/sendfile "):
            _, path = line.split(" ", 1)
            await client.send_file(path)
        else:
            print("Unknown command. /help")

async def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
    client = ChatClient(host, port, on_event=print_event)
    await client.connect()
    print(HELP)
    await user_input_loop(client)

if __name__ == "__main__":
    asyncio.run(main())
