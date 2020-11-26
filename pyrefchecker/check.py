from dataclasses import dataclass
from typing import Container, Dict, List, Set, cast

import libcst as cst
import libcst.metadata as meta

from .block_scope_provider import BlockScopeProvider, monkeypatch_nameutil
from .ignore_comment_provider import IgnoreCommentProvider
from .import_star_provider import ImportStarProvider


class BaseWarning:
    pass


class BaseRefWarning(BaseWarning):
    pass


@dataclass(frozen=True)
class RefWarning(BaseRefWarning):
    """ A warning of a potentially undefined reference at a specific location """

    line: int
    column: int
    reference: str

    def __str__(self) -> str:
        return f"Warning on line {self.line:2d}, column {self.column:2d}: reference to potentially undefined `{self.reference}`"


@dataclass(frozen=True)
class NoLocationRefWarning(BaseRefWarning):
    """ A warning of a potentially undefined reference (at an unknown location, because bugs) """

    reference: str

    def __str__(self) -> str:
        return f"Warning: reference to potentially undefined `{self.reference}`"


@dataclass(frozen=True)
class ImportStarWarning(BaseWarning):
    """ A warning of the precense of import * """

    def __str__(self) -> str:
        return f"Unable to check file, import * detected"


EXCEPTIONS = {"__file__", "__name__", "__doc__", "__package__"}

_Ranges = Dict[cst.CSTNode, meta.position_provider.CodeRange]


@dataclass(frozen=True)
class Metadata:
    scopes: Set[meta.Scope]
    ranges: _Ranges
    import_star: bool
    ignored_lines: Container[int]


def get_metadata(code: str) -> Metadata:
    """ Parse metadata about scopes, ignores, etc, from Python code """
    parsed = cst.parse_module(code)
    wrapper = cst.MetadataWrapper(parsed)

    providers = [
        BlockScopeProvider,
        meta.PositionProvider,
        ImportStarProvider,
        IgnoreCommentProvider,
    ]
    metadata = wrapper.resolve_many(providers)  # type: ignore

    scopes = cast(Set[meta.Scope], set(metadata[BlockScopeProvider].values()))

    ranges = cast(
        _Ranges,
        metadata[meta.PositionProvider],
    )

    ignored_lines = cast(Set[int], set(metadata[IgnoreCommentProvider].values()))

    return Metadata(
        scopes=scopes,
        ranges=ranges,
        import_star=len(metadata[ImportStarProvider]) > 0,
        ignored_lines=ignored_lines,
    )


@monkeypatch_nameutil()
def check(code: str) -> List[BaseWarning]:
    """ Return a list of warnings related to some Python code """
    warnings: List[BaseWarning] = []

    metadata = get_metadata(code)

    if metadata.import_star:
        return [ImportStarWarning()]

    for scope in metadata.scopes:
        if not scope:
            continue
        for access in scope.accesses:
            if len(access.referents) == 0:
                node = access.node
                if node.value not in EXCEPTIONS:
                    try:
                        location = metadata.ranges[node].start
                    except KeyError:
                        # XXX: libCST's scope provider doesn't properly handle string-y type annotations
                        warnings.append(NoLocationRefWarning(reference=str(node.value)))
                    else:
                        if location.line not in metadata.ignored_lines:
                            warnings.append(
                                RefWarning(
                                    line=location.line,
                                    column=location.column,
                                    reference=str(node.value),
                                )
                            )
    return warnings
