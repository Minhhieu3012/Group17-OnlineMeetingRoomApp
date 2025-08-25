# UDP nhanh, không đảm bảo đủ gói → chấp nhận mất vài gói, dùng cho video,voice
import socket,json 

clients_udp={} 

def udp_server():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM) # UDP
    sock.bind(('0.0.0.0',5000))
    print("UDP server started on port 5000")

    while True:
        data,addr=sock.recvfrom(65536) # nhận dữ liệu từ client
        try:
            # header + payload 
            header, payload=data.split(b'\n\n',1)
            h=json.loads(header.decode('utf-8'))
            username=h['from']
            room=h['room']

            # dang ky endpoint
            clients_udp[username]=addr

            # relay den cac client khac trong phong
            for u,ep in clients_udp.items():
                if u != username:
                    sock.sendto(data,ep)
        except Exception as e:
            print("UDP error:", e)

if __name__=="__main__":
    udp_server()