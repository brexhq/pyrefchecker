from .block_scope_provider import monkeypatch_nameutil

# XXX: This is kind of ugly
monkeypatch_nameutil()

import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List

import click
import timeout_decorator

from .check import BaseRefWarning, ImportStarWarning, Warnings, check
from .pyproject_provider import PyProjectTOML

defaults = PyProjectTOML("tool.pyrefchecker")


def check_file(path: str, timeout_seconds: int = 5) -> List[Warnings]:
    """ Read a file path and check it for errors """

    text = Path(path).read_text()
    return timeout_decorator.timeout(timeout_seconds)(check)(text)


@click.command()
@click.argument(
    "infiles",
    type=click.Path(
        exists=True, readable=True, allow_dash=False, file_okay=True, dir_okay=False
    ),
    nargs=-1,
)
@click.option(
    "--show-successes/--no-show-successes",
    default=defaults.get("show_successes", False),
    help="When set, show checks for good files (default: show)",
)
@click.option(
    "--timeout",
    type=int,
    default=defaults.get("timeout", 5),
    help="Maximum processing time for a single file (default: 5)",
)
@click.option(
    "--allow-import-star/--disallow-import-star",
    default=defaults.get("allow_import_star", True),
    help="Whether or not to consider `import *` a failure (default: allowed)",
)
def main(
    infiles: Iterable[str], show_successes: bool, timeout: int, allow_import_star: bool
) -> None:
    """
    Check python files for potentially undefined references.

    Example:

        pyrefchecker **.py

    """

    failed = False

    with ProcessPoolExecutor() as e:
        futures = {e.submit(check_file, x, timeout_seconds=timeout): x for x in infiles}
        for future in as_completed(futures.keys()):
            infile = futures[future]

            try:
                warnings = future.result()
            except timeout_decorator.TimeoutError as e:
                click.echo(f"🚩 {infile}: Timed out")
            except Exception as e:
                raise Exception(f"Error processing {infile}") from e
            else:
                for warning in warnings:
                    # TODO: Maybe do this without isinstance
                    if isinstance(warning, BaseRefWarning):
                        failed = True
                        click.echo(f"⚠️  {infile}: {warning}")
                    elif isinstance(warning, ImportStarWarning):
                        emoji = "❔"
                        if not allow_import_star:
                            failed = True
                            emoji = "⚠️"
                        click.echo(f"{emoji} {infile}: {warning}")
                if show_successes and not warnings:
                    click.echo(f"✅ {infile}")

    if failed:
        sys.exit(1)

    else:
        click.echo(f"✅ all good!")
