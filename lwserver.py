#!/usr/bin/python3
from sys import argv
from queue import Queue
import json
import signal
from time import sleep
from network.servers import GenericTCPServer
from utils import pop_args, error, info, debug, set_log_level, inc_log_level, VERSION
from utils import parse_yes_no_option, warning
from server.configuration import Configuration
from server.subprocess import SubprocessCommunication
from server.service_manager import ServiceManager

class StartupShutdownState:
    def __init__(self, state_machine, actions, server_manager, next_state, state_after_stopped):
        self._state_machine = state_machine
        self._actions = actions
        self._action_ix = 0
        self._server_manager = server_manager
        self._next_state = next_state
        self._state_after_stopped = state_after_stopped
        self._subprocess = None
        self._stopping = False

    def _on_subprocess_finished(self):
        if not self._stopping:
            self._state_machine.transition(None, "next")
        self._subprocess = None

    def _execute_action(self, action):
        if "command" in action:
            self._subprocess = SubprocessCommunication(action["command"],
                                                       "system",
                                                       self._server_manager)
            self._subprocess.set_command_finished_callback(
                lambda: self._on_subprocess_finished())
            self._subprocess.run()

    def on_event(self, event_name):
        if event_name == "begin":
            self._stopping = False
            if len(self._actions) > 0:
                self._action_ix = 0
                self._execute_action(self._actions[self._action_ix])
            else:
                self._state_machine.transition(self._next_state, "begin")

        elif event_name == "next":
            self._action_ix += 1
            if self._action_ix >= len(self._actions):
                self._state_machine.transition(self._next_state, "begin")
            else:
                self._execute_action(self._actions[self._action_ix])
        
        elif event_name == "stop":
            print("Stopping -- to %s" % self._state_after_stopped)
            self._stopping = True
            if self._subprocess is not None:
                self._subprocess.stop()
            self._state_machine.transition(self._state_after_stopped, "begin")


class ActiveState:
    def __init__(self, state_machine, subprocesses: list):
        self._state_machine = state_machine
        self._subprocesses = subprocesses
        self._active_subprocesses = 0

    def _run_subprocesses(self):
        for subproc in self._subprocesses:
            subproc.set_command_finished_callback(
                lambda: self._state_machine.transition("active", "command-finished"))
            subproc.run()
            self._active_subprocesses += 1

    def on_event(self, event_name):
        if event_name == "begin":
            self._run_subprocesses()

        elif event_name == "command-finished":
            self._active_subprocesses -= 1
            if self._active_subprocesses == 0:
                self._state_machine.transition("shutdown", "begin")

        elif event_name == "stop":
            for subproc in self._subprocesses:
                subproc.stop()

class StoppedState:
    def __init__(self, state_machine):
        self._state_machine = state_machine

    def on_event(self, event_name):
        if event_name == "begin":
            self._state_machine.stop()

class StateMachine:
    def __init__(self, config: Configuration, subprocesses: list, server_manager):
        self._config = config

        self._states = {
            "startup": StartupShutdownState(
                state_machine=self,
                actions=config.startup_actions,
                server_manager=server_manager,
                next_state="active",
                state_after_stopped="shutdown"),
            "active": ActiveState(
                state_machine=self,
                subprocesses=subprocesses),
            "shutdown": StartupShutdownState(
                state_machine=self,
                actions=config.shutdown_actions,
                server_manager=server_manager,
                next_state="stopped",
                state_after_stopped="stopped"),
            "stopped": StoppedState(self)
        }

        self._state = None
        self._state_name = ""
        self._event = None
        self._active = False

    def start(self):
        self._state_name = "startup"
        self._state = self._states[self._state_name]
        self._event = "begin"
        self._active = True

    def stop(self):
        self._active = False

    def get_state_name(self):
        return self._state_name

    def transition(self, state, event):
        msg = "[%s]%s" % (self._state_name, "\u2500" * 4)
        if state is not None:
            self._state = self._states[state]
            self._state_name = state
        msg += "%s%s>[%s]" % (event, "\u2500" * 4, self._state_name)
        self._event = event
        debug(msg)

    def execute(self):
        current_event = self._event
        self._event = None
        self._state.on_event(current_event)
        return self._active


