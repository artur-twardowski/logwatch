import pytest
from server.separators.by_brackets import ByBracketsSeparator


def test_sep_basic():
    emitted_events = []
    sep = ByBracketsSeparator({}, lambda fd, data: emitted_events.append((fd, data)))

    sep.feed("fd0", "header {x, y}")
    assert len(emitted_events) == 1
    assert emitted_events[0] == ("fd0", "header {x, y}")


def test_sep_many():
    emitted_events = []
    sep = ByBracketsSeparator({}, lambda fd, data: emitted_events.append((fd, data)))

    sep.feed("fd0", "header {x, y} header2 {j, k}")
    assert len(emitted_events) == 2
    assert emitted_events[0] == ("fd0", "header {x, y}")
    assert emitted_events[1] == ("fd0", " header2 {j, k}")


def test_sep_partial():
    emitted_events = []
    sep = ByBracketsSeparator({}, lambda fd, data: emitted_events.append((fd, data)))

    sep.feed("fd0", "some structure {da")
    assert len(emitted_events) == 0

    sep.feed("fd0", "ta} anoth")
    assert len(emitted_events) == 1
    assert emitted_events[0] == ("fd0", "some structure {data}")

    sep.feed("fd0", "er {}")
    assert len(emitted_events) == 2
    assert emitted_events[1] == ("fd0", " another {}")


def test_sep_with_quotes():
    emitted_events = []
    sep = ByBracketsSeparator({}, lambda fd, data: emitted_events.append((fd, data)))

    sep.feed("fd0", 'some structure {data "}"}')
    assert len(emitted_events) == 1
    assert emitted_events[0] == ("fd0", 'some structure {data "}"}')


def test_sep_nested():
    emitted_events = []
    sep = ByBracketsSeparator({"trim": True}, lambda fd, data: emitted_events.append((fd, data)))

    sep.feed("fd0", '{ a { b { c, d } } e { x } } {z {x} c}')
    assert len(emitted_events) == 2
    assert emitted_events[0] == ("fd0", '{ a { b { c, d } } e { x } }')
    assert emitted_events[1] == ("fd0", '{z {x} c}')




