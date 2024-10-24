#!/usr/bin/python3
import subprocess as sp
from sys import argv
import threading as thrd
from collections import deque
from queue import Queue
import json
import yaml
from time import sleep
from datetime import datetime
from servers import GenericTCPServer
from utils import pop_args, error, info, set_log_level, VERSION

class SubprocessCommunication:
    def __init__(self, command_line, endpoint_name, servers):
        self._command_line = command_line
        self._endpoint_name = endpoint_name
        self._stdin_buffer = Queue()
        self._servers = servers
        self._worker_thread = None

    def run(self):
        self._worker_thread = thrd.Thread(target=self._worker)
        self._worker_thread.start()

    def wait(self):
        self._worker_thread.join()

    def _worker(self):
        info("Endpoint %s: running command: %s" % (self._endpoint_name, self._command_line))
        proc = sp.Popen(self._command_line,
                        shell=True,
                        stdin=sp.PIPE,
                        stdout=sp.PIPE,
                        stderr=sp.PIPE,
                        universal_newlines=True)

        stdout_thread = thrd.Thread(target=self._receiver, args=(proc.stdout, 'stdout'))
        stderr_thread = thrd.Thread(target=self._receiver, args=(proc.stderr, 'stderr'))
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
            self._servers.broadcast_data(self._endpoint_name, fd, line.strip())
        info("Receiver thread finished for fd=%s" % fd)

    def _sender(self, proc, stream):
        while proc.poll() is None:
            if not self._stdin_buffer.empty():
                line = self._stdin_buffer.get()
                stream.write(line)
                stream.flush()
            else:
                sleep(0.01)
        info("Sender thread finished")

class ServerManager:
    def __init__(self):
        self._servers = []
        self._line_seq_no = 0
        self._default_marker_no = 1
        self._late_join_buf = deque()
        self._late_join_buf_size = 256

    def set_late_join_buf_size(self, size):
        if size is not None:
            info("Set late joiners buffer size to %d records" % size)
            self._late_join_buf_size = size
        else:
            info("No late joiners buffer size configured, using default of %d records" % self._late_join_buf_size)

    def add_to_late_join_buf(self, record):
        while len(self._late_join_buf) >= self._late_join_buf_size:
            self._late_join_buf.popleft()
        self._late_join_buf.append(record)

    def register(self, server):
        self._servers.append(server)

    def run_all(self):
        for server in self._servers:
            server.run()

    def broadcast_data(self, endpoint_name, fd, data):
        today = datetime.now()
        for server in self._servers:
            record = {
                "type": "data",
                "endpoint": endpoint_name,
                "fd": fd,
                "data": data,
                "seq": self._line_seq_no,
                "date": today.strftime("%Y-%m-%d"),
                "time": today.strftime("%H:%M:%S")
            }
            server.broadcast(json.dumps(record))
            self.add_to_late_join_buf(record)
        self._line_seq_no += 1

    def broadcast_keepalive(self, seq_no):
        for server in self._servers:
            server.broadcast(json.dumps({
                "type": "keepalive",
                "seq": seq_no
            }))

    def broadcast_marker(self, name):
        today = datetime.now()

        if name == "":
            name = "MARKER %d" % self._default_marker_no
            self._default_marker_no += 1

        for server in self._servers:
            record = {
                "type": "marker",
                "name": name,
                "date": today.strftime("%Y-%m-%d"),
                "time": today.strftime("%H:%M:%S")
            }
            server.broadcast(json.dumps(record))
            self.add_to_late_join_buf(record)

    def send_late_join_records(self, server, client_addr):
        info("Sending previous %d lines to %s:%s" % (len(self._late_join_buf), client_addr[0], client_addr[1]))
        for rec in self._late_join_buf:
            server.send(client_addr, json.dumps(rec))


class Configuration:
    def __init__(self):
        self.subprocesses = []
        self.socket = None
        self.websocket = None
        self.late_join_buf_size = None

    def read(self, filename):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            if 'server' not in data:
                error("Configuration file does not have \"server\" section")
                exit(1)
            
            self.socket = data['server'].get('socket-port', None)
            self.websocket = data['server'].get('websocket-port', None)
            self.late_join_buf_size = data['server'].get('late-joiners-buffer-size', None)

            for endpoint in data['server'].get('endpoints', []):
                if 'type' not in endpoint:
                    error("Endpoint type must be provided")
                    exit(1)
                if 'name' not in endpoint:
                    error("Endpoint name must be provided")
                    exit(1)

                if endpoint['type'] == 'subprocess':
                    if 'command' not in endpoint:
                        error("Subprocess endpoint must have a command specified")
                    self.subprocesses.append((endpoint['name'], endpoint['command']))

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
        elif arg in ['-c', '--config']:
            config_file, = pop_args(arg_queue, arg, "file-name")
            config.read(config_file)

        elif arg in ['--help']:
            print("USAGE: %s [-s | --subprocess <endpoint-name> <command>]*")
        else:
            print("Unknown option: %s" % arg)
            exit(1)

    return config

class TCPServer(GenericTCPServer):
    def __init__(self, port, server_manager: ServerManager):
        super().__init__(port)
        self._server_manager = server_manager
        self._recv_buffer = bytearray()

    def on_data_received(self, addr, recv_data):
        for byte in recv_data:
            if byte == 0:
                data_recv_str = str(self._recv_buffer, 'utf-8')

                if len(data_recv_str) > 0:
                    try:
                        data = json.loads(data_recv_str)
                        if data['type'] == 'set-marker':
                            self._server_manager.broadcast_marker(data['name'])
                        elif data['type'] == 'get-late-join-records':
                            self._server_manager.send_late_join_records(self, addr)

                    except json.decoder.JSONDecodeError as err:
                        error("Failed to parse JSON: %s: %s" % (err, data_recv_str))

                self._recv_buffer.clear()
            else:
                self._recv_buffer.append(byte)

if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGSERVER v%s" % VERSION)
    config = read_args(argv[1:])
    server_manager = ServerManager()
    server_manager.set_late_join_buf_size(config.late_join_buf_size)

    if config.socket is not None:
        server_manager.register(TCPServer(config.socket, server_manager))

    server_manager.run_all()

    subprocesses = []
    for endpoint_name, command in config.subprocesses:
        subproc = SubprocessCommunication(command, endpoint_name, server_manager)
        subprocesses.append(subproc)
        subproc.run()

    ix = 0
    while True:
        server_manager.broadcast_keepalive(ix)
        ix += 0
        sleep(1)
