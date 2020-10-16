import pytest

from pyrefchecker import (
    ImportStarWarning,
    NoLocationRefWarning,
    RefWarning,
    check,
    monkeypatch_nameutil,
)


def test_if_in_else() -> None:
    code = """
if True:
    a = 1
else:
    if True:
        return True
"""
    assert not check(code)


def test_if() -> None:
    code = """
if True:
    a = 1
print(a)
"""
    assert check(code) == [RefWarning(line=4, column=6, reference="a")]


def test_try() -> None:
    code = """
try:
    assert False
    a = 1
except Exception:
    pass
print(a)
"""
    assert check(code) == [RefWarning(line=7, column=6, reference="a")]


def test_try_finally() -> None:
    code = """
try:
    assert False
    a = 1
except Exception:
    pass
finally:
    b = 1
print(a)
print(b)
"""
    assert check(code) == [RefWarning(line=9, column=6, reference="a")]


def test_try_define_in_handler() -> None:
    code = """
try:
    assert False
    a = 1
except IndexError:
    a = 1
print(a)
"""
    assert not check(code)


def test_try_define_in_multiple_handlers() -> None:
    code = """
try:
    assert True
except IndexError:
    a = 1
except SyntaxError:
    b = 1

print(a)
print(b)
"""
    assert check(code) == [
        RefWarning(line=9, column=6, reference="a"),
        RefWarning(line=10, column=6, reference="b"),
    ]


def test_try_except_else() -> None:
    code = """
try:
    assert True
    a = 1
except IndexError:
    pass
except SyntaxError:
    pass
else:
    print(a)

"""
    assert not check(code)


@pytest.mark.parametrize("stmt", ["raise", "return"])
def test_terminal_except(stmt: str) -> None:
    code = f"""
try:
    assert False
    a = 1
except Exception:
    {stmt}
print(a)
"""
    assert not check(code)


@pytest.mark.parametrize("stmt", ["raise", "return"])
def test_not_all_terminal_except(stmt: str) -> None:
    code = f"""
try:
    assert False
    a = 1
except ImportError:
    pass
except SyntaxError:
    {stmt}
print(a)
"""
    assert check(code) == [RefWarning(line=9, column=6, reference="a")]


@pytest.mark.parametrize("stmt", ["raise", "return"])
def test_all_terminal_else(stmt: str) -> None:
    code = f"""
if False:
    a = 1
else:
    {stmt}
print(a)
"""
    assert not check(code)


def test_import_star() -> None:
    code = f"""
from foo import *

print(yolo)
"""
    assert check(code) == [ImportStarWarning()]


def test_import_star_fake() -> None:
    code = f"""

a = "import *"
print(a)
"""
    assert not check(code)


def test_string_annotation() -> None:
    code = """
from typing import Set
A = str
def wrap_req(func: Set["A"]):
    pass
"""
    assert not check(code)


def test_string_annotation_missing() -> None:
    code = """
from typing import Set

def wrap_req(func: Set["A"]):
    pass
"""
    assert check(code) == [NoLocationRefWarning("A")]


def test_for() -> None:
    code = """
for _ in range(0):
    a = 1

print(a)
"""
    assert check(code) == [RefWarning(line=5, column=6, reference="a")]


def test_for_else() -> None:
    code = """
for _ in range(0):
    pass
else:
    a = 1

print(a)
"""
    assert check(code) == [RefWarning(line=7, column=6, reference="a")]


def test_ignore_comment() -> None:
    code = """
if True:
    a = 1

print(a) # ref: ignore
"""
    assert not check(code)


def test_ignore_comment_fake() -> None:
    code = """

print(a, ''' # ref: ignore

''')
"""
    assert check(code) == [RefWarning(line=3, column=6, reference="a")]


def test_monkeypatch() -> None:
    code = """
for a in []:
    a = lambda: None
    a()
"""
    # This fails without the monkey patch...
    with pytest.raises(Exception, match=r"Unexpected Scope"):
        check(code)

    # And succeeds with it
    monkeypatch_nameutil()
    assert not check(code)
