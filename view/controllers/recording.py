from view.interactive_mode import InteractiveModeContext


def _not_implemented(ctx: InteractiveModeContext):
    ctx.show_message("This functionality is not implemented yet")


def install(ctx: InteractiveModeContext):
    ctx.register_action(
        "R",
        "Record logs",
        "Records the logs from selected (armed) endpoints to a file.",
        callback1=lambda _: _not_implemented(ctx))

    ctx.register_action(
        "&<Register>R",
        "Record immediately an endpoint",
        "",
        callback2=lambda _, reg: _not_implemented(ctx))

    ctx.register_action(
        "&&<Register><Register>*;R",
        "Record immediately selected endpoints",
        "",
        callback4=lambda _1, _2, reg1, regs: _not_implemented(ctx))

    ctx.register_action(
        "&<Register>r",
        "Arm an endpoint for recording",
        "",
        callback2=lambda _, reg: _not_implemented(ctx))

    ctx.register_action(
        "&&<Register><Register>*;r",
        "Arm multiple endpoints for recording",
        "",
        callback4=lambda _1, _2, reg1, regs: _not_implemented(ctx))

    ctx.register_action(
        "&\\*r",
        "Arm all endpoints for recording",
        "",
        callback2=lambda _1, _2: _not_implemented(ctx))
