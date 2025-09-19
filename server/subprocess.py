from queue import Queue
import threading as thrd
from utils import info
import subprocess as sp
from time import sleep
import os
import signal

class SubprocessCommunication:
    def __init__(self, command_line, endpoint_name, servers):
        self._command_line = command_line
        self._endpoint_name = endpoint_name
        self._stdin_buffer = Queue()
        self._servers = servers
        self._worker_thread = None
        self._active = False
        self._on_command_finished = None
        self._pid = None

    def run(self):
        self._worker_thread = thrd.Thread(target=self._worker)
        self._worker_thread.start()

    def set_command_finished_callback(self, cb: callable):
        self._on_command_finished = cb

    def wait(self):
        self._worker_thread.join()

    def _worker(self):
        self._active = True
        info("Endpoint %s: running command: %s" % (self._endpoint_name, self._command_line))
        proc = sp.Popen(self._command_line,
                        shell=True,
                        stdin=sp.PIPE,
                        stdout=sp.PIPE,
                        stderr=sp.PIPE,
                        universal_newlines=True)

        self._pid = proc.pid
        info("Endpoint %s: PID %d" % (self._endpoint_name, self._pid))

        stdout_thread = thrd.Thread(target=self._receiver, args=(proc.stdout, 'stdout'))
        stderr_thread = thrd.Thread(target=self._receiver, args=(proc.stderr, 'stderr'))
        stdin_thread = thrd.Thread(target=self._sender, args=(proc, proc.stdin))

        stdout_thread.start()
        stderr_thread.start()
        stdin_thread.start()
        exitcode = proc.wait()

        stdout_thread.join()
        stderr_thread.join()
        stdin_thread.join()

        info("Endpoint %s: command returned with exit code %d" % (self._endpoint_name, exitcode))
        self._active = False

        if self._on_command_finished is not None:
            self._on_command_finished()

    def stop(self):
        if self._pid is not None:
            os.killpg(os.getpgid(self._pid), signal.SIGTERM)


    def is_active(self):
        return self._active

    def _receiver(self, stream, fd):
        for line in stream:
            self._servers.broadcast_data(self._endpoint_name, fd, line.strip())
        info("Receiver thread finished for fd=%s" % fd)

    def _sender(self, proc, stream):
        while proc.poll() is None:
            if not self._stdin_buffer.empty():
                line = self._stdin_buffer.get()
                stream.write(line)
                stream.flush()
            else:
                sleep(0.01)
        info("Sender thread finished")

