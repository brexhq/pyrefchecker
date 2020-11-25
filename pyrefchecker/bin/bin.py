import re
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Optional, Union

import click
import timeout_decorator

from .. import BaseRefWarning, BaseWarning, ImportStarWarning, check
from .find_files import find_files
from .pyproject_toml import PyProjectTOML
from .regex_type import Regex

defaults = PyProjectTOML("tool.pyrefchecker")

# Copied from Black!
DEFAULT_EXCLUDE = r"(\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|buck-out|build|dist)"


@click.command()
@click.argument(
    "paths",
    type=click.Path(
        exists=True, readable=True, allow_dash=False, file_okay=True, dir_okay=True
    ),
    nargs=-1,
)
@click.option(
    "--show-successes/--hide-successes",
    default=defaults.get("show_successes", False),
    help="When set, show checks for good files",
    show_default="show" if defaults.get("show_successes", False) else "hide",
)
@click.option(
    "--timeout",
    type=int,
    default=defaults.get("timeout", 5),
    help="Maximum processing time for a single file",
    show_default=True,
)
@click.option(
    "--allow-import-star/--disallow-import-star",
    default=defaults.get("allow_import_star", True),
    help="Whether or not to consider `import *` a failure",
    show_default="allowed" if defaults.get("allow_import_star", True) else "disallowed",
)
@click.option(
    "--include",
    type=Regex(),
    default=defaults.get("include", r"\.pyi?$"),
    help="Regex for paths to include",
    show_default=True,
)
@click.option(
    "--exclude",
    type=Regex(),
    default=defaults.get("exclude", DEFAULT_EXCLUDE),
    help="Regex for paths to exclude. When specified, the default is replaced.",
    show_default=True,
)
@click.option(
    "--extra-excludes",
    type=Regex(),
    multiple=True,
    default=defaults.get("extra_excludes", []),
    help="Additional regexes for paths to exclude",
    show_default=False,
)
def main(
    paths: Iterable[Union[str, Path]],
    show_successes: bool,
    timeout: int,
    allow_import_star: bool,
    include: Optional[re.Pattern],
    exclude: Optional[re.Pattern],
    extra_excludes: List[re.Pattern],
) -> None:
    """
    Check python files for potentially undefined references.

    Example:

        pyrefchecker .

    """

    excludes = [x for x in [exclude, *extra_excludes] if x is not None]
    paths = find_files(paths, include, excludes)

    if not paths:
        raise click.UsageError("No files specified")

    if not run(
        paths,
        timeout=timeout,
        allow_import_star=allow_import_star,
        show_successes=show_successes,
    ):
        sys.exit(1)

    else:
        click.echo(f"✨ all good!")


def run(
    paths: Iterable[Union[str, Path]],
    timeout: int,
    allow_import_star: bool,
    show_successes: bool,
) -> bool:
    """
    Check all provided paths, using all available processors.
    Echo warnings (and optionally successes) on stdout.
    Return True if no files had any warnings.
    """
    success = True

    with ProcessPoolExecutor() as e:
        futures = {e.submit(check_file, x, timeout_seconds=timeout): x for x in paths}
        try:
            for future in as_completed(futures.keys()):
                infile = futures[future]
                try:
                    warnings = future.result()
                except timeout_decorator.TimeoutError as e:
                    click.echo(f"⏰ {infile}: Timed out")
                except Exception:
                    # Exit early if any files could not be processed
                    for future in futures:
                        future.cancel()
                    traceback.print_exc(file=sys.stderr)
                    click.echo(
                        f"\n❌ {infile}: Failed to process due to the above exception"
                    )
                    return False
                else:
                    for warning in warnings:
                        # TODO: Maybe do this without isinstance
                        if isinstance(warning, BaseRefWarning):
                            success = False
                            click.echo(f"⚠️  {infile}: {warning}")
                        elif isinstance(warning, ImportStarWarning):
                            emoji = "❔"
                            if not allow_import_star:
                                success = False
                                emoji = "⚠️"
                            click.echo(f"{emoji} {infile}: {warning}")
                    if show_successes and not warnings:
                        click.echo(f"✅ {infile}")
        except KeyboardInterrupt:
            # Without this, ctrl-c causes the process to hang waiting
            # for all unscheduled tasks to complete.
            for future in futures:
                future.cancel()
            click.echo(f"🛑 Interrupted", err=True)
            return False

    return success


def check_file(path: Union[str, Path], timeout_seconds: int = 5) -> List[BaseWarning]:
    """ Read a file path and check it for errors """

    text = Path(path).read_text()
    return timeout_decorator.timeout(timeout_seconds)(check)(text)
