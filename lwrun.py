#!/usr/bin/python3

from sys import argv
from utils import pop_args, info, warning, set_log_level, VERSION
from utils import lw_assert
from queue import Queue
import yaml
import subprocess as sp

class Configuration:
    def __init__(self):
        self.log_level = 2
        self.layout = None
        self.config_file_name = None

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

            self.config_file_name = filename


def read_args(args):
    arg_queue = Queue()
    config = Configuration()
    for arg in args:
        arg_queue.put(arg)

    while not arg_queue.empty():
        arg = arg_queue.get()
        if arg in ['-c', '--config']:
            config_file, layout_name = pop_args(arg_queue, arg, "file-name", "layout-name")
            config.read(config_file, layout_name)
        elif arg in ['-v', '--verbose']:
            config.log_level += 1
        else:
            print("Unknown option: %s" % arg)
            exit(1)

    return config

def instantiate_tmux_layout(config: dict, config_file_name):
    lw_assert("panels" in config,
              "Layout configuration does not have \"panels\" node")
    lw_assert("layout" in config,
              "Layout configuration does not have \"layout\" node")
    layout = config["layout"]

    cmdline_common = ["tmux", "split-window", "-b"]

    for panel_ix, panel_config in enumerate(config["panels"]):
        cmdline_main_pane = cmdline_common
        if "size" in panel_config:
            cmdline_main_pane += ["-l", str(panel_config["size"])]

        if "view" in panel_config:
            cmdline_lwview = "./lwview.py -c %s %s" % (config_file_name, panel_config['view'])
            sp.run(cmdline_main_pane + [cmdline_lwview])
        elif "command" in panel_config:
            sp.run(cmdline_main_pane + [panel_config["command"]])
        else:
            warning("Either \"view\" or \"shell\" must be provided for panel %d" % panel_ix)

        if "filters-panel" in panel_config and panel_config["filters-panel"]:
            sp.run(["tmux", "split-window", "-hd", "-l", "40", "sh"])

        sp.run(["tmux", "select-pane", "-D"])

def instantiate_layout(layout_config, config_file_name):
    ENGINES = {
        "tmux": lambda c, f: instantiate_tmux_layout(c, f)
    }
    lw_assert("engine" in layout_config,
              "No \"engine\" field in layout_config")
    lw_assert(layout_config["engine"] in ENGINES,
              "Unsupported layouting engine: \"%s\"" % layout_config["engine"])

    ENGINES[layout_config["engine"]](layout_config, config_file_name)


if __name__ == "__main__":
    set_log_level(3)
    info("*** LOGWATCH v%s: lwrun" % VERSION)
    config = read_args(argv[1:])
    set_log_level(config.log_level)
    instantiate_layout(config.layout, config.config_file_name)

