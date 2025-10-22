from utils import info, error, lw_assert
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
        self.status_line_bg = resolve_color("x100")
        self.status_line_fg = resolve_color("x554")

        self.pred_help_bg = -1
        self.pred_help_fg = resolve_color("x211")

        self.empty_placeholder_bg = -1
        self.empty_placeholder_fg = resolve_color("x322")

class Configuration:
    DEFAULT_LINE_FORMAT = "{format:endpoint}{endpoint:8} {seq:6} {time} {data}"

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 2207
        self.log_level = 2
        self.socket = None
        self.websocket = None
        self.line_format = None
        self.continued_line_format = None
        self.endpoint_styles = {}
        self.watches = {}
        self.commands = {}
        self.filtered_mode = False
        self.max_held_lines = None
        self.default_endpoint = '0'
        self.colors = ColorsConfiguration()

    def _parse_endpoint_style_node(self, node):
        style = Style()
        for fd, formats in node.items():
            if fd in ["endpoint"]:
                continue

            if not isinstance(formats, dict):
                error("Invalid format of formatting node")
                exit(1)
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

    def read(self, filename, view_name="main"):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            if 'views' not in data:
                error("Configuration file does not have \"views\" section")
                exit(1)
            if view_name not in data['views']:
                error("Configuration file does not have \"views\".\"%s\" section" % view_name)
                exit(1)

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




