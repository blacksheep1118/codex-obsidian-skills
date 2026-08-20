"""Fail-closed helpers for command-line output files."""

from __future__ import annotations

import os
import secrets
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

TRUSTED_TOP_LEVEL_ALIASES = (
    {
        Path("/etc"): Path("/private/etc"),
        Path("/tmp"): Path("/private/tmp"),
        Path("/var"): Path("/private/var"),
    }
    if sys.platform == "darwin"
    else {}
)


class InputRootError(ValueError):
    """Stable public error for an invalid directory scan root."""

    REASON = "root must be an existing directory without symlink components"

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"{path}: {self.REASON}")


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _normalize_top_level_alias(path: Path) -> Path:
    """Resolve only a platform-owned first component such as macOS /var."""

    absolute = _absolute_path(path)
    anchor = Path(absolute.anchor)
    relative = absolute.relative_to(anchor)
    if not relative.parts:
        return absolute
    first = anchor / relative.parts[0]
    try:
        first_mode = first.lstat().st_mode
    except FileNotFoundError:
        return absolute
    if not stat.S_ISLNK(first_mode):
        return absolute
    expected = TRUSTED_TOP_LEVEL_ALIASES.get(first)
    if expected is None:
        raise ValueError(f"path contains untrusted top-level symlink: {first}")
    try:
        resolved_first = first.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"path contains unsafe top-level symlink: {first}") from exc
    if resolved_first != expected or not resolved_first.is_dir():
        raise ValueError(f"top-level path alias has unexpected target: {first} -> {resolved_first}")
    return resolved_first.joinpath(*relative.parts[1:])


def _directory_flags() -> int:
    flags = os.O_RDONLY
    for name in ("O_DIRECTORY", "O_CLOEXEC", "O_NOFOLLOW"):
        flags |= getattr(os, name, 0)
    return flags


def _supports_dir_fd() -> bool:
    return os.name != "nt" and os.open in os.supports_dir_fd and os.mkdir in os.supports_dir_fd


def _open_directory_fd(path: Path, *, create: bool) -> tuple[Path, int]:
    """Open each directory component relative to the previously verified one."""

    candidate = _normalize_top_level_alias(path)
    anchor = Path(candidate.anchor)
    descriptor = os.open(anchor, _directory_flags())
    current = anchor
    try:
        for component in candidate.relative_to(anchor).parts:
            current = current / component
            try:
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise ValueError(f"directory does not exist: {current}") from None
                try:
                    os.mkdir(component, 0o777, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except OSError as exc:
                raise ValueError(f"directory path contains symlink or non-directory component: {current}") from exc
            os.close(descriptor)
            descriptor = child
        return candidate, descriptor
    except Exception:
        os.close(descriptor)
        raise


def ensure_safe_directory(path: Path, *, create: bool) -> Path:
    """Return an absolute directory path without traversing symlink components."""

    candidate = _normalize_top_level_alias(path)
    if _supports_dir_fd():
        candidate, descriptor = _open_directory_fd(candidate, create=create)
        os.close(descriptor)
        return candidate

    anchor = Path(candidate.anchor)
    current = anchor
    for component in candidate.relative_to(anchor).parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            if not create:
                raise ValueError(f"directory does not exist: {current}") from None
            try:
                current.mkdir()
            except FileExistsError:
                pass
            mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"directory path contains symlink component: {current}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"directory path component is not a directory: {current}")
    return candidate


def _entry_mode(parent_fd: int, name: str) -> int | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False).st_mode
    except FileNotFoundError:
        return None


