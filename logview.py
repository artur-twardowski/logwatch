import socket
from sys import argv, stdout
import json

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = int(argv[1])  # The port used by the server

COLORS={
    "stdout": "1;34m",
    "stderr": "1;31m",
    "stdin": "1;33m"
}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(b"Hello, world")

    while True:
        data_recv = s.recv(4096)

        if not data_recv:
            break

        data_recv_str = str(data_recv, 'utf-8')

        for data_json in data_recv_str.split('\0'):
            if len(data_json) == 0:
                continue
            data = json.loads(data_json)
            if data['type'] == 'data':
                stdout.write("\x1b[%s%s \x1b[0m%s\n" % (COLORS[data['fd']], data['endpoint'], data['data']))

