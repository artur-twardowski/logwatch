#!/usr/bin/python3

from sys import argv
import json
from clients import GenericTCPClient
from time import sleep
from queue import Queue
from utils import pop_args, info, error, warning, set_log_level, VERSION
from formatter import Formatter, Format, resolve_color
import yaml
import re

class Filter:
    def __init__(self):
        self.name = None
        self.regex = None
        self.format = Format()
        self.enabled = True
        self._prepared_regex = None

    def set_regex(self, regex):
        self.regex = regex
        self._prepared_regex = re.compile(regex)

    def match(self, line):
        result = self._prepared_regex.search(line)
        return result is not None

class Configuration:
    DEFAULT_LINE_FORMAT = "{format:endpoint}{endpoint:8} {seq:6} {time} {data}"
    DEFAULT_MARKER_FORMAT = "{format:endpoint}>>>>>>>> MARKER {time} {name}"

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 2207
        self.log_level = 2
        self.socket = None
        self.websocket = None
        self.line_format = None
        self.marker_format = None
        self.endpoint_formats = {}
        self.filters = {}
        self.marker_format = None
        self.filtered_mode = False

    def _parse_format_node(self, node):
        fmt = Format()
        for fd, formats in node.items():
            if fd in ["endpoint"]:
                continue

            if not isinstance(formats, dict):
                error("Invalid format of formatting node")
                exit(1)
            fmt.background_color[fd] = resolve_color(formats.get('background-color', "none"))
            fmt.foreground_color[fd] = resolve_color(formats.get('foreground-color', "white"))
        return fmt

    def _parse_filter_node(self, node):
        filter = Filter()
        if 'regex' not in node:
            error("Missing \"regex\" field in filter definition")
            exit(1)

        filter.set_regex(node['regex'])
        filter.name = node.get('name', filter.regex)
        filter.enabled = node.get('enabled', True)
        filter.format.background_color['stdout'] = resolve_color(node.get('background-color', 'none'))
        filter.format.foreground_color['stdout'] = resolve_color(node.get('foreground-color', 'white'))
        return filter

    def read(self, filename, view_name="main"):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            if 'views' not in data:
                error("Configuration file does not have \"views\" section")
                exit(1)
            if view_name not in data['views']:
                error("Configuration file does not have \"views\".\"%s\" section" % view_name)
                exit(1)

            server_data = data.get("server", None)
            view_data = data['views'][view_name]

            self.host = view_data.get('host', '127.0.0.1')
            self.port = view_data.get('server-port', None)
            if self.port is None and server_data is not None:
                self.port = server_data.get("socket-port", None)

            self.socket = view_data.get('socket-port', None)
            self.websocket = view_data.get('websocket-port', None)

            self.line_format = view_data.get('line-format', self.DEFAULT_LINE_FORMAT) 
            self.marker_format = view_data.get('marker-format', self.DEFAULT_MARKER_FORMAT)
            self.filtered_mode = view_data.get('filtered', False)

            for format in view_data.get('formats', []):
                if 'endpoint' in format:
                    self.endpoint_formats[format['endpoint']] = self._parse_format_node(format)
                if 'regex' in format:
                    filter_node = self._parse_filter_node(format)
                    self.filters[filter_node.name] = filter_node

class ConsoleOutput:
    def __init__(self, config: Configuration, formatter: Formatter):
        self._config = config
        self._formatter = formatter

    def print_line(self, data):
        if not self._config.filtered_mode:
            print(self._formatter.format_line(self._config.line_format, data))
        else:
            for name, filter in self._config.filters.items():
                if filter.enabled and filter.match(data['data']):
                    data['filter'] = name
                    print(self._formatter.format_line(self._config.line_format, data))

    def print_marker(self, data):
        data['data'] = data['name']
        data['endpoint'] = '_'
        data['fd'] = 'marker'
        print(self._formatter.format_line(self._config.marker_format, data))


class TCPClient(GenericTCPClient):
    def __init__(self, config: Configuration, cout: ConsoleOutput):
        super().__init__(config.host, config.port)
        self._config = config
        self._cout = cout
        self._recv_buffer = bytearray()

    def on_data_received(self, recv_data):
        for byte in recv_data:
            if byte == 0:
                data_recv_str = str(self._recv_buffer, 'utf-8')

                if len(data_recv_str) > 0:
                    try:
                        data = json.loads(data_recv_str)
                        if data['type'] == 'data':
                            self._cout.print_line(data);
                        elif data['type'] == 'marker':
                            self._cout.print_marker(data)
                    except json.decoder.JSONDecodeError as err:
                        warning("Failed to parse JSON: %s: %s" % (err, data_recv_str))

                self._recv_buffer.clear()
            else:
                self._recv_buffer.append(byte)

    def send_enc(self, data):
        self.send(json.dumps(data))

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
        elif arg in ['-v', '--verbose']:
            config.log_level += 1
        else:
            print("Unknown option: %s" % arg)
            exit(1)
    return config

def process_command(client_socket, inp):
    SUPPORTED_COMMANDS = ["marker"]

    inp_split = inp.split(' ', 1)
    if len(inp_split) == 2:
        command_short, argument = inp_split
    else:
        command_short, argument = (inp_split[0], "")
    command = None
    for match in SUPPORTED_COMMANDS:
        if match.startswith(command_short):
            if command is None:
                command = match
            else:
                error("Command \"%s\" is ambiguous" % command_short)
                return
    if command is None:
        error("No command matches \"%s\"" % command_short)

    if command == "marker":
        client_socket.send_enc({"type": "set-marker", "name": argument})

if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGVIEW v%s" % VERSION)
    config = read_args(argv[1:])
    set_log_level(config.log_level)

    formatter = Formatter()
    console_output = ConsoleOutput(config, formatter)

    for endpoint_name, endpoint_format in config.endpoint_formats.items():
        formatter.add_endpoint_format(endpoint_name, endpoint_format)

    for filter_name, filter in config.filters.items():
        formatter.add_filter_format(filter_name, filter.format)

    try:
        client = TCPClient(config, console_output)
        client.run()
        client.send_enc({'type': 'get-late-join-records'})
        while True:
            command = input()
            process_command(client, command)
    except ConnectionRefusedError:
        error("Could not connect to the server: connection refused")
        exit(1)
    except KeyboardInterrupt:
        pass
    client.stop()
