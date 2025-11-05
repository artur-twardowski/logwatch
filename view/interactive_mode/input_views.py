from utils import TerminalRawMode, remove_last_key, text_window

SYM_ARROW_UP="\u2191"
SYM_ARROW_DOWN="\u2193"
SYM_ARROW_UP_DOWN="\u2195"


class ComplexInputSubprompt:
    def __init__(self, subprompt, initial_value):
        self.subprompt = subprompt
        self.initial_value = initial_value
        self.value = initial_value


class SimpleInputView:
    def __init__(self, prompt, initial_value, on_confirm: callable, on_cancel: callable):
        self._prompt = prompt
        self._current_value = initial_value
        self._initial_value = initial_value
        self._on_confirm_cb = on_confirm
        self._on_cancel_cb = on_cancel

    def render_content(self, available_cols, terminal: TerminalRawMode):
        avail_width = available_cols - len(self._prompt) - 2
        terminal.write(self._prompt + ": " + text_window(self._current_value, avail_width))

    def on_custom_key(self, key):
        return False

    def on_key(self, key):
        if key == TerminalRawMode.KEY_ENTER:
            self._on_confirm_cb(self._current_value)
            self._current_value = self._initial_value
        elif key == TerminalRawMode.KEY_ESC:
            self._on_cancel_cb()
        elif self.on_custom_key(key):
            pass
        elif key == TerminalRawMode.KEY_BACKSPACE:
            if len(self._current_value) > 0:
                self._current_value = remove_last_key(self._current_value)
        else:
            self._current_value += key


class ComplexInputView:
    def __init__(self, prompt, subprompts: list, on_confirm: callable, on_cancel: callable):
        self._prompt = prompt
        self._subprompts = subprompts
        self._on_confirm_cb = on_confirm
        self._on_cancel_cb = on_cancel
        self._subprompt_index = 0
        self._last_subprompt = len(self._subprompts) - 1

    def render_content(self, available_cols, terminal: TerminalRawMode):
        current_subprompt = self._subprompts[self._subprompt_index]
        value = str(current_subprompt.value or "")
        avail_width = available_cols - len(self._prompt) - len(value) - 5
        if self._last_subprompt == 0:
            arrow = " "
        elif self._subprompt_index == 0:
            arrow = SYM_ARROW_DOWN
        elif self._subprompt_index == self._last_subprompt:
            arrow = SYM_ARROW_DOWN
        else:
            arrow = SYM_ARROW_UP_DOWN
        terminal.write(self._prompt + " |" + arrow + current_subprompt.subprompt + \
                       ": " + value or "", avail_width)

    def _create_callback_args(self):
        return [sp.value for sp in self._subprompts]

    def on_custom_key(self, key):
        return False

    def on_key(self, key):
        if key == TerminalRawMode.KEY_ENTER:
            self._on_confirm_cb(*self._create_callback_args())
        elif key == TerminalRawMode.KEY_ESC:
            self._on_cancel_cb()
        elif key == TerminalRawMode.KEY_DOWN_ARROW:
            if self._subprompt_index < self._last_subprompt:
                self._subprompt_index += 1
        elif key == TerminalRawMode.KEY_UP_ARROW:
            if self._subprompt_index > 0:
                self._subprompt_index -= 1
        elif self.on_custom_key(self):
            # In derived class, on_custom_key can capture any key except ENTER, ESC and up and down arrows.
            # If the key is not captured (the function returns False), the default handling will be used
            pass
        elif key == TerminalRawMode.KEY_BACKSPACE:
            self._subprompts[self._subprompt_index].value = remove_last_key(self._subprompts[self._subprompt_index].value)
        else:
            val = str(self._subprompts[self._subprompt_index].value or "")
            self._subprompts[self._subprompt_index].value = val + key

