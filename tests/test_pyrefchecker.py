import pytest

from pyrefchecker import ImportStarWarning, NoLocationRefWarning, RefWarning, check


def test_if_in_else() -> None:
    code = """
if True:
    a = 1
else:
    if True:
        return True
"""
    result = check(code)
    assert not result


def test_if() -> None:
    code = """
if True:
    a = 1
print(a)
"""
    result = check(code)
    assert result == [RefWarning(line=4, column=6, reference="a")]


def test_try() -> None:
    code = """
try:
    assert False
    a = 1
except Exception:
    pass
print(a)
"""
    result = check(code)
    assert result == [RefWarning(line=7, column=6, reference="a")]


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
    result = check(code)
    assert result == [RefWarning(line=9, column=6, reference="a")]


def test_try_define_in_handler() -> None:
    code = """
try:
    assert False
    a = 1
except IndexError:
    a = 1
print(a)
"""
    result = check(code)
    assert not result


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
    result = check(code)
    assert result == [
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
    result = check(code)
    assert not result


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
    result = check(code)
    assert not result


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
    result = check(code)
    assert result == [RefWarning(line=9, column=6, reference="a")]


@pytest.mark.parametrize("stmt", ["raise", "return"])
def test_all_terminal_else(stmt: str) -> None:
    code = f"""
if False:
    a = 1
else:
    {stmt}
print(a)
"""
    result = check(code)
    assert not result


def test_import_star() -> None:
    code = f"""
from foo import *

print(yolo)
"""
    result = check(code)
    assert result == [ImportStarWarning()]


def test_import_star_fake() -> None:
    code = f"""

a = "import *"
print(a)
"""
    result = check(code)
    assert not result


def test_string_annotation() -> None:
    code = """
from typing import Set
A = str
def wrap_req(func: Set["A"]):
    pass
"""
    result = check(code)
    assert not result


def test_string_annotation_missing() -> None:
    code = """
from typing import Set

def wrap_req(func: Set["A"]):
    pass
"""
    result = check(code)
    assert result == [NoLocationRefWarning("A")]


def test_for() -> None:
    code = """
for _ in range(0):
    a = 1

print(a)
"""
    result = check(code)
    assert result == [RefWarning(line=5, column=6, reference="a")]


def test_for_else() -> None:
    code = """
for _ in range(0):
    pass
else:
    a = 1

print(a)
"""
    result = check(code)
    assert result == [RefWarning(line=7, column=6, reference="a")]


def test_ignore_comment() -> None:
    code = """
if True:
    a = 1

print(a) # ref: ignore
"""
    result = check(code)
    assert not result


def test_ignore_comment_fake() -> None:
    code = """

print(a, ''' # ref: ignore

''')
"""
    result = check(code)
    assert result == [RefWarning(line=3, column=6, reference="a")]


def test_monkeypatch() -> None:
    code = """
for a in []:
    a = lambda: None
    a()
"""
    # This test fails
    #   result = check(code) when the nameutil monkeypatch is not used
    result = check(code)
    assert not result


def test_type_complaints() -> None:
    code = """
from typing import TYPE_CHECKING
from typing import TYPE_CHECKING as is_type_checking
import typing
import typing as meep

if TYPE_CHECKING:
    from g1 import Good1
if typing.TYPE_CHECKING:
    from g2 import Good2
if is_type_checking:
    from g3 import Good3
if meep.TYPE_CHECKING == True:
    from g4 import Good4
if meep.TYPE_CHECKING == False:
    from baz import Bad1

a: Good1
b: Good2
c: Good3
d: Good4
d: Bad1
e: Bad2
"""

    result = check(code)
    assert result == [
        RefWarning(line=22, column=3, reference="Bad1"),
        RefWarning(line=23, column=3, reference="Bad2"),
    ]


def test_noreturn() -> None:
    code = """
from typing import NoReturn

def done() -> NoReturn:
    pass

if False:
    a = 10
else:
    done()

print(a)
"""
    result = check(code)
    assert not result


def test_exit_from_sys_with_alias() -> None:
    code = """
import sys as foo

if False:
    a = 10
else:
    foo.exit()

print(a)
"""
    result = check(code)
    assert not result


def test_exit_with_alias() -> None:
    code = """
from sys import exit as nope

if False:
    a = 10
else:
    nope()

print(a)
"""
    result = check(code)
    assert not result


def test_exit_in_called_function() -> None:
    code = """
from typing import NoReturn
from sys import exit

def done():
    exit()

if False:
    a = 10
else:
    done()

print(a)
"""
    result = check(code)
    assert not result


def test_os_exit_in_called_function() -> None:
    code = """
from typing import NoReturn
import os

def done():
    os._exit()

if False:
    a = 10
else:
    done()

print(a)
"""
    result = check(code)
    assert not result
