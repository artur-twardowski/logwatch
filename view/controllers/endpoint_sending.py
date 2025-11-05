from view.interactive_mode import InteractiveModeContext
from view.interactive_mode.input_views import SimpleInputView
from view.configuration import Configuration


def _do_send_stdin(ctx: InteractiveModeContext,
                   endpoint_register,
                   on_send_stdin: callable,
                   initial_content="",
                   stay_in_input_mode=False):
    ctx.enter_view(SimpleInputView(
        prompt="Send to '" + endpoint_register,
        initial_value=initial_content,
        on_confirm=lambda cmd, ep=endpoint_register: (
            on_send_stdin(ep, cmd),
            stay_in_input_mode or ctx.return_to_predicate_mode()),
        on_cancel=lambda: ctx.return_to_predicate_mode()))


def _do_set_command_register(ctx: InteractiveModeContext,
                             config: Configuration,
                             command_register):
    ctx.enter_view(SimpleInputView(
        prompt="Set command in \"%c\"" % command_register,
        initial_value=config.get_command_register(command_register),
        on_confirm=lambda content, reg=command_register: (
            config.set_command_register(reg, content),
            ctx.return_to_predicate_mode()),
        on_cancel=lambda: ctx.return_to_predicate_mode()))


def _assert_command_register_set(ctx: InteractiveModeContext,
                                 config: Configuration,
                                 command_register=None):
    if command_register not in config.commands:
        ctx.show_message("Nothing is stored in command register \"%c" % (
            command_register))
        return False
    return True


def install(ctx: InteractiveModeContext,
            config: Configuration,
            on_send_stdin: callable):
    ctx.register_action(
        "i",
        "Send a line to the default endpoint",
        "Enters interactive input allowing to send a string to the default "
        "endpoint.",
        callback1=lambda _: _do_send_stdin(ctx,
                                           ctx.get_default_endpoint(),
                                           stay_in_input_mode=False,
                                           on_send_stdin=on_send_stdin))
    ctx.register_action(
        "I",
        "Send continuously data to the default endpoint",
        "Enters interactive input allowing to send multiple strings to the "
        "default endpoint. Press ESC key to leave this mode. ",
        callback1=lambda _: _do_send_stdin(ctx,
                                           ctx.get_default_endpoint(),
                                           stay_in_input_mode=True,
                                           on_send_stdin=on_send_stdin))
    ctx.register_action(
        "&<Register>d",
        "Select a default endpoint",
        "Selects a default endpoint to which the data will be sent using "
        "'i'/'I' commands",
        callback2=lambda _, reg: ctx.set_default_endpoint(reg))

    ctx.register_action(
        "&<Register>i",
        "Send a line to the indicated endpoint",
        "Enters interactive input allowing to send a string to the endpoint "
        "indicated.",

        callback2=lambda _, reg: _do_send_stdin(
            ctx, reg, stay_in_input_mode=False, on_send_stdin=on_send_stdin))

    ctx.register_action(
        "&<Register>I",
        "Send continuously data to the indicated endpoint",
        "Enters interactive input allowing to send multiple strings to the "
        "endpoint indicated. Press ESC key to leave this mode.",

        callback2=lambda _, reg: _do_send_stdin(
            ctx, reg, stay_in_input_mode=True, on_send_stdin=on_send_stdin))

    ctx.register_action(
        "\"<Register>i",
        "Send data from command register to default endpoint",
        "",
        callback2=lambda _, reg:
            _assert_command_register_set(ctx, config, reg) and\
            _do_send_stdin(
                ctx, ctx.get_default_endpoint(),
                initial_content=config.commands.get(reg),
                stay_in_input_mode=False,
                on_send_stdin=on_send_stdin)) 

    ctx.register_action(
        "\"<Register>I",
        "Send continuously data from command register to default endpoint",
        "",
        callback2=lambda _, reg:
            _assert_command_register_set(ctx, config, reg) and\
            _do_send_stdin(
                ctx, ctx.get_default_endpoint(),
                initial_content=config.commands.get(reg),
                stay_in_input_mode=True,
                on_send_stdin=on_send_stdin)) 

    ctx.register_action(
        "\"<Register>r",
        "", "",
        callback2=lambda _, reg:
            _assert_command_register_set(ctx, config, reg) and\
            on_send_stdin(ctx.get_default_endpoint(),
                          config.commands.get(reg)))

    ctx.register_action(
        "\"<Register>s",
        "", "",
        callback2=lambda _, reg: _do_set_command_register(ctx, config, reg))

    ctx.register_action(
        "&<Register>\"<Register>i",
        "Send data from command register to indicated endpoint, edit before sending",
        "",
        callback3=lambda _, ep_reg, cmd_reg:
            _assert_command_register_set(ctx, config, cmd_reg) and\
            _do_send_stdin(
                ctx, ep_reg,
                initial_content=config.commands.get(cmd_reg),
                stay_in_input_mode=False,
                on_send_stdin=on_send_stdin)) 

    ctx.register_action(
        "&<Register>\"<Register>I",
        "Send data from command register to indicated endpoint, edit before sending, continuous",
        "",
        callback3=lambda _, ep_reg, cmd_reg:
            _assert_command_register_set(ctx, config, cmd_reg) and\
            _do_send_stdin(
                ctx, ep_reg,
                initial_content=config.commands.get(cmd_reg),
                stay_in_input_mode=True,
                on_send_stdin=on_send_stdin)) 

    ctx.register_action(
        "&<Register>\"<Register>r",
        "", "",
        callback3=lambda _, ep_reg, cmd_reg:
            _assert_command_register_set(ctx, config, cmd_reg) and\
            on_send_stdin(ep_reg, config.commands.get(cmd_reg)))


