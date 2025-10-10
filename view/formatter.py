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


def subscript(ch):
    REPLACEMENTS = {
        '0': '\u2080', '1': '\u2081', '2': '\u2082', '3': '\u2083',
        '4': '\u2084', '5': '\u2085', '6': '\u2086', '7': '\u2087',
        '8': '\u2088', '9': '\u2089', '(': '\u208d', ')': '\u208e'
    }
    return REPLACEMENTS.get(ch, ch)


def superscript(ch):
    REPLACEMENTS = {
        '0': '\u2070', '1': '\u00b9', '2': '\u00b2', '3': '\u00b3',
        '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077',
        '8': '\u2078', '9': '\u2079', '(': '\u207d', ')': '\u207e'
    }
    return REPLACEMENTS.get(ch, ch)


def repr_watch_register(r):
    return "'%c" % r


def repr_endpoint_register(r):
    return "&%c" % r

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

    # transformations in context of PRINT_FIELD
    TRANSFORM_UPPERCASE = 0x01
    TRANSFORM_LOWERCASE = 0x02
    TRANSFORM_SUPERSCRIPT = 0x04
    TRANSFORM_SUBSCRIPT = 0x08

    # transformation in context of XXX_STYLE
    TRANSFORM_DISCARD_ANSI = 0x01

    ALIGN_LEFT = 0
    ALIGN_RIGHT = 1

    def __init__(self, type):
        self.type = type
        self.field_name = None
        self.field_transform = 0
        self.field_width = None
        self.field_align = self.ALIGN_RIGHT
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
            token_rest = token[7:]

            KEYWORDS = {
                "endpoint": CompiledTag.USE_ENDPOINT_STYLE,
                "watch": CompiledTag.USE_WATCH_STYLE,
                "default": CompiledTag.USE_DEFAULT_STYLE,
                "reset": CompiledTag.RESET_STYLE
            }

            for keyword, flag in KEYWORDS.items():
                if token_rest.startswith(keyword):
                    self._compiled_format[-1] = CompiledTag(flag)
                    token_rest = token_rest[len(keyword):]

            if token_rest == ",plain":
                self._compiled_format[-1].field_transform = CompiledTag.TRANSFORM_DISCARD_ANSI
        else:
            pos = token.find(':')
            tag = CompiledTag(CompiledTag.PRINT_FIELD)
            if pos == -1:
                tag.field_name = token
            else:
                tag.field_name = token[0:pos]
                while pos < len(token) and token[pos] in ['^', '_', '<', '>', 'A', 'a', '0', ':']:
                    if token[pos] == '^':
                        tag.field_transform |= CompiledTag.TRANSFORM_SUPERSCRIPT
                    elif token[pos] == '_':
                        tag.field_transform |= CompiledTag.TRANSFORM_SUBSCRIPT
                    elif token[pos] == 'A':
                        tag.field_transform |= CompiledTag.TRANSFORM_UPPERCASE
                    elif token[pos] == 'a':
                        tag.field_transform |= CompiledTag.TRANSFORM_LOWERCASE
                    elif token[pos] == '<':
                        tag.field_align = CompiledTag.ALIGN_LEFT
                    elif token[pos] == '>':
                        tag.field_align = CompiledTag.ALIGN_RIGHT
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


