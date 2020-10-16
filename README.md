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
pyrefchecker .
```

Pyrefchecker checks all files and recursively checks all directories. It returns an exit code of 0 if no files have problems, and 1 otherwise.
Files containing `import *` statements cannot be checked, so they are ignored by default. This can be changed with `--disallow-import-star`.

## Configuration

```
> poetry run pyrefchecker --help

Usage: pyrefchecker [OPTIONS] [PATHS]...

  Check python files for potentially undefined references.

  Example:

      pyrefchecker .

Options:
  --show-successes / --hide-successes
                                  When set, show checks for good files
                                  [default: (hide)]

  --timeout INTEGER               Maximum processing time for a single file
                                  [default: 5]

  --allow-import-star / --disallow-import-star
                                  Whether or not to consider `import *` a
                                  failure  [default: (allowed)]

  --exclude REGEX                 Regex for paths to exclude  [default: (\.egg
                                  s|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv
                                  |\.svn|_build|buck-out|build|dist)]

  --include REGEX                 Regex for paths to include  [default:
                                  \.pyi?$]

  --help                          Show this message and exit.
```

Commandline options can also be configured in _pyproject.toml_ under `tool.pyrefchecker`. For example

```
[tool.pyrefchecker]
allow_import_star = False
exclude = "_pb2"
```

## Examples

Here are some examples, which tools like mypy, pylint and pyflakes do not catch:

```py
if False:
    a = "Hello!"

print(a)
```

```py
try:
    assert False
    a = "Hello!"
except Exception:
    pass

print(a)
```

```py
for _ in range(0):
    a = "Hello!"

print(a)
```

However, this is a difficult problem. Since pyrefchecker does not check semantics, it does produce 'false positives'. Often, though,
the false positives are pretty weird code anyway. For example, it will warn about this, unless you include a `ref: ignore` comment:


```py
if True:
    a = "Hello!"

if True:
    print(a)  # ref: ignore
```

## Library usage

You can also use pyrefchecker as a library:

```py
import pyrefchecker

print(pyrefchecker.check("""
if True:
    a = "hello"
print(a)
"""))

# [RefWarning(line=4, column=6, reference='a')]
```
