#!/usr/bin/python3

from sys import argv
import json
from network.clients import GenericTCPClient
from time import sleep
from collections import deque
from queue import Queue
from utils import pop_args, info, error, warning, set_log_level, VERSION
from utils import TerminalRawMode
from view.formatter import Formatter, resolve_color, ansi_format1, Format
from view.formatter import render_watch_register, get_default_register_format
from view.configuration import Configuration, Watch
import yaml
import re

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
        self._set_watch_cb = None
        self._set_watch_enable_cb = None
        self._input_mode = self.PREDICATE_MODE
        self._text_input_buffer = ""
        self._prompt = ""
        self._subprompts = []
        self._buf_index = 0
        self._context = {}

        self._syntax_tree = {
            "p": "eval",         # p  - pause
            "a": {"p": "eval"},  # ap - analysis pause
            "r": "eval",         # r - resume
            "q": "eval",         # q - quit
            "w": "eval",         # w - set watch in first free register
            "'": {},             # '... - operation on watch register
            "\"": {}             # "... - operation on command register
        }


        for k in "0123456789":
            self._syntax_tree[k] = "continue"

        for k in self.AVAILABLE_REGISTERS:
            self._syntax_tree["'"][k] = {
                    "w": "eval",   # 'Rw Set a watch in register R
                    "d": "eval",   # 'Rd Disable the watch
                    "e": "eval",   # 'Re Enable the watch
                    "x": "eval"    # 'Rx Delete the watch
            }

        self._syntax_tree_ptr = self._syntax_tree

    def get_modified_watch(self):
        if "set_watch" in self._context and "register" in self._context:
            return self._context["register"]
        else:
            return None

    def get_user_input_string(self):
        if self._input_mode == self.PREDICATE_MODE:
            return "\u21c9 " + self._command_buffer
        elif self._input_mode == self.TEXT_INPUT_MODE:
            return self._prompt + self._text_input_buffer
        elif self._input_mode == self.MULTI_INPUT_MODE:
            count = len(self._subprompts)
            arrow = " "
            if count > 2:
                if self._buf_index == 0:
                    arrow = "\u2193" # Down arrow
                elif self._buf_index == count - 1:
                    arrow = "\u2191" # Up arrow
                else:
                    arrow = "\u2195" # Up/down arrow

            return "%s | %c%s%s" % (self._prompt, arrow, self._subprompts[self._buf_index], self._text_input_buffer[self._buf_index])


    def on_command_buffer_changed(self, callback: callable):
        self._command_buffer_changed_cb = callback

    def on_pause(self, callback: callable):
        self._pause_cb = callback

    def on_resume(self, callback: callable):
        self._resume_cb = callback

    def on_quit(self, callback: callable):
        self._quit_cb = callback

    def on_set_watch(self, callback: callable):
        self._set_watch_cb = callback

    def on_enable_watch(self, callback: callable):
        self._set_watch_enable_cb = callback

    def _reset_command_buffer(self):
        self._command_buffer = ""
        self._text_input_buffer = ""
        self._syntax_tree_ptr = self._syntax_tree

    def _enter_text_input(self, command, prompt, **kwargs):
        self._command_buffer = command
        self._input_mode = self.TEXT_INPUT_MODE
        self._prompt = "Regular expression: "
        self._context = kwargs

    def _enter_predicate_mode(self, **kwargs):
        self._input_mode = self.PREDICATE_MODE
        self._context = kwargs

    def _enter_multi_mode(self, command, prompt, fields, **kwargs):
        self._command_buffer = command
        self._input_mode = self.MULTI_INPUT_MODE
        self._prompt = prompt
        self._subprompts = [""] * len(fields)
        self._text_input_buffer = [""] * len(fields)
        for field_ix, field in enumerate(fields):
            if isinstance(field, (list, tuple)):
                assert len(field) == 2
                self._subprompts[field_ix] = field[0]
                self._text_input_buffer[field_ix] = field[1]
            else:
                self._subprompts[field_ix] = field
                self._text_input_buffer[field_ix] = ""

        self._buf_index = 0
        self._context = kwargs

    def _find_first_available_watch(self):
        for w in self.AVAILABLE_REGISTERS:
            if w not in self._config.watches:
                return w
        return None

    def _handle_set_watch(self, register):
        if len(self._text_input_buffer) == 0:
            if register in self._config.watches:
                watch = self._config.watches[register]
                regex = watch.regex
                bg_color, fg_color = watch.format.get()
            else:
                regex = ""
                bg_color, fg_color = get_default_register_format(register)
            self._enter_multi_mode(self._command_buffer, "Set watch '%c" % register, [
                ("Regular expression: ", regex),
                ("Background color: ", str(bg_color)),
                ("Foreground color: ", str(fg_color))],
                register=register,
                set_watch=True)
        else:
            self._set_watch_cb((self._context['register'], self._text_input_buffer[0], self._text_input_buffer[1], self._text_input_buffer[2]))
            self._reset_command_buffer()
            self._enter_predicate_mode()

    def _handle_command(self):
        command = self._command_buffer
        command_params = self._text_input_buffer
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
            register = self._find_first_available_watch()
            self._handle_set_watch(register)
        elif command[0] == "'" and command[2] == "w":
            self._handle_set_watch(command[1])
        elif command[0] == "'" and command[2] == "x":
            self._set_watch_cb((command[1], '', -1, -1))
        elif command[0] == "'" and command[2] == "d":
            self._set_watch_enable_cb(command[1], False)
        elif command[0] == "'" and command[2] == "e":
            self._set_watch_enable_cb(command[1], True)
        else:
            print("Unhandled command: %s, %s, %s" % (counter, command, command_params))

    def _read_key_predicate_input(self, key):
        if key in self._syntax_tree_ptr:
            self._command_buffer += key
            if isinstance(self._syntax_tree_ptr[key], dict):
                self._syntax_tree_ptr = self._syntax_tree_ptr[key]
            elif self._syntax_tree_ptr[key] == "continue":
                pass  # Stay on the same level of parser tree
            elif self._syntax_tree_ptr[key] == "eval":
                self._handle_command()
                if self._input_mode == self.PREDICATE_MODE:
                    self._reset_command_buffer()
        else:
            self._reset_command_buffer()

    def _on_backspace(self):
        if isinstance(self._text_input_buffer, list):
            if len(self._text_input_buffer[self._buf_index]) > 0:
                self._text_input_buffer[self._buf_index] = self._text_input_buffer[self._buf_index][:-1]
        else:
            if len(self._text_input_buffer) > 0:
                self._text_input_buffer = self._text_input_buffer[:-1]

    def _on_input(self, content):
        if isinstance(self._text_input_buffer, list):
                self._text_input_buffer[self._buf_index] += content
        else:
            self._text_input_buffer += content

    def _read_key_common(self, key):
        if key == "<BS>":
            self._on_backspace()
        elif key == "<Space>":
            self._on_input(" ")
        elif key == "<LT>":
            self._on_input("<")
        elif key == "<GT>":
            self._on_input(">")
        elif key == "<ESC>":
            self._input_mode = self.PREDICATE_MODE
            self._reset_command_buffer()
        elif key == "<Enter>":
            self._handle_command()
        else:
            return False
        return True

    def _read_key_text_input(self, key):
        if not self._read_key_common(key):
            self._text_input_buffer += key

    def _read_key_multi_input(self, key):
        if key in ["<Up>"]:
            if self._buf_index > 0:
                self._buf_index -= 1
        elif key in ["<Down>"]:
            if self._buf_index < len(self._subprompts) - 1:
                self._buf_index += 1
        elif not self._read_key_common(key):
            self._text_input_buffer[self._buf_index] += key

    def read_key(self, term: TerminalRawMode):
        key = term.read_key()
        if key != "":
            if self._input_mode == self.PREDICATE_MODE:
                self._read_key_predicate_input(key)
            elif self._input_mode == self.TEXT_INPUT_MODE:
                self._read_key_text_input(key)
            elif self._input_mode == self.MULTI_INPUT_MODE:
                self._read_key_multi_input(key)

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
        self._server_state = ""

    def set_max_held_lines(self, size):
        if size is not None:
            info("Set maximum number of held lines to %d" % size)
            self._max_held_lines = size
        else:
            info("No maximum number of held lines set, using default of %d" % self._max_held_lines)

    def set_drop_newest_lines_policy(self, value):
        self._drop_newest_lines = value

    def _print_line(self, data):
        matched_register = None
        for register, watch in self._config.watches.items():
            if watch.enabled and watch.match(data['data']):
                matched_register = register
                break

        if matched_register is not None:
            data['watch'] = matched_register
            data['watch-symbol'] = render_watch_register(matched_register)
        else:
            data['watch'] = ""
            data['watch-symbol'] = "   "

        if not self._config.filtered_mode or matched_register is not None:
            self._terminal.reset_current_line()
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

    def notify_server_state(self, state):
        self._server_state = state

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
        STATE_MAP = {"startup": "\u2197",
                     "active": "\u2506",
                     "shutdown": "\u2198",
                     "stopped": "\u2500"}

        if self._status_line_req_update:
            term.reset_current_line("43;30")

            term.write("%s " % STATE_MAP.get(self._server_state, '?'))
            if self._pause:
                if self._drop_newest_lines:
                    term.write("\u2507\u2507", flush=False)
                else:
                    term.write("\u2503\u2503", flush=False) # Pause character
                term.write("%3d%%" % (len(self._held_lines) * 100 / self._max_held_lines))
            else:
                term.write("\u2b9e     ", flush=False)

            changed_register = self._interact.get_modified_watch()

            for register, filter_data in self._formatter.get_filters().items():
                if register == changed_register:
                    term.set_color_format("5")

                if self._config.watches[register].enabled:
                    term.set_color_format(ansi_format1(filter_data.get()))
                else:
                    term.set_color_format("43;30")

                term.write(render_watch_register(register))
                if register == changed_register:
                    term.set_color_format("25")

            term.set_color_format("43;30")
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
                        elif data['type'] == 'keepalive':
                            self._cout.notify_server_state(data['state'])

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


