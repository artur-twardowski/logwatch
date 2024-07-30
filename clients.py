import socket
import threading as thrd


class GenericTCPClient:
    RECV_SIZE = 1024

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._socket = None
        self._receiver_thread = None
        self._enabled = True

    def run(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._host, self._port))

        self._receiver_thread = thrd.Thread(target=self._receiver_worker)
        self._receiver_thread.start()

    def stop(self):
        self._enabled = False
        self._receiver_thread.join()

    def _receiver_worker(self):
        while self._enabled:
            data_recv = self._socket.recv(self.RECV_SIZE)

            if not data_recv:
                self._enabled = False
                break

            self.on_data_received(data_recv)

    def send(self, data):
        if isinstance(data, str):
            self._socket.sendall(bytes(data + '\0', 'utf-8'))
        else:
            self._socket.sendall(data)

    def on_data_received(self, data):
        pass



