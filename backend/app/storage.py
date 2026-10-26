"""Blob storage for audio. Local filesystem today; the interface is small enough to back with S3/GCS."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def put_bytes(self, key: str, data: bytes) -> int: ...
    def put_file(self, key: str, source_path: str) -> int: ...
    def local_path(self, key: str) -> str: ...
    def read_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    """Stores blobs under `root/<key>`. Keys look like `usr_x/med_y.m4a` or `shared/med_z.mp3`."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Invalid storage key")
        return path

    def put_bytes(self, key: str, data: bytes) -> int:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return len(data)

    def put_file(self, key: str, source_path: str) -> int:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, path)
        return path.stat().st_size

    def local_path(self, key: str) -> str:
        return str(self._path(key))

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass

    def delete_prefix(self, prefix: str) -> None:
        path = self._path(prefix)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
