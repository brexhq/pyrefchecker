import re
from pathlib import Path
from typing import Iterable, Optional, Set, Union


def find_files(
    paths: Iterable[Union[str, Path]],
    include: Optional[re.Pattern],
    exclude: Optional[re.Pattern],
) -> Set[Path]:
    """
    Recurse any directories specified in 'paths', and include any files specified.

    For recursive searches, only include paths which match 'include'.
    For all paths, exclude any which match 'exclude'.
    """
    final_paths: Set[Path] = set()

    for path in paths:
        p = Path(path)
        if p.is_dir():
            final_paths.update(
                x for x in p.glob("**/*") if (not include or include.search(str(x)))
            )
        elif p.is_file():
            final_paths.add(Path(p))

    if exclude:
        final_paths = {x for x in final_paths if not exclude.search(str(x))}
    return final_paths
