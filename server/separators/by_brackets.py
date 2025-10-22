class ByBracketsSeparator:
    NAME = "by-brackets"

    class AnalysisContext:
        def __init__(self):
            self._data = ""
            self._nest_level = 0
            self._pending_events = []

        def push(self, data):
            remainder_index = 0
            quoting = False
            for pos, c in enumerate(data):
                if c == '{' and not quoting:
                    self._nest_level += 1
                elif c == '}' and not quoting:
                    self._nest_level -= 1
                    if self._nest_level <= 0:
                        self._nest_level = 0
                        self._pending_events.append(self._data + data[remainder_index:pos + 1])
                        self._data = ""
                        remainder_index = pos + 1
                elif c == "\"":
                    quoting = not quoting
            self._data += data[remainder_index:]

        def get_pending_events(self):
            return self._pending_events

        def clear_pending_events(self):
            self._pending_events.clear()

    def __init__(self, configuration, on_event_cb: callable):
        self._on_event_cb = on_event_cb
        self._analysis_contexts = {}
        self._trim = configuration.get("trim", False)

    def feed(self, fd, data):
        if fd not in self._analysis_contexts:
            self._analysis_contexts[fd] = self.AnalysisContext()
        self._analysis_contexts[fd].push(data)

        for d in self._analysis_contexts[fd].get_pending_events():
            if self._trim:
                d = d.strip()
            self._on_event_cb(fd, d)
        self._analysis_contexts[fd].clear_pending_events()

