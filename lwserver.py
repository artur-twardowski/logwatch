#!/usr/bin/python3
from sys import argv
from queue import Queue
import json
import signal
from time import sleep
from network.servers import GenericTCPServer
from utils import pop_args, error, info, debug, set_log_level, inc_log_level, VERSION
from utils import parse_yes_no_option, warning, lw_assert
from common import SYSTEM_ENDPOINT
from server.configuration import Configuration, ActionConfiguration, SubprocessConfig, SSHSessionConfig
from server.subprocess import SubprocessCommunication
from server.ssh_session import SSHSessionCommunication
from server.service_manager import ServiceManager
from server.separators import create_separator
from server.separators.by_newline import ByNewlineSeparator

class ActiveState:
    def __init__(self, state_machine, subprocesses: list):
        self._state_machine = state_machine
        self._subprocesses = subprocesses
        self._active_subprocesses = 0

    def _run_subprocesses(self):
        for _, subproc in self._subprocesses.items():
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


def read_args(args):
    arg_queue = Queue()
    config = Configuration()
    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()

        if arg in ['-p', '--process']:
            endpoint_register, command_line = pop_args(arg_queue, arg, "endpoint-register", "command")
            config.subprocesses.append((endpoint_register, command_line))
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
    def __init__(self, addr, port, server_manager: ServiceManager, endpoints: dict):
        super().__init__(address=addr, port=port)
        self._server_manager = server_manager
        self._recv_buffer = bytearray()
        self._endpoints = endpoints

    def on_data_received(self, addr, recv_data):
        for byte in recv_data:
            if byte == 0:
                data_recv_str = str(self._recv_buffer, 'utf-8')

                if len(data_recv_str) > 0:
                    try:
                        data = json.loads(data_recv_str)
                        if data['type'] == 'set-marker':
                            self._server_manager.broadcast_marker(data.get("name", ""))
                        elif data['type'] == 'get-late-join-records':
                            self._server_manager.send_late_join_records(self, addr)
                        elif data['type'] == 'send-stdin':
                            endpoint = self._endpoints.get(data['endpoint-register'])
                            if endpoint is not None:
                                endpoint.send(data['data'] + "\n")


                    except json.decoder.JSONDecodeError as err:
                        error("Failed to parse JSON: %s: %s" % (err, data_recv_str))

                self._recv_buffer.clear()
            else:
                self._recv_buffer.append(byte)


class ActionManager:
    STATE_AWAITING = 0
    STATE_RUNNING = 1
    STATE_FINISHED = 2

    def __init__(self, separators: dict, default_separator_cb: callable):
        self._actions = {}
        self._action_states = {}
        self._action_states_to_publish = {}
        self._preconditions = {}
        self._separators = separators
        self._default_separator_cb = default_separator_cb

        self.STATE_NAMES = {
            self.STATE_AWAITING: "awaiting",
            self.STATE_RUNNING: "running",
            self.STATE_FINISHED: "finished"
        }

    def _on_data(self, action, fd, data):
        self._separators[action].feed(fd, data)

    def register(self, name, config, preconditions = []):
        if isinstance(config, SubprocessConfig):
            action = SubprocessCommunication(config.command, name, lambda a, f, d: self._on_data(a, f, d))
        elif isinstance(config, SSHSessionConfig):
            action = SSHSessionCommunication(config, name, lambda a, f, d: self._on_data(a, f, d))
        else:
            raise RuntimeError("Cannot register an action described as %s" % str(config))

        lw_assert(name not in self._actions,
                  "Action name \"%s\" used multiple times" % name)

        info("Registered action %s (preconditions: %s): %s" % (name, preconditions, action))

        self._actions[name] = action
        self._action_states[name] = self.STATE_AWAITING
        self._preconditions[name] = preconditions

        if name not in self._separators:
            self._separators[name] = ByNewlineSeparator({"trim": True}, lambda f, d, a=name: self._default_separator_cb(a, f, d))

    def get(self, action_name):
        return self._actions[action_name]

    def _can_be_run(self, action_name):
        if self._action_states[action_name] != self.STATE_AWAITING:
            return False

        result = True
        for dep_name, dep_requirement in self._preconditions[action_name].items():
            if dep_requirement == ActionConfiguration.AWAIT_COMPLETION:
                result = result and (self._action_states[dep_name] == self.STATE_FINISHED)
        return result

    def _notify_finished(self, action_name):
        self._action_states[action_name] = self.STATE_FINISHED

    def execute(self, print_debug_line=False):
        for action_name, action in self._actions.items():
            if self._can_be_run(action_name):
                action = self._actions[action_name]
                action.set_command_finished_callback(lambda a=action_name: self._notify_finished(a))
                self._action_states[action_name] = self.STATE_RUNNING
                action.run()

        finished_actions = 0
        debug_line = "Actions summary:"
        for action_name, state in self._action_states.items():
            state_s = self.STATE_NAMES.get(state)
            self._action_states_to_publish[action_name] = state_s
            debug_line += " %s:%s" % (action_name, state_s)
            if state == self.STATE_FINISHED:
                finished_actions += 1
        debug_line += " finished_actions=%d/%d" % (finished_actions, len(self._action_states))
        if print_debug_line:
            debug(debug_line)
        return finished_actions < len(self._action_states)

    def get_action_states(self):
        return self._action_states_to_publish


def _on_signal(sig, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    set_log_level(1)
    print("*** LOGWATCH v%s: lwserver" % VERSION)
    config = read_args(argv[1:])
    server_manager = ServiceManager()
    server_manager.set_late_join_buf_size(config.late_join_buf_size)

    endpoint_registers = {}
    actions_to_endpoints = {}
    separators = {}

    for action_name, rule_name in config.event_separation_rules.items():
        separators[action_name] = create_separator(rule_name, lambda fd, data, a=action_name:
            server_manager.broadcast_data(actions_to_endpoints.get(a, '-'), a, fd, data))

    if config.socket_port is not None:
        server_manager.register(TCPServer(addr=config.socket_addr,
                                          port=config.socket_port,
                                          server_manager=server_manager,
                                          endpoints=endpoint_registers))

    if not server_manager.run_all():
        error("Failed to start the server")
        exit(1)

    action_manager = ActionManager(
        separators=separators,
        default_separator_cb=lambda action, fd, data:
            server_manager.broadcast_data(actions_to_endpoints.get(action, '-'), action, fd, data))

    for action_name, action_config in config.actions.items():
        action_manager.register(action_name, action_config.data, action_config.preconditions)

    for endpoint_register, action_name in config.endpoint_registers.items():
        endpoint_registers[endpoint_register] = action_manager.get(action_name)
        actions_to_endpoints[action_name] = endpoint_register

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda s, f: _on_signal(s, f))

    keepalive_counter = 0
    while action_manager.execute(keepalive_counter % 10 == 0):
        try:
            if keepalive_counter % 4 == 0:
                server_manager.broadcast_keepalive(int(keepalive_counter / 10), actions=action_manager.get_action_states())
            keepalive_counter += 1
            sleep(0.1)

        except KeyboardInterrupt:
            warning("User-triggered termination, stopping the server")
            break
        except Exception as ex:
            error("Server error: %s. Stopping the server" % ex)
            break

    server_manager.broadcast_keepalive(int(keepalive_counter / 10))

    server_manager.stop_all()
