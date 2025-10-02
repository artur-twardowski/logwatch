import re
from utils import debug, error

COLOR_MAP = {
    "red1": 16 + 1*36 + 0*6 + 0,
    "red2": 16 + 2*36 + 0*6 + 0,
    "red3": 16 + 3*36 + 0*6 + 0,
    "red4": 16 + 4*36 + 0*6 + 0,
    "red5": 16 + 5*36 + 0*6 + 0,
    "red6": 16 + 5*36 + 1*6 + 1,
    "red7": 16 + 5*36 + 2*6 + 2,
    "red8": 16 + 5*36 + 3*6 + 3,
    "red9": 16 + 5*36 + 4*6 + 4,

    "yellow1": 16 + 1*36 + 1*6 + 0,
    "yellow2": 16 + 2*36 + 2*6 + 0,
    "yellow3": 16 + 3*36 + 3*6 + 0,
    "yellow4": 16 + 4*36 + 4*6 + 0,
    "yellow5": 16 + 5*36 + 5*6 + 0,
    "yellow6": 16 + 5*36 + 5*6 + 1,
    "yellow7": 16 + 5*36 + 5*6 + 2,
    "yellow8": 16 + 5*36 + 5*6 + 3,
    "yellow9": 16 + 5*36 + 5*6 + 4,

    "green1": 16 + 0*36 + 1*6 + 0,
    "green2": 16 + 0*36 + 2*6 + 0,
    "green3": 16 + 0*36 + 3*6 + 0,
    "green4": 16 + 0*36 + 4*6 + 0,
    "green5": 16 + 0*36 + 5*6 + 0,
    "green6": 16 + 1*36 + 5*6 + 1,
    "green7": 16 + 2*36 + 5*6 + 2,
    "green8": 16 + 3*36 + 5*6 + 3,
    "green9": 16 + 4*36 + 5*6 + 4,

    "cyan1": 16 + 0*36 + 1*6 + 1,
    "cyan2": 16 + 0*36 + 2*6 + 2,
    "cyan3": 16 + 0*36 + 3*6 + 3,
    "cyan4": 16 + 0*36 + 4*6 + 4,
    "cyan5": 16 + 0*36 + 5*6 + 5,
    "cyan6": 16 + 1*36 + 5*6 + 5,
    "cyan7": 16 + 2*36 + 5*6 + 5,
    "cyan8": 16 + 3*36 + 5*6 + 5,
    "cyan9": 16 + 4*36 + 5*6 + 5,

    "blue1": 16 + 0*36 + 0*6 + 1,
    "blue2": 16 + 0*36 + 0*6 + 2,
    "blue3": 16 + 0*36 + 0*6 + 3,
    "blue4": 16 + 0*36 + 0*6 + 4,
    "blue5": 16 + 0*36 + 0*6 + 5,
    "blue6": 16 + 1*36 + 1*6 + 5,
    "blue7": 16 + 2*36 + 2*6 + 5,
    "blue8": 16 + 3*36 + 3*6 + 5,
    "blue9": 16 + 4*36 + 4*6 + 5,

    "magenta1": 16 + 1*36 + 0*6 + 1,
    "magenta2": 16 + 2*36 + 0*6 + 2,
    "magenta3": 16 + 3*36 + 0*6 + 3,
    "magenta4": 16 + 4*36 + 0*6 + 4,
    "magenta5": 16 + 5*36 + 0*6 + 5,
    "magenta6": 16 + 5*36 + 1*6 + 5,
    "magenta7": 16 + 5*36 + 2*6 + 5,
    "magenta8": 16 + 5*36 + 3*6 + 5,
    "magenta9": 16 + 5*36 + 4*6 + 5,

    "white": 231,
    "black": 16,
    "grey0": 16,
    "grey1": 232,
    "grey2": 233,
    "grey3": 234,
    "grey4": 235,
    "grey5": 236,
    "grey6": 237,
    "grey7": 238,
    "grey8": 239,
    "grey9": 240,
    "grey10": 241,
    "grey11": 242,
    "grey12": 243,
    "grey13": 244,
    "grey14": 245,
    "grey15": 246,
    "grey16": 247,
    "grey17": 248,
    "grey18": 249,
    "grey19": 250,
    "grey20": 251,
    "grey21": 252,
    "grey22": 253,
    "grey23": 254,
    "grey24": 255,
    "none": -1
}

