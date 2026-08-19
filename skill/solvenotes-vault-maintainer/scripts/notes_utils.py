#!/usr/bin/env python3
"""Shared utilities for checking the Obsidian notes vault."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import re
import secrets
import stat
import sys
from pathlib import Path
from typing import BinaryIO, Callable, NoReturn

# Source-manifest normalization uses an explicit date rather than wall-clock
# time so that `--check` remains deterministic in CI.
DEFAULT_LAST_CHECKED = "2026-07-30"

NOTE_TYPES = {
    "agent_rule",
    "audit_record",
    "concept_index",
    "course_note",
    "coverage_audit",
    "exam_review",
    "game_design_note",
    "global_coverage_audit",
    "navigation",
    "paper_note",
    "paper_topic_note",
    "research_method_note",
    "review_compact",
    "review_detailed",
    "source_index",
    "source_manifest",
    "source_manifest_history",
    "template",
    "vault_audit",
}

COVERAGE_VALUES = {"checked", "generated", "source_mapped", "special_rule"}

SKIP_DIRS = {".git", ".obsidian", ".pytest_cache", ".ruff_cache", "__pycache__", "agent", "scripts", "tests"}
FORMAL_MANIFEST_EXCLUDED_TOP_LEVEL = {".github", "agent", "scripts", "tests", "模板"}
RESERVED_AGENT_NAME = "agent"
RESERVED_AGENT_RULE_NAME = "agent.md"


def is_reserved_agent_name(name: str) -> bool:
    """Match the singular ``agent`` boundary on case-insensitive filesystems."""

    return name.casefold() == RESERVED_AGENT_NAME


def is_reserved_agent_rule_name(name: str) -> bool:
    """Match ``AGENT.md`` regardless of an on-disk case-only spelling change."""

    return name.casefold() == RESERVED_AGENT_RULE_NAME


def configured_vault_root() -> Path:
    """Return the explicitly selected vault, refusing to use the Skill tree.

    The maintenance implementation lives outside the vault.  An explicit
    environment variable prevents a command launched from the Skills
    repository from accidentally scanning its own source files.
    """

    raw = os.environ.get("SOLVENOTES_VAULT_ROOT")
    if not raw:
        raise RuntimeError(
            "SOLVENOTES_VAULT_ROOT is required; point it at the external Solvenotes notes vault"
        )
    root = lexical_absolute_path(Path(raw).expanduser())
    if not root.is_dir() or not (root / "AGENT.md").is_file():
        raise RuntimeError(f"SOLVENOTES_VAULT_ROOT is not a notes vault with AGENT.md: {root}")
    return root


class UnsafePathError(OSError):
    """Raised when a repository read or publication path is not trustworthy."""


class AtomicPublishError(UnsafePathError):
    """A publication failure with explicit commit and recovery state."""

    def __init__(
        self,
        message: str,
        *,
        committed: bool,
        conflict_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.committed = committed
        self.conflict_path = conflict_path


class ConcurrentWriteError(AtomicPublishError):
    """Raised when a non-cooperating writer races atomic publication."""


class DurabilityUncertainError(AtomicPublishError):
    """Raised after commit when the directory durability sync fails."""


# Keep the exact bytes, rather than only a digest, so a cooperating
# read-transform-write path can compare the transformation input without a
# probabilistic equality assumption.
TextVersion = tuple[tuple[int, int, int, int, int, int], bytes]


def lexical_absolute_path(path: Path) -> Path:
    """Return an absolute, dot-normalized path without resolving symlinks."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    # Darwin exposes these fixed system aliases as root-level symlinks.  Map
    # only the operating-system aliases lexically; never resolve a caller-
    # controlled component such as ``vault/output``.
    if sys.platform == "darwin" and len(absolute.parts) > 1:
        aliases = {"tmp": "tmp", "var": "var", "etc": "etc"}
        mapped = aliases.get(absolute.parts[1])
        if mapped is not None:
            return Path("/private") / mapped / Path(*absolute.parts[2:])
    return absolute


ROOT = configured_vault_root()


def _relative_lexically(path: Path, root: Path) -> Path | None:
    path = lexical_absolute_path(path)
    root = lexical_absolute_path(root)
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def has_symlink_component(path: Path, root: Path) -> bool:
    """Return whether ``path`` is outside ``root`` or uses a symlink component."""

    path = lexical_absolute_path(path)
    root = lexical_absolute_path(root)
    relative = _relative_lexically(path, root)
    if relative is None:
        return True

    current = Path(root.anchor)
    for part in (*root.parts[1:], *relative.parts):
        current /= part
        if current.is_symlink():
            return True
    return False


def is_regular_file_without_symlinks(path: Path, root: Path) -> bool:
    """Return whether ``path`` is a regular file reached without symlinks."""

    return not has_symlink_component(path, root) and path.is_file()