def _validate_output_entry(parent_fd: int, candidate: Path) -> None:
    mode = _entry_mode(parent_fd, candidate.name)
    if mode is None:
        return
    if stat.S_ISLNK(mode):
        raise ValueError(f"output path is a symlink: {candidate}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"output path is not a regular file: {candidate}")


def _directory_identity_matches(parent_fd: int, parent: Path) -> bool:
    try:
        opened = os.fstat(parent_fd)
        current = os.stat(parent, follow_symlinks=False)
    except OSError:
        return False
    return (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)


def ensure_safe_output_path(path: Path, *, create_parent: bool = True) -> Path:
    """Validate an output path and reject final or ancestor symlinks."""

    candidate = _normalize_top_level_alias(path)
    if _supports_dir_fd():
        parent, descriptor = _open_directory_fd(candidate.parent, create=create_parent)
        try:
            candidate = parent / candidate.name
            _validate_output_entry(descriptor, candidate)
            return candidate
        finally:
            os.close(descriptor)

    parent = ensure_safe_directory(candidate.parent, create=create_parent)
    candidate = parent / candidate.name
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError:
        return candidate
    if stat.S_ISLNK(mode):
        raise ValueError(f"output path is a symlink: {candidate}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"output path is not a regular file: {candidate}")
    return candidate


def ensure_safe_input_file(path: Path) -> Path:
    """Validate a regular input file reached without symlink components."""

    candidate = _normalize_top_level_alias(path)
    parent = ensure_safe_directory(candidate.parent, create=False)
    candidate = parent / candidate.name
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError:
        raise ValueError(f"input file does not exist: {candidate}") from None
    if stat.S_ISLNK(mode):
        raise ValueError(f"input path is a symlink: {candidate}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"input path is not a regular file: {candidate}")
    return candidate


def ensure_safe_input_directory(path: Path) -> Path:
    """Validate an input directory reached without symlink components."""

    return ensure_safe_directory(path, create=False)


def validate_input_root(path: Path) -> Path:
    """Return a real directory scan root or raise one stable shape error."""

    try:
        return ensure_safe_input_directory(path)
    except (OSError, ValueError):
        raise InputRootError(path) from None


def _open_temporary_at(parent_fd: int, candidate: Path) -> tuple[str, int]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    for _attempt in range(100):
        name = f".{candidate.name}.{secrets.token_hex(12)}.tmp"
        try:
            return name, os.open(name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError:
            continue
    raise FileExistsError(f"could not allocate a unique temporary output beside {candidate}")


def _apply_output_mode(descriptor: int, mode: int | None) -> None:
    if mode is None:
        return
    fchmod = getattr(os, "fchmod", None)
    if fchmod is not None:
        fchmod(descriptor, mode)


@contextmanager
def atomic_binary_writer(path: Path, *, mode: int | None = None) -> Iterator[BinaryIO]:
    """Yield a binary file and publish it atomically without path traversal."""

    candidate = _normalize_top_level_alias(path)
    if not _supports_dir_fd():
        candidate = ensure_safe_output_path(candidate)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{candidate.name}.", dir=candidate.parent)
        _apply_output_mode(descriptor, mode)
        temporary = Path(temporary_name)
        handle = os.fdopen(descriptor, "w+b")
        try:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            candidate = ensure_safe_output_path(candidate, create_parent=False)
            os.replace(temporary, candidate)
        finally:
            if not handle.closed:
                handle.close()
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return

    parent, parent_fd = _open_directory_fd(candidate.parent, create=True)
    candidate = parent / candidate.name
    temporary_name = ""
    handle: BinaryIO | None = None
    try:
        _validate_output_entry(parent_fd, candidate)
        temporary_name, temporary_fd = _open_temporary_at(parent_fd, candidate)
        _apply_output_mode(temporary_fd, mode)
        handle = os.fdopen(temporary_fd, "w+b")
        yield handle
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        if not _directory_identity_matches(parent_fd, parent):
            raise ValueError(f"output parent directory changed while writing: {parent}")
        _validate_output_entry(parent_fd, candidate)
        os.replace(temporary_name, candidate.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temporary_name = ""
    finally:
        if handle is not None and not handle.closed:
            handle.close()
        if temporary_name:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def safe_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int | None = None,
) -> Path:
    """Write text atomically without following final or ancestor symlinks."""

    with atomic_binary_writer(path, mode=mode) as handle:
        handle.write(text.encode(encoding))
    return ensure_safe_output_path(path, create_parent=False)
