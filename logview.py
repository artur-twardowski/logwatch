#!/usr/bin/python3

from sys import argv
import json
from clients import GenericTCPClient
from time import sleep
from collections import deque
from queue import Queue
from utils import pop_args, info, error, warning, set_log_level, VERSION
from utils import TerminalRawMode
from formatter import Formatter, Format, resolve_color
import yaml
import re

status_line_updated = True

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
        self.max_held_lines = None

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

    def register_filter(self, filter_node):
        info("Registered filter %s: %s" % (filter_node.name, filter_node.regex))
        self.filters[filter_node.name] = filter_node

    def enable_filter(self, filter_name):
        if filter_name in self.filters:
            self.filters[filter_name].enabled = True

    def disable_filter(self, filter_name):
        if filter_name in self.filters:
            self.filters[filter_name].enabled = False

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
            self.max_held_lines = view_data.get('max-held-lines', None)

            for format in view_data.get('formats', []):
                if 'endpoint' in format:
                    self.endpoint_formats[format['endpoint']] = self._parse_format_node(format)
                if 'regex' in format:
                    filter_node = self._parse_filter_node(format)
                    self.filters[filter_node.name] = filter_node

class InteractiveModeContext:
    def __init__(self):
        self._command_buffer = ""
        self._command_buffer_changed_cb = None
        self._pause_cb = None
        self._resume_cb = None

        self._syntax_tree = {
            "p": "pause",
            "a": {"p": "analysis-pause"},
            "r": "resume",
        }

        for k in "0123456789":
            self._syntax_tree[k] = "continue"

        self._syntax_tree_ptr = self._syntax_tree

    def get_command_buffer(self):
        return self._command_buffer

    def on_command_buffer_changed(self, callback: callable):
        self._command_buffer_changed_cb = callback

    def on_pause(self, callback: callable):
        self._pause_cb = callback

    def on_resume(self, callback: callable):
        self._resume_cb = callback

    def _reset_command_buffer(self):
        self._command_buffer = ""
        self._syntax_tree_ptr = self._syntax_tree

    def _handle_command(self, command):
        if command == "pause":
            self._pause_cb(False)
        elif command == "analysis-pause":
            self._pause_cb(True)
        elif command == "resume":
            self._resume_cb()
        else:
            print("Unhandled command: %s" % command)

    def read_key(self, term:TerminalRawMode):
        key = term.read_key()
        if key != "":
            if key == "<C-c>":
                raise KeyboardInterrupt()
            else:
                if key in self._syntax_tree_ptr:
                    if isinstance(self._syntax_tree_ptr[key], dict):
                        self._syntax_tree_ptr = self._syntax_tree_ptr[key]
                        self._command_buffer += key
                    elif self._syntax_tree_ptr[key] == "continue":
                        self._command_buffer += key
                        # Stay on the same level of parser tree
                    else:
                        self._handle_command(self._syntax_tree_ptr[key])
                        self._reset_command_buffer()
                else:
                    self._reset_command_buffer()

                self._command_buffer_changed_cb(self._command_buffer)



class ConsoleOutput:
    def __init__(self, config: Configuration, formatter: Formatter, term: TerminalRawMode, interactive: InteractiveModeContext):
        self._config = config
        self._formatter = formatter
        self._terminal = term
        self._interact = interactive
        self._held_lines = deque()
        self._max_held_lines = 5000
        self._pause = False
        self._held_lines_overflow = False
        self._drop_newest_lines = False
        self._status_line_req_update = True

    def set_max_held_lines(self, size):
        if size is not None:
            info("Set maximum number of held lines to %d" % size)
            self._max_held_lines = size
        else:
            info("No maximum number of held lines set, using default of %d" % self._max_held_lines)

    def set_drop_newest_lines_policy(self, value):
        self._drop_newest_lines = value

    def _print_line(self, data):
        global status_line_updated
        
        if not self._config.filtered_mode:
            self._terminal.reset_current_line()
            self._terminal.write_line(self._formatter.format_line(self._config.line_format, data))
            self._status_line_req_update = True
        else:
            for name, filter in self._config.filters.items():
                if filter.enabled and filter.match(data['data']):
                    data['filter'] = name
                    self._terminal.write_line(self._formatter.format_line(self._config.line_format, data))
                    self._status_line_req_update = True

    def _print_marker(self, data):
        self._terminal.write_line(self._formatter.format_line(self._config.marker_format, data))
        self._status_line_req_update = True

    def _hold(self, data):
        drop_line = False
        while len(self._held_lines) >= self._max_held_lines:
            if not self._held_lines_overflow:
                self._held_lines_overflow = True
                warning("Some lines have been dropped, only %s %d will be displayed after resuming" % (
                    "first" if self._drop_newest_lines else "last",
                    self._max_held_lines))

            if self._drop_newest_lines:
                drop_line = True
            else:
                self._held_lines.popleft()

        if not drop_line:
            self._held_lines.append(data)

    def print_line(self, data):
        if self._pause:
            self._hold(data)
            self._status_line_req_update = True
        else:
            self._print_line(data)
            self._status_line_req_update = True

    def print_marker(self, data):
        data['data'] = data['name']
        data['endpoint'] = '_'
        data['fd'] = 'marker'
        if self._pause:
            self._hold(data)
        else:
            self._print_marker(data)

    def pause(self):
        self._pause = True

    def resume(self):
        while len(self._held_lines) > 0:
            data = self._held_lines.popleft()
            if data['endpoint'] == '_' and data['fd'] == 'marker':
                self._print_marker(data)
            else:
                self._print_line(data)
        self._pause = False
        self._held_lines_overflow = False

    def feed(self, amount):
        for _ in range(0, amount):
            if len(self._held_lines) == 0:
                break
            data = self._held_lines.popleft()
            if data['endpoint'] == '_' and data['fd'] == 'marker':
                self._print_marker(data)
            else:
                self._print_line(data)

    def render_status_line(self):
        if self._status_line_req_update:
            term.reset_current_line("43;30")
            if self._pause:
                if self._drop_newest_lines:
                    term.write("A-PAUSE", flush=False)
                else:
                    term.write("PAUSE", flush=False)
                term.write(" (%d/%d)" % (len(self._held_lines), self._max_held_lines))
            else:
                term.write("RUN", flush=False)

            term.write(" ")
            term.write(self._interact.get_command_buffer())
            self._status_line_req_update = False

    def notify_status_line_changed(self):
        self._status_line_req_update = True


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

