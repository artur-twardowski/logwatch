import pytest
from view.formatter import Formatter, Format, Style, CompiledTag

class FormattingTest:
    def __init__(self, fmt, data, expected_result):
        self.format = fmt
        self.data = data
        self.expected_result = expected_result

formatting_tests = [
    FormattingTest("{format:endpoint}{data}",
                   {"endpoint": "E1", "fd": "FD0", "data": "XYZ"},
                   "\x1b[0m\x1b[48;5;0;38;5;14mXYZ\x1b[K\x1b[0m"),

    FormattingTest("{format:endpoint}{data}",
                   {"endpoint": "E1", "fd": "FD0", "data": "\x1b[32mGreen\x1b[0m, Default"},
                   "\x1b[0m\x1b[48;5;0;38;5;14m\x1b[32mGreen\x1b[0m\x1b[48;5;0;38;5;14m, Default\x1b[K\x1b[0m"),

    FormattingTest("{format:endpoint}{data}",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "\x1b[32mGreen\x1b[0m, Default"},
                   "\x1b[0m\x1b[48;5;18;38;5;15m\x1b[32mGreen\x1b[0m\x1b[48;5;18;38;5;15m, Default\x1b[K\x1b[0m"),

    FormattingTest("{format:watch}{data}",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "\x1b[32mGreen\x1b[0m, Default"},
                   "\x1b[0m\x1b[48;5;254;38;5;4m\x1b[32mGreen\x1b[0m\x1b[48;5;254;38;5;4m, Default\x1b[K\x1b[0m"),

    FormattingTest("{format:default}{data}",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "\x1b[32mGreen\x1b[0m, Default"},
                   "\x1b[0m\x1b[48;5;254;38;5;4m\x1b[32mGreen\x1b[0m\x1b[48;5;254;38;5;4m, Default\x1b[K\x1b[0m"),

    FormattingTest("{format:default,plain}{data}",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "\x1b[32mGreen\x1b[0m, Default"},
                   "\x1b[0m\x1b[48;5;254;38;5;4mGreen\x1b[48;5;254;38;5;4m, Default\x1b[K\x1b[0m"),

    FormattingTest("[{data}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "123"},
                   "\x1b[0m[123]\x1b[K\x1b[0m"),

    FormattingTest("[{data:6}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "123"},
                   "\x1b[0m[   123]\x1b[K\x1b[0m"),

    FormattingTest("[{data:06}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "123"},
                   "\x1b[0m[000123]\x1b[K\x1b[0m"),

    FormattingTest("[{data:>6}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "123"},
                   "\x1b[0m[   123]\x1b[K\x1b[0m"),

    FormattingTest("[{data:^}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "123"},
                   "\x1b[0m[¹²³]\x1b[K\x1b[0m"),

    FormattingTest("[{data:_}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "123"},
                   "\x1b[0m[₁₂₃]\x1b[K\x1b[0m"),

    FormattingTest("[{data:<10}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "qwerty"},
                   "\x1b[0m[qwerty    ]\x1b[K\x1b[0m"),

    FormattingTest("[{data:<A10}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "qwerty"},
                   "\x1b[0m[QWERTY    ]\x1b[K\x1b[0m"),

    FormattingTest("[{data:<a10}]",
                   {"endpoint": "E1", "fd": "FD1", "watch": "w", "data": "QweRty"},
                   "\x1b[0m[qwerty    ]\x1b[K\x1b[0m"),

]

@pytest.fixture(params=formatting_tests)
def formatter(request):
    formatter = Formatter()
    format_e1 = Style()
    format_e1.background_color = {'FD0': 0, 'FD1': 18}
    format_e1.foreground_color = {'FD0': 14, 'FD1': 15}

    format_watch = Style()
    format_watch.background_color = {'default': 254}
    format_watch.foreground_color = {'default': 4}

    formatter.add_endpoint_style("E1", format_e1)
    formatter.add_watch_format('w', format_watch)

    return formatter, request.param


def test_formatting(formatter):
    fmt, param = formatter
    compiled_format = Format(param.format)
    actual_result = fmt.format_line(compiled_format, param.data)
    print("\nACT: %s\nEXP: %s" % (actual_result, param.expected_result))

    assert actual_result.encode('utf-8') == param.expected_result.encode('utf-8')


def test_compilation_literal():
    compiled_format = Format("ABC").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], str)
    assert compiled_format[0] == "ABC"


def test_compilation_style():
    compiled_format = Format("{format:endpoint}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.USE_ENDPOINT_STYLE
    assert compiled_format[0].field_transform == 0


def test_compilation_style_plain():
    compiled_format = Format("{format:endpoint,plain}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.USE_ENDPOINT_STYLE
    assert compiled_format[0].field_transform == CompiledTag.TRANSFORM_DISCARD_ANSI


def test_compilation_field1():
    compiled_format = Format("{data}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.PRINT_FIELD
    assert compiled_format[0].field_name == "data"


def test_compilation_field2():
    compiled_format = Format("{data:10}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.PRINT_FIELD
    assert compiled_format[0].field_name == "data"
    assert compiled_format[0].field_width == 10


def test_compilation_field3():
    compiled_format = Format("{data:<^7}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.PRINT_FIELD
    assert compiled_format[0].field_name == "data"
    assert compiled_format[0].field_width == 7
    assert compiled_format[0].field_transform == CompiledTag.TRANSFORM_SUPERSCRIPT
    assert compiled_format[0].field_align == CompiledTag.ALIGN_LEFT


def test_compilation_field4():
    compiled_format = Format("{data:<7}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.PRINT_FIELD
    assert compiled_format[0].field_name == "data"
    assert compiled_format[0].field_width == 7
    assert compiled_format[0].field_transform == 0
    assert compiled_format[0].field_align == CompiledTag.ALIGN_LEFT


def test_compilation_field5():
    compiled_format = Format("{data:>7}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.PRINT_FIELD
    assert compiled_format[0].field_name == "data"
    assert compiled_format[0].field_width == 7
    assert compiled_format[0].field_transform == 0
    assert compiled_format[0].field_align == CompiledTag.ALIGN_RIGHT


def test_compilation_field6():
    compiled_format = Format("{data:>07}").get()
    assert len(compiled_format) == 1
    assert isinstance(compiled_format[0], CompiledTag)
    assert compiled_format[0].type == CompiledTag.PRINT_FIELD
    assert compiled_format[0].field_name == "data"
    assert compiled_format[0].field_width == 7
    assert compiled_format[0].field_transform == 0
    assert compiled_format[0].field_pad == '0'
    assert compiled_format[0].field_align == CompiledTag.ALIGN_RIGHT


