# PyRefChecker

Py-Ref checker checks for _potential_ undefined references in Python code.

## Installation

```
git clone git@github.com:brexhq/pyrefchecker.git
cd pyrefchecker
pip install --upgrade pip
pip install .
```

## Usage

```
pyrefchecker **.py
```

Pyrefchecker returns an exit code of 0 if it succeeds, and nonzero otherwise.

## Configuration

See `pyrefchecker --help` for configuration options. Options can also be configured in pyproject.toml.

## Examples

Here are some examples, which tools like mypy, pylint and pyflakes do not catch:

```
if False:
    a = "Hello!"

print(a)
```

```
try:
    assert False
    a = "Hello!"
except Exception:
    pass

print(a)
```

```
for _ in range(0):
    a = "Hello!"

print(a)
```

However, this is a difficult problem, so this tool does produce false positives. For example, it will warn about this:


```
if True:
    a = "Hello!"

if True:
    print(a) 
```
