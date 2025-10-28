from view.configuration import Configuration
from view.formatter import ansi_format, get_default_register_format
from utils import TerminalRawMode

SYM_ARROW_UP="\u2191"
SYM_ARROW_DOWN="\u2193"
SYM_ARROW_UP_DOWN="\u2195"
SYM_PREDICATE_MODE_PROMPT="\u21e8"

class MultiModeSubprompt:
    def __init__(self, subprompt, current_value, fmt=None, value_on_empty=""):
        self.subprompt = subprompt
        self.current_value = current_value
        self.format = fmt
        self.value_on_empty = value_on_empty


class InteractiveModeContext:
    PREDICATE_MODE = 1
    TEXT_INPUT_MODE = 2
    MULTI_INPUT_MODE = 3
    MESSAGE_MODE = 4

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
        self._default_endpoint = config.default_endpoint
        self._next_keys_in_predicate_mode = ""

        self._syntax_tree = {
            "a": {"p": "eval"},  # ap - analysis pause
            "F": "eval",         # F - toggle filtered mode
            "i": "eval",         # i - send data to stdin in to active endpoint
            "I": "eval",
            "m": "eval",
            "p": "eval",         # p  - pause
            "q": "eval",         # q - quit
            "r": "eval",         # r - resume
            "w": "eval",         # w - set watch in first free register
            "'": {},             # '... - operation on watch register
            "\"": {
                "?": "eval"
            },                   # "... - operation on command register
            "&": {}              # &... - operation on endpoint register
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

            self._syntax_tree["\""][k] = {
                    "i": "eval",
                    "I": "eval",
                    "r": "eval",
                    "s": "eval"
            }

            self._syntax_tree["&"][k] = {
                    "d": "eval",
                    "i": "eval",   # ;Ri Send data to stdin to indicated endpoint
                    "I": "eval",
                    "n": "eval",
                    "f": "eval",
                    "a": "eval",
                    "\"": {}       # ;R"R Send data from indicated command register to indicated endpoint
            }

            for k2 in self.AVAILABLE_REGISTERS:
                self._syntax_tree['&'][k]["\""][k2] = {
                    "i": "eval",
                    "I": "eval",
                    "r": "eval"
                }

        self._syntax_tree_ptr = self._syntax_tree

    def get_modified_watch(self):
        if "set_watch" in self._context and "register" in self._context:
            return self._context["register"]
        else:
            return None

    def get_default_endpoint(self):
        return self._default_endpoint

    def _format_displayable(self, data):
        result = ""
        for ch in data:
            if ch == "\x01":
                result += "<"
            elif ch == "\x02":
                result += ">"
            else:
                result += ch
        return result

    def is_predicate_mode(self):
        return self._input_mode == self.PREDICATE_MODE

    def get_user_input_string(self):
        if self._input_mode == self.PREDICATE_MODE:
            return SYM_PREDICATE_MODE_PROMPT + self._format_displayable(self._command_buffer)
        elif self._input_mode == self.TEXT_INPUT_MODE:
            return self._prompt + self._format_displayable(self._text_input_buffer)
        elif self._input_mode == self.MULTI_INPUT_MODE:
            count = len(self._subprompts)
            arrow = " "
            if count > 2:
                if self._buf_index == 0:
                    arrow = SYM_ARROW_DOWN
                elif self._buf_index == count - 1:
                    arrow = SYM_ARROW_UP
                else:
                    arrow = SYM_ARROW_UP_DOWN

            disp_value = self._text_input_buffer[self._buf_index]
            if disp_value == "":
                placeholder = self._values_on_empty[self._buf_index]
                disp_value = "\x1b[%sm%s\x1b[%dD" % (
                    ansi_format(self._config.colors.empty_placeholder_bg,
                                self._config.colors.empty_placeholder_fg),
                    placeholder, len(placeholder))
            disp_value = self._format_displayable(disp_value)

            return "%s | %c%s%s" % (self._prompt, arrow, self._subprompts[self._buf_index], disp_value)
        elif self._input_mode == self.MESSAGE_MODE:
            return self._prompt

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

    def on_send_stdin(self, callback: callable):
        self._send_stdin_cb = callback

    def on_print_info(self, callback: callable):
        self._print = callback

    def on_set_marker(self, callback: callable):
        self._set_marker_cb = callback

    def _reset_command_buffer(self):
        self._command_buffer = ""
        self._text_input_buffer = ""
        self._syntax_tree_ptr = self._syntax_tree

    def _enter_text_input(self, command, prompt, initial_content="", **kwargs):
        self._command_buffer = command
        self._input_mode = self.TEXT_INPUT_MODE
        self._prompt = prompt
        self._text_input_buffer = initial_content
        self._context = kwargs

    def _enter_predicate_mode(self, **kwargs):
        self._input_mode = self.PREDICATE_MODE
        self._context = kwargs

    def _enter_multi_mode(self, command, prompt, fields: list, **kwargs):
        self._command_buffer = command
        self._input_mode = self.MULTI_INPUT_MODE
        self._prompt = prompt
        self._subprompts = [""] * len(fields)
        self._text_input_buffer = [""] * len(fields)
        self._values_on_empty = [""] * len(fields)
        for field_ix, field in enumerate(fields):
            assert isinstance(field, MultiModeSubprompt)
            self._subprompts[field_ix] = field.subprompt
            self._text_input_buffer[field_ix] = field.current_value
            self._values_on_empty[field_ix] = field.value_on_empty

        self._buf_index = 0
        self._context = kwargs

    def _enter_message_mode(self, message):
        self._input_mode = self.MESSAGE_MODE
        self._prompt = message

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
                replacement = watch.replacement
                bg_color, fg_color = watch.format.get()
            else:
                regex = ""
                replacement = None
                bg_color, fg_color = get_default_register_format(register)

            # TODO: should not be required
            if replacement is None:
                replacement = ""

            self._enter_multi_mode(self._command_buffer, "Set watch '%c" % register, fields=[
                MultiModeSubprompt("Regular expression: ", regex),
                MultiModeSubprompt("Replacement: ", replacement, value_on_empty="No replacement"),
                MultiModeSubprompt("Background color: ", str(bg_color)),
                MultiModeSubprompt("Foreground color: ", str(fg_color))],
                register=register,
                set_watch=True)
        else:
            try:
                self._set_watch_cb(self._context['register'], self._text_input_buffer)
                self._reset_command_buffer()
                self._enter_predicate_mode()
            except Exception as ex:
                self._enter_message_mode("Error: %s" % ex)

    def _handle_send_stdin(self, endpoint_register, initial_content = "", stay_in_input_mode=False):
        if len(self._text_input_buffer) == 0:
            self._enter_text_input(self._command_buffer, "Send: ", initial_content, register=endpoint_register, stay_in_input_mode=stay_in_input_mode)
        else:
            self._send_stdin_cb(self._context['register'], self._text_input_buffer)

            if self._context['stay_in_input_mode']:
                self._text_input_buffer = initial_content
            else:
                self._reset_command_buffer()
                self._enter_predicate_mode()

    def _handle_set_command_register(self, command_register):
        if len(self._text_input_buffer) == 0:
            self._enter_text_input(self._command_buffer, "Set command in \"%c: " % command_register,
                                   initial_content=self._config.commands.get(command_register, ""),
                                   register=command_register)
        else:
            self._config.commands[self._context['register']] = self._text_input_buffer
            self._reset_command_buffer()
            self._enter_predicate_mode()

    def _print_command_registers(self):
        for reg, command in self._config.commands.items():
            self._print("info", "\"%c: %s" % (reg, command))

    def _command_matches(self, command, pattern):
        if len(command) != len(pattern):
            return False

        for ix in range(0, len(command)):
            if pattern[ix] == '\x01':
                if command[ix] not in self.AVAILABLE_REGISTERS:
                    return False
            else:
                if command[ix] != pattern[ix]:
                    return False
        return True

    def _command_matches_any(self, command, *patterns):
        for pattern in patterns:
            if self._command_matches(command, pattern):
                return True
        return False

    def _assert_registers_set(self, endpoint_register=None, command_register=None):
        if command_register not in self._config.commands:
            self._enter_message_mode("Nothing is stored in command register \"%c" % command_register)
            return False
        return True

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

        if self._command_matches(command, "p"):
            self._pause_cb(False)
        elif command == "ap":
            self._pause_cb(True)
        elif command == "r":
            self._resume_cb()
        elif command == "q":
            self._quit_cb()
        elif self._command_matches(command, "m"):
            self._set_marker_cb()
        elif command == "w":
            register = self._find_first_available_watch()
            self._handle_set_watch(register)
        elif command[0] == "'" and command[2] == "w":
            self._handle_set_watch(command[1])
        elif command[0] == "'" and command[2] == "x":
            self._set_watch_cb(command[1], ('', '', -1, -1))
        elif command[0] == "'" and command[2] == "d":
            self._set_watch_enable_cb(command[1], False)
        elif command[0] == "'" and command[2] == "e":
            self._set_watch_enable_cb(command[1], True)
        elif self._command_matches_any(command, "i", "I"):
            self._handle_send_stdin(self._default_endpoint,
                                    stay_in_input_mode=command[0] == 'I')
        elif self._command_matches_any(command, "F"):
            self._config.filtered_mode = not self._config.filtered_mode

        elif self._command_matches(command, "\"?"):
            # "? - Print the information about all command registers
            self._print_command_registers()

        elif self._command_matches_any(command, "\"\x01i", "\"\x01I"):
            # "Ri - Send the data from command register "R to the default endpoint. Edit the contents before sending
            if self._assert_registers_set(self._default_endpoint, command[1]):
                self._handle_send_stdin(
                    self._default_endpoint,
                    initial_content=self._config.commands.get(command[1]),
                    stay_in_input_mode=(command[2] == 'I'))

        elif self._command_matches_any(command, "&\x01\"\x01i", "&\x01\"\x01I"):
            # &R"Ri - Send the data from command register "R to the endpoint &R. Edit the contents before sending
            if self._assert_registers_set(command[1], command[3]):
                self._handle_send_stdin(
                    command[1],
                    initial_content=self._config.commands.get(command[3]),
                    stay_in_input_mode=(command[4] == 'I'))

        elif self._command_matches(command, "\"\x01r"):
            # "Rr - Send the data from command register "R to the default endpoint.
            if self._assert_registers_set(self._default_endpoint, command[1]):
                self._send_stdin_cb(self._default_endpoint, self._config.commands.get(command[1]))

        elif self._command_matches(command, "&\x01\"\x01r"):
            # "Rr - Send the data from command register "R to the default endpoint.
            if self._assert_registers_set(command[1], command[3]):
                self._send_stdin_cb(command[1], self._config.commands.get(command[3]))

        elif self._command_matches(command, "\"\x01s"):
            # "Rs - Set the content of command register "R
            self._handle_set_command_register(command[1])

        elif self._command_matches(command, "&\x01d"):
            # &Rd - Select register &R as a default endpoint register
            self._default_endpoint = command[1]
            self._enter_message_mode("Changed default endpoint to &%c" % self._default_endpoint)

        elif self._command_matches(command, "&\x01n"):
            self._config.set_endpoint_show_mode(command[1], Configuration.SHOW_NONE)

        elif self._command_matches(command, "&\x01f"):
            self._config.set_endpoint_show_mode(command[1], Configuration.SHOW_FILTERED)

        elif self._command_matches(command, "&\x01a"):
            self._config.set_endpoint_show_mode(command[1], Configuration.SHOW_ALL)

        elif self._command_matches_any(command, "&\x01i", "&\x01I"):
            # &Ri - Send data to endpoint &R.
            self._handle_send_stdin(command[1],
                                    stay_in_input_mode=(command[2] == 'I'))

        else:
            self._print("error", "Unhandled command: %s, %s, %s" % (counter, command, command_params))

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

    def _build_predicate_mode_help(self):
        result = ""
        for k in sorted(self._syntax_tree_ptr.keys()):
            result += k
        self._next_keys_in_predicate_mode = result

    def get_predicate_mode_help(self):
        self._build_predicate_mode_help()
        if self._input_mode == self.PREDICATE_MODE:
            return self._next_keys_in_predicate_mode
        else:
            return ""

    def _remove_last_key(self, data):
        last_char = len(data) - 1
        if data[last_char] == "\x02":
            while data[last_char] != "\x01":
                last_char -= 1
        return data[0:last_char]

    def _on_backspace(self):
        if isinstance(self._text_input_buffer, list):
            if len(self._text_input_buffer[self._buf_index]) > 0:
                self._text_input_buffer[self._buf_index] = self._remove_last_key(self._text_input_buffer[self._buf_index])
        else:
            if len(self._text_input_buffer) > 0:
                self._text_input_buffer = self._remove_last_key(self._text_input_buffer)

    def _on_input(self, content):
        if isinstance(self._text_input_buffer, list):
                self._text_input_buffer[self._buf_index] += content
        else:
            self._text_input_buffer += content

    def _read_key_common(self, key):
        if key == TerminalRawMode.KEY_BACKSPACE:
            self._on_backspace()
        elif key == "<Space>":
            self._on_input(" ")
        elif key == TerminalRawMode.KEY_ESC:
            self._input_mode = self.PREDICATE_MODE
            self._reset_command_buffer()
        elif key == TerminalRawMode.KEY_ENTER:
            self._handle_command()
        else:
            return False
        return True

    def _read_key_text_input(self, key):
        if not self._read_key_common(key):
            self._text_input_buffer += key

    def _read_key_multi_input(self, key):
        if key in [TerminalRawMode.KEY_UP_ARROW]:
            if self._buf_index > 0:
                self._buf_index -= 1
        elif key in [TerminalRawMode.KEY_DOWN_ARROW]:
            if self._buf_index < len(self._subprompts) - 1:
                self._buf_index += 1
        elif not self._read_key_common(key):
            self._text_input_buffer[self._buf_index] += key

    def _read_key_message(self, key):
        self._input_mode = self.PREDICATE_MODE
        self._reset_command_buffer()
        self._read_key_predicate_input(key)

    def read_key(self, term: TerminalRawMode):
        key = term.read_key()
        if key != "":
            if self._input_mode == self.PREDICATE_MODE:
                self._read_key_predicate_input(key)
            elif self._input_mode == self.TEXT_INPUT_MODE:
                self._read_key_text_input(key)
            elif self._input_mode == self.MULTI_INPUT_MODE:
                self._read_key_multi_input(key)
            elif self._input_mode == self.MESSAGE_MODE:
                self._read_key_message(key)

            self._command_buffer_changed_cb(self._command_buffer)

