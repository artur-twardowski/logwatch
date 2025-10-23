from queue import Queue
import threading as thrd
from utils import info, debug, error
import subprocess as sp
from time import sleep
import os
import signal

class SubprocessCommunication:
    def __init__(self, command_line, action_name, on_data_emit_cb: callable):
        self._command_line = command_line
        self._action_name = action_name
        self._stdin_buffer = Queue()
        self._worker_thread = None
        self._active = False
        self._on_command_finished = None
        self._pid = None
        self._on_data_emit_cb = on_data_emit_cb

    def run(self):
        self._worker_thread = thrd.Thread(target=self._worker)
        self._worker_thread.start()

    def set_command_finished_callback(self, cb: callable):
        self._on_command_finished = cb

    def wait(self):
        self._worker_thread.join()

    def _worker(self):
        self._active = True
        info("&%s: running command: %s" % (self._action_name, self._command_line))
        proc = sp.Popen(self._command_line,
                        shell=True,
                        stdin=sp.PIPE,
                        stdout=sp.PIPE,
                        stderr=sp.PIPE,
                        universal_newlines=True)

        self._pid = proc.pid
        info("%s: PID %d" % (self._action_name, self._pid))

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

        info("%s: command returned with exit code %d" % (self._action_name, exitcode))
        self._active = False
        self._pid = None

        if self._on_command_finished is not None:
            self._on_command_finished()

    def stop(self):
        if self._pid is not None:
            try:
                os.killpg(os.getpgid(self._pid), signal.SIGTERM)
                info("%s: sent signal TERM" % self._action_name)
            except ProcessLookupError:
                debug("%s: process has already ended" % self._action_name)
            except Exception as ex:
                error("%s: %s" % (self._action_name, str(ex)))

    def send(self, data):
        self._stdin_buffer.put(data)

    def is_active(self):
        return self._active

    def _receiver(self, stream, fd):
        for line in stream:
            self._on_data_emit_cb(self._action_name, fd, line)
        info("Receiver thread finished for fd=%s" % fd)

    def _sender(self, proc, stream):
        while proc.poll() is None:
            if not self._stdin_buffer.empty():
                line = self._stdin_buffer.get()
                stream.write(line)
                self._on_data_emit_cb(self._action_name, 'stdin', line)
                stream.flush()
            else:
                sleep(0.01)
        info("Sender thread finished")

