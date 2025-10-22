from view.configuration import Configuration
from view.formatter import Formatter, ansi_format, ansi_format1
from view.formatter import repr_watch_register, repr_endpoint_register
from view.interactive_mode import InteractiveModeContext
from collections import deque
from utils import info, warning
from utils import TerminalRawMode
import common


SYM_VERTICAL_THICK_BAR="\u2503"

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

        data['endpoint-symbol'] = repr_endpoint_register(data['endpoint'])

        if matched_register is not None:
            data['watch'] = matched_register
            data['watch-symbol'] = repr_watch_register(matched_register)
            data['matches'] = watch.matches

            # TODO: other condition should not be required
            if watch.replacement is not None and watch.replacement != "":
                repl = watch.replacement
                for ix, match in enumerate(data['matches']):
                    repl = repl.replace('\\%d' % (ix + 1), match)
                data['data'] = repl
        else:
            data['watch'] = ""
            data['watch-symbol'] = repr_watch_register(None)
            data['matches'] = []

        if not self._config.filtered_mode or matched_register is not None:
            first_row = True
            for content in data['data'].split('\n'):
                data_row = data
                data_row['data'] = content
                self._terminal.reset_current_line()
                use_format = self._config.line_format if first_row else self._config.continued_line_format
                self._terminal.write_line(self._formatter.format_line(use_format, data_row))
                self._status_line_req_update = True
                first_row = False

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
        data['seq'] = '-'
        data['endpoint'] = common.SYSTEM_ENDPOINT
        data['fd'] = 'marker'
        self._hold(data)

    def print_message(self, msg, fd="info"):
        self._hold({
            "data": msg,
            "endpoint": common.SELF_ENDPOINT,
            "fd": fd
        })

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
            self._print_line(data)

    def feed(self, amount):
        for _ in range(0, amount):
            if len(self._held_lines) == 0:
                break
            data = self._held_lines.popleft()
            self._print_line(data)

    def render_status_line(self):
        STATE_MAP = {"startup": "\u2197",
                     "active": "\u2506",
                     "shutdown": "\u2198",
                     "stopped": "\u2500"}
        colors = self._config.colors

        status_line_style = ansi_format(colors.status_line_bg, colors.status_line_fg)

        if self._status_line_req_update:
            self._terminal.reset_current_line(status_line_style)

            self._terminal.write("%s " % STATE_MAP.get(self._server_state, '?'))
            if self._pause:
                self._terminal.write("PAU ")
            else:
                self._terminal.write("RUN ", flush=False)
            if self._config.filtered_mode:
                self._terminal.write("FLT ", flush=False)

            changed_register = self._interact.get_modified_watch()
            default_endpoint = self._interact.get_default_endpoint()

            self._terminal.write("&%c " % default_endpoint)

            for register, filter_data in self._formatter.get_filters().items():
                if register == changed_register:
                    self._terminal.set_format("5")

                if self._config.watches[register].enabled:
                    self._terminal.set_format(ansi_format1(filter_data.get()))
                else:
                    self._terminal.set_format(status_line_style)

                self._terminal.write(repr_watch_register(register) + " ")
                if register == changed_register:
                    self._terminal.set_format("25")

            self._terminal.set_format(status_line_style)
            self._terminal.write(" ")
            self._terminal.write(self._interact.get_user_input_string())
            predicate_mode_help = self._interact.get_predicate_mode_help()
            if predicate_mode_help != "":
                self._terminal.write("  " + SYM_VERTICAL_THICK_BAR)
                self._terminal.set_format(
                    ansi_format(colors.pred_help_bg, colors.pred_help_fg))
                self._terminal.write(predicate_mode_help + "\x1b[%dD" % (len(predicate_mode_help) + 3))
            self._status_line_req_update = False

    def notify_status_line_changed(self):
        self._status_line_req_update = True


