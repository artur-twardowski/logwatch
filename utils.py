from sys import stdin, stdout
import tty
import termios

VERSION = "0.1"
log_level = 2


def set_log_level(level):
    global log_level
    log_level = level


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


class TerminalRawMode:
    IFLAG = 0
    OFLAG = 1
    CFLAG = 2
    LFLAG = 3
    ISPEED = 4
    OSPEED = 5
    CC = 6

    def __init__(self):
        self._fd = stdin.fileno()
        self._original_attrs = None

        self._translation = {
            " ": "<Space>", "\r": "<Enter>", "\x7F": "<BS>",
            "<": "<LT>", ">": "<GT>",
            "<ESC OP>": "<F1>", "<ESC O2P>": "<S-F1>",
            "<ESC OQ>": "<F2>", "<ESC O2Q>": "<S-F2>",
            "<ESC OR>": "<F3>", "<ESC O2R>": "<S-F3>",
            "<ESC OS>": "<F4>", "<ESC O2S>": "<S-F4>",
            "<ESC [A>": "<Up>", "<ESC [1;5A>": "<C-Up>",
            "<ESC [B>": "<Down>", "<ESC [1;5B>": "<C-Down>",
            "<ESC [C>": "<Right>", "<ESC [1;5C>": "<C-Right>",
            "<ESC [D>": "<Left>", "<ESC [1;5D>": "<C-Left>",
            "<ESC [Z>": "<S-Tab>"
        }
        
        for key in range(ord('a'), ord('z') + 1):
            self._translation["<%02x>" % (key - 96)] = "<C-%s>" % chr(key)

        altkeys = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        altkeys += "1234567890-=!@#$%^&*()_+]\}|;':\",./?"

        for altkey in altkeys:
            self._translation["<ESC %s>" % altkey] = "<M-%s>" % altkey

        self._translation["<ESC <>"] = "<M-LT>"
        self._translation["<ESC >>"] = "<M-GT>"

    def enter_raw_mode(self):
        self._original_attrs = termios.tcgetattr(self._fd)
        new_attrs = termios.tcgetattr(self._fd)

        new_attrs[self.IFLAG] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
        new_attrs[self.OFLAG] &= ~(termios.OPOST)
        new_attrs[self.CFLAG] |= termios.CS8
        new_attrs[self.LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        new_attrs[self.CC][termios.VMIN] = 0
        new_attrs[self.CC][termios.VTIME] = 0

        termios.tcsetattr(self._fd, termios.TCSAFLUSH, new_attrs)

    def exit_raw_mode(self):
        termios.tcsetattr(self._fd, termios.TCSAFLUSH, self._original_attrs)

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

    def read_key(self, blocking=True):
        result = ""
        char0 = stdin.read(1)
        if len(char0) == 0:
            return ""
        elif char0 == "\x1b":
            char1 = stdin.read(1)
            if len(char1) == 0:
                result = "<ESC>"
            else:
                rest = self._ansi_read_many()
                if char1 == "\x1b":
                    result = "<ESC><ESC %s>" % self.read_key(blocking)
                else:
                    result = "<ESC %s%s>" % (char1, rest)

        elif char0 >= ' ':
            result = char0
        else:
            result = "<%02x>" % ord(char0)

        return self._translation.get(result, result)


    def write(self, line):
        stdout.write("%s" % line)
        stdout.flush()

    def write_line(self, line):
        stdout.write("%s\r\n" % line)

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
