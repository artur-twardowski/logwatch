import socket
import threading as thrd

class GenericTCPClient:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._socket = None
        self._receiver_thread = None
        self._enabled = True

    def run(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect( (self._host, self._port) )

        self._receiver_thread = thrd.Thread(target=self._receiver_worker)
        self._receiver_thread.start()

    def stop(self):
        self._enabled = False
        self._receiver_thread.join()
        pass

    def _receiver_worker(self):
        while self._enabled:
            #TODO: this should be buffered
            data_recv = self._socket.recv(32768)

            if not data_recv:
                self._enabled = False
                break

            self.on_data_received(data_recv)

    def send(self, data):
        self._socket.sendall(data)

    def on_data_received(self, data):
        pass



