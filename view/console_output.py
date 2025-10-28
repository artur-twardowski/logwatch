from view.configuration import Configuration
from view.formatter import Formatter, ansi_format, ansi_format1
from view.formatter import repr_watch_register, repr_endpoint_register
from view.interactive_mode import InteractiveModeContext
from collections import deque
from utils import info, warning
from utils import TerminalRawMode
from utils import create_progress_bar, text_window
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
        self._endpoints = {}
        self._other_actions = {}

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
        self._endpoints = endpoints
        self._other_actions = other_actions
        self.notify_status_line_changed()

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
            self._print_line(data)

    def feed(self, amount):
        for _ in range(0, amount):
            if len(self._held_lines) == 0:
                break
            data = self._held_lines.popleft()
            self._print_line(data)

    def _get_endpoint_style(self, state, is_default):
        colors = self._config.colors
        STYLES = [
            (colors.awaiting_endpoint_bg, colors.awaiting_endpoint_fg),
            (colors.running_endpoint_bg, colors.running_endpoint_fg),
            (colors.finished_endpoint_bg, colors.finished_endpoint_fg)
        ]
        result = STYLES[state]
        if is_default:
            result = (colors.default_endpoint_bg, colors.default_endpoint_fg)
        return ansi_format1(result)

    def _write_register(self, width, prefix, reg, prefix_format=None, reg_format=None):
        if width >= 2:
            if prefix_format is not None:
                self._terminal.set_format(prefix_format)
            self._terminal.write(prefix)

            if reg_format is not None:
                self._terminal.set_format(reg_format)
            self._terminal.write(reg)
            if width == 3:
                self._terminal.write(" ")  # Extra space for readability
        else:
            if reg_format is not None:
                self._terminal.set_format(reg_format)
            self._terminal.write(reg)

    def render_status_line(self):
        colors = self._config.colors

        status_line_style = ansi_format(colors.status_line_bg, colors.status_line_fg)
        buffer_bar_style = ansi_format(colors.buffer_bar_bg, colors.buffer_bar_fg)
        FILTERING_FORMATS = {
            Configuration.SHOW_NONE: ansi_format(colors.show_none_endpoint_bg, colors.show_none_endpoint_fg),
            Configuration.SHOW_FILTERED: ansi_format(colors.show_flt_endpoint_bg, colors.show_flt_endpoint_fg),
            Configuration.SHOW_ALL: ansi_format(colors.show_all_endpoint_bg, colors.show_all_endpoint_fg)
        }


        if self._status_line_req_update:
            self._terminal.reset_current_line(status_line_style)

            if self._interact.is_predicate_mode():
                tokens = self._interact.get_user_input_string()
                self._terminal.write(text_window(tokens, 9))
                cursor_column = min(9, len(tokens) + 1)

                reg_width = 3

                self._terminal.write(" | ")
                if self._pause:
                    self._terminal.set_format(buffer_bar_style)
                    self._terminal.write(create_progress_bar(len(self._held_lines), self._max_held_lines, 4))
                else:
                    self._terminal.write(">>> ")
                self._terminal.set_format(status_line_style)
                if self._config.filtered_mode:
                    self._terminal.write("F ")

                if reg_width == 1:
                    self._terminal.write("&")

                default_endpoint = self._interact.get_default_endpoint()

                for register, (name, state) in self._endpoints.items():
                    self._write_register(reg_width, "&", register,
                                         prefix_format=FILTERING_FORMATS[self._config.get_endpoint_show_mode(register)],
                                         reg_format=self._get_endpoint_style(state, default_endpoint == register))

                self._terminal.set_format(status_line_style)
                
                n_other_actions = len(self._other_actions)
                if n_other_actions > 0:
                    self._write_register(reg_width, "&", "-")
                    if n_other_actions > 1:
                        self._terminal.write("(%d)" % n_other_actions)
                self._terminal.write(' | ')

                if reg_width == 1:
                    self._terminal.write("'")

                for register, filter_data in self._formatter.get_filters().items():
                    if self._config.watches[register].enabled:
                        self._terminal.set_format(ansi_format1(filter_data.get()))
                    else:
                        self._terminal.set_format(status_line_style)

                    self._write_register(reg_width, "'", register)

                self._terminal.set_format(status_line_style)
                self._terminal.set_cursor_position(cursor_column)

            else:
                self._terminal.write(self._interact.get_user_input_string())
            self._terminal.set_cursor_style(TerminalRawMode.CURSOR_BLINKING_BAR)
            self._terminal.flush()

            self._status_line_req_update = False


    def notify_status_line_changed(self):
        self._status_line_req_update = True