def get_default_register_format(register):
    DEFAULT_FORMATS = {
        '0': (COLOR_MAP['blue3'], COLOR_MAP['blue9']),
        '1': (COLOR_MAP['green1'], COLOR_MAP['green6']),
        '2': (COLOR_MAP['cyan1'], COLOR_MAP['cyan6']),
        '3': (COLOR_MAP['red1'], COLOR_MAP['red6']),
        '4': (COLOR_MAP['magenta1'], COLOR_MAP['magenta6']),
        '5': (COLOR_MAP['yellow1'], COLOR_MAP['yellow6']),
        '6': (COLOR_MAP['grey4'], COLOR_MAP['grey23']),
    }

    if register in DEFAULT_FORMATS:
        return DEFAULT_FORMATS[register]
    else:
        return DEFAULT_FORMATS['1']

def pad_left(string, char, size):
    while len(string) < size:
        string = str(char) + string
    return string


def pad_right(string, char, size):
    while len(string) < size:
        string = string + str(char)
    return string


def resolve_color(name: str):
    if name in COLOR_MAP:
        return COLOR_MAP[name]
    else:
        try:
            return int(name)
        except Exception:
            return -1


class Style:
    DEFAULT_BG_COLOR = resolve_color("none")
    DEFAULT_FG_COLOR = resolve_color("white")

    def __init__(self):
        self.background_color = {
            "default": self.DEFAULT_BG_COLOR,
            "stderr": resolve_color("red1"),
            "stdin": resolve_color("yellow1")
        }
        self.foreground_color = {
            "default": self.DEFAULT_FG_COLOR,
            "stderr": self.DEFAULT_FG_COLOR,
            "stdin": resolve_color("yellow7")
        }

    def get(self, fd="default"):
        if fd not in self.background_color:
            fd = "default"
        bg_color = self.background_color.get(fd, self.DEFAULT_BG_COLOR)
        fg_color = self.foreground_color.get(fd, self.DEFAULT_FG_COLOR)
        return bg_color, fg_color


def ansi_format(bg_color, fg_color):
    if bg_color == -1:
        return "0;38;5;%d" % fg_color
    else:
        return "48;5;%d;38;5;%d" % (bg_color, fg_color)


def ansi_format1(colors):
    assert isinstance(colors, (list, tuple))
    assert len(colors) == 2
    return ansi_format(colors[0], colors[1])


def subscript(s):
    REPLACEMENTS = {
        '0': '\u2080', '1': '\u2081', '2': '\u2082', '3': '\u2083',
        '4': '\u2084', '5': '\u2085', '6': '\u2086', '7': '\u2087',
        '8': '\u2088', '9': '\u2089', '(': '\u208d', ')': '\u208e'
    }
    result = s

    for char, replacement in REPLACEMENTS.items():
        result = result.replace(char, replacement)
    return result


def superscript(s):
    REPLACEMENTS = {
        '0': '\u2070', '1': '\u00b9', '2': '\u00b2', '3': '\u00b3',
        '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077',
        '8': '\u2078', '9': '\u2079', '(': '\u207d', ')': '\u207e'
    }
    result = s

    for char, replacement in REPLACEMENTS.items():
        result = result.replace(char, replacement)
    return result


def render_watch_register(r):
    return "\u257a%c\u2578" % r

class TokenizationContext:
    def __init__(self, compiled_result):
        self._token = ""
        self._compiled_result = compiled_result

    def start_next(self, ch=''):
        if self._token != "":
            self._compiled_result.append(self._token)
        self._token = ch

    def append(self, ch):
        self._token += ch


class CompiledTag:
    RESET_STYLE = 0
    USE_ENDPOINT_STYLE = 1
    USE_WATCH_STYLE = 2
    USE_DEFAULT_STYLE = 3
    PRINT_FIELD = 4

    TRANSFORM_UPPERCASE = 0x01
    TRANSFORM_LOWERCASE = 0x02
    TRANSFORM_UPPER_INDEX = 0x04
    TRANSFORM_LOWER_INDEX = 0x08

    ALIGN_LEFT = 0
    ALIGN_RIGHT = 1

    def __init__(self, type):
        self.type = type
        self.field_name = None
        self.field_transform = 0
        self.field_width = None
        self.field_align = None
        self.field_pad = None

