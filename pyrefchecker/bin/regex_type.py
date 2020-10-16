import re
from typing import Any, Optional, Union

import click


class Regex(click.ParamType):
    """
    A datetime object parsed via datetime.strptime.
    Format specifiers can be found here :
    https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
    """

    name = "regex"

    def convert(
        self,
        value: Union[re.Pattern, None, str],
        param: Optional[click.Parameter],
        ctx: Any,
    ) -> Optional[re.Pattern]:
        if value is None or isinstance(value, re.Pattern):
            return value

        try:
            return re.compile(value)
        except re.error as e:
            self.fail(
                f'Could not parse regex string "{value}": {e}',
                param,
                ctx,
            )
