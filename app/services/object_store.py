"""Uploaded-file storage behind one interface (BUILD_SPEC.md section 1).

Callers only use put/get/exists with opaque string keys, so moving to S3/MinIO means
adding one class here and returning it from get_object_store().
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class LocalObjectStore:
    def __init__(self, root: Path):
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise ValueError(f"Object key escapes the storage root: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except ValueError:
            return False


@lru_cache
def get_object_store() -> ObjectStore:
    return LocalObjectStore(get_settings().storage_dir)
