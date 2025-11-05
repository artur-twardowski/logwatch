from utils import TerminalRawMode
from utils import text_window, create_progress_bar
from view.formatter import ansi_format, ansi_format1
from view.configuration import Configuration


SYM_PREDICATE_MODE_PROMPT = "\u21e8"


class PredicateModeView:
    def __init__(self, interactive_mode, pred_input_ctx, config, formatter, console_output):
        self._interact = interactive_mode
        self._pred_input_ctx = pred_input_ctx
        self._config = config
        self._formatter = formatter
        self._console_output = console_output
        self._endpoints = {}
        self._other_actions = {}

    def notify_active_actions(self, endpoints, other_actions):
        self._endpoints = endpoints
        self._other_actions = other_actions

    def _write_register(self, terminal, width, prefix, reg, prefix_format=None, reg_format=None):
        if width >= 2:
            if prefix_format is not None:
                terminal.set_format(prefix_format)
            terminal.write(prefix)

            if reg_format is not None:
                terminal.set_format(reg_format)
            terminal.write(reg)
            if width == 3:
                terminal.write(" ")  # Extra space for readability
        else:
            if reg_format is not None:
                terminal.set_format(reg_format)
            terminal.write(reg)

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

    def render_content(self, available_cols, terminal: TerminalRawMode):
        colors = self._config.colors

        status_line_style = ansi_format(colors.status_line_bg, colors.status_line_fg)
        buffer_bar_style = ansi_format(colors.buffer_bar_bg, colors.buffer_bar_fg)
        FILTERING_FORMATS = {
            Configuration.SHOW_NONE: ansi_format(colors.show_none_endpoint_bg, colors.show_none_endpoint_fg),
            Configuration.SHOW_FILTERED: ansi_format(colors.show_flt_endpoint_bg, colors.show_flt_endpoint_fg),
            Configuration.SHOW_ALL: ansi_format(colors.show_all_endpoint_bg, colors.show_all_endpoint_fg)
        }

        tokens = self._pred_input_ctx.get_current_input()
        terminal.write(SYM_PREDICATE_MODE_PROMPT + text_window(tokens, 8))
        cursor_column = min(9, len(tokens) + 1)

        reg_width = 3

        terminal.write(" | ")
        paused, held_lines, max_held_lines, overflow = self._console_output.get_pause_data()
        if paused:
            terminal.set_format(buffer_bar_style)
            terminal.write(create_progress_bar(held_lines, max_held_lines, 4))
        else:
            terminal.write(">>> ")
        terminal.set_format(status_line_style)

        if reg_width == 1:
            terminal.write("&")

        default_endpoint = self._interact.get_default_endpoint()

        for register, (name, state) in self._endpoints.items():
            self._write_register(terminal, reg_width, "&", register,
                                 prefix_format=FILTERING_FORMATS[self._config.get_endpoint_show_mode(register)],
                                 reg_format=self._get_endpoint_style(state, default_endpoint == register))

        terminal.set_format(status_line_style)
        
        n_other_actions = len(self._other_actions)
        if n_other_actions > 0:
            self._write_register(reg_width, "&", "-")
            if n_other_actions > 1:
                terminal.write("(%d)" % n_other_actions)
        terminal.write(' | ')

        if reg_width == 1:
            terminal.write("'")

        for register, filter_data in self._formatter.get_filters().items():
            if self._config.watches[register].enabled:
                terminal.set_format(ansi_format1(filter_data.get()))
            else:
                terminal.set_format(status_line_style)

            self._write_register(terminal, reg_width, "'", register)

        terminal.set_format(status_line_style)
        terminal.set_cursor_position(cursor_column)

    def on_key(self, key):
        self._pred_input_ctx.push(key)



