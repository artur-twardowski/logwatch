class ByNewlineSeparator:
    NAME = 'by-newline'
    def __init__(self, configuration, on_event_cb: callable):
        self._on_event_cb = on_event_cb
        self._recv_buf = {}
        self._trim = configuration.get("trim", False)

    def feed(self, fd, data):
        if fd not in self._recv_buf:
            self._recv_buf[fd] = ""
        self._recv_buf[fd] += data
        while True:
            pos = self._recv_buf[fd].find('\n')
            if pos != -1:
                data = self._recv_buf[fd][0:pos]
                if self._trim:
                    data = data.strip()
                self._on_event_cb(fd, data)
                self._recv_buf[fd] = self._recv_buf[fd][pos + 1:]
            else:
                break

