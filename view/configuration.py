from utils import fatal_error, warning, lw_assert
from view.formatter import Style, resolve_color, Format, ansi_format, ansi_format1
import re
import yaml

re_fmt_tag_general = re.compile(r'({.*})')
re_fmt_tag_format = re.compile(r'({format:([A-Za-z0-9]+)(:([A-Za-z0-9]+))?})')

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
        try:
            self._prepared_regex = re.compile(self.regex)
        except Exception:
            self._prepared_regex = None
            raise

    def set_replacement(self, replacement):
        self.replacement = replacement

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

def _compare_equals(op1, op2):
    return op1 == op2


class FormatterClass:
    def __init__(self, parent):
        self._parent = parent
        self._default_format = Style()
        self._conditions = []

    def set_default_format(self, bg, fg):
        self._default_format.set("default", bg, fg)

    def set_conditional_format(self, formal_op1, operator, formal_op2, bg, fg):
        COMPARING_FUNCTIONS={
            "equals": _compare_equals
        }
        style = Style()
        style.set("default", bg, fg)
        lw_assert(operator in COMPARING_FUNCTIONS,
                  "No such comparison function: %s" % operator)
        self._conditions.append((formal_op1, formal_op2, COMPARING_FUNCTIONS.get(operator), style))
        self._parent.register_operands(formal_op1, formal_op2)

    def fill_in_default_colors(self):
        for _, _, _, style in self._conditions:
            for k, v in style.background_color.items():
                if style.background_color[k] == -1:
                    style.background_color[k] = self._default_format.background_color[k]
            for k, v in style.foreground_color.items():
                if style.foreground_color[k] == -1:
                    style.foreground_color[k] = self._default_format.foreground_color[k]

    def get_format(self, fetch_actual_op1: callable, fetch_actual_op2: callable):
        for formal_op1, formal_op2, func, style in self._conditions:
            if func(fetch_actual_op1(formal_op1), fetch_actual_op2(formal_op2)):
                return style
        return self._default_format

class Formatter:
    def __init__(self):
        self.regex = None
        self._prepared_regex = None
        self.replacement = None
        self.classes = {}
        self.operands = set()

    def set_regex(self, regex):
        self.regex = regex
        try:
            self._prepared_regex = re.compile(self.regex)
        except Exception:
            self._prepared_regex = None
            raise

    def set_replacement(self, replacement):
        self.replacement = replacement

    def add_class(self, class_name):
        self.classes[class_name] = FormatterClass(self)
        return self.classes[class_name]

    def register_operands(self, op1, op2):
        for operand in [op1, op2]:
            self.operands.add((operand, True if re_fmt_tag_general.match(operand) else False))

    def _substitute(self, match: re.Match, in_str):
        result = in_str
        for ix, s in enumerate(match.groups()):
            result = result.replace("{%d}" % (ix + 1), s)
        for key, s in match.groupdict().items():
            result = result.replace("{%s}" % key, s)
        return result

    def _dereference(self, operands, in_str):
        result = {}
        for operand, requires_dereference in operands:
            if requires_dereference:
                result[operand] = operand

        for match in self._prepared_regex.finditer(in_str):
            for operand in result.keys():
                result[operand] = self._substitute(match, result[operand])

        for operand, requires_dereference in operands:
            if not requires_dereference:
                result[operand] = operand
        return result

    def generate_replacement(self, input_line):
        if not self._prepared_regex.match(input_line):
            return input_line
        result = self.replacement
        dbg_result = ""
        for match in self._prepared_regex.finditer(input_line):
            dbg_result += str(match.groups()) + ", " + str(match.groupdict()) + " | "
            result = self._substitute(match, result)

        dereferenced_operands = self._dereference(self.operands, input_line)
        classes = {}
        for class_name, class_def in self.classes.items():
            fmt = class_def.get_format(
                fetch_actual_op1=lambda k: dereferenced_operands[k],
                fetch_actual_op2=lambda k: dereferenced_operands[k])
            classes[class_name] = (fmt.background_color["default"],
                                   fmt.foreground_color["default"])

        for match in re_fmt_tag_format.finditer(result):
            lw_assert(len(match.groups()) == 4, "Invalid number of matches")
            entire_tag, param1, _, param2 = match.groups()

            fmt = None
            if param1 == "class":
                fmt = "\x1b[" + ansi_format1(classes[param2]) + "m"
            elif param1 == "reset":
                fmt = "\x1b[0m"

            if fmt is not None:
                result = result.replace(entire_tag, fmt)

        return result


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
        self.formatters = []
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

    def _parse_watch_node(self, node, register_field: str):
        watch = Watch()
        lw_assert("regex" in node, "Missing \"regex\" field in definition of watch")
        lw_assert(register_field in node, "Missing \"%s\" field in definition of watch" % register_field)
        lw_assert(len(node[register_field]) == 1, "Watch register name must be a single character")

        watch.set_regex(node['regex'])
        watch.set_replacement(node.get('replacement'))
        watch.enabled = node.get('enabled', True)
        watch.format.set("default",
                         resolve_color(node.get('background-color', 'none')),
                         resolve_color(node.get('foreground-color', 'white')))
        return node[register_field], watch

    def _parse_formatter_node(self, node):
        formatter = Formatter()
        lw_assert("regex" in node, "Missing \"regex\" field in definition of formatter")
        formatter.set_regex(node.get("regex"))
        formatter.set_replacement(node.get("replacement"))
        for class_name, definitions in node.get("classes", {}).items():
            cls = formatter.add_class(class_name)
            for definition in definitions:
                if "if" in definition:
                    condition = definition["if"]
                    lw_assert(
                        isinstance(condition, list) and len(condition) == 3,
                        "Definition of formatting condition must be a list consisting of 3 elements")
                    cls.set_conditional_format(
                        condition[0], condition[1], condition[2],
                        resolve_color(definition.get('background-color', 'none')),
                        resolve_color(definition.get('foreground-color', 'none')))
                else:
                    cls.set_default_format(
                        resolve_color(definition.get('background-color', 'none')),
                        resolve_color(definition.get('foreground-color', 'none')))
        return formatter

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

    def set_endpoint_show_mode(self, endpoints, mode):
        for endpoint in endpoints:
            self.show_endpoints[endpoint] = mode

    def get_endpoint_show_mode(self, endpoint):
        if endpoint in self.show_endpoints:
            return self.show_endpoints[endpoint]
        else:
            return self.default_endpoint_show

    def set_command_register(self, register, value):
        self.commands[register] = value

    def get_command_register(self, register):
        if register in self.commands:
            return self.commands[register]
        else:
            return ""

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
                    # Obsolete format; use watches node instead
                    watch_register, watch_node = self._parse_watch_node(style, "watch")
                    self.add_watch(watch_register, watch_node)

            for watch in view_data.get('watches', []):
                watch_register, watch_node = self._parse_watch_node(watch, "register")
                self.add_watch(watch_register, watch_node)

            for formatter in view_data.get('formatters', []):
                self.formatters.append(self._parse_formatter_node(formatter))

            for command in view_data.get('commands', []):
                lw_assert("register" in command, "Missing \"register\" field in definition of command")
                lw_assert("command" in command, "Missing \"command\" field in definition of command")
                self.commands[command['register']] = command['command']