class Format:
    READING_LITERAL = 0
    READING_TAG = 1

    def __init__(self, format=None):
        self._compiled_format = []
        self._ctx = TokenizationContext(self._compiled_format)
        if format is not None:
            self.compile(format)

    def get(self):
        return self._compiled_format

    def _compile_last_token(self):
        token = "%s" % self._compiled_format[-1]
        if token.startswith('format:'):
            if token == "format:endpoint":
                self._compiled_format[-1] = CompiledTag(CompiledTag.USE_ENDPOINT_STYLE)
            if token == "format:watch":
                self._compiled_format[-1] = CompiledTag(CompiledTag.USE_WATCH_STYLE)
            if token == "format:default":
                self._compiled_format[-1] = CompiledTag(CompiledTag.USE_DEFAULT_STYLE)
            if token == "format:reset":
                self._compiled_format[-1] = CompiledTag(CompiledTag.RESET_STYLE)
        else:
            pos = token.find(':')
            tag = CompiledTag(CompiledTag.PRINT_FIELD)
            if pos == -1:
                tag.field_name = token
            else:
                tag.field_name = token[0:pos]
                while pos < len(token) and token[pos] in ['^', '_', '<', '>', 'A', 'a', '0', ':']:
                    if token[pos] == '^':
                        tag.field_transform |= CompiledTag.TRANSFORM_UPPER_INDEX
                    elif token[pos] == '_':
                        tag.field_transform |= CompiledTag.TRANSFORM_LOWER_INDEX
                    elif token[pos] == 'A':
                        tag.field_transform |= CompiledTag.TRANSFORM_UPPERCASE
                    elif token[pos] == 'a':
                        tag.field_transform |= CompiledTag.TRANSFORM_LOWERCASE
                    elif token[pos] == '<':
                        tag.field_alignment = CompiledTag.ALIGN_LEFT
                    elif token[pos] == '>':
                        tag.field_alignment = CompiledTag.ALIGN_RIGHT
                    elif token[pos] == '0':
                        tag.field_pad = '0'
                    pos += 1
                if pos < len(token):
                    tag.field_width = int(token[pos:])
            self._compiled_format[-1] = tag

    def compile(self, format: str):
        self._compiled_format.clear()
        state = self.READING_LITERAL

        char_index = 0
        while char_index < len(format):
            ch = format[char_index]
            if ch == '{':
                if state == self.READING_LITERAL:
                    state = self.READING_TAG
                    self._ctx.start_next()
                else:
                    # TODO: emit an error
                    continue
            elif ch == '}':
                if state == self.READING_TAG:
                    state = self.READING_LITERAL
                    self._ctx.start_next()
                    self._compile_last_token()
                else:
                    self._ctx.append(ch)
            else:
                self._ctx.append(ch)

            char_index += 1
        self._ctx.start_next('')
        print(self._compiled_format)

