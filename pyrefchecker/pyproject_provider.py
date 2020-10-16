from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, cast

import toml

T = TypeVar("T")


class PyProjectTOML:
    def __init__(self, key: str):
        self.key = key
        self._data: Dict[str, Any] = {}

    def load(self) -> Optional[Dict[str, Any]]:
        """ Load the pyproject.toml file """
        if not self._data:
            path = Path("pyproject.toml")
            if not path.is_file():
                return None
            self._data = cast(Dict[str, Any], toml.load(path))

            for name in self.key.split("."):
                self._data = self._data.get(name, {})

        return self._data

    def get(self, name: str, fallback: T) -> T:
        """ Get a config entry from pyproject.toml, or fallback """
        data = self.load()
        if not data or name not in data:
            return fallback
        return data[name]
