import pytest
from view.formatter import Formatter, Format

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
    format_e1 = Format()
    format_e1.background_color['FD0'] = 0
    format_e1.background_color['FD1'] = 1
    format_e1.foreground_color['FD0'] = 14
    format_e1.foreground_color['FD1'] = 15

    formatter.add_endpoint_format("E1", format_e1)

    return formatter, request.param


def test_formatting(formatter):
    fmt, param = formatter
    actual_result = fmt.format_line(param.format, param.data)
    print("\nACT: %s\nEXP: %s" % (actual_result, param.expected_result))

    assert actual_result.encode('ascii') == param.expected_result.encode('ascii')
