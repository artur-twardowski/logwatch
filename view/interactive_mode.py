from view.configuration import Configuration
from view.formatter import ansi_format1, get_default_register_format
from utils import TerminalRawMode


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

            disp_value = self._text_input_buffer[self._buf_index]
            if disp_value == "":
                disp_value = "\x1b[%sm%s" % (
                    ansi_format1((3, 245)),
                    self._values_on_empty[self._buf_index])

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
            self._set_watch_cb(command[1], ('', '', -1, -1))
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

    def _read_key_message(self, key):
        if key in ["<Enter>", "<ESC>"]:
            self._input_mode = self.PREDICATE_MODE
            self._reset_command_buffer()

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

