from sys import stdin, stdout
import tty
import termios

VERSION = "0.2"
log_level = 2


def set_log_level(level):
    global log_level
    log_level = level


def inc_log_level(amount: int):
    global log_level
    log_level += amount


def debug(message):
    global log_level
    if log_level >= 4:
        print("\x1b[35mDEBUG: %s\x1b[0m" % message)
    pass


def info(message):
    global log_level
    if log_level >= 3:
        print("\x1b[1;37m%s\x1b[0m" % message)


def warning(message):
    global log_level
    if log_level >= 2:
        print("\x1b[1;33mWARNING: %s\x1b[0m" % message)


def error(message):
    global log_level
    if log_level >= 1:
        print("\x1b[1;31mERROR: %s\x1b[0m" % message)


def fatal_error(message):
    error(message)
    exit(1)


def lw_assert(condition, message_on_error):
    if not condition:
        error(message_on_error)
        exit(1)


def pop_args(arg_queue, argument, *names):
    if arg_queue.qsize() < len(names):
        if len(names) == 1:
            print("Option %s requires %s argument" % (argument, names[0]))
        else:
            print("Option %s requires %d arguments: %s" % (argument, len(names), ", ".join(names)))
        exit(1)

    retval = []
    for _ in names:
        retval.append(arg_queue.get())
    return retval


def parse_yes_no_option(arg_name: str, arg_value: str):
    if arg_value.lower() == "no":
        return False
    elif arg_value.lower() == "yes":
        return True
    else:
        error("Incorrect argument for %s (\"%s\"); valid values are \"yes\" or \"no\" (case-insensitive)" % (arg_name, arg_value))
        exit(1)


def special_key(data):
    return "\x01%s\x02" % data


def create_progress_bar(position, maximum, width):
    BLK_CHARS = ['\u258f', '\u258e', '\u258d', '\u258c', 
                 '\u258b', '\u258a', '\u2589', '\u2588']

    substeps = len(BLK_CHARS)
    result = ""

    segments = int(position * width * substeps / maximum)
    while segments > 0:
        if segments > substeps:
            result += BLK_CHARS[-1]
            segments -= substeps
        else:
            result += BLK_CHARS[segments - 1]
            segments = 0

    while len(result) < width:
        result += " "

    return result


def text_window(content, max_size):
    if len(content) < max_size:
        return "%-*s" % (max_size, content)

    first_char = len(content) - max_size + 1
    if first_char < 0:
        first_char = 0
    return "%-*s" % (max_size, content[first_char:first_char + max_size - 1])

