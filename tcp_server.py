# TCP đảm bảo dữ liệu không mất, nên dùng cho chat text, login/logout, truyền file nhỏ.
import asyncio
import json 
import struct 

clients={} # dict để lưu trữ thông tin client

async def send_msg(writer, data: dict):
    raw=json.dumps(data).encode('utf-8') # mã hóa dict thành JSON và sau đó thành bytes
    writer.write(struct.pack('!I',len(raw))+raw) # gửi tiền tố độ dài và dữ liệu
    await writer.drain() # đảm bảo dữ liệu được gửi

async def read_msg(reader):
    header=await reader.readexactly(4) # đọc tiền tố độ dài
    (ln,)=struct.unpack("!I",header) # giải nén độ dài
    raw=await reader.readexactly(ln) # đọc dữ liệu
    return json.loads(raw.decode('utf-8')) # giải mã JSON và trả về dict

# Set up and main loop
async def handle_client(reader,writer):
    username=None 
    try:
        while True:
            # Message processing 
            msg=await read_msg(reader) # đọc tin nhắn từ client
            t=msg.get('type')

            # Login handling
            if t=='login':
                username=msg['user']
                clients[username]=writer # lưu thông tin client
                await send_msg(writer,{'type':'login_ok'})
                print(f"{username} logged in")
            # Chat broadcasting
            elif t=='chat':
                text=msg['text']
                for u,w in clients.items():
                    if u != username:
                        await send_msg(w,{'type':'chat','from':username,'text':text})
            # File sharing
            elif t=='file_chunk':
                # relay file chunk cho tat ca client khac 
                for u,w in clients.items():
                    if u != username:
                        await send_msg(w,msg)
            # Logout handling
            elif t=='logout':
                break 
    # Error handling và cleanup
    except Exception as e:
        print('Error:',e)
    finally:
        if username and username in clients: # Kiểm tra xem người dùng có tồn tại trong clients không
            clients.pop(username) # xóa client khỏi dict
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client,'0.0.0.0',5000)
    print("Server started on port 5000")
    async with server:
        await server.serve_forever()

if __name__=="__main__":
    asyncio.run(main())