class MutableString:
    def __init__(self, content=""):
        self._data = content

    def append(self, content):
        self._data += content

    def get(self):
        return self._data

    def endswith(self, suffix):
        return self._data.endswith(suffix)

    def reset(self, content=""):
        self._data = content

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
        self._watch_styles = {}

    def add_endpoint_style(self, name, style: Style):
        debug("Adding formatting for endpoint %s: background=%s, foreground=%s" % (
            name, style.background_color, style.foreground_color))
        self._endpoint_styles[name] = style

    def add_watch_style(self, register, style: Style):
        debug("Adding formatting for filter %s: background=%s, foreground=%s" % (
            register, style.background_color, style.foreground_color))
        self._watch_styles[register] = style

    def delete_watch_style(self, register):
        if register in self._watch_styles:
            del self._watch_styles[register]

    def get_filters(self):
        # TODO: Remove this function, holding watch information is not the responsibility
        # of formatter.
        return self._watch_styles

    def _get_style(self, endpoint, watch, fd, fallback_style):
        if watch in self._watch_styles:
            return self._watch_styles[watch].get(fd)
        elif endpoint in self._endpoint_styles:
            return self._endpoint_styles[endpoint].get(fd)
        else:
            return fallback_style

    def _transform_char(self, ch, rules: CompiledTag):
        if (rules.field_transform & CompiledTag.TRANSFORM_UPPERCASE) != 0:
            return ch.upper()
        elif (rules.field_transform & CompiledTag.TRANSFORM_LOWERCASE) != 0:
            return ch.lower()

        if (rules.field_transform & CompiledTag.TRANSFORM_SUPERSCRIPT) != 0:
            return superscript(ch)
        elif (rules.field_transform & CompiledTag.TRANSFORM_SUBSCRIPT) != 0:
            return subscript(ch)

        return ch

    def _append_transforming(self,
                             result: MutableString,
                             content: str,
                             remove_formatting: bool,
                             reset_style,
                             rules: CompiledTag):
        ansi_sequence = MutableString()
        data_to_append = MutableString()
        plaintext_length = 0
        inside_ansi_sequence = False

        for ch in content:
            do_reset_formatting = False
            if ch == "\x1b":
                inside_ansi_sequence = True
                if not remove_formatting:
                    data_to_append.append(ch)
                    continue

            if inside_ansi_sequence:
                ansi_sequence.append(ch)

                if ch >= 'A' and ch <= 'z' and ch != '[':
                    inside_ansi_sequence = False
                    if ansi_sequence.endswith(";0m") or ansi_sequence.endswith("[0m"):
                        do_reset_formatting = True
                    ansi_sequence.reset()
                if not remove_formatting:
                    data_to_append.append(ch)
            else:
                data_to_append.append(self._transform_char(ch, rules))
                plaintext_length += 1

            if do_reset_formatting:
                self._put_formatting_tag(data_to_append, reset_style)

        field_width = rules.field_width or 0
        padding_size = max(field_width - plaintext_length, 0)
        padding_char = rules.field_pad or ' '

        if rules.field_align == CompiledTag.ALIGN_RIGHT:
            result.append(padding_char * padding_size)

        result.append(data_to_append.get())

        if rules.field_align == CompiledTag.ALIGN_LEFT:
            result.append(" " * padding_size)

    def _put_formatting_tag(self,
                            result: MutableString,
                            style: tuple):
        result.append("\x1b[")
        result.append("48;5;%d;38;5;%dm" % style)

    def format_line(self, fmt: Format, data):
        result = MutableString("\x1b[0m")
        RESET_STYLE = Style.DEFAULT_BG_COLOR, Style.DEFAULT_FG_COLOR
        active_style = RESET_STYLE
        remove_formatting = False

        for item in fmt.get():
            if isinstance(item, str):
                result.append(item)
                continue

            assert isinstance(item, CompiledTag)

            if item.type == CompiledTag.PRINT_FIELD:
                if item.field_name in data:
                    self._append_transforming(result,
                                              str(data.get(item.field_name, "[?]")),
                                              remove_formatting,
                                              active_style,
                                              item)
            else:
                if item.type == CompiledTag.RESET_STYLE:
                    active_style = RESET_STYLE
                elif item.type == CompiledTag.USE_DEFAULT_STYLE:
                    active_style = self._get_style(data.get('endpoint', None),
                                                   data.get('watch', None),
                                                   data.get('fd', 'default'),
                                                   RESET_STYLE)
                elif item.type == CompiledTag.USE_WATCH_STYLE:
                    active_style = self._get_style(None,
                                                   data.get('watch', None),
                                                   data.get('fd', 'default'),
                                                   RESET_STYLE)
                elif item.type == CompiledTag.USE_ENDPOINT_STYLE:
                    active_style = self._get_style(data.get('endpoint', None),
                                                   None,
                                                   data.get('fd', 'default'),
                                                   RESET_STYLE)
                remove_formatting = (item.field_transform == CompiledTag.TRANSFORM_DISCARD_ANSI)
                self._put_formatting_tag(result, active_style)

        # Clear the line till the end, so that the entire line is filled
        # with the appropriate background color
        result.append("\x1b[K\x1b[0m")

        return result.get()




