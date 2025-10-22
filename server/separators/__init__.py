from .by_newline import ByNewlineSeparator
from .by_brackets import ByBracketsSeparator
from utils import lw_assert

def create_separator(configuration, on_data_emit_cb: callable):
    lw_assert('method' in configuration,
              "\"method\" field must be specified for event separation specification")
    method_name = configuration["method"]

    CLASSES = [ByNewlineSeparator, ByBracketsSeparator]

    for cls in CLASSES:
        if method_name == cls.NAME:
            return cls(configuration, on_data_emit_cb)
    raise RuntimeError("Invalid event separation method: %s" % method_name)