class Formatter:
    FORMATTING_TAG_DELIM = "\x10"
    FORMATTING_RESET = "R"
    FORMATTING_ENDPOINT = "E"
    FORMATTING_WATCH = "W"
    FORMATTING_DEFAULT = "D"
    TAG_REGEX = r'(\{([A-Za-z0-9_-]+)(?::([^}]+))?\})'

    def __init__(self):
        self._re_tag = re.compile(self.TAG_REGEX)
        self._endpoint_styles = {}
        self._filter_styles = {}
        pass

    def add_endpoint_style(self, name, style: Style):
        debug("Adding formatting for endpoint %s: background=%s, foreground=%s" % (
            name, style.background_color, style.foreground_color))
        self._endpoint_styles[name] = style

    def add_watch_format(self, register, style: Style):
        debug("Adding formatting for filter %s: background=%s, foreground=%s" % (
            register, style.background_color, style.foreground_color))
        self._watch_styles[register] = style

    def delete_watch_format(self, register):
        if register in self._watch_styles:
            del self._watch_styles[register]

    def get_filters(self):
        # TODO: Remove this function, holding watch information is not the responsibility
        # of formatter.
        return self._watch_styles

    def format_line(self, fmt, fields):
        tags = self._re_tag.findall(fmt)
        result = fmt

        # Replace tags with the values or delimiters
        for needle, key, param in tags:
            replacement = needle

            if key == 'format':
                if param == "reset":
                    replacement = self.FORMATTING_TAG_DELIM + self.FORMATTING_RESET + "\x1b[0m"

                elif param == "endpoint":
                    replacement = self.FORMATTING_TAG_DELIM + self.FORMATTING_ENDPOINT + "\x1b[0m"

                elif param == "watch":
                    replacement = self.FORMATTING_TAG_DELIM + self.FORMATTING_WATCH + "\x1b[0m"

                elif param =="default":
                    replacement = self.FORMATTING_TAG_DELIM + self.FORMATTING_DEFAULT + "\x1b[0m"

            elif key in fields:
                try:
                    view_value = str(fields[key])
                    if len(param) > 0:
                        if param[0] == '^':
                            view_value = superscript(view_value)
                            param = param[1:]
                        elif param[0] == "_":
                            view_value = subscript(view_value)
                            param = param[1:]

                        if param[0] >= '1' and param[0] <= '9':
                            replacement = "%*s" % (int(param), view_value)
                        elif param[0] == '<' and param[2] >= '1' and param[2] <= '9':
                            replacement = pad_right(str(view_value),
                                                    param[1],
                                                    int(param[2:]))
                        elif param[0] == '>' and param[2] >= '1' and param[2] <= '9':
                            replacement = pad_left(str(view_value),
                                                   param[1],
                                                   int(param[2:]))
                    else:
                        replacement = view_value
                except IndexError:
                    error("Incorrect formatting parameter: %s" % param)
                    exit(1)

            result = result.replace(needle, replacement)

        # Process the ANSI codes:
        #   - replace all the formatting reset messages (ESC[0m) with appropriate formatting
        #     as configured
        reset_fmt = Style.DEFAULT_BG_COLOR, Style.DEFAULT_FG_COLOR

        if 'watch' in fields and fields['watch'] in self._filter_styles:
            watch_fmt = self._watch_styles[fields['watch']].get(fields['fd'])
            default_fmt = watch_fmt
        else:
            watch_fmt = reset_fmt
            default_fmt = None

        if fields['endpoint'] in self._endpoint_styles:
            endpoint_fmt = self._endpoint_styles[fields['endpoint']].get(fields['fd'])
            if default_fmt is None:
                default_fmt = endpoint_fmt
        else:
            endpoint_fmt = reset_fmt
            default_fmt = reset_fmt


        use_format = reset_fmt

        data_to_format = result
        result = ""
        ch_ix = 0
        while ch_ix < len(data_to_format):
            if data_to_format[ch_ix] == self.FORMATTING_TAG_DELIM:
                if data_to_format[ch_ix + 1] == self.FORMATTING_RESET:
                    use_format = reset_fmt
                elif data_to_format[ch_ix + 1] == self.FORMATTING_ENDPOINT:
                    use_format = endpoint_fmt
                elif data_to_format[ch_ix + 1] == self.FORMATTING_WATCH:
                    use_format = watch_fmt
                elif data_to_format[ch_ix + 1] == self.FORMATTING_DEFAULT:
                    use_format = default_fmt
                ch_ix += 2
                continue

            elif data_to_format[ch_ix] == '\x1b':
                if data_to_format[ch_ix + 1] == "[":  # Formatting tag
                    tag_end = data_to_format.find('m', ch_ix + 2)
                    values = data_to_format[ch_ix + 2:tag_end].split(';')
                    new_values = []
                    for v in values:
                        if v == "0":
                            new_values.append("0;" + ansi_format(use_format[0], use_format[1]))
                        else:
                            new_values.append(v)

                    result += "\x1b[" + (";".join(new_values)) + "m"

                    ch_ix = tag_end + 1
                    continue

            result += data_to_format[ch_ix]
            ch_ix += 1

        # Clear the line till the end, so that the entire line is filled
        # with the appropriate background color
        result += "\x1b[K\x1b[0m"

        return result

    def format_line_new(self, fmt: Format, data):
        pass

