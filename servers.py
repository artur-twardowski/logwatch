import socket
import selectors
from types import SimpleNamespace
import threading as thrd
from utils import debug, info, error
from time import sleep
import os


class GenericTCPServer:
    def __init__(self, port=None, filename=None):
        self._port = port
        self._filename = filename
        self._enabled = True
        self._selector = selectors.DefaultSelector()
        self._listen_thread = None
        self._clients = {}

    def run(self):
        self._listen_thread = thrd.Thread(target=self._listen_worker)
        self._listen_thread.start()

    def stop(self):
        self._enabled = False
        self._listen_thread.join()

    def _accept(self, client_sock):
        conn, addr = client_sock.accept()
        info("Received a connection from %s:%s" % addr)
        conn.setblocking(False)
        self._selector.register(conn, selectors.EVENT_READ | selectors.EVENT_WRITE, SimpleNamespace(addr=addr, inb=b'', outb=b''))
        self._clients[addr] = conn
        self.on_client_connected(addr, conn)

    def _serve(self, sock, data, mask):
        if mask & selectors.EVENT_READ:
            try:
                recv_data = sock.recv(4096)
            except ConnectionResetError:
                recv_data = None

            if recv_data:
                debug("Received data: %s" % recv_data)
                self.on_data_received(data.addr, recv_data)
            else:
                info("Closing connection from %s:%s" % data.addr)
                self._selector.unregister(sock)
                del self._clients[data.addr]
                sock.close()

        if mask & selectors.EVENT_WRITE:
            if data.outb:
                try:
                    sent_bytes = sock.send(data.outb)
                    data.outb = data.outb[sent_bytes:]
                    debug("Sent %d bytes, %d bytes remaining" % (sent_bytes, len(data.outb)))
                except Exception as ex:
                    print("Exception on sending: %s" % ex)
                    sock.close()

    def _listen_worker(self):
        if self._port is not None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("127.0.0.1", self._port))
                info("Listening on TCP port %d" % self._port)
            except OSError:
                error("Port %d is already in use" % self._port)
                self._enabled = False
        elif self._filename is not None:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(self._filename)
                info("Listening on socket file %s" % self._filename)
            except OSError:
                error("Could not open file %s" % self._filename)
                self._enabled = False
        else:
            error("Either port number or socket file name must be specified")
            self._enabled = False

        sock.listen()
        sock.setblocking(False)
        self._selector.register(sock, selectors.EVENT_READ, data=None)

        while self._enabled:
            events = self._selector.select(timeout=1)
            for key, mask in events:
                if key.data is None:
                    self._accept(key.fileobj)
                else:
                    self._serve(key.fileobj, key.data, mask)
            sleep(0.01)

        if self._filename is not None:
            os.unlink(self._filename)

    def broadcast(self, data):
        debug("Broadcasting message %s" % data)
        for key, conn in self._clients.items():
            debug("... to %s:%s" % key)
            data_raw = bytes(data + "\0", 'utf-8')
            self._selector.get_key(conn).data.outb += data_raw

    def send(self, addr, data):
        debug("Sending to %s:%s: %s" % (addr[0], addr[1], data))
        try:
            conn = self._clients[addr]
            data_raw = bytes(data + "\0", 'utf-8')
            self._selector.get_key(conn).data.outb += data_raw
        except Exception:
            raise

    def on_data_received(self, addr, data):
        pass

    def on_client_connected(self, addr, conn):
        pass

    def is_active(self):
        return self._enabled

