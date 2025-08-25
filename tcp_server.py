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

async def handle_client(reader,writer):
    username=None 
    try:
        while True:
            msg=await read_msg(reader) # đọc tin nhắn từ client
            t=msg.get('type')

            if t=='login':
                username=msg['user']
                clients[username]=writer # lưu thông tin client
                await send_msg(writer,{'type':'login_ok'})
                print(f"{username} logged in")
            elif t=='chat':
                text=msg['text']
                for u,w in clients.items():
                    if u != username:
                        await send_msg(w,{'type':'chat','from':username,'text':text})
            elif t=='file_chunk':
                # relay file chunk cho tat ca client khac 
                for u,w in clients.items():
                    if u != username:
                        await send_msg(w,msg)
            
            elif t=='logout':
                break 
    except Exception as e:
        print('Error:',e)
    finally:
        if username and username in clients:
            clients.pop(username) # xóa client khỏi dict
        writer.close()
        await writer.wait_closed()