from view.configuration import Configuration
from view.formatter import get_default_register_format
from utils import TerminalRawMode, text_window, remove_last_key, lw_assert
from predicate_input import PredicateInput
from view.interactive_mode.predicate_mode_view import PredicateModeView
from view.interactive_mode.input_views import SimpleInputView, ComplexInputView, ComplexInputSubprompt
from common import AVAILABLE_REGISTERS


class MessageView:
    def __init__(self, message: str, on_keypress: callable):
        self._message = message
        self._on_keypress = on_keypress

    def render_content(self, available_cols, terminal: TerminalRawMode):
        terminal.write(self._message)

    def on_key(self, key):
        self._on_keypress(key)


class InteractiveModeContext:
    
    def __init__(self, config: Configuration, formatter, console_output):
        self._config = config
        self._command_buffer_changed_cb = None
        self._prompt = ""
        self._subprompts = []
        self._buf_index = 0
        self._default_endpoint = config.default_endpoint
        self._predicate_input = PredicateInput()
        self._predicate_input_ctx = self._predicate_input.begin()
        self._predicate_mode_view = PredicateModeView(self, self._predicate_input_ctx, self._config, formatter, console_output)
        self._active_view = self._predicate_mode_view
        self._console_output = None
        self._char_classes = {}

        tc_digits = PredicateInput.TokenClass(frozenset({ch for ch in "0123456789"}),
                                              placeholder="<Digit>")
        tc_registers = PredicateInput.TokenClass(frozenset({ch for ch in AVAILABLE_REGISTERS}),
                                                 placeholder="<Register>")
        tc_trigger_operation = PredicateInput.TokenClass(frozenset({"=", "+", "x"}), placeholder="<TriggerOp>")

        for cls in (tc_digits, tc_registers, tc_trigger_operation):
            self._char_classes[cls.placeholder] = cls

        self._predicate_input.register([tc_digits], PredicateInput.Continue)

    def register_action(self, seq: str, name, description, **callbacks):
        sequence = []
        ch_ix = 0
        while ch_ix < len(seq):
            ch = seq[ch_ix]
            if ch == '<':
                end_ix = seq.find('>', ch_ix + 1)
                lw_assert(end_ix != -1, "Missing '>' in sequence specification")
                class_name = seq[ch_ix:end_ix + 1]
                ch_ix = end_ix

                lw_assert(class_name in self._char_classes,
                          "Unknown character class: \"%s\"" % class_name)
                sequence.append(self._char_classes[class_name])

            elif ch == '\\':
                lw_assert(ch_ix + 1 < len(seq), "Expected a character after '\\'")
                ch_ix += 1
                sequence.append(seq[ch_ix])

            elif ch == '*':
                print("At %s: <continue>" % sequence)
                self._predicate_input.register(sequence, PredicateInput.Continue)
                sequence.pop()

            else:
                sequence.append(seq[ch_ix])

            ch_ix += 1

        print("At %s: %s" % (sequence, name))
        self._predicate_input.register(sequence,
                                       PredicateInput.Action(description=(name, description),
                                                             **callbacks))

    def notify_active_actions(self, endpoints, other_actions):
        self._predicate_mode_view.notify_active_actions(endpoints, other_actions)

    def get_default_endpoint(self):
        return self._default_endpoint

    def is_predicate_mode(self):
        return self._active_view == self._predicate_mode_view

    def render_view(self, terminal: TerminalRawMode):
        return self._active_view.render_content(64, terminal)

    def on_command_buffer_changed(self, callback: callable):
        self._command_buffer_changed_cb = callback

    def on_send_stdin(self, callback: callable):
        self._send_stdin_cb = callback

    def on_print_info(self, callback: callable):
        self._print = callback

    def return_to_predicate_mode(self):
        self._active_view = self._predicate_mode_view

    def show_message(self, message):
        self.enter_view(MessageView(message, on_keypress=lambda key: (
            self._predicate_mode_view.on_key(key),
            self.return_to_predicate_mode()
        )))

    def enter_view(self, view):
        self._active_view = view

    def _do_send_stdin(self, endpoint_register, initial_content = "", stay_in_input_mode=False):
        self.enter_view(SimpleInputView(
            prompt="Send to '" + endpoint_register,
            initial_value=initial_content,
            on_confirm=lambda cmd, ep=endpoint_register: (
                self._send_stdin_cb(ep, cmd),
                stay_in_input_mode or self.return_to_predicate_mode()),
            on_cancel=lambda: self.return_to_predicate_mode()))

    def _print_command_registers(self):
        for reg, command in self._config.commands.items():
            self._print("info", "\"%c: %s" % (reg, command))

    def _assert_registers_set(self, endpoint_register=None, command_register=None):
        if command_register not in self._config.commands:
            self.show_message("Nothing is stored in command register \"%c" % command_register)
            return False
        return True

    def set_default_endpoint(self, endpoint):
        self._default_endpoint = endpoint

    def read_key(self, term: TerminalRawMode):
        key = term.read_key()
        if key != "":
            self._active_view.on_key(key)
            self._command_buffer_changed_cb()