def is_directory_without_symlinks(path: Path, root: Path) -> bool:
    """Return whether ``path`` is a directory reached without symlinks."""

    return not has_symlink_component(path, root) and path.is_dir()


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _leaf_open_flags(flags: int) -> int:
    return flags | getattr(os, "O_NOFOLLOW", 0)


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _stable_file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _exchanged_file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    """Version fields unaffected by rename-exchange's platform ctime update."""

    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_uid,
        metadata.st_gid,
    )


def _platform_exchange_names(parent_fd: int, left: str, right: str) -> None:
    """Atomically exchange two names using the native no-follow primitive."""

    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = library.renameatx_np
        # Darwin renameatx_np(2): RENAME_SWAP.
        flag = 0x00000002
    elif sys.platform.startswith("linux"):
        function = library.renameat2
        # Linux renameat2(2): RENAME_EXCHANGE.
        flag = 0x00000002
    else:
        raise AttributeError(f"unsupported platform {sys.platform}")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = function(parent_fd, os.fsencode(left), parent_fd, os.fsencode(right), flag)
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), f"{left} <-> {right}")


def _exchange_names(parent_fd: int, left: str, right: str) -> None:
    """Exchange names or fail closed; never fall back to unconditional replace."""

    try:
        _platform_exchange_names(parent_fd, left, right)
    except AttributeError as exc:
        raise UnsafePathError(
            f"atomic name exchange is unavailable on {sys.platform}; refusing unsafe replacement"
        ) from exc
    except OSError as exc:
        unsupported = {
            errno.EINVAL,
            errno.ENOSYS,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if exc.errno in unsupported:
            raise UnsafePathError(
                f"atomic name exchange is unavailable for this filesystem: {exc}"
            ) from exc
        raise


def _open_directory_without_symlinks(directory: Path, *, create: bool) -> int:
    """Open an absolute directory path component-by-component without links."""

    directory = lexical_absolute_path(directory)
    current_fd = os.open(directory.anchor, _directory_open_flags())
    try:
        for part in directory.parts[1:]:
            try:
                next_fd = os.open(part, _directory_open_flags(), dir_fd=current_fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o777, dir_fd=current_fd)
                next_fd = os.open(part, _directory_open_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _assert_directory_identity(directory: Path, expected: os.stat_result) -> None:
    """Fail if the lexical directory path no longer names the opened directory."""

    try:
        verification_fd = _open_directory_without_symlinks(directory, create=False)
    except OSError as exc:
        raise UnsafePathError(f"unsafe parent directory {directory}: {exc}") from exc
    try:
        current = os.fstat(verification_fd)
    finally:
        os.close(verification_fd)
    if _identity(current) != _identity(expected):
        raise UnsafePathError(f"parent directory identity changed: {directory}")


def _opened_directory_path(descriptor: int, fallback: Path) -> Path:
    """Return the current path of an opened directory for recovery reporting."""

    try:
        if sys.platform == "darwin":
            import fcntl

            raw = fcntl.fcntl(descriptor, 50, b"\0" * 1024)  # F_GETPATH / MAXPATHLEN
            return Path(raw.split(b"\0", 1)[0].decode(errors="surrogateescape"))
        if sys.platform.startswith("linux"):
            return Path(os.readlink(f"/proc/self/fd/{descriptor}"))
    except (OSError, ValueError):
        pass
    return fallback


def _sidecar_path(parent_fd: int, path: Path, name: str) -> Path:
    return _opened_directory_path(parent_fd, path.parent) / name


def _leaf_metadata(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _require_regular_leaf(path: Path, metadata: os.stat_result | None) -> None:
    if metadata is None:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise UnsafePathError(f"refusing symlink path: {path}")
    if not stat.S_ISREG(metadata.st_mode):
        raise UnsafePathError(f"refusing non-regular file path: {path}")


def _assert_leaf_identity(
    parent_fd: int,
    path: Path,
    expected: os.stat_result | None,
    expected_bytes: bytes | None,
) -> None:
    current = _leaf_metadata(parent_fd, path.name)
    if expected is None:
        if current is not None:
            raise UnsafePathError(f"destination appeared during write: {path}")
        return
    if current is None or _stable_file_identity(current) != _stable_file_identity(expected):
        raise UnsafePathError(f"destination identity changed during write: {path}")
    if expected_bytes is not None and _read_leaf_bytes(parent_fd, path, current) != expected_bytes:
        raise UnsafePathError(f"destination content changed during write: {path}")


def _read_leaf_bytes(parent_fd: int, path: Path, expected: os.stat_result) -> bytes:
    descriptor = os.open(path.name, _leaf_open_flags(os.O_RDONLY), dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _stable_file_identity(opened) != _stable_file_identity(expected):
            raise UnsafePathError(f"file identity changed during read: {path}")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            data = stream.read()
            finished = os.fstat(stream.fileno())
            if _stable_file_identity(finished) != _stable_file_identity(opened):
                raise UnsafePathError(f"file changed during read: {path}")
            return data
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_leaf_digest(parent_fd: int, path: Path, expected: os.stat_result) -> bytes:
    """Hash one stable regular-file version without following the leaf."""

    descriptor = os.open(path.name, _leaf_open_flags(os.O_RDONLY), dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _stable_file_identity(opened) != _stable_file_identity(expected):
            raise UnsafePathError(f"file identity changed during read: {path}")
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            finished = os.fstat(stream.fileno())
            if _stable_file_identity(finished) != _stable_file_identity(opened):
                raise UnsafePathError(f"file changed during read: {path}")
        return digest.digest()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _leaf_matches_version(
    parent_fd: int,
    path: Path,
    name: str,
    expected: os.stat_result,
    expected_digest: bytes,
) -> bool:
    """Return whether a name still exposes the exact expected file version."""

    current = _leaf_metadata(parent_fd, name)
    if current is None or not stat.S_ISREG(current.st_mode):
        return False
    if _exchanged_file_identity(current) != _exchanged_file_identity(expected):
        return False
    candidate = path.with_name(name)
    try:
        return _read_leaf_digest(parent_fd, candidate, current) == expected_digest
    except OSError:
        return False


def _leaf_is_staged_content(
    parent_fd: int,
    path: Path,
    name: str,
    stage_metadata: os.stat_result,
    stage_digest: bytes,
) -> bool:
    """Recognize the staged inode/content even if a hard-link changed ctime."""

    current = _leaf_metadata(parent_fd, name)
    if current is None or not stat.S_ISREG(current.st_mode):
        return False
    if _identity(current) != _identity(stage_metadata):
        return False
    if stat.S_IMODE(current.st_mode) != stat.S_IMODE(stage_metadata.st_mode):
        return False
    if current.st_size != stage_metadata.st_size:
        return False
    candidate = path.with_name(name)
    try:
        return _read_leaf_digest(parent_fd, candidate, current) == stage_digest
    except OSError:
        return False


def _unlink_verified_sidecar(
    parent_fd: int,
    path: Path,
    name: str,
    expected: os.stat_result,
    expected_digest: bytes,
    *,
    staged: bool,
    committed: bool,
) -> None:
    """Remove only the expected random internal sidecar version.

    The 128-bit random namespace makes accidental collision negligible, and the
    writer revalidates inode, metadata, and content immediately before unlink so
    an earlier replacement is preserved and reported.  POSIX has no portable
    unlink-if-inode operation, so this does not promise protection from an
    adversary that learns the random name and replaces it inside the final unlink
    system-call window.
    """

    matches = (
        _leaf_is_staged_content(parent_fd, path, name, expected, expected_digest)
        if staged
        else _leaf_matches_version(parent_fd, path, name, expected, expected_digest)
    )
    if not matches:
        conflict_path = _sidecar_path(parent_fd, path, name)
        raise AtomicPublishError(
            f"internal publication sidecar changed before cleanup; preserved it at {conflict_path}",
            committed=committed,
            conflict_path=conflict_path,
        )
    os.unlink(name, dir_fd=parent_fd)


def read_bytes_with_metadata(
    path: Path,
    *,
    root: Path | None = None,
) -> tuple[bytes, os.stat_result]:
    """Read a regular file and return trusted metadata without following links."""

    path = lexical_absolute_path(path)
    if root is not None and _relative_lexically(path, root) is None:
        raise UnsafePathError(f"path is outside the allowed root: {path}")
    parent_fd = _open_directory_without_symlinks(path.parent, create=False)
    try:
        parent_metadata = os.fstat(parent_fd)
        _assert_directory_identity(path.parent, parent_metadata)
        metadata = _leaf_metadata(parent_fd, path.name)
        _require_regular_leaf(path, metadata)
        if metadata is None:
            raise FileNotFoundError(path)
        return _read_leaf_bytes(parent_fd, path, metadata), metadata
    finally:
        os.close(parent_fd)


def read_bytes(path: Path, *, root: Path | None = None) -> bytes:
    """Read a regular file without following any component symlink."""

    data, _metadata = read_bytes_with_metadata(path, root=root)
    return data


def _atomic_publish_hook(_path: Path) -> None:
    """Test seam immediately before final identity checks and publication."""


def _rollback_exchanged_publish(
    parent_fd: int,
    path: Path,
    temporary_name: str,
    stage_metadata: os.stat_result,
    stage_digest: bytes,
    cause: BaseException,
) -> tuple[None, BaseException]:
    """Restore the exchanged destination or preserve every conflicting name."""

    conflict_path = _sidecar_path(parent_fd, path, temporary_name)
    if not _leaf_is_staged_content(
        parent_fd,
        path,
        path.name,
        stage_metadata,
        stage_digest,
    ):
        return None, ConcurrentWriteError(
            f"destination changed again after exchange; preserved the earlier version at {conflict_path}",
            committed=False,
            conflict_path=conflict_path,
        )

    try:
        _exchange_names(parent_fd, path.name, temporary_name)
    except BaseException as rollback_error:
        if _leaf_is_staged_content(
            parent_fd,
            path,
            temporary_name,
            stage_metadata,
            stage_digest,
        ):
            return None, ConcurrentWriteError(
                f"rollback primitive returned an error after restoring the earlier destination; "
                f"preserved staged or conflicting output at {conflict_path}: {rollback_error}",
                committed=False,
                conflict_path=conflict_path,
            )
        return None, ConcurrentWriteError(
            f"publication rollback failed ({rollback_error}); writer output remains at {path} and the "
            f"previous version is preserved at {conflict_path}",
            committed=True,
            conflict_path=conflict_path,
        )

    if not _leaf_is_staged_content(
        parent_fd,
        path,
        temporary_name,
        stage_metadata,
        stage_digest,
    ):
        return None, ConcurrentWriteError(
            f"destination changed during rollback; restored the earlier destination and preserved the "
            f"other version at {conflict_path}",
            committed=False,
            conflict_path=conflict_path,
        )

    try:
        _unlink_verified_sidecar(
            parent_fd,
            path,
            temporary_name,
            stage_metadata,
            stage_digest,
            staged=True,
            committed=False,
        )
    except OSError as cleanup_error:
        return None, AtomicPublishError(
            f"publication was rolled back, but staged output cleanup failed at {conflict_path}: "
            f"{cleanup_error}",
            committed=False,
            conflict_path=conflict_path,
        )
    return None, cause


def _committed_directory_sync(parent_fd: int, path: Path) -> None:
    """Sync a committed directory entry or report honest durability state."""

    try:
        os.fsync(parent_fd)
    except OSError as exc:
        raise DurabilityUncertainError(
            f"publication committed at {path}, but directory durability is uncertain: {exc}",
            committed=True,
        ) from exc


def _raise_interrupted_publication(
    cause: BaseException,
    *,
    path: Path,
    committed: bool,
    conflict_path: Path | None = None,
) -> NoReturn:
    """Preserve an interrupt's type while attaching observable publish state."""

    cause.committed = committed  # type: ignore[attr-defined]
    cause.conflict_path = conflict_path  # type: ignore[attr-defined]
    detail = f"atomic publication state for {path}: committed={committed}"
    if conflict_path is not None:
        detail += f", recovery={conflict_path}"
    add_note = getattr(cause, "add_note", None)
    if callable(add_note):
        add_note(detail)
    raise cause


def _atomic_publish(
    path: Path,
    writer: Callable[[BinaryIO], None],
    *,
    root: Path | None,
    unchanged_bytes: bytes | None,
    expected_version: TextVersion | None = None,
) -> tuple[bool, os.stat_result]:
    path = lexical_absolute_path(path)
    if root is not None and _relative_lexically(path, root) is None:
        raise UnsafePathError(f"path is outside the allowed root: {path}")
    if not path.name:
        raise UnsafePathError(f"destination must name a file: {path}")

    parent_fd = _open_directory_without_symlinks(path.parent, create=True)
    temporary_name: str | None = None
    sidecar_owned = False
    stage_inode_identity: tuple[int, int] | None = None
    stage_metadata: os.stat_result | None = None
    stage_digest: bytes | None = None
    try:
        parent_metadata = os.fstat(parent_fd)
        _assert_directory_identity(path.parent, parent_metadata)
        destination_metadata = _leaf_metadata(parent_fd, path.name)
        _require_regular_leaf(path, destination_metadata)
        destination_bytes: bytes | None = None
        destination_digest: bytes | None = None
        if (unchanged_bytes is not None or expected_version is not None) and destination_metadata is not None:
            destination_bytes = _read_leaf_bytes(parent_fd, path, destination_metadata)
            destination_digest = hashlib.sha256(destination_bytes).digest()
        elif destination_metadata is not None:
            destination_digest = _read_leaf_digest(parent_fd, path, destination_metadata)

        if expected_version is not None:
            expected_identity, expected_bytes = expected_version
            if (
                destination_metadata is None
                or destination_bytes is None
                or _stable_file_identity(destination_metadata) != expected_identity
                or destination_bytes != expected_bytes
            ):
                raise ConcurrentWriteError(
                    f"destination changed since transformation input was read: {path}",
                    committed=False,
                )
        if unchanged_bytes is not None and destination_bytes == unchanged_bytes:
            return False, destination_metadata  # type: ignore[return-value]

        mode = stat.S_IMODE(destination_metadata.st_mode) if destination_metadata is not None else 0o666
        for _attempt in range(100):
            candidate = f".{path.name}.conflict-{os.getpid()}-{secrets.token_hex(16)}"
            try:
                descriptor = os.open(
                    candidate,
                    _leaf_open_flags(os.O_RDWR | os.O_CREAT | os.O_EXCL),
                    mode,
                    dir_fd=parent_fd,
                )
            except FileExistsError:
                continue
            temporary_name = candidate
            sidecar_owned = True
            stage_inode_identity = _identity(os.fstat(descriptor))
            break
        else:  # pragma: no cover - requires repeated secure-token collisions
            raise FileExistsError(f"cannot allocate staging file beside {path}")

        with os.fdopen(descriptor, "w+b", closefd=True) as stream:
            writer(stream)
            stream.flush()
            if destination_metadata is not None:
                os.fchmod(stream.fileno(), stat.S_IMODE(destination_metadata.st_mode))
            os.fsync(stream.fileno())

        stage_metadata = _leaf_metadata(parent_fd, temporary_name)
        if stage_metadata is None or not stat.S_ISREG(stage_metadata.st_mode):  # pragma: no cover - O_EXCL contract
            raise UnsafePathError(f"staged output is missing or non-regular beside {path}")
        stage_digest = _read_leaf_digest(parent_fd, path.with_name(temporary_name), stage_metadata)

        _atomic_publish_hook(path)
        _assert_directory_identity(path.parent, parent_metadata)
        _assert_leaf_identity(parent_fd, path, destination_metadata, destination_bytes)

        if destination_metadata is None:
            try:
                os.link(
                    temporary_name,
                    path.name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise ConcurrentWriteError(
                    f"destination appeared during no-replace publication: {path}",
                    committed=False,
                ) from exc
            except BaseException as cause:
                if _leaf_is_staged_content(
                    parent_fd,
                    path,
                    path.name,
                    stage_metadata,
                    stage_digest,
                ):
                    _raise_interrupted_publication(cause, path=path, committed=True)
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                temporary_name = None
                _raise_interrupted_publication(
                    cause,
                    path=path,
                    committed=False,
                    conflict_path=conflict_path,
                )
            try:
                _assert_directory_identity(path.parent, parent_metadata)
            except UnsafePathError as parent_error:
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                temporary_name = None
                raise ConcurrentWriteError(
                    f"parent identity changed after no-replace publication; no public destination name "
                    f"was unlinked, and the staged alias is preserved at {conflict_path}: {parent_error}",
                    committed=True,
                    conflict_path=conflict_path,
                ) from parent_error
            except BaseException as cause:
                public_is_staged = _leaf_is_staged_content(
                    parent_fd,
                    path,
                    path.name,
                    stage_metadata,
                    stage_digest,
                )
                conflict_path = None
                if not public_is_staged:
                    conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                    temporary_name = None
                _raise_interrupted_publication(
                    cause,
                    path=path,
                    committed=True,
                    conflict_path=conflict_path,
                )
            try:
                _unlink_verified_sidecar(
                    parent_fd,
                    path,
                    temporary_name,
                    stage_metadata,
                    stage_digest,
                    staged=True,
                    committed=True,
                )
            except AtomicPublishError:
                temporary_name = None
                raise
            except OSError as cleanup_error:
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                temporary_name = None
                raise AtomicPublishError(
                    f"publication committed at {path}, but staged alias cleanup failed at "
                    f"{conflict_path}: {cleanup_error}",
                    committed=True,
                    conflict_path=conflict_path,
                ) from cleanup_error
            except BaseException as cause:
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                if _leaf_is_staged_content(
                    parent_fd,
                    path,
                    temporary_name,
                    stage_metadata,
                    stage_digest,
                ):
                    temporary_name = None
                else:
                    conflict_path = None
                _raise_interrupted_publication(
                    cause,
                    path=path,
                    committed=True,
                    conflict_path=conflict_path,
                )
            temporary_name = None
            try:
                _committed_directory_sync(parent_fd, path)
            except AtomicPublishError:
                raise
            except BaseException as cause:
                _raise_interrupted_publication(cause, path=path, committed=True)
        else:
            if destination_digest is None:  # pragma: no cover - destination implies digest
                raise AssertionError("existing destination digest is missing")
            sidecar_owned = False
            try:
                _exchange_names(parent_fd, temporary_name, path.name)
            except BaseException as cause:
                exchange_happened = _leaf_matches_version(
                    parent_fd,
                    path,
                    temporary_name,
                    destination_metadata,
                    destination_digest,
                )
                exchange_not_started = _leaf_matches_version(
                    parent_fd,
                    path,
                    path.name,
                    destination_metadata,
                    destination_digest,
                ) and _leaf_is_staged_content(
                    parent_fd,
                    path,
                    temporary_name,
                    stage_metadata,
                    stage_digest,
                )
                if exchange_not_started:
                    sidecar_owned = True
                    _raise_interrupted_publication(cause, path=path, committed=False)
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                temporary_name = None
                _raise_interrupted_publication(
                    cause,
                    path=path,
                    committed=exchange_happened,
                    conflict_path=conflict_path,
                )
            try:
                _assert_directory_identity(path.parent, parent_metadata)
            except UnsafePathError as parent_error:
                temporary_name, failure = _rollback_exchanged_publish(
                    parent_fd,
                    path,
                    temporary_name,
                    stage_metadata,
                    stage_digest,
                    parent_error,
                )
                raise failure
            except BaseException as cause:
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                temporary_name = None
                _raise_interrupted_publication(
                    cause,
                    path=path,
                    committed=True,
                    conflict_path=conflict_path,
                )
            if not _leaf_matches_version(
                parent_fd,
                path,
                temporary_name,
                destination_metadata,
                destination_digest,
            ):
                conflict = ConcurrentWriteError(
                    f"destination changed between validation and atomic exchange: {path}",
                    committed=False,
                )
                temporary_name, failure = _rollback_exchanged_publish(
                    parent_fd,
                    path,
                    temporary_name,
                    stage_metadata,
                    stage_digest,
                    conflict,
                )
                raise failure
            try:
                _unlink_verified_sidecar(
                    parent_fd,
                    path,
                    temporary_name,
                    destination_metadata,
                    destination_digest,
                    staged=False,
                    committed=True,
                )
            except AtomicPublishError:
                temporary_name = None
                raise
            except OSError as cleanup_error:
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                temporary_name = None
                raise AtomicPublishError(
                    f"publication committed at {path}, but previous-version cleanup failed at "
                    f"{conflict_path}: {cleanup_error}",
                    committed=True,
                    conflict_path=conflict_path,
                ) from cleanup_error
            except BaseException as cause:
                conflict_path = _sidecar_path(parent_fd, path, temporary_name)
                if _leaf_matches_version(
                    parent_fd,
                    path,
                    temporary_name,
                    destination_metadata,
                    destination_digest,
                ):
                    temporary_name = None
                else:
                    conflict_path = None
                _raise_interrupted_publication(
                    cause,
                    path=path,
                    committed=True,
                    conflict_path=conflict_path,
                )
            temporary_name = None
            try:
                _committed_directory_sync(parent_fd, path)
            except AtomicPublishError:
                raise
            except BaseException as cause:
                _raise_interrupted_publication(cause, path=path, committed=True)

        published = _leaf_metadata(parent_fd, path.name)
        if published is None or not stat.S_ISREG(published.st_mode):
            raise UnsafePathError(f"published file is missing or non-regular: {path}")
        return True, published
    finally:
        current_sidecar = (
            _leaf_metadata(parent_fd, temporary_name)
            if temporary_name is not None and sidecar_owned
            else None
        )
        owned_sidecar_matches = (
            current_sidecar is not None
            and stage_inode_identity is not None
            and _identity(current_sidecar) == stage_inode_identity
            and (
                stage_metadata is None
                or stage_digest is None
                or _leaf_is_staged_content(
                    parent_fd,
                    path,
                    temporary_name,
                    stage_metadata,
                    stage_digest,
                )
            )
        )
        if temporary_name is not None and sidecar_owned and owned_sidecar_matches:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def atomic_write_file(
    path: Path,
    writer: Callable[[BinaryIO], None],
    *,
    root: Path | None = None,
) -> os.stat_result:
    """Stage a complete file beside its destination and publish atomically.

    Existing regular-file Unix mode bits are preserved; ownership, ACLs,
    extended attributes, and timestamps are not part of this publication
    contract.  Existing hard links are intentionally broken by atomic name
    exchange so another name for the old inode is never truncated.  A raced
    destination is exchanged back, or every conflicting version is preserved
    with an explicit recovery path.  Once an exchange has happened, unknown
    exceptions default to preserving its random sidecar rather than deleting
    the prior version.  A post-commit directory sync failure is reported as
    committed with uncertain durability.  Missing exchange primitives fail
    closed instead of falling back to replacement.

    The 128-bit random sidecar namespace makes accidental collision negligible.
    POSIX provides no portable unlink-if-inode primitive, so cleanup revalidates
    the exact version immediately before unlink but does not promise protection
    from an adversary that learns the name and replaces it inside that final
    system-call window.
    """

    _changed, metadata = _atomic_publish(
        path,
        writer,
        root=root,
        unchanged_bytes=None,
        expected_version=None,
    )
    return metadata


def _is_supporting_markdown(path: Path, root: Path = ROOT) -> bool:
    """Keep guidance/tooling outside ordinary study-note iterators.

    The root ``AGENT.md`` is project guidance, not an Obsidian study note.  A
    non-root file with that reserved name is rejected by the guidance gate and
    must not masquerade as an ordinary note or link target before that gate
    runs.  ``agent/`` remains in ``SKIP_DIRS`` as the same fail-safe.
    """

    relative = path.relative_to(root)
    return is_reserved_agent_rule_name(relative.name)


def markdown_files(vault_root: Path | None = None) -> list[Path]:
    """Return Markdown files for quality/stat passes.

    Guidance and tooling are excluded from both the study-note population and
    the ordinary Obsidian link target population.
    """

    root = vault_root or ROOT
    if not is_directory_without_symlinks(root, root):
        return []
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if not is_regular_file_without_symlinks(path, root):
            continue
        relative_parts = path.relative_to(root).parts
        if _is_supporting_markdown(path, root) or any(
            part in SKIP_DIRS or is_reserved_agent_name(part) for part in relative_parts
        ):
            continue
        files.append(path)
    return sorted(files)


def read_text(path: Path) -> str:
    """Read a regular file and decode strict UTF-8 without hidden state."""

    text, _version = read_text_with_version(path)
    return text


def read_text_with_version(path: Path) -> tuple[str, TextVersion]:
    """Decode strict UTF-8 and return an explicit compare-before-write token."""

    data, metadata = read_bytes_with_metadata(path)
    absolute = lexical_absolute_path(path)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsafePathError(
            f"invalid UTF-8 in {absolute} at byte offset {exc.start}: {exc.reason}"
        ) from exc

    return text, (_stable_file_identity(metadata), data)


def write_text_if_changed(
    path: Path,
    text: str,
    *,
    expected_version: TextVersion | None = None,
) -> bool:
    """Publish text, optionally requiring an explicit transformation-input token."""

    encoded = text.encode("utf-8")

    def write(stream: BinaryIO) -> None:
        stream.write(encoded)

    changed, _metadata = _atomic_publish(
        path,
        write,
        root=ROOT,
        unchanged_bytes=encoded,
        expected_version=expected_version,
    )
    return changed


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + len("\n---\n") :]


def split_frontmatter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---\n", 4)
    if end == -1:
        return [], text
    header = text[4:end].splitlines()
    body = text[end + len("\n---\n") :]
    return header, body


def frontmatter_note_type(text: str) -> str | None:
    """Return an explicitly declared, supported ``note_type`` when present.

    Frontmatter is the note author's classification.  Path heuristics remain a
    fallback for new notes, but must not turn a bibliography, tutorial, or
    course summary into a paper note merely because it lives beside papers.
    """

    header, _body = split_frontmatter(text)
    for line in header:
        if not line.startswith("note_type:"):
            continue
        value = line.split(":", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value if value in NOTE_TYPES else None
    return None


def remove_fenced_code(text: str) -> str:
    kept: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            kept.append("")
            continue
        if not in_code:
            kept.append(line)
        else:
            kept.append("")
    return "\n".join(kept)


def remove_inline_code(text: str) -> str:
    return re.sub(r"`[^`]*`", "", text)


def remove_indented_code(text: str) -> str:
    """Blank CommonMark indented code blocks while preserving line count."""

    return "\n".join("" if line.startswith(("    ", "\t")) else line for line in text.splitlines())


def text_without_code(text: str) -> str:
    return remove_indented_code(remove_inline_code(remove_fenced_code(text)))


def wikilinks(text: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    # A code-like ``[[...]]`` is not an Obsidian link.  Mask all three
    # CommonMark code forms before parsing so the notes-side checker agrees
    # with the stricter skill-side scanner.
    for match in re.finditer(r"(?<!!)\[\[([^\]]+)\]\]", text_without_code(text)):
        raw = match.group(1).strip()
        if not raw:
            continue
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            matches.append((raw, target))
    return matches


def build_note_index(vault_root: Path | None = None) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    root = vault_root or ROOT
    # Ordinary Obsidian navigation resolves only to actual vault notes.  Root
    # guidance and the forbidden ``agent/`` tree never enter this index.
    for path in markdown_files(root):
        relative = path.relative_to(root).as_posix()
        no_suffix = relative[:-3] if relative.endswith(".md") else relative
        keys = {
            relative,
            no_suffix,
            path.name,
            path.stem,
            f"/{no_suffix}",
            f"/{relative}",
        }
        for key in keys:
            index.setdefault(key, []).append(path)
    return index


def wikilink_matches(
    target: str,
    source: Path,
    index: dict[str, list[Path]],
    vault_root: Path | None = None,
) -> list[Path]:
    """Return the matches from the first applicable Obsidian resolution tier.

    A leading slash is treated as an explicit vault-root path. Bare names first
    try a sibling note and only then fall back to the vault-wide basename index.
    Returning every match in one tier lets callers distinguish a missing link
    from an ambiguous basename instead of silently picking the first file.
    """

    root = vault_root or ROOT
    target = target.strip()
    if not target or "://" in target:
        return []
    candidates: list[str] = []
    explicit_root = target.startswith("/")
    clean = target.lstrip("/")

    if explicit_root:
        candidates.append(f"/{clean}")
        if not clean.endswith(".md"):
            candidates.append(f"/{clean}.md")
        candidates.append(clean)
        if not clean.endswith(".md"):
            candidates.append(f"{clean}.md")
    elif "/" in clean:
        candidates.append(clean)
        if not clean.endswith(".md"):
            candidates.append(f"{clean}.md")
    else:
        sibling = source.parent.relative_to(root).as_posix()
        if sibling != ".":
            candidates.append(f"{sibling}/{clean}")
            if not clean.endswith(".md"):
                candidates.append(f"{sibling}/{clean}.md")
        candidates.append(clean)
        if not clean.endswith(".md"):
            candidates.append(f"{clean}.md")

    seen_candidates: set[str] = set()
    for candidate in candidates:
        if candidate in seen_candidates:
            continue
        seen_candidates.add(candidate)
        matches = list(dict.fromkeys(index.get(candidate, [])))
        if matches:
            return matches
    return []


def resolve_wikilink(target: str, source: Path, index: dict[str, list[Path]]) -> Path | None:
    matches = wikilink_matches(target, source, index)
    return matches[0] if len(matches) == 1 else None


def split_table_row(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def formal_source_manifests(root: Path = ROOT) -> list[Path]:
    """Return every authoritative manifest, including nested course topics."""

    if not is_directory_without_symlinks(root, root):
        return []
    manifests: list[Path] = []
    for manifest in root.rglob("source_manifest.md"):
        if not is_regular_file_without_symlinks(manifest, root):
            continue
        relative = manifest.relative_to(root)
        if not relative.parts:
            continue
        if any(is_reserved_agent_name(part) for part in relative.parts[:-1]):
            continue
        top_level = relative.parts[0]
        if top_level.startswith(".") or top_level in FORMAL_MANIFEST_EXCLUDED_TOP_LEVEL:
            continue
        manifests.append(manifest)
    return sorted(manifests)


def manifest_rows(root: Path = ROOT) -> list[tuple[Path, list[str]]]:
    rows: list[tuple[Path, list[str]]] = []
    for manifest in formal_source_manifests(root):
        for line in read_text(manifest).splitlines():
            if not line.startswith("| `") or is_table_separator(line):
                continue
            cells = split_table_row(line)
            if cells:
                rows.append((manifest, cells))
    return rows


def escape_md_cell(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<!\\)\|", r"\|", text)


def infer_note_type(path: Path) -> str:
    relative = rel(path)
    name = path.name
    parts = path.relative_to(ROOT).parts

    # Templates are repository scaffolding even when their example frontmatter
    # demonstrates the type that a copied note should eventually use.
    if len(parts) >= 2 and parts[0] == ".obsidian" and parts[1] == "templates":
        return "template"

    # Existing valid frontmatter is authoritative.  This is essential in mixed
    # paper/course folders, where directory-level heuristics are necessarily
    # coarse.  New or malformed notes still fall through to deterministic path
    # inference so the frontmatter synchronizer can initialize them.
    if path.exists():
        declared = frontmatter_note_type(read_text(path))
        if declared is not None:
            return declared
    if name == "99_全课程PPT_PDF覆盖总审查.md":
        return "global_coverage_audit"
    if len(parts) >= 2 and parts[0] == ".obsidian" and parts[1] == "templates":
        return "template"
    if len(parts) == 1 and is_reserved_agent_rule_name(parts[0]):
        return "agent_rule"
    if parts[0] == "学习路径":
        return "navigation"
    if relative == "README.md":
        return "navigation"
    if name == "source_manifest.md":
        return "source_manifest"
    if name.endswith("_source_manifest.md"):
        return "source_manifest_history"
    if name == "99_内容覆盖审查.md":
        return "coverage_audit"
    if "来源整理记录" in name:
        return "audit_record"
    if name.startswith("00_") or "学习地图" in name or "总导航" in name or "课程总览" in name:
        return "navigation"
    if "网络资源与原始论文索引" in name:
        return "source_index"
    if "知识点详细版_含公式" in name:
        return "review_detailed"
    if "知识点精简复习版_含公式" in name:
        return "review_compact"
    if parts[0] == "概念索引":
        return "concept_index"
    if parts[0] == "游戏数值策划":
        return "game_design_note"
    if parts[0] == "科研方法论":
        return "research_method_note"
    if parts[0] in {"all-in-one", "mllm", "去雾"}:
        return "paper_note"
    if "图像Raw域去噪" in parts:
        return "paper_topic_note"
    if name.startswith("99_全仓"):
        return "vault_audit"
    return "course_note"


def note_title(path: Path, text: str | None = None) -> str:
    text = read_text(path) if text is None else text
    body = strip_frontmatter(text)
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def table_split_unescaped(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        return []
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    in_code = False
    for ch in line.strip()[1:-1]:
        if ch == "`" and not escaped:
            in_code = not in_code
        if ch == "|" and not escaped and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        escaped = ch == "\\" and not escaped
        if ch != "\\":
            escaped = False
    cells.append("".join(current).strip())
    return cells