def process_command(client_socket, console_output, formatter, config, inp):
    SUPPORTED_COMMANDS = ["marker", "pause", "resume", "feed", "watch", "enable", "disable"]

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
    elif command == "feed":
        if argument == "":
            num_lines = 10
        else:
            try:
                num_lines = int(argument)
            except Exception:
                error("Not a valid number: \"%s\"" % argument)
                return
        console_output.feed(num_lines)
    elif command == "watch":
        if argument.startswith(':'):
            format, regex = argument.split(' ', 1)
            format = format[1:]
            if format.find(':') == -1:
                foreground_color = format
                background_color = "none"
            else:
                foreground_color, background_color = format.split(':')
        else:
            regex = argument
            foreground_color = "white"
            background_color = "none"

        filter = Filter()
        filter.enabled = True
        filter.format.background_color["stdout"] = resolve_color(background_color)
        filter.format.foreground_color["stdout"] = resolve_color(foreground_color)
        filter.format.background_color["stderr"] = filter.format.background_color["stdout"]
        filter.format.foreground_color["stderr"] = filter.format.foreground_color["stdout"]
        filter.set_regex(regex)

        filter_ix = 1
        while ("F%d" % filter_ix) in config.filters:
            filter_ix += 1
        filter.name = "F%d" % filter_ix

        config.register_filter(filter)
        formatter.add_filter_format(filter.name, filter.format)
    elif command == "enable":
        config.enable_filter(argument)
    elif command == "disable":
        config.disable_filter(argument)

def pause_callback(console_output, analysis_mode):
    console_output.set_drop_newest_lines_policy(analysis_mode)
    console_output.pause()

def resume_callback(console_output):
    console_output.resume()

if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGVIEW v%s" % VERSION)
    term = TerminalRawMode()
    interact = InteractiveModeContext()
    term.enter_raw_mode()
    config = read_args(argv[1:])
    set_log_level(config.log_level)

    formatter = Formatter()
    console_output = ConsoleOutput(config, formatter, term, interact)
    console_output.set_max_held_lines(config.max_held_lines)

    interact.on_command_buffer_changed(lambda buf: console_output.notify_status_line_changed())
    interact.on_pause(lambda analysis_mode: pause_callback(console_output, analysis_mode))
    interact.on_resume(lambda: resume_callback(console_output))

    for endpoint_name, endpoint_format in config.endpoint_formats.items():
        formatter.add_endpoint_format(endpoint_name, endpoint_format)

    for filter_name, filter in config.filters.items():
        formatter.add_filter_format(filter_name, filter.format)

    try:
        client = TCPClient(config, console_output)
        client.run()
        client.send_enc({'type': 'get-late-join-records'})

        command_buffer = ""
        status_line_updated = True
        while True:
            console_output.render_status_line()
            interact.read_key(term)

            #command = input()
            #if command == "" and last_command is not None:
            #    command = last_command
            #if command != "":
            #    process_command(client, console_output, formatter, config, command)
            #    last_command = command
    except ConnectionRefusedError:
        error("Could not connect to the server: connection refused")
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        term.exit_raw_mode()
