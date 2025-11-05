from view.interactive_mode import InteractiveModeContext


def _not_implemented(ctx: InteractiveModeContext):
    ctx.show_message("This functionality is not implemented yet")


def install(ctx: InteractiveModeContext):
    ctx.register_action(
        "tm<TriggerOp>",
        "Define a trigger on marker",
        "",
        callback2=lambda _, op: _not_implemented(ctx))

    ctx.register_action(
        "t'<Register><TriggerOp>",
        "Define a trigger on a watch",
        "",
        callback3=lambda _, reg, op: _not_implemented(ctx))

    ctx.register_action(
        "t''<Register><Register>*;<TriggerOp>",
        "Define a trigger on a watch",
        "",
        callback5=lambda _1, _2, reg1, regs, op: _not_implemented(ctx))

