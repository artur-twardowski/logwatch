import re

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

    "white": 255,
    "none": -1
}

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
        except:
            return -1

class Format:
    def __init__(self):
        self.background_color = 0
        self.foreground_color = 255

class Formatter:
    def __init__(self):
        self._re_tag = re.compile(r'(\{([A-Za-z0-9_-]+)(?::([^}]+))?\})')
        self._endpoint_formats = {}
        pass

    def add_endpoint_format(self, name, format: Format):
        print("Adding formatting for endpoint %s: background=%d, foreground=%d" % (
            name, format.background_color, format.foreground_color))
        self._endpoint_formats[name] = format

    def format_line(self, fmt, fields):
        tags = self._re_tag.findall(fmt)
        result = fmt
        for needle, key, param in tags:
            replacement = needle
            if key == 'format':
                if param == "reset":
                    replacement = "\x1b[0m"
                elif param == "endpoint":
                    endpoint_fmt = self._endpoint_formats[fields['endpoint']]
                    if endpoint_fmt is None:
                        print("No configuration for endpoint %s" % fields['endpoint'])
                    if endpoint_fmt.background_color == -1:
                        replacement = "\x1b[0;38;5;%dm" % endpoint_fmt.foreground_color
                    else:
                        replacement = "\x1b[48;5;%d;38;5;%dm" % (
                                        endpoint_fmt.background_color,
                                        endpoint_fmt.foreground_color)
            elif key in fields:
                try:
                    if len(param) > 0:
                        if param[0] >= '1' and param[0] <= '9':
                            replacement = "%*s" % (int(param), fields[key])
                        elif param[0] == '<' and param[2] >= '1' and param[2] <= '9':
                            replacement = pad_right(str(fields[key]),
                                                   param[1],
                                                   int(param[2:]))
                        elif param[0] == '>' and param[2] >= '1' and param[2] <= '9':
                            replacement = pad_left(str(fields[key]),
                                                    param[1],
                                                    int(param[2:]))
                    else:
                        replacement = str(fields[key])
                except IndexError:
                    print("Incorrect formatting parameter: %s" % param)
                    exit(1)

            result = result.replace(needle, replacement)
        return result

if __name__ == "__main__":
    formatter = Formatter()

    shell_fmt = Format()
    shell_fmt.foreground_color = 2
    shell_fmt.background_color = 23
    formatter.add_endpoint_format("Shell", shell_fmt)

    print(formatter.format_line("{format:endpoint}[{endpoint}] {seq:>.6} {date} {time} |{format:reset} {content}", {
        "endpoint": "Shell",
        "date": "2023-02-09",
        "time": "22:07:00",
        "seq": 111,
        "content": "My content \x1b[1;31mwith colors\x1b[0m"
        }))

    for color, k in COLOR_MAP.items():
        print("\x1b[38;5;%dm%s\x1b[0m" % (k, color))