def read_args(args):
    arg_queue = Queue()
    config = Configuration()
    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()

        if arg in ['-p', '--process']:
            endpoint_name, command_line = pop_args(arg_queue, arg, "endpoint-name", "command")
            config.subprocesses.append((endpoint_name, command_line))
        elif arg in ['-P', '--port']:
            port, = pop_args(arg_queue, arg, "port")
            config.socket_port = int(port)
        elif arg in ['-a', '--stay-active']:
            stay_active_s, = pop_args(arg_queue, arg, "yes/no")
            config.stay_active = parse_yes_no_option(arg, stay_active_s)
        elif arg == "--verbose":
            inc_log_level(1)
        elif arg.startswith('-v'):
            inc_log_level(len(arg) - 1)

        elif arg in ['--help']:
            print("USAGE: %s <config-file> [options]")
            print("Available options:")
            print("\n * -p | --process <endpoint-name> <command>")
            print("   Add a subprocess endpoint executing the specified command")
            print("\n * -P | --port <port>")
            print("   Override the port number at which the server will listen")
            print("\n * -a | --stay-active <yes|no>")
            print("   Override the stay-active option from the configuration")
            print("\n * -v[v...] | --verbose")
            print("   Increase the level of verbosity of console logs")

        elif not arg.startswith('-'):
            config.read(arg)
        else:
            print("Unknown option: %s" % arg)
            exit(1)

    return config


class TCPServer(GenericTCPServer):
    def __init__(self, port, server_manager: ServiceManager):
        super().__init__(port)
        self._server_manager = server_manager
        self._recv_buffer = bytearray()

    def on_data_received(self, addr, recv_data):
        for byte in recv_data:
            if byte == 0:
                data_recv_str = str(self._recv_buffer, 'utf-8')

                if len(data_recv_str) > 0:
                    try:
                        data = json.loads(data_recv_str)
                        if data['type'] == 'set-marker':
                            self._server_manager.broadcast_marker(data['name'])
                        elif data['type'] == 'get-late-join-records':
                            self._server_manager.send_late_join_records(self, addr)

                    except json.decoder.JSONDecodeError as err:
                        error("Failed to parse JSON: %s: %s" % (err, data_recv_str))

                self._recv_buffer.clear()
            else:
                self._recv_buffer.append(byte)


def _on_signal(sig, frame, state_machine: StateMachine):
    warning("Received signal %s" % signal.Signals(sig).name)
    state_machine.transition(None, "stop")

if __name__ == "__main__":
    set_log_level(1)
    print("*** LOGWATCH v%s: lwserver" % VERSION)
    config = read_args(argv[1:])
    server_manager = ServiceManager()
    server_manager.set_late_join_buf_size(config.late_join_buf_size)

    if config.socket_port is not None:
        server_manager.register(TCPServer(config.socket_port, server_manager))

    if not server_manager.run_all():
        error("Failed to start the server")
        exit(1)

    subprocesses = []
    for endpoint_name, command in config.subprocesses:
        subproc = SubprocessCommunication(command, endpoint_name, server_manager)
        subprocesses.append(subproc)

    state_machine = StateMachine(config, subprocesses, server_manager)
    state_machine.start()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda s, f: _on_signal(s, f, state_machine))

    keepalive_counter = 0
    while state_machine.execute():
        try:
            if keepalive_counter % 4 == 0:
                server_manager.broadcast_keepalive(int(keepalive_counter / 10), state_machine.get_state_name())
            keepalive_counter += 1
            sleep(0.1)

        except KeyboardInterrupt:
            warning("User-triggered termination, stopping the server")
            state_machine.transition(None, "stop")
        except Exception as ex:
            error("Server error: %s. Stopping the server" % ex)
            state_machine.transition(None, "stop")

    server_manager.broadcast_keepalive(int(keepalive_counter / 10), state_machine.get_state_name())

    server_manager.stop_all()
