VERSION = "0.1"
log_level = 2


def set_log_level(level):
    global log_level
    log_level = level


def debug(message):
    global log_level
    if log_level >= 4:
        print("\x1b[35mDEBUG: %s\x1b[0m" % message)
    pass


def info(message):
    global log_level
    if log_level >= 3:
        print("\x1b[1;37m%s\x1b[0m" % message)


def warning(message):
    global log_level
    if log_level >= 2:
        print("\x1b[1;35mWARNING: %s\x1b[0m" % message)


def error(message):
    global log_level
    if log_level >= 1:
        print("\x1b[1;31mERROR: %s\x1b[0m" % message)


def pop_args(arg_queue, argument, *names):
    if arg_queue.qsize() < len(names):
        if len(names) == 1:
            print("Option %s requires %s argument" % (argument, names[0]))
        else:
            print("Option %s requires %d arguments: %s" % (argument, len(names), ", ".join(names)))
        exit(1)

    retval = []
    for _ in names:
        retval.append(arg_queue.get())
    return retval

