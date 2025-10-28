#!/usr/bin/python3

from sys import argv
import json
from network.clients import GenericTCPClient
from queue import Queue
from utils import pop_args, fatal_error

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

        if arg in ['-m', '--marker']:
            marker_name, = pop_args(arg_queue, arg, 'marker-name')
            config.commands.append({
                "type": "set-marker",
                "name": marker_name
            })
        elif arg in ['-k', '--kill']:
            config.commands.append({
                "type": "stop-all"
            })
        elif arg in ['-i', '--send']:
            endpoint_register, data = pop_args(arg_queue, arg, 'endpoint', 'data')
            config.commands.append({
                "type": "send-stdin",
                "endpoint-register": endpoint_register,
                "data": data
            })

        elif arg.find(':') != -1:
            host, port = arg.split(':')
            if host != "":
                config.host = host
            if port != "":
                config.port = int(port)
        else:
            fatal_error("Invalid option: \"%s\"" % arg)

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
