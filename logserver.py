#!/usr/bin/python3
import subprocess as sp
from sys import argv, stdout
import threading as thrd
from queue import Queue
import socket
import selectors
from types import SimpleNamespace
from time import sleep

class SocketServer:
    def __init__(self, port):
        self._port = port
        self._enabled = True
        self._selector = selectors.DefaultSelector()
        self._listen_thread = None
        self._client_sockets = {}

    def run(self):
        self._listen_thread = thrd.Thread(target=self._listen_worker)
        self._listen_thread.start()

    def stop(self):
        self._enabled = False
        self._listen_thread.join()

    def _accept(self, client_sock):
        conn, addr = client_sock.accept()
        print("Received a connection from %s:%s" % addr)
        conn.setblocking(False)
        self._selector.register(conn, selectors.EVENT_READ | selectors.EVENT_WRITE, SimpleNamespace(addr=addr, inb=b'', outb=b''))
        self._client_sockets[addr] = conn

    def _serve(self, sock, data, mask):
        if mask & selectors.EVENT_READ:
            recv_data = sock.recv(1024)
            if recv_data:
                print("Received data: ", recv_data)
            else:
                print("Closing connection from %s:%s" % data.addr)
                self._selector.unregister(sock)
                del self._client_sockets[data.addr]
                sock.close()

        if mask & selectors.EVENT_WRITE:
            if data.outb:
                sent_bytes = sock.send(data.outb)
                data.outb = data.outb[sent_bytes:]


    def _listen_worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind( ("127.0.0.1", self._port) )
        sock.listen()
        print("Listening on port %d" % self._port)
        sock.setblocking(False)
        self._selector.register(sock, selectors.EVENT_READ, data=None)

        while self._enabled:
            events = self._selector.select(timeout=1)
            for key, mask in events:
                if key.data is None:
                    self._accept(key.fileobj)
                else:
                    self._serve(key.fileobj, key.data, mask)

    def broadcast(self, data):
        print("Broadcasting message %s" % data)
        for key, conn in self._client_sockets.items():
            print("... to %s:%s" % key)
            data_raw = bytes(data, 'utf-8')
            self._selector.get_key(conn).data.outb += data_raw


class SubprocessCommunication:
    def __init__(self, command_line, endpoint_name="Subprocess"):
        self._command_line = command_line
        self._endpoint_name = endpoint_name
        self._stdin_buffer = Queue()

    def run(self):
        proc = sp.Popen(self._command_line,
                        shell=True,
                        stdin=sp.PIPE,
                        stdout=sp.PIPE,
                        stderr=sp.PIPE,
                        universal_newlines=True)

        stdout_thread = thrd.Thread(target=self._receiver, args=(proc.stdout, 1))
        stderr_thread = thrd.Thread(target=self._receiver, args=(proc.stderr, 2))
        stdin_thread = thrd.Thread(target=self._sender, args=(proc, proc.stdin))

        stdout_thread.start()
        stderr_thread.start()
        stdin_thread.start()
        proc.wait()

        stdout_thread.join()
        stderr_thread.join()
        stdin_thread.join()

    def _receiver(self, stream, fd):
        for line in stream:
            stdout.write("FD%d: %s\n" % (fd, line.strip()))
            stdout.flush()
        print("Receiver thread finished for fd=%d" % fd)

    def _sender(self, proc, stream):
        while proc.poll() is None:
            if not self._stdin_buffer.empty():
                line = self._stdin_buffer.get()
                stream.write(line)
                stream.flush()
        print("Sender thread finished")

class Configuration:
    def __init__(self):
        self.subprocesses = []
        self.socket = None

def pop_args(arg_queue, argument, *names):
    if arg_queue.qsize() < len(names):
        if len(names) == 1:
            print("Option %s requires %s argument" % (argument, names[0]))
        else:
            print("Option %s requires %d arguments: %s" % (argument, len(names), ", ".join(names)))
        exit(1)

    retval = []
    for _ in names:
        retval.append(arg_queue.get())
    return retval

def read_args(args):
    arg_queue = Queue()
    config = Configuration()
    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()

        if arg in ['-p', '--process']:
            endpoint_name, command_line = pop_args(arg_queue, arg, "endpoint-name", "command")
            config.subprocesses.append((endpoint_name, command_line))
        elif arg in ['-S', '--socket']:
            port, = pop_args(arg_queue, arg, "port")
            config.socket = int(port)
        elif arg in ['--help']:
            print("USAGE: %s [-s | --subprocess <endpoint-name> <command>]*")
        else:
            print("Unknown option: %s" % arg)
            exit(1)

    return config


if __name__ == "__main__":
    config = read_args(argv[1:])

    sockets = []
    if config.socket is not None:
        sock = SocketServer(config.socket)
        sock.run()
        sockets.append(sock)

    for subproc in config.subprocesses:
        print("Subprocess ", subproc)

    ix = 0
    while True:
        for sock in sockets:
            sock.broadcast("XXX %d" % ix)
            sleep(1)
            ix += 1
