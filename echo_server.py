import socket

host = "0.0.0.0"
port = 5050

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((host, port))
sock.listen()
print('Socket listening on host', host, 'and port', port)

while True:
    conn, addr = sock.accept()
    print("connected:", addr)
    try:
        while conn:
            data = conn.recv(512)
            if not data:
                break
            conn.sendall(data.upper())
    finally:
        print("disconnected:", addr)
        conn.close()