def pause_callback(console_output, analysis_mode):
    console_output.set_drop_newest_lines_policy(analysis_mode)
    console_output.pause()


def resume_callback(console_output):
    console_output.resume()


def set_filter_callback(formatter: Formatter, config: Configuration, params: tuple):
    register, regex, background, foreground = params
    filter = Watch()
    filter.set_regex(regex)
    filter.enabled = True
    filter.format.background_color = {"default": resolve_color(background)}
    filter.format.foreground_color = {"default": resolve_color(foreground)}

    if regex == "":
        formatter.delete_watch_format(register)
        config.delete_watch(register)
    else:
        formatter.add_filter_format(register, filter.format)
        config.add_watch(register, filter)


def set_watch_enable(config: Configuration, register: str, enabled: bool):
    if register in config.watches:
        config.watches[register].enabled = enabled


def quit_callback():
    raise KeyboardInterrupt

if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGWATCH v%s: lwview" % VERSION)
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
    interact.on_set_watch(lambda params: set_filter_callback(formatter, config, params))
    interact.on_enable_watch(lambda watch, enabled: set_watch_enable(config, watch, enabled))
    interact.on_quit(lambda: quit_callback())

    for endpoint_name, endpoint_format in config.endpoint_formats.items():
        formatter.add_endpoint_format(endpoint_name, endpoint_format)

    for filter_name, filter in config.watches.items():
        formatter.add_filter_format(filter_name, filter.format)

    try:
        client = TCPClient(config, console_output)
        client.run()
        client.send_enc({'type': 'get-late-join-records'})

        command_buffer = ""
        while True:
            console_output.write_pending_lines()
            console_output.render_status_line()
            interact.read_key(term)
    except ConnectionRefusedError:
        error("Could not connect to the server: connection refused")
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        term.exit_raw_mode()
