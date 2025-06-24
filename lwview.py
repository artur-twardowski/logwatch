#!/usr/bin/python3

from sys import argv
import json
from network.clients import GenericTCPClient
from time import sleep
from collections import deque
from queue import Queue
from utils import pop_args, info, error, warning, set_log_level, VERSION
from utils import TerminalRawMode
from view.formatter import Formatter, resolve_color
from view.configuration import Configuration, Filter
import yaml
import re

status_line_updated = True

class InteractiveModeContext:
    PREDICATE_MODE = 1
    TEXT_INPUT_MODE = 2
    MULTI_INPUT_MODE = 3

    AVAILABLE_REGISTERS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, config: Configuration):
        self._config = config
        self._command_buffer = ""
        self._command_buffer_changed_cb = None
        self._pause_cb = None
        self._resume_cb = None
        self._quit_cb = None
        self._input_mode = self.PREDICATE_MODE
        self._text_input_buffer = ""
        self._prompt = ""
        self._subprompts = []
        self._position = 0

        # p   - pause
        # ap  - pause, analysis mode
        # r   - resume
        # q   - quit
        # w   - set new filter in first available register
        # 'Rs - set filter in register R
        # 'Rx - clear filter register R
        # 'Rd - disable filter from register R
        # 'Re - enable filter from register R
        # "Rs - set command in register R
        # "Rx - clear command register R
        # "Re - execute command from register R
        # !R  - same as "Re
        # <M-0>..<M-9> - same as "0e .. "9e

        self._syntax_tree = {
            "p": "eval",
            "a": {"p": "eval"},
            "r": "eval",
            "q": "eval",
            "w": "eval",
            "'": {},
            "\"": {}
        }


        for k in "0123456789":
            self._syntax_tree[k] = "continue"

        for k in self.AVAILABLE_REGISTERS:
            self._syntax_tree["'"][k] = {"s": "eval", "d": "eval", "e": "eval", "x": "eval"}

        self._syntax_tree_ptr = self._syntax_tree

    def get_user_input_string(self):
        if self._input_mode == self.PREDICATE_MODE:
            return "\u21c9 " + self._command_buffer
        elif self._input_mode == self.TEXT_INPUT_MODE:
            return self._prompt + self._text_input_buffer
        elif self._input_mode == self.MULTI_INPUT_MODE:
            count = len(self._subprompts)
            arrow = " "
            if count > 2:
                if self._position == 0:
                    arrow = "\u2193" # Down arrow
                elif self._position == count - 1:
                    arrow = "\u2191" # Up arrow
                else:
                    arrow = "\u2195" # Up/down arrow

            return "%s | %c%s%s" % (self._prompt, arrow, self._subprompts[self._position], self._text_input_buffer[self._position])


    def on_command_buffer_changed(self, callback: callable):
        self._command_buffer_changed_cb = callback

    def on_pause(self, callback: callable):
        self._pause_cb = callback

    def on_resume(self, callback: callable):
        self._resume_cb = callback

    def on_quit(self, callback: callable):
        self._quit_cb = callback

    def _reset_command_buffer(self):
        self._command_buffer = ""
        self._text_input_buffer = ""
        self._syntax_tree_ptr = self._syntax_tree

    def _enter_text_input(self, command, prompt):
        self._command_buffer = command
        self._input_mode = self.TEXT_INPUT_MODE
        self._prompt = "Regular expression: "

    def _enter_predicate_mode(self):
        self._input_mode = self.PREDICATE_MODE

    def _enter_multi_mode(self, command, prompt, fields):
        self._command_buffer = command
        self._input_mode = self.MULTI_INPUT_MODE
        self._prompt = prompt
        self._subprompts = fields
        self._position = 0
        self._text_input_buffer = [""] * len(fields)


    def _handle_command(self, command_params):
        if isinstance(command_params, list):
            command = command_params[0]
            if len(command_params) > 1:
                command_params = command_params[1:]
            else:
                command_params = []
        else:
            command = command_params
            command_params = []

        counter_s = ""
        while len(command) > 0 and command[0] >= '0' and command[0] <= '9':
            counter_s += command[0]
            command = command[1:]
        if counter_s != "":
            counter = int(counter_s)
        else:
            counter = 0

        if command == "p":
            self._pause_cb(False)
        elif command == "ap":
            self._pause_cb(True)
        elif command == "r":
            self._resume_cb()
        elif command == "q":
            self._quit_cb()
        elif command == "w":
            if len(command_params) == 0:
                self._enter_multi_mode(command, "Set filter", ["Regular expression: ", "Background color: ", "Foreground color: "])
            else:
                print("Set filter " + command_params[0])
                self._reset_command_buffer()
                self._enter_predicate_mode()
        elif command[0] == "'" and command[2] == "s":
            if len(command_params) == 0:
                self._enter_multi_mode(command, "Set filter '%c" % command[2], ["Regular expression: ", "Background color: ", "Foreground color: "])
            else:
                self._reset_command_buffer()
                self._enter_predicate_mode()

        else:
            print("Unhandled command: %s, %s, %s" % (counter, command, command_params))

    def _predicate_input(self, key):
        if key in self._syntax_tree_ptr:
            self._command_buffer += key
            if isinstance(self._syntax_tree_ptr[key], dict):
                self._syntax_tree_ptr = self._syntax_tree_ptr[key]
            elif self._syntax_tree_ptr[key] == "continue":
                pass  # Stay on the same level of parser tree
            elif self._syntax_tree_ptr[key] == "eval":
                self._handle_command(self._command_buffer)
                if self._input_mode == self.PREDICATE_MODE:
                    self._reset_command_buffer()
        else:
            self._reset_command_buffer()

    def _text_input(self, key):
        if key == "<BS>":
            if len(self._text_input_buffer) > 0:
                self._text_input_buffer = self._text_input_buffer[:-1]
        elif key == "<ESC>":
            self._input_mode = self.PREDICATE_MODE
            self._reset_command_buffer()
        elif key == "<Enter>":
            self._handle_command([self._command_buffer, self._text_input_buffer])
        else:
            self._text_input_buffer += key

    def _multi_input(self, key):
        if key == "<BS>":
            if len(self._text_input_buffer[self._position]) > 0:
                self._text_input_buffer[self._position] = self._text_input_buffer[self._position][:-1]
        elif key == "<ESC>":
            self._input_mode = self.PREDICATE_MODE
            self._reset_command_buffer()
        elif key == "<Enter>":
            self._handle_command([self._command_buffer] + self._text_input_buffer)
        elif key in ["<Up>"]:
            if self._position > 0:
                self._position -= 1
        elif key in ["<Down>"]:
            if self._position < len(self._subprompts) - 1:
                self._position += 1
        else:
            self._text_input_buffer[self._position] += key

    def read_key(self, term:TerminalRawMode):
        key = term.read_key()
        if key != "":
            if self._input_mode == self.PREDICATE_MODE:
                self._predicate_input(key)
            elif self._input_mode == self.TEXT_INPUT_MODE:
                self._text_input(key)
            elif self._input_mode == self.MULTI_INPUT_MODE:
                self._multi_input(key)

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
        self._hold(data)
        self._status_line_req_update = True

    def print_marker(self, data):
        data['data'] = data['name']
        data['endpoint'] = '_'
        data['fd'] = 'marker'
        self._hold(data)

    def pause(self):
        self._pause = True

    def resume(self):
        self._pause = False
        self._held_lines_overflow = False
        self.write_pending_lines()

    def write_pending_lines(self):
        if self._pause:
            return

        while len(self._held_lines) > 0:
            data = self._held_lines.popleft()
            if data['endpoint'] == '_' and data['fd'] == 'marker':
                self._print_marker(data)
            else:
                self._print_line(data)

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
                    term.write("\u2507\u2507", flush=False)
                else:
                    term.write("\u2503\u2503", flush=False) # Pause character
                term.write("%3d%%" % (len(self._held_lines) * 100 / self._max_held_lines))
            else:
                term.write("\u2b9e     ", flush=False)

            term.write(" ")
            term.write(self._interact.get_user_input_string())
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

def quit_callback():
    raise KeyboardInterrupt

if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGVIEW v%s" % VERSION)
    config = read_args(argv[1:])
    set_log_level(config.log_level)

    term = TerminalRawMode()
    interact = InteractiveModeContext(config)
    term.enter_raw_mode()

    formatter = Formatter()
    console_output = ConsoleOutput(config, formatter, term, interact)
    console_output.set_max_held_lines(config.max_held_lines)

    interact.on_command_buffer_changed(lambda buf: console_output.notify_status_line_changed())
    interact.on_pause(lambda analysis_mode: pause_callback(console_output, analysis_mode))
    interact.on_resume(lambda: resume_callback(console_output))
    interact.on_quit(lambda: quit_callback())

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
            console_output.write_pending_lines()
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
