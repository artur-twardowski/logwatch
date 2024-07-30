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
        self.marker_format = None
        self.endpoint_formats = {}
        self.filter_formats = {}
        self.marker_format = None

    def _parse_format_node(self, node):
        fmt = Format()
        for fd, formats in node.items():
            print(fd, formats)
            if fd in ["endpoint"]: continue
            if not isinstance(formats, dict):
                print("Invalid format of formatting node")
                exit(1)
            fmt.background_color[fd] = resolve_color(formats.get('background-color', "none"))
            fmt.foreground_color[fd] = resolve_color(formats.get('foreground-color', "white"))
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

            #TODO: define default formats for both
            self.line_format = view_data.get('line-format', None) 
            self.marker_format = view_data.get('marker-format', None)

            for format in view_data.get('formats', []):
                if 'endpoint' in format:
                    self.endpoint_formats[format['endpoint']] = self._parse_format_node(format)

class TCPClient(GenericTCPClient):
    def __init__(self, config: Configuration, formatter: Formatter):
        super().__init__(config.host, config.port)
        self._config = config
        self._formatter = formatter
        self._recv_buffer = bytearray()

    def on_data_received(self, recv_data):
        for byte in recv_data:
            if byte == 0:
                data_recv_str = str(self._recv_buffer, 'utf-8')

                if len(data_recv_str) > 0:
                    try:
                        data = json.loads(data_recv_str)
                        if data['type'] == 'data':
                            print(formatter.format_line(self._config.line_format, data))
                        elif data['type'] == 'marker':
                            data['data'] = data['name']
                            data['endpoint'] = '_'
                            data['fd'] = 'marker'
                            print(formatter.format_line(self._config.marker_format, data))
                    except json.decoder.JSONDecodeError as err:
                        print("Failed to parse JSON: %s: %s" % (err, data_recv_str))

                self._recv_buffer.clear()
            else:
                self._recv_buffer.append(byte)

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
            config_file, view_name = pop_args(arg_queue, arg, "file-name", "view-name")
            config.read(config_file, view_name)
        else:
            print("Unknown option: %s" % arg)
            exit(1)
    return config

if __name__ == "__main__":
    config = read_args(argv[1:])
    formatter = Formatter()
    for endpoint_name, endpoint_format in config.endpoint_formats.items():
        formatter.add_endpoint_format(endpoint_name, endpoint_format)
    try:
        client = TCPClient(config, formatter)
        client.run()
        while True:
            sleep(1)
    except ConnectionRefusedError:
        print("Could not connect to the server: connection refused")
        exit(1)
    client.stop()
