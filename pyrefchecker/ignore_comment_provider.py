from typing import Optional

import libcst as cst
from libcst.metadata.base_provider import BatchableMetadataProvider


class IgnoreCommentProvider(BatchableMetadataProvider[int]):
    """ Records the line numbers of any 'ref: ignore' - comments """

    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def visit_Comment(self, node: cst.Comment) -> Optional[bool]:
        if "ref: ignore" in node.value:
            comment_loc = self.get_metadata(cst.metadata.PositionProvider, node)
            line = comment_loc.start.line
            self.set_metadata(node, line)
        return None
