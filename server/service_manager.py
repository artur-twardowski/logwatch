from utils import info, error
from collections import deque
import json
from datetime import datetime
from time import sleep

class ServiceManager:
    def __init__(self):
        self._servers = []
        self._line_seq_no = 0
        self._default_marker_no = 1
        self._late_join_buf = deque()
        self._late_join_buf_size = 256

    def set_late_join_buf_size(self, size):
        if size is not None:
            info("Set late joiners buffer size to %d records" % size)
            self._late_join_buf_size = size
        else:
            info("No late joiners buffer size configured, using default of %d records" % self._late_join_buf_size)

    def add_to_late_join_buf(self, record):
        while len(self._late_join_buf) >= self._late_join_buf_size:
            self._late_join_buf.popleft()
        self._late_join_buf.append(record)

    def register(self, server):
        self._servers.append(server)

    def run_all(self):
        if len(self._servers) == 0:
            error("No services to run")

        for server in self._servers:
            server.run()

        sleep(0.2)
        result = False
        for server in self._servers:
            if server.is_active():
                result = True
                break
        return result

    def stop_all(self):
        for server in self._servers:
            server.stop()

    def broadcast_data(self, endpoint_name, fd, data):
        today = datetime.now()
        for server in self._servers:
            record = {
                "type": "data",
                "endpoint": endpoint_name,
                "fd": fd,
                "data": data,
                "seq": self._line_seq_no,
                "date": today.strftime("%Y-%m-%d"),
                "time": today.strftime("%H:%M:%S")
            }
            server.broadcast(json.dumps(record))
            self.add_to_late_join_buf(record)
        self._line_seq_no += 1

    def broadcast_keepalive(self, seq_no):
        for server in self._servers:
            server.broadcast(json.dumps({
                "type": "keepalive",
                "seq": seq_no
            }))

    def broadcast_marker(self, name):
        today = datetime.now()

        if name == "":
            name = "MARKER %d" % self._default_marker_no
            self._default_marker_no += 1

        for server in self._servers:
            record = {
                "type": "marker",
                "name": name,
                "date": today.strftime("%Y-%m-%d"),
                "time": today.strftime("%H:%M:%S")
            }
            server.broadcast(json.dumps(record))
            self.add_to_late_join_buf(record)

    def send_late_join_records(self, server, client_addr):
        info("Sending previous %d lines to %s:%s" % (len(self._late_join_buf), client_addr[0], client_addr[1]))
        for rec in self._late_join_buf:
            server.send(client_addr, json.dumps(rec))

