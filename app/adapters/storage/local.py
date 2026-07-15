"""Immutable content-addressed local evidence storage."""

import hashlib
import io
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class StoredFile:
    file_id: str
    uri: str
    sha256: str


class LocalEvidenceStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def store_path(self, source: Path, category: str) -> StoredFile:
        with source.open("rb") as stream:
            return self.store_bytes(stream.read(), source.suffix.lower(), category)

    def store_bytes(self, content: bytes, suffix: str, category: str) -> StoredFile:
        digest = hashlib.sha256(content).hexdigest()
        file_id = f"FILE-{uuid4().hex}"
        relative = Path(category) / digest[:2] / f"{file_id}{suffix}"
        destination = self._root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with io.BytesIO(content) as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        return StoredFile(file_id=file_id, uri=relative.as_posix(), sha256=digest)

    @staticmethod
    def hash_path(source: Path) -> str:
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def delete_uri(self, uri: str) -> None:
        """Delete a stored test artifact while preventing paths outside the evidence root."""
        root = self._root.resolve()
        target = (root / Path(uri)).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Evidence URI escapes the configured storage root")
        target.unlink(missing_ok=True)
