from view.interactive_mode import InteractiveModeContext
from view.configuration import Configuration


def install(ctx: InteractiveModeContext, config: Configuration):
    ctx.register_action(
        "&<Register>n",
        "Drop all the log events from the endpoint",
        "Stops displaying any data from the endpoint.",
        callback2=lambda _, reg: config.set_endpoint_show_mode(reg, Configuration.SHOW_NONE)
    )

    ctx.register_action(
        "&&<Register><Register>*;n",
        "Drop all the log events from multiple endpoints",
        "Stops displaying any data from the endpoints indicated.",
        callback4=lambda _1, _2, reg1, regs:
            config.set_endpoint_show_mode(reg1 + regs, Configuration.SHOW_NONE)
    )

    ctx.register_action(
        "&<Register>f",
        "",
        "",
        callback2=lambda _, reg: config.set_endpoint_show_mode(reg, Configuration.SHOW_FILTERED)
    )

    ctx.register_action(
        "&&<Register><Register>*;f",
        "",
        "",
        callback4=lambda _1, _2, reg1, regs:
            config.set_endpoint_show_mode(reg1 + regs, Configuration.SHOW_FILTERED)
    )

    ctx.register_action(
        "&<Register>a",
        "",
        "",
        callback2=lambda _, reg: config.set_endpoint_show_mode(reg, Configuration.SHOW_ALL)
    )

    ctx.register_action(
        "&&<Register><Register>*;a",
        "",
        "",
        callback4=lambda _1, _2, reg1, regs:
            config.set_endpoint_show_mode(reg1 + regs, Configuration.SHOW_ALL)
    )

