from typing import Optional

import libcst as cst
from libcst.metadata.base_provider import BatchableMetadataProvider


class ImportStarProvider(BatchableMetadataProvider[bool]):
    """ Picks out any "import *" nodes """

    def visit_ImportStar(self, node: cst.ImportStar) -> Optional[bool]:
        self.set_metadata(node, True)
        return None
