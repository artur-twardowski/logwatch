from view.interactive_mode import InteractiveModeContext
from view.configuration import Configuration
from view.interactive_mode.input_views import ComplexInputView
from view.interactive_mode.input_views import ComplexInputSubprompt
from view.formatter import get_default_register_format, encode_color
from common import AVAILABLE_REGISTERS


def _enter_watch_editor(interact: InteractiveModeContext,
                        config: Configuration,
                        register: str,
                        set_watch_cb: callable):
    if register in config.watches:
        watch = config.watches[register]
        regex = watch.regex
        replacement = watch.replacement
        bg_color, fg_color = watch.format.get()
    else:
        regex = ""
        replacement = None
        bg_color, fg_color = get_default_register_format(register)

    interact.enter_view(ComplexInputView(
        prompt="Set watch '" + register,
        subprompts=[
            ComplexInputSubprompt("Regular expression", regex),
            ComplexInputSubprompt("Replacement", replacement),
            ComplexInputSubprompt("Background color", encode_color(bg_color)),
            ComplexInputSubprompt("Foreground color", encode_color(fg_color))
        ],
        on_confirm=lambda regex, replacement, bg_color, fg_color, r=register: (
            set_watch_cb(r, (regex, replacement, bg_color, fg_color)) and \
            interact.return_to_predicate_mode()),
        on_cancel=lambda: interact.return_to_predicate_mode()))


def _find_first_available_watch(config: Configuration):
    for w in AVAILABLE_REGISTERS:
        if w not in config.watches:
            return w
    return None


def _delete_watch(register, on_set_watch: callable):
    on_set_watch(register, ('', '', -1, -1))


def _assert_watch_set(ctx: InteractiveModeContext, config: Configuration, register):
    if register in config.watches:
        return True
    else:
        ctx.show_message("Register '%c has not been set" % register)
        return False


def install(ctx: InteractiveModeContext,
            config: Configuration,
            on_set_watch: callable,
            on_watch_set_enable: callable):
    ctx.register_action(
        "w",
        "Set a watch in first available register",
        "Enters interactive input allowing to configure a watch. Picks first "
        "available register.",
        callback1=lambda _: _enter_watch_editor(
            ctx, config, _find_first_available_watch(config), on_set_watch))

    ctx.register_action(
        "'<Register>w",
        "Set a watch in specified register",
        "Enters interactive input allowing to configure a watch under the "
        "register specified",
        callback2=lambda _, reg: _enter_watch_editor(
            ctx, config, reg, on_set_watch))

    ctx.register_action(
        "'<Register>d",
        "Disable a watch",
        "Disables a watch defined under register specified",
        callback2=lambda _, reg: on_watch_set_enable(reg, False))

    ctx.register_action(
        "'<Register>e",
        "Enable a watch",
        "Enables a watch defined under register specified",
        callback2=lambda _, reg: on_watch_set_enable(reg, True))

    ctx.register_action(
        "'<Register>D",
        "Delete a watch",
        "Deletes a watch by clearing the indicated watch register.",
        callback2=lambda _, reg: 
            _assert_watch_set(ctx, config, reg) and \
            _delete_watch(reg, on_set_watch))

    ctx.register_action(
        "''<Register><Register>*;d",
        "Disable multiple watches",
        "",
        callback4=lambda _1, _2, reg1, regs: on_watch_set_enable(reg1 + regs,
                                                                 False))

    ctx.register_action(
        "''<Register><Register>*;e",
        "Enable multiple watches",
        "",
        callback4=lambda _1, _2, reg1, regs: on_watch_set_enable(reg1 + regs,
                                                                 True))
