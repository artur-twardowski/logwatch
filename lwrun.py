#!/usr/bin/python3

from sys import argv
from os import chdir
from os.path import dirname, realpath, join
from utils import pop_args, error, info, warning, set_log_level, VERSION
from utils import lw_assert, parse_yes_no_option
from queue import Queue
from time import sleep
import yaml
import subprocess as sp

class Configuration:
    def __init__(self):
        self.log_level = 2
        self.work_dir = None
        self.layout = None
        self.config_file_name = None
        self.run_server = None

    def read(self, filename, layout_name):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)

            lw_assert('layouts' in data,
                      "Configuration file does not have \"layouts\" section")

            lw_assert('views' in data,
                      "Configuration file does not have \"views\" section")

            lw_assert(layout_name in data['layouts'],
                      "Configuration file does not define a layout named \"%s\"" % layout_name)
            self.layout = data['layouts'][layout_name]

            self.config_file_name = realpath(filename)


def read_args(args, run_path):
    arg_queue = Queue()
    config = Configuration()
    config.work_dir = dirname(realpath(run_path))
    print(config.work_dir)

    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()
        if arg in ['-c', '--config']:
            config_file, layout_name = pop_args(arg_queue, arg, "file-name", "layout-name")
            config.read(config_file, layout_name)
        elif arg in ['-s', '--run-server']:
            run_server_s, = pop_args(arg_queue, arg, "no/yes")
            config.run_server = parse_yes_no_option(arg, run_server_s)

        elif arg in ['-v', '--verbose']:
            config.log_level += 1
        else:
            print("Unknown option: %s" % arg)
            exit(1)

    return config

def instantiate_tmux_layout(config: dict, config_file_name, work_dir):
    lw_assert("panels" in config,
              "Layout configuration does not have \"panels\" node")
    lw_assert("layout" in config,
              "Layout configuration does not have \"layout\" node")
    layout = config["layout"]

    lwview_path = join(work_dir, "lwview.py")

    cmdline_common = ["tmux", "split-window", "-b"]

    for panel_ix, panel_config in enumerate(config["panels"]):
        cmdline_main_pane = cmdline_common
        if "size" in panel_config:
            cmdline_main_pane += ["-l", str(panel_config["size"])]

        if "view" in panel_config:
            cmdline_lwview = "%s -c %s %s" % (lwview_path, config_file_name, panel_config['view'])
            sp.run(cmdline_main_pane + [cmdline_lwview])
        elif "command" in panel_config:
            sp.run(cmdline_main_pane + [panel_config["command"]])
        else:
            warning("Either \"view\" or \"shell\" must be provided for panel %d" % panel_ix)

        if "filters-panel" in panel_config and panel_config["filters-panel"]:
            sp.run(["tmux", "split-window", "-hd", "-l", "40", "sh"])

        sp.run(["tmux", "select-pane", "-D"])


def instantiate_layout(config: Configuration, config_file_name):
    ENGINES = {
        "tmux": lambda c, f: instantiate_tmux_layout(c, f, config.work_dir)
    }
    lw_assert("engine" in config.layout,
              "No \"engine\" field in layout_config")
    lw_assert(config.layout["engine"] in ENGINES,
              "Unsupported layouting engine: \"%s\"" % config.layout["engine"])

    do_run_server = config.run_server

    if do_run_server is None:
        do_run_server = "run-server" in config.layout and config.layout["run-server"]
    
    if do_run_server:
        lwserver_path = join(config.work_dir, "lwserver.py")
        info("Starting server")
        sp.Popen([lwserver_path, "-c", config_file_name])
        sleep(0.3) # TODO: should check if the server was actually started

    ENGINES[config.layout["engine"]](config.layout, config_file_name)


if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGWATCH v%s: lwrun" % VERSION)
    config = read_args(argv[1:], argv[0])
    set_log_level(config.log_level)

    chdir(config.work_dir)
    instantiate_layout(config, config.config_file_name)

