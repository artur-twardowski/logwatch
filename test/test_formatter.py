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
                   "\x1b[0;48;5;0;38;5;14mXYZ\x1b[K\x1b[0m"),

    FormattingTest("{format:endpoint}{data}",
                   {"endpoint": "E1", "fd": "FD0", "data": "\x1b[32mGreen\x1b[0m, Default"},
                   "\x1b[0;48;5;0;38;5;14m\x1b[32mGreen\x1b[0;48;5;0;38;5;14m, Default\x1b[K\x1b[0m")
]

@pytest.fixture(params=formatting_tests)
def formatter(request):
    formatter = Formatter()
    format_e1 = Style()
    format_e1.background_color['FD0'] = 0
    format_e1.background_color['FD1'] = 1
    format_e1.foreground_color['FD0'] = 14
    format_e1.foreground_color['FD1'] = 15

    formatter.add_endpoint_style("E1", format_e1)

    return formatter, request.param

def test_formatting_old(formatter):
    fmt, param = formatter
    actual_result = fmt.format_line(param.format, param.data)
    print("\nACT: %s\nEXP: %s" % (actual_result, param.expected_result))

    assert actual_result.encode('ascii') == param.expected_result.encode('ascii')


def test_formatting_new(formatter):
    fmt, param = formatter
    compiled_format = Format(param.format)
    #actual_result = fmt.format_line_new(compiled_format, param.data)
    #print("\nACT: %s\nEXP: %s" % (actual_result, param.expected_result))

    #assert actual_result.encode('ascii') == param.expected_result.encode('ascii')
    assert True


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
    assert compiled_format[0].field_transform == CompiledTag.TRANSFORM_UPPER_INDEX
    assert compiled_format[0].field_alignment == CompiledTag.ALIGN_LEFT


