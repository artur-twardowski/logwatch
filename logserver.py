#!/usr/bin/python3
import subprocess as sp
from sys import argv
import threading as thrd
from queue import Queue
import json
import yaml
from time import sleep
from servers import GenericTCPServer
from utils import pop_args

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
        print("Endpoint %s: running command: %s" % (self._endpoint_name, self._command_line))
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
        print("Receiver thread finished for fd=%s" % fd)

    def _sender(self, proc, stream):
        while proc.poll() is None:
            if not self._stdin_buffer.empty():
                line = self._stdin_buffer.get()
                stream.write(line)
                stream.flush()
            else:
                sleep(0.01)
        print("Sender thread finished")

class ServerManager:
    def __init__(self):
        self._servers = []

    def register(self, server):
        self._servers.append(server)

    def run_all(self):
        for server in self._servers:
            server.run()

    def broadcast_data(self, endpoint_name, fd, data):
        for server in self._servers:
            server.broadcast(json.dumps({
                "type": "data",
                "endpoint": endpoint_name,
                "fd": fd,
                "data": data
            }))

    def broadcast_keepalive(self, seq_no):
        for server in self._servers:
            server.broadcast(json.dumps({
                "type": "keepalive",
                "seq": seq_no
            }))


class Configuration:
    def __init__(self):
        self.subprocesses = []
        self.socket = None
        self.websocket = None

    def read(self, filename):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            if 'server' not in data:
                print("Configuration file does not have \"server\" section")
                exit(1)
            
            self.socket = data['server'].get('socket-port', None)
            self.websocket = data['server'].get('websocket-port', None)

            for endpoint in data['server'].get('endpoints', []):
                if 'type' not in endpoint:
                    print("Endpoint type must be provided")
                    exit(1)
                if 'name' not in endpoint:
                    print("Endpoint name must be provided")
                    exit(1)

                if endpoint['type'] == 'subprocess':
                    if 'command' not in endpoint:
                        print("Subprocess endpoint must have a command specified")
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
    def __init__(self, port):
        super().__init__(port)

    def on_data_received(self, addr, data):
        print("Received data from %s:%s: %s" % (addr[0], addr[1], data))

if __name__ == "__main__":
    config = read_args(argv[1:])
    server_manager = ServerManager()

    if config.socket is not None:
        server_manager.register(TCPServer(config.socket))

    server_manager.run_all()

    subprocesses = []
    for endpoint_name, command in config.subprocesses:
        subproc = SubprocessCommunication(command, endpoint_name, server_manager)
        subprocesses.append(subproc)
        subproc.run()

    ix = 0
    while True:
        server_manager.broadcast_keepalive(ix)
        ix += 1
        sleep(1)
