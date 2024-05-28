import socket
from sys import argv

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = int(argv[1])  # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(b"Hello, world")

    while True:
        data = s.recv(1024)
        if data:
            print(f"Received {data!r}")
        else:
            break

