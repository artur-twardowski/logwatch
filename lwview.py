#!/usr/bin/python3

from sys import argv
import json
from network.clients import GenericTCPClient
from time import sleep
from queue import Queue
from utils import pop_args, info, error, warning, set_log_level, VERSION
from utils import TerminalRawMode
from view.formatter import Formatter, resolve_color
from view.configuration import Configuration, Watch
from view.interactive_mode import InteractiveModeContext
from view.console_output import ConsoleOutput
import signal


class TCPClient(GenericTCPClient):
    def __init__(self, config: Configuration, cout: ConsoleOutput):
        super().__init__(config.host, config.port)
        self._config = config
        self._cout = cout
        self._recv_buffer = bytearray()

    def on_data_received(self, recv_data):
        for byte in recv_data:
            if byte == 0:
                data_recv_str = str(self._recv_buffer, 'utf-8')

                if len(data_recv_str) > 0:
                    try:
                        data = json.loads(data_recv_str)
                        if data['type'] == 'data':
                            self._cout.print_line(data);
                        elif data['type'] == 'marker':
                            self._cout.print_marker(data)
                        elif data['type'] == 'keepalive':
                            self._cout.notify_server_state(data['state'])

                    except json.decoder.JSONDecodeError as err:
                        warning("Failed to parse JSON: %s: %s" % (err, data_recv_str))

                self._recv_buffer.clear()
            else:
                self._recv_buffer.append(byte)

    def send_enc(self, data):
        self.send(json.dumps(data))

def read_args(args):
    arg_queue = Queue()
    config = Configuration()
    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()

        if arg in ['-p', '--port']:
            port_s, = pop_args(arg_queue, arg, "port")
            config.port = int(port_s)
        elif arg in ['-h', '--host']:
            host, = pop_args(arg_queue, arg, "host")
            config.host = host
        elif arg in ['-S', '--socket']:
            port_s, = pop_args(arg_queue, arg, "port")
            config.socket = int(port_s)
        elif arg in ['-c', '--config']:
            config_file, view_name = pop_args(arg_queue, arg, "file-name", "view-name")
            config.read(config_file, view_name)
        elif arg in ['-v', '--verbose']:
            config.log_level += 1
        else:
            print("Unknown option: %s" % arg)
            exit(1)
    return config


def pause_callback(console_output, analysis_mode):
    console_output.set_drop_newest_lines_policy(analysis_mode)
    console_output.pause()


def resume_callback(console_output):
    console_output.resume()


def set_watch_callback(formatter: Formatter, config: Configuration, register: str, params: tuple):
    regex, replacement, background, foreground = params
    watch = Watch()
    watch.set_regex(regex)
    watch.replacement = replacement
    watch.enabled = True
    watch.format.background_color = {"default": resolve_color(background)}
    watch.format.foreground_color = {"default": resolve_color(foreground)}

    if regex == "":
        formatter.delete_watch_style(register)
        config.delete_watch(register)
    else:
        formatter.add_watch_style(register, watch.format)
        config.add_watch(register, watch)

    watch.compile_regex()


def set_watch_enable(config: Configuration, register: str, enabled: bool):
    if register in config.watches:
        config.watches[register].enabled = enabled


def send_to_stdin(client: TCPClient, register, data):
    client.send_enc({
        'type': 'send-stdin',
        'endpoint-register': register,
        'data': data
    })


def quit_callback():
    raise KeyboardInterrupt

def disconnect_callback(console_output):
    console_output.print_message("Disconnected from server")

if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGWATCH v%s: lwview" % VERSION)
    config = read_args(argv[1:])
    set_log_level(config.log_level)

    term = TerminalRawMode()
    try:
        interact = InteractiveModeContext(config)
        term.enter_raw_mode()

        formatter = Formatter()
        console_output = ConsoleOutput(config, formatter, term, interact)
        console_output.set_max_held_lines(config.max_held_lines)

        interact.on_command_buffer_changed(lambda buf: console_output.notify_status_line_changed())
        interact.on_pause(lambda analysis_mode: pause_callback(console_output, analysis_mode))
        interact.on_resume(lambda: resume_callback(console_output))
        interact.on_set_watch(lambda register, params: set_watch_callback(formatter, config, register, params))
        interact.on_enable_watch(lambda watch, enabled: set_watch_enable(config, watch, enabled))
        interact.on_quit(lambda: quit_callback())
        interact.on_print_info(lambda fd, content: console_output.print_message(content, fd))

        for endpoint_name, endpoint_style in config.endpoint_styles.items():
            formatter.add_endpoint_style(endpoint_name, endpoint_style)

        for watch_name, watch in config.watches.items():
            formatter.add_watch_style(watch_name, watch.format)

        app_active = True
        client = TCPClient(config, console_output)
        client.set_connection_loss_cb(lambda: disconnect_callback(console_output))

        interact.on_send_stdin(lambda register, data: send_to_stdin(client, register, data))
        interact.on_set_marker(lambda: client.send_enc({"type": "set-marker"}))

        signal.signal(signal.SIGWINCH, lambda s, f: term.notify_resized())

        while app_active:
            try:
                if not client.is_active():
                    try:
                        client.run()
                        client.send_enc({'type': 'get-late-join-records'})
                    except ConnectionRefusedError:
                        sleep(0.1)

                console_output.write_pending_lines()
                console_output.render_status_line()
                interact.read_key(term)
            except KeyboardInterrupt:
                app_active = False

        client.stop()
    except Exception as ex:
        raise
    finally:
        term.exit_raw_mode()
        print("")
        client.stop()