class TerminalRawMode:
    IFLAG = 0
    OFLAG = 1
    CFLAG = 2
    LFLAG = 3
    ISPEED = 4
    OSPEED = 5
    CC = 6

    KEY_ESC = special_key("ESC")
    KEY_ENTER = special_key("Enter")
    KEY_BACKSPACE = special_key("BS")
    KEY_UP_ARROW = special_key("Up")
    KEY_DOWN_ARROW = special_key("Down")
    KEY_LEFT_ARROW = special_key("Left")
    KEY_RIGHT_ARROW = special_key("Right")

    CURSOR_BLINKING_BAR = '5'

    def __init__(self):
        self._fd = stdin.fileno()
        self._original_attrs = None
        self._expect_dimensions = False

        SPECIAL_SEQUENCES = [
            ("ESC OP", "F1"),
            ("ESC OQ", "F2"),
            ("ESC OR", "F3"),
            ("ESC OS", "F4"),
            ("ESC [15~", "F5"),
            ("ESC [17~", "F6"),
            ("ESC [18~", "F7"),
            ("ESC [19~", "F8"),
            ("ESC [20~", "F9"),
            ("ESC [21~", "F10"),
            ("ESC [23~", "F11"),
            ("ESC [24~", "F12"),

            ("ESC [1;2P", "S-F1"),
            ("ESC [1;2Q", "S-F2"),
            ("ESC [1;2R", "S-F3"),
            ("ESC [1;2S", "S-F4"),
            ("ESC [15;2~", "S-F5"),
            ("ESC [17;2~", "S-F6"),
            ("ESC [18;2~", "S-F7"),
            ("ESC [19;2~", "S-F8"),
            ("ESC [20;2~", "S-F9"),
            ("ESC [21;2~", "S-F10"),
            ("ESC [23;2~", "S-F11"),
            ("ESC [24;2~", "S-F12"),

            ("ESC [1;3P", "M-F1"),
            ("ESC [1;3Q", "M-F2"),
            ("ESC [1;3R", "M-F3"),
            ("ESC [1;3S", "M-F4"),
            ("ESC [15;3~", "M-F5"),
            ("ESC [17;3~", "M-F6"),
            ("ESC [18;3~", "M-F7"),
            ("ESC [19;3~", "M-F8"),
            ("ESC [20;3~", "M-F9"),
            ("ESC [21;3~", "M-F10"),
            ("ESC [23;3~", "M-F11"),
            ("ESC [24;3~", "M-F12"),

            ("ESC [1;4P", "M-S-F1"),
            ("ESC [1;4Q", "M-S-F2"),
            ("ESC [1;4R", "M-S-F3"),
            ("ESC [1;4S", "M-S-F4"),
            ("ESC [15;4~", "M-S-F5"),
            ("ESC [17;4~", "M-S-F6"),
            ("ESC [18;4~", "M-S-F7"),
            ("ESC [19;4~", "M-S-F8"),
            ("ESC [20;4~", "M-S-F9"),
            ("ESC [21;4~", "M-S-F10"),
            ("ESC [23;4~", "M-S-F11"),
            ("ESC [24;4~", "M-S-F12"),

            ("ESC [1;5P", "C-F1"),
            ("ESC [1;5Q", "C-F2"),
            ("ESC [1;5R", "C-F3"),
            ("ESC [1;5S", "C-F4"),
            ("ESC [15;5~", "C-F5"),
            ("ESC [17;5~", "C-F6"),
            ("ESC [18;5~", "C-F7"),
            ("ESC [19;5~", "C-F8"),
            ("ESC [20;5~", "C-F9"),
            ("ESC [21;5~", "C-F10"),
            ("ESC [23;5~", "C-F11"),
            ("ESC [24;5~", "C-F12"),

            ("ESC [A", "Up"),
            ("ESC [B", "Down"),
            ("ESC [C", "Right"),
            ("ESC [D", "Left"),

            ("ESC [1;2A", "S-Up"),
            ("ESC [1;2B", "S-Down"),
            ("ESC [1;2C", "S-Right"),
            ("ESC [1;2D", "S-Left"),

            ("ESC [1;3A", "M-Up"),
            ("ESC [1;3B", "M-Down"),
            ("ESC [1;3C", "M-Right"),
            ("ESC [1;3D", "M-Left"),

            ("ESC [1;5A", "C-Up"),
            ("ESC [1;5B", "C-Down"),
            ("ESC [1;5C", "C-Right"),
            ("ESC [1;5D", "C-Left"),
            ("ESC [Z", "S-Tab"),
        ]

        self._translation = {
            special_key("0d"): self.KEY_ENTER,
            "\x7F": self.KEY_BACKSPACE,
        }

        for v1, v2 in SPECIAL_SEQUENCES:
            self._translation[special_key(v1)] = special_key(v2)
        
        for key in "abcdefghijklnopqrstuvwxyz":
            self._translation[special_key("%02x" % (ord(key) - 96))] = special_key("C-" + key)

        altkeys = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        altkeys += "1234567890-=!@#$%^&*()_+]\\}|;':\",./?"

        for altkey in altkeys:
            self._translation[special_key("ESC %s" % altkey)] = special_key("M-%s" % altkey)

        self._terminal_rows = 25
        self._terminal_cols = 80
        self._resize_cb = None

    def enter_raw_mode(self):
        self._original_attrs = termios.tcgetattr(self._fd)
        new_attrs = termios.tcgetattr(self._fd)

        new_attrs[self.IFLAG] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
        new_attrs[self.OFLAG] &= ~(termios.OPOST)
        new_attrs[self.CFLAG] |= termios.CS8
        new_attrs[self.LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        new_attrs[self.CC][termios.VMIN] = 0
        new_attrs[self.CC][termios.VTIME] = 1

        termios.tcsetattr(self._fd, termios.TCSAFLUSH, new_attrs)

    def exit_raw_mode(self):
        termios.tcsetattr(self._fd, termios.TCSAFLUSH, self._original_attrs)

    def set_resize_cb(self, callback: callable):
        self._resize_cb = callback

    def _ansi_read_many(self):
        result = ""
        while True:
            data = stdin.read(1)
            if len(data) == 0:
                return result
            else:
                result += data
                if ord(data) >= 0x40 and ord(data) <= 0x7F:
                    return result

    def _on_terminal_dimensions(self, data):
        rows_s, cols_s = data.split(';')
        self._terminal_rows = int(rows_s)
        self._terminal_cols = int(cols_s)
        self._expect_dimensions = False
        if self._resize_cb is not None:
            self._resize_cb(self._terminal_rows, self._terminal_cols)

    def get_dimensions(self):
        return (self._terminal_rows, self._terminal_cols)

    def read_key(self, blocking=True):
        result = ""
        char0 = stdin.read(1)
        if len(char0) == 0:
            return ""
        elif char0 == "\x1b":
            char1 = stdin.read(1)
            if len(char1) == 0:
                result = self.KEY_ESC
            else:
                rest = self._ansi_read_many()
                if char1 == "\x1b":
                    result = self.KEY_ESC + special_key("ESC " + self.read_key(blocking))
                elif self._expect_dimensions and char1 == '[' and rest.endswith('R'):
                    # Perform special handling of \x1b[x;yR: this is the response
                    # from terminal containing the number of rows and columns
                    self._on_terminal_dimensions(rest[:-1])
                    return ""
                else:
                    result = special_key("ESC %s%s" % (char1, rest))

        elif char0 >= ' ':
            result = char0
        else:
            result = special_key("%02x" % ord(char0))

        return self._translation.get(result, result)

    def request_terminal_size(self):
        self.write("\x1b[999;999f\x1b[6n", flush=True)
        self._expect_dimensions = True

    def write(self, line, flush=False):
        stdout.write("%s" % line)
        if flush:
            self.flush()

    def flush(self):
        stdout.flush()

    def write_line(self, line):
        stdout.write("%s\r\n" % line)
        self.flush()

    def set_format(self, format):
        stdout.write("\x1b[%sm" % format)

    def set_cursor_position(self, col, row=None):
        if row is None:
            self.write("\x1b[%dG" % col)
        else:
            self.write("\x1b[%d;%dH" % (row, col))

    def set_cursor_style(self, style):
        self.write("\x1b[%c q" % style)

    def reset_current_line(self, format="0"):
        # Move to first column, reset formatting, clear till the end of line
        stdout.write("\x1b[G\x1b[%sm\x1b[K" % format)

if __name__ == "__main__":
    rawmode = TerminalRawMode()
    rawmode.enter_raw_mode()
    while True:
        data = rawmode.read_key()
        rawmode.write(data)

        if data == "Q": break

    rawmode.exit_raw_mode()
