from utils import fatal_error, warning, lw_assert
from view.formatter import Style, resolve_color, Format
import re
import yaml

class Watch:
    def __init__(self):
        self.regex = None
        self.replacement = None
        self.format = Style()
        self.enabled = True
        self._prepared_regex = None
        self.matches = []

    def set_regex(self, regex):
        self.regex = regex

    def compile_regex(self):
        try:
            self._prepared_regex = re.compile(self.regex)
        except Exception:
            self._prepared_regex = None
            raise

    def is_regex_valid(self):
        return self._prepared_regex is not None

    def match(self, line):
        if self._prepared_regex is None:
            return False

        result = self._prepared_regex.search(line)
        if result is not None:
            self.matches.clear()
            hit = self._prepared_regex.findall(line)[0]
            if isinstance(hit, tuple):
                self.matches = list(hit)
            else:
                self.matches = [hit]
            return True
        else:
            return False

class ColorsConfiguration:
    def __init__(self):
        self.status_line_bg = resolve_color("x012")
        self.status_line_fg = resolve_color("x554")

        self.buffer_bar_bg = resolve_color("x023")
        self.buffer_bar_fg = resolve_color("x045")

        self.pred_help_bg = -1
        self.pred_help_fg = resolve_color("x211")

        self.empty_placeholder_bg = -1
        self.empty_placeholder_fg = resolve_color("x322")

        self.awaiting_endpoint_bg = resolve_color("x210")
        self.awaiting_endpoint_fg = resolve_color("x440")

        self.running_endpoint_bg = resolve_color("x031")
        self.running_endpoint_fg = resolve_color("x000")

        self.finished_endpoint_bg = resolve_color("x010")
        self.finished_endpoint_fg = resolve_color("x333")

        self.default_endpoint_bg = resolve_color("x003")
        self.default_endpoint_fg = resolve_color("x540")

        self.show_none_endpoint_bg = resolve_color("x012")
        self.show_none_endpoint_fg = resolve_color("x000")

        self.show_flt_endpoint_bg = resolve_color("x012")
        self.show_flt_endpoint_fg = resolve_color("x530")

        self.show_all_endpoint_bg = resolve_color("x012")
        self.show_all_endpoint_fg = resolve_color("x050")


class Configuration:
    DEFAULT_LINE_FORMAT = "{format:endpoint}{endpoint:8} {seq:6} {time} {data}"

    SHOW_NONE = 0
    SHOW_FILTERED = 1
    SHOW_ALL = 2

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 2207
        self.log_level = 2
        self.socket = None
        self.websocket = None
        self.line_format = None
        self.continued_line_format = None
        self.endpoint_styles = {}
        self.show_endpoints = {}
        self.default_endpoint_show = self.SHOW_ALL
        self.watches = {}
        self.commands = {}
        self.max_held_lines = None
        self.default_endpoint = '0'
        self.colors = ColorsConfiguration()

    def _show_mode_from_string(self, v):
        MAPPING = {
            "none": self.SHOW_NONE,
            "filtered": self.SHOW_FILTERED,
            "all": self.SHOW_ALL
        }
        return MAPPING[v]

    def _parse_endpoint_style_node(self, node):
        style = Style()
        for fd, formats in node.items():
            if fd in ["endpoint"]:
                continue

            if not isinstance(formats, dict):
                fatal_error("Invalid format of formatting node")

            style.background_color[fd] = resolve_color(formats.get('background-color', "none"))
            style.foreground_color[fd] = resolve_color(formats.get('foreground-color', "white"))
        return style

    def _parse_watch_style_node(self, node):
        watch = Watch()
        lw_assert("regex" in node, "Missing \"regex\" field in definition of watch")
        lw_assert("watch" in node, "Missing \"watch\" field in definition of watch")
        lw_assert(len(node["watch"]) == 1, "Watch register name must be a single character")

        watch.set_regex(node['regex'])
        watch.compile_regex()
        watch.enabled = node.get('enabled', True)
        watch.format.background_color['default'] = resolve_color(node.get('background-color', 'none'))
        watch.format.foreground_color['default'] = resolve_color(node.get('foreground-color', 'white'))
        return node["watch"], watch

    def _parse_show_node(self, node):
        if isinstance(node, dict):
            for endpoint_register, view_mode in node.items():
                try:
                    if endpoint_register == "default":
                        self.default_endpoint_show = self._show_mode_from_string(view_mode)
                    else:
                        if isinstance(endpoint_register, int):
                            endpoint_register = str(endpoint_register)
                        if endpoint_register.startswith('&') and len(endpoint_register) == 2:
                            endpoint_register = endpoint_register[1]
                        self.show_endpoints[endpoint_register] = self._show_mode_from_string(view_mode)
                except KeyError:
                    fatal_error("Invalid show mode: %s" % view_mode)
        elif isinstance(node, str):
            try:
                self.default_endpoint_show = self._show_mode_from_string(node)
            except KeyError:
                fatal_error("Invalid show mode: %s" % view_mode)

    def add_watch(self, register, watch):
        self.watches[register] = watch

    def delete_watch(self, register):
        if register in self.watches:
            del self.watches[register]

    def enable_watch(self, filter_name):
        if filter_name in self.watches:
            self.watches[filter_name].enabled = True

    def disable_watch(self, filter_name):
        if filter_name in self.watches:
            self.watches[filter_name].enabled = False

    def set_endpoint_show_mode(self, endpoint, mode):
        self.show_endpoints[endpoint] = mode

    def get_endpoint_show_mode(self, endpoint):
        if endpoint in self.show_endpoints:
            return self.show_endpoints[endpoint]
        else:
            return self.default_endpoint_show

    def read(self, filename, view_name="main"):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            lw_assert('views' in data, "Configuration file does not have \"views\" section")
            lw_assert(view_name in data['views'],
                      "Configuration file does not have configuration for view \"%s\"" % view_name)

            server_data = data.get("server", None)
            view_data = data['views'][view_name]

            self.host = view_data.get('host', '127.0.0.1')
            self.port = view_data.get('server-port', None)
            if self.port is None and server_data is not None:
                self.port = server_data.get("socket-port", None)

            self.socket = view_data.get('socket-port', None)
            self.websocket = view_data.get('websocket-port', None)

            self.line_format = Format(view_data.get('line-format', self.DEFAULT_LINE_FORMAT))
            if "continued-line-format" in view_data:
                self.continued_line_format = Format(view_data['continued-line-format'])
            else:
                self.continued_line_format = self.line_format

            if 'filtered' in view_data:
                warning("\"filtered\" field is deprecated, use \"show\" instead")
                if view_data['filtered']:
                    self.default_endpoint_show = self.SHOW_FILTERED

            if 'show' in view_data:
                self._parse_show_node(view_data['show'])

            self.filtered_mode = view_data.get('filtered', False)
            self.max_held_lines = view_data.get('max-held-lines', None)
            self.default_endpoint = view_data.get('default-endpoint', self.default_endpoint)

            for style in view_data.get('styles', []):
                if 'endpoint' in style:
                    self.endpoint_styles[style['endpoint']] = self._parse_endpoint_style_node(style)
                if 'watch' in style:
                    watch_register, watch_node = self._parse_watch_style_node(style)
                    self.add_watch(watch_register, watch_node)

            for command in view_data.get('commands', []):
                lw_assert("register" in command, "Missing \"register\" field in definition of command")
                lw_assert("command" in command, "Missing \"command\" field in definition of command")
                self.commands[command['register']] = command['command']

