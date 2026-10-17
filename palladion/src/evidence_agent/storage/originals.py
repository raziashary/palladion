"""Write-once content-addressed storage for canonical source bytes."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from evidence_agent.core.ids import digest_bytes

_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


class OriginalIntegrityError(ValueError):
    """Stored bytes no longer match their content-addressed identifier."""


class OriginalNotFound(FileNotFoundError):
    """No source object exists for the requested SHA-256 digest."""


class OriginalStore:
    """Publish immutable byte objects under paths derived only from their digest.

    ``put`` writes a temporary sibling, flushes it, then creates the final name
    exclusively. Repeated publication of identical bytes is idempotent. Reads
    always verify the digest before returning bytes or a range.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise ValueError("original store root must be a directory")

    def put(self, data: bytes) -> str:
        """Atomically publish bytes and return their SHA-256 content handle."""
        if not isinstance(data, bytes):
            raise TypeError("original content must be bytes")
        digest = digest_bytes(data)
        directory = self._digest_directory(digest, create=True)
        target = directory / f"{digest}.blob"
        self._reject_symlink(target)

        if target.exists():
            self._read_verified(digest)
            return digest

        descriptor, temporary_name = tempfile.mkstemp(prefix=".pending-", dir=directory)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                # Another writer published the same digest first. It must be
                # verified before this call can safely report success.
                self._read_verified(digest)
            self._fsync_directory(directory)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return digest

    def read(self, digest: str) -> bytes:
        """Return the complete object after verifying its digest."""
        return self._read_verified(digest)

    def read_range(self, digest: str, start_byte: int, end_byte: int) -> bytes:
        """Return the half-open byte range ``[start_byte, end_byte)``."""
        if isinstance(start_byte, bool) or isinstance(end_byte, bool):
            raise TypeError("byte offsets must be integers")
        if not isinstance(start_byte, int) or not isinstance(end_byte, int):
            raise TypeError("byte offsets must be integers")
        data = self._read_verified(digest)
        if start_byte < 0 or end_byte < start_byte or end_byte > len(data):
            raise ValueError("byte range is outside the original content")
        return data[start_byte:end_byte]

    def path_for(self, digest: str) -> Path:
        """Return the verified store-owned path for diagnostics and tests."""
        path = self._object_path(digest)
        self._reject_symlink(path)
        return path

    def _read_verified(self, digest: str) -> bytes:
        path = self._object_path(digest)
        self._reject_symlink(path)
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise OriginalNotFound(digest) from exc
        if digest_bytes(data) != digest:
            raise OriginalIntegrityError("original content does not match its SHA-256 handle")
        return data

    def _object_path(self, digest: str) -> Path:
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ValueError("content handle must be a lowercase SHA-256 digest")
        directory = self._digest_directory(digest, create=False)
        path = directory / f"{digest}.blob"
        if path.parent != self.root / digest[:2]:
            raise ValueError("content handle resolved outside the store")
        return path

    def _digest_directory(self, digest: str, *, create: bool) -> Path:
        directory = self.root / digest[:2]
        try:
            if create:
                directory.mkdir(mode=0o700, exist_ok=True)
        except FileExistsError as exc:
            raise OriginalIntegrityError("content directory is not a directory") from exc
        if directory.is_symlink():
            raise OriginalIntegrityError("content directory must not be a symlink")
        if create and not directory.is_dir():
            raise OriginalIntegrityError("content directory is not a directory")
        if directory.resolve() != directory:
            raise OriginalIntegrityError("content directory resolves outside its store path")
        return directory

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise OriginalIntegrityError("content object must not be a symlink")

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
