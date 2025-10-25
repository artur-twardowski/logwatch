import socket
import selectors
from types import SimpleNamespace
import threading as thrd
from utils import debug, info, error, warning
from time import sleep
import os


class GenericTCPServer:
    def __init__(self, address=None, port=None, filename=None):
        self._address = address
        self._port = port
        self._filename = filename
        self._active = False
        self._connected = False
        self._selector = selectors.DefaultSelector()
        self._listen_thread = None
        self._clients = {}

    def run(self):
        self._active = True
        self._listen_thread = thrd.Thread(target=self._listen_worker)
        self._listen_thread.start()

    def stop(self):
        info("Stopping server listening at %s:%s" % (self._address or "", self._port))
        self._active = False
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
            retry_count = 0
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            info("Trying to bind port %d" % self._port)
            while not self._connected:
                if not self._active:
                    return

                try:
                    addr = self._address
                    if addr is None:
                        addr = "127.0.0.1"
                    sock.bind((addr, self._port))
                    self._connected = True
                    info("Listening on TCP port %d" % self._port)
                except OSError as ex:
                    if retry_count < 60:
                        warning("Cannot listen on port %d: %s, retrying in 5 seconds" % (self._port, ex))
                        retry_count += 1
                        sleep(5)
                    else:
                        error("Giving up")
                        self._active = False
        elif self._filename is not None:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(self._filename)
                info("Listening on socket file %s" % self._filename)
            except OSError:
                error("Could not open file %s" % self._filename)
                self._active = False
        else:
            error("Either port number or socket file name must be specified")
            self._active = False
            return

        sock.listen()
        sock.setblocking(False)
        self._selector.register(sock, selectors.EVENT_READ, data=None)

        while self._active:
            events = self._selector.select(timeout=1)
            for key, mask in events:
                if key.data is None:
                    self._accept(key.fileobj)
                else:
                    self._serve(key.fileobj, key.data, mask)
            sleep(0.01)

        info("Closing")

        if self._filename is not None:
            os.unlink(self._filename)
        else:
            self._selector.close()
            sock.close()

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
        return self._active and self._connected

