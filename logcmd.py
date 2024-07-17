#!/usr/bin/python3

import socket
from sys import argv, stdout
import json
from clients import GenericTCPClient
from time import sleep
from queue import Queue
from utils import pop_args
from formatter import Formatter, Format, resolve_color
import yaml

COLORS={
    "stdout": "1;34m",
    "stderr": "1;31m",
    "stdin": "1;33m"
}

class Configuration:
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 2207
        self.commands = []

class TCPClient(GenericTCPClient):
    def __init__(self, config: Configuration):
        super().__init__(config.host, config.port)
        self._config = config

    def on_data_received(self, recv_data):
        pass

def read_args(args):
    arg_queue = Queue()
    config = Configuration()
    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()

        if arg in ['-p', '--port']:
            port_s, = pop_args(arg_queue, arg, "port")
            config.port = int(port_s)
        elif arg in ['-h', '--host']:
            host, = pop_args(arg_queue, arg, "host")
            config.host = host
        elif arg in ['-f', '--set-filter']:
            index_s, regex, formatting = pop_args(arg_queue, arg, 'index', 'regex', 'formatting')
            config.commands.append({
                "type": "set-filter",
                "index": index_s,
                "regex": regex,
                "format": formatting
            })
        elif arg in ['-F', '--clear-filter']:
            index_s = pop_args(arg_queue, arg, 'index')
            config.commands.append({
                "type": "clear-filter",
                "index": index_s
            })
        elif arg in ['-x', '--execute']:
            command = pop_args(arg_queue, arg, 'command')
            config.commands.append({
                "type": "execute",
                "command": command
            })
        elif arg in ['-X', '--execute-index']:
            command_index_s = pop_args(arg_queue, arg, 'command-index')
            config.commands.append({
                "type": "execute-index",
                "index": command_index_s
            })


        else:
            print("Unknown option: %s" % arg)
            exit(1)
    return config

if __name__ == "__main__":
    config = read_args(argv[1:])
    client = TCPClient(config)
    client.run()
    for cmd in config.commands:
        data = json.dumps(cmd)
        print("Sending: %s" % data)
        client.send(data)
    client.stop()
