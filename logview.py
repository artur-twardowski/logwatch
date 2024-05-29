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
        self.socket = None
        self.websocket = None
        self.line_format = None
        self.endpoint_formats = {}
        self.filter_formats = {}

    def _parse_format_node(self, node):
        fmt = Format()
        fmt.background_color = resolve_color(node.get('background-color', "none"))
        fmt.foreground_color = resolve_color(node.get('foreground-color', "white"))
        return fmt

    def read(self, filename, view_name="main"):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            if 'views' not in data:
                print("Configuration file does not have \"views\" section")
                exit(1)
            if view_name not in data['views']:
                print("Configuration file does not have \"views\".\"%s\" section" % view_name)
                exit(1)

            server_data = data.get("server", None)
            view_data = data['views'][view_name]

            self.host = view_data.get('host', '127.0.0.1')
            self.port = view_data.get('server-port', None)
            if self.port is None and server_data is not None:
                self.port = server_data.get("socket-port", None)

            self.socket = view_data.get('socket-port', None)
            self.websocket = view_data.get('websocket-port', None)

            self.line_format = view_data.get('line-format', None) #TODO: default format

            for format in view_data.get('formats', []):
                if 'endpoint' in format:
                    self.endpoint_formats[format['endpoint']] = self._parse_format_node(format)

class TCPClient(GenericTCPClient):
    def __init__(self, config: Configuration, formatter: Formatter):
        super().__init__(config.host, config.port)
        self._config = config
        self._formatter = formatter

    def on_data_received(self, recv_data):
        data_recv_str = str(recv_data, 'utf-8')

        for data_json in data_recv_str.split('\0'):
            if len(data_json) == 0:
                continue
            data = json.loads(data_json)
            if data['type'] == 'data':
                print(formatter.format_line(self._config.line_format, data))

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
        elif arg in ['-S', '--socket']:
            port_s, = pop_args(arg_queue, arg, "port")
            config.socket = int(port_s)
        elif arg in ['-c', '--config']:
            config_file, = pop_args(arg_queue, arg, "file-name")
            config.read(config_file)
        else:
            print("Unknown option: %s" % arg)
            exit(1)
    return config

if __name__ == "__main__":
    config = read_args(argv[1:])
    formatter = Formatter()
    for endpoint_name, endpoint_format in config.endpoint_formats.items():
        formatter.add_endpoint_format(endpoint_name, endpoint_format)
    client = TCPClient(config, formatter)
    client.run()
    sleep(7200)
    client.stop()
