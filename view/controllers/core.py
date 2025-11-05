from view.interactive_mode import InteractiveModeContext


def install(ctx: InteractiveModeContext,
            on_set_marker: callable,
            on_quit: callable,
            on_pause: callable,
            on_feed: callable):

    ctx.register_action("p", "Pause/resume",
                        "Temporarily stop printing new lines onto screen. "
                        "The lines will be held in a buffer and will appear "
                        "back on the screen after resuming. If the buffer "
                        "overflows, the oldest lines will be dropped.",
                        callback1=lambda _: on_pause(False))

    ctx.register_action("P", "Pause for analysis/resume",
                        "Similar to regular pause, but in case of buffer "
                        "overflow the latest lines will be dropped instead.",
                        callback1=lambda _: on_pause(True))

    ctx.register_action("f", "Feed line",
                        "While in pause mode, print a single line from the "
                        "buffer. If preceded by a counter, the indicated "
                        "number of lines will be fed",
                        callback1=lambda counter: on_feed(counter))

    ctx.register_action("q", "Quit", "Quits the application.",
                        callback1=lambda _: on_quit())

    ctx.register_action("m", "Insert marker", 
                        "Requests the server to emit a marker, effectively "
                        "inserting it into the watched logs. This operation "
                        "affects all the viewers connected to the server.",
                        callback1=lambda _: on_set_marker())

