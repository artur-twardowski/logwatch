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
    def __init__(self, config: Configuration, formatter: Formatter, term: TerminalRawMode):
        self._config = config
        self._formatter = formatter
        self._terminal = term
        self._interact = None
        self._held_lines = deque()
        self._max_held_lines = 5000
        self._pause = False
        self._held_lines_overflow = False
        self._drop_newest_lines = False
        self._status_line_req_update = True
        self._server_state = ""
        self._endpoints = {}
        self._other_actions = {}

    def bind_interact(self, interact: InteractiveModeContext):
        self._interact = interact

    def get_pause_data(self):
        return self._pause, len(self._held_lines), self._max_held_lines, self._held_lines_overflow

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
            data['watch-symbol'] = repr_watch_register(data['watch'])
            #data['matches'] = watch.matches

            # TODO: other condition should not be required
            if watch.compiled_replacement is not None and watch.compiled_replacement != "":
                repl = watch.compiled_replacement
                for ix, match in enumerate(watch.matches):
                    repl = repl.replace('\\%d' % (ix + 1), match)
                data['data'] = repl
        else:
            data['watch'] = ""
            data['watch-symbol'] = repr_watch_register(None)
            #data['matches'] = []

        show_mode = self._config.get_endpoint_show_mode(data['endpoint'])
        print_line = (show_mode == Configuration.SHOW_ALL) or \
                     (show_mode == Configuration.SHOW_FILTERED and matched_register is not None)

        if print_line:
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

    def notify_active_actions(self, endpoints, other_actions):
        self._interact.notify_active_actions(endpoints, other_actions)
        self.notify_status_line_changed()

    def pause(self):
        self._pause = not self._pause

    def resume(self):
        self._pause = False
        self._held_lines_overflow = False
        self.write_pending_lines()

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
        if self._status_line_req_update:
            colors = self._config.colors
            status_line_style = ansi_format(colors.status_line_bg, colors.status_line_fg)
            self._terminal.reset_current_line(status_line_style)

            self._interact.render_view(self._terminal)
            self._terminal.set_cursor_style(TerminalRawMode.CURSOR_BLINKING_BAR)
            self._terminal.flush()

            self._status_line_req_update = False

    def notify_status_line_changed(self):
        self._status_line_req_update = True


