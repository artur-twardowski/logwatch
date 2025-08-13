from utils import info, error, lw_assert
from view.formatter import Format, resolve_color
import re
import yaml

class Watch:
    def __init__(self):
        self.regex = None
        self.replacement = None
        self.format = Format()
        self.enabled = True
        self._prepared_regex = None
        self.matches = []

    def set_regex(self, regex):
        self.regex = regex
        self._prepared_regex = re.compile(regex)

    def match(self, line):
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

class Configuration:
    DEFAULT_LINE_FORMAT = "{format:endpoint}{endpoint:8} {seq:6} {time} {data}"
    DEFAULT_MARKER_FORMAT = "{format:endpoint}>>>>>>>> MARKER {time} {name}"

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 2207
        self.log_level = 2
        self.socket = None
        self.websocket = None
        self.line_format = None
        self.marker_format = None
        self.endpoint_formats = {}
        self.watches = {}
        self.marker_format = None
        self.filtered_mode = False
        self.max_held_lines = None

    def _parse_format_node(self, node):
        fmt = Format()
        for fd, formats in node.items():
            if fd in ["endpoint"]:
                continue

            if not isinstance(formats, dict):
                error("Invalid format of formatting node")
                exit(1)
            fmt.background_color[fd] = resolve_color(formats.get('background-color', "none"))
            fmt.foreground_color[fd] = resolve_color(formats.get('foreground-color', "white"))
        return fmt

    def _parse_watch_node(self, node):
        watch = Watch()
        lw_assert("regex" in node, "Missing \"regex\" field in definition of watch")
        lw_assert("register" in node, "Missing \"register\" field in definition of watch")
        lw_assert(len(node["register"]) == 1, "Watch register name must be a single character")

        watch.set_regex(node['regex'])
        watch.name = node.get('name', watch.regex)
        watch.enabled = node.get('enabled', True)
        watch.format.background_color['default'] = resolve_color(node.get('background-color', 'none'))
        watch.format.foreground_color['default'] = resolve_color(node.get('foreground-color', 'white'))
        return node["register"], watch

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

            self.line_format = view_data.get('line-format', self.DEFAULT_LINE_FORMAT) 
            self.marker_format = view_data.get('marker-format', self.DEFAULT_MARKER_FORMAT)
            self.filtered_mode = view_data.get('filtered', False)
            self.max_held_lines = view_data.get('max-held-lines', None)

            for format in view_data.get('formats', []):
                if 'endpoint' in format:
                    self.endpoint_formats[format['endpoint']] = self._parse_format_node(format)
                if 'regex' in format:
                    watch_register, watch_node = self._parse_watch_node(format)
                    self.add_watch(watch_register, watch_node)


