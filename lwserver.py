#!/usr/bin/python3
from sys import argv
from queue import Queue
import json
from time import sleep
from network.servers import GenericTCPServer
from utils import pop_args, error, info, set_log_level, VERSION
from utils import parse_yes_no_option
from server.configuration import Configuration
from server.subprocess import SubprocessCommunication
from server.service_manager import ServiceManager


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
        elif arg in ['-S', '--socket']:
            port, = pop_args(arg_queue, arg, "port")
            config.socket = int(port)
        elif arg in ['-a', '--stay-active']:
            stay_active_s, = pop_args(arg_queue, arg, "yes/no")
            config.stay_active = parse_yes_no_option(arg, stay_active_s)
        elif arg in ['-c', '--config']:
            config_file, = pop_args(arg_queue, arg, "file-name")
            config.read(config_file)

        elif arg in ['--help']:
            print("USAGE: %s [-s | --subprocess <endpoint-name> <command>]*")
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


def any_active(subprocesses: list):
    result = False
    for subproc in subprocesses:
        if subproc.is_active():
            result = True
            break
    return result


if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGWATCH v%s: logserver" % VERSION)
    config = read_args(argv[1:])
    server_manager = ServiceManager()
    server_manager.set_late_join_buf_size(config.late_join_buf_size)

    if config.socket is not None:
        server_manager.register(TCPServer(config.socket, server_manager))

    if not server_manager.run_all():
        error("Failed to start the server")
        exit(1)

    subprocesses = []
    for endpoint_name, command in config.subprocesses:
        subproc = SubprocessCommunication(command, endpoint_name, server_manager)
        subprocesses.append(subproc)
        subproc.run()

    keepalive_counter = 0
    while True:
        try:
            if keepalive_counter % 10 == 0:
                server_manager.broadcast_keepalive(keepalive_counter / 10)
            keepalive_counter += 1
            sleep(0.1)

            if not config.stay_active and not any_active(subprocesses):
                info("No subprocesses are running, stopping the server")
                break
        except KeyboardInterrupt:
            info("User-triggered termination, stopping the server")
            break
        except Exception as ex:
            error("Server error: %s. Stopping the server" % ex)

    server_manager.stop_all()
