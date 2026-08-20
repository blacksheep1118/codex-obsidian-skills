#!/usr/bin/env python3
"""Install one or more bundled skills into a Codex skills directory."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
import tempfile
import zipfile

from install_ignore import ignore_patterns, should_ignore_relative
from shared.skill_metadata import MetadataValidationError, load_skill_frontmatter, validate_skill_metadata
from shared.skill_provenance import (
    PROVENANCE_FILENAME,
    PROVENANCE_SCHEMA_VERSION,
    build_provenance,
    content_digest,
    file_records,
    load_provenance,
    write_provenance,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
_TIMEOUT_HELPER = REPO_ROOT / "skill" / "solvenotes-vault-maintainer" / "scripts" / "run_with_timeout.py"
_TIMEOUT_SPEC = importlib.util.spec_from_file_location("_solvenotes_timeout_runner_install", _TIMEOUT_HELPER)
if _TIMEOUT_SPEC is None or _TIMEOUT_SPEC.loader is None:
    raise ImportError(f"cannot load timeout helper: {_TIMEOUT_HELPER}")
_TIMEOUT_MODULE = importlib.util.module_from_spec(_TIMEOUT_SPEC)
_TIMEOUT_SPEC.loader.exec_module(_TIMEOUT_MODULE)
run_process = _TIMEOUT_MODULE.run


SKILL_ROOT = REPO_ROOT / "skill"
DEPENDENCIES_PATH = SKILL_ROOT / "dependencies.json"
SKILLS_REPOSITORY = "blacksheep1118/codex-obsidian-skills"
INSTALL_EXCLUDED_PARTS = {"tests"}
TRUSTED_TOP_LEVEL_ALIASES = (
    {
        Path("/etc"): Path("/private/etc"),
        Path("/tmp"): Path("/private/tmp"),
        Path("/var"): Path("/private/var"),
    }
    if sys.platform == "darwin"
    else {}
)


class UnsafeDestinationError(ValueError):
    """Raised when an install target could escape through a symlink."""


def should_install_relative(relative: Path) -> bool:
    """Return whether a source entry belongs to the installed runtime payload."""

    return not should_ignore_relative(relative) and not any(
        part in INSTALL_EXCLUDED_PARTS for part in relative.parts
    )


def install_ignore_patterns(directory: str, names: list[str]) -> set[str]:
    ignored = ignore_patterns(directory, names)
    ignored.update(name for name in names if name in INSTALL_EXCLUDED_PARTS)
    return ignored


class UnsafeSourceError(ValueError):
    """Raised when an install source contains or traverses a symlink."""


def configure_output_encoding() -> None:
    """Use UTF-8 for dry-run/self-check messages on Windows consoles."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _absolute_with_platform_alias(path: Path) -> Path:
    """Normalize an absolute path while permitting only a top-level OS alias."""

    absolute = Path(os.path.abspath(path.expanduser()))
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
        raise UnsafeDestinationError(f"unsafe untrusted top-level destination symlink: {first}")
    try:
        resolved_first = first.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UnsafeDestinationError(f"unsafe top-level destination symlink: {first}") from exc
    if resolved_first != expected or not resolved_first.is_dir():
        raise UnsafeDestinationError(
            f"top-level destination alias has unexpected target: {first} -> {resolved_first}"
        )
    return resolved_first.joinpath(*relative.parts[1:])


def _ensure_safe_directory_chain(path: Path) -> None:
    """Reject existing symlinks/non-directories while allowing a missing tail."""

    candidate = _absolute_with_platform_alias(path)
    anchor = Path(candidate.anchor)
    current = anchor
    for component in candidate.relative_to(anchor).parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return
        if stat.S_ISLNK(mode):
            raise UnsafeDestinationError(f"unsafe destination symlink component: {current}")
        if not stat.S_ISDIR(mode):
            raise UnsafeDestinationError(f"destination component is not a directory: {current}")


def ensure_safe_destination_root(destination_root: Path) -> None:
    """Reject symlinks/non-directories in the full destination ancestor chain."""

    _ensure_safe_directory_chain(destination_root)


def ensure_safe_source_tree(source: Path) -> None:
    """Reject a source root or tree containing any symlink, including dangling ones."""

    try:
        root_mode = source.lstat().st_mode
    except FileNotFoundError:
        raise UnsafeSourceError(f"install source does not exist: {source}") from None
    if stat.S_ISLNK(root_mode):
        raise UnsafeSourceError(f"unsafe install source symlink: {source}")
    if not stat.S_ISDIR(root_mode):
        raise UnsafeSourceError(f"install source is not a directory: {source}")

    for current_root, directory_names, file_names in os.walk(source, followlinks=False):
        current = Path(current_root)
        for name in (*directory_names, *file_names):
            candidate = current / name
            try:
                mode = candidate.lstat().st_mode
            except FileNotFoundError as exc:
                raise UnsafeSourceError(f"install source changed while scanning: {candidate}") from exc
            if stat.S_ISLNK(mode):
                raise UnsafeSourceError(f"unsafe install source symlink: {candidate}")


def ensure_safe_destination_tree(destination: Path) -> None:
    """Reject existing or dangling symlinks anywhere in a destination skill tree."""

    ensure_safe_destination_root(destination.parent)
    if destination.is_symlink():
        raise UnsafeDestinationError(f"unsafe destination symlink: {destination}")
    if not destination.exists():
        return
    if not destination.is_dir():
        raise UnsafeDestinationError(f"destination skill is not a directory: {destination}")

    for current_root, directory_names, file_names in os.walk(destination, followlinks=False):
        current = Path(current_root)
        for name in (*directory_names, *file_names):
            candidate = current / name
            if candidate.is_symlink():
                raise UnsafeDestinationError(f"unsafe destination symlink: {candidate}")


def _directory_flags() -> int:
    flags = os.O_RDONLY
    for name in ("O_DIRECTORY", "O_CLOEXEC", "O_NOFOLLOW"):
        flags |= getattr(os, name, 0)
    return flags


def _supports_dir_fd() -> bool:
    return os.name != "nt" and os.open in os.supports_dir_fd and os.mkdir in os.supports_dir_fd


def _path_error(label: str, message: str) -> ValueError:
    error_type = UnsafeSourceError if label == "source" else UnsafeDestinationError
    return error_type(message)


def _open_directory_fd(path: Path, *, create: bool, label: str) -> tuple[Path, int]:
    """Open a path one no-follow directory component at a time."""

    candidate = _absolute_with_platform_alias(path)
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
                    raise _path_error(label, f"{label} directory does not exist: {current}") from None
                try:
                    os.mkdir(component, 0o777, dir_fd=descriptor)
                except FileExistsError:
                    pass
                try:
                    child = os.open(component, _directory_flags(), dir_fd=descriptor)
                except OSError as exc:
                    raise _path_error(
                        label,
                        f"unsafe {label} symlink or non-directory component: {current}",
                    ) from exc
            except OSError as exc:
                raise _path_error(
                    label,
                    f"unsafe {label} symlink or non-directory component: {current}",
                ) from exc
            os.close(descriptor)
            descriptor = child
        return candidate, descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_relative_directory_fd(
    root_fd: int,
    relative: Path,
    *,
    create: bool,
    label: str,
) -> int:
    descriptor = os.dup(root_fd)
    current = Path(".")
    try:
        for component in relative.parts:
            if component in {"", ".", ".."}:
                raise _path_error(label, f"unsafe {label} relative directory: {relative}")
            current = current / component
            try:
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise _path_error(label, f"{label} directory changed while copying: {current}") from None
                try:
                    os.mkdir(component, 0o777, dir_fd=descriptor)
                except FileExistsError:
                    pass
                try:
                    child = os.open(component, _directory_flags(), dir_fd=descriptor)
                except OSError as exc:
                    raise _path_error(label, f"unsafe {label} directory while copying: {current}") from exc
            except OSError as exc:
                raise _path_error(label, f"unsafe {label} directory while copying: {current}") from exc
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _directory_identity_matches(descriptor: int, path: Path) -> bool:
    try:
        opened = os.fstat(descriptor)
        current = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)


def _source_entries(source: Path) -> tuple[list[Path], list[Path]]:
    directories: list[Path] = []
    files: list[Path] = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if not should_install_relative(relative):
            continue
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError as exc:
            raise UnsafeSourceError(f"install source changed while listing: {path}") from exc
        if stat.S_ISLNK(mode):
            raise UnsafeSourceError(f"unsafe install source symlink: {path}")
        if stat.S_ISDIR(mode):
            directories.append(relative)
        elif stat.S_ISREG(mode):
            files.append(relative)
        else:
            raise UnsafeSourceError(f"install source entry is not a regular file or directory: {path}")
    directories.sort(key=lambda relative: (len(relative.parts), relative.as_posix()))
    files.sort(key=lambda relative: relative.as_posix())
    return directories, files


def _validate_entry_mode(mode: int | None, path: Path, *, label: str) -> None:
    if mode is None:
        return
    if stat.S_ISLNK(mode):
        raise _path_error(label, f"unsafe {label} symlink: {path}")
    if not stat.S_ISREG(mode):
        raise _path_error(label, f"{label} entry is not a regular file: {path}")


def _entry_mode(parent_fd: int, name: str) -> int | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False).st_mode
    except FileNotFoundError:
        return None


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short write while installing skill")
        view = view[written:]


def _copy_regular_file_at(source_root_fd: int, destination_root_fd: int, relative: Path) -> None:
    source_parent_fd = _open_relative_directory_fd(
        source_root_fd,
        relative.parent,
        create=False,
        label="source",
    )
    destination_parent_fd = _open_relative_directory_fd(
        destination_root_fd,
        relative.parent,
        create=True,
        label="destination",
    )
    source_fd = -1
    temporary_fd = -1
    temporary_name = ""
    try:
        before = os.stat(relative.name, dir_fd=source_parent_fd, follow_symlinks=False)
        _validate_entry_mode(before.st_mode, relative, label="source")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            source_fd = os.open(relative.name, flags, dir_fd=source_parent_fd)
        except OSError as exc:
            raise UnsafeSourceError(f"unsafe source file while copying: {relative}") from exc
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise UnsafeSourceError(f"source file changed while opening: {relative}")

        _validate_entry_mode(_entry_mode(destination_parent_fd, relative.name), relative, label="destination")
        destination_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        for _attempt in range(100):
            temporary_name = f".{relative.name}.{secrets.token_hex(12)}.tmp"
            try:
                temporary_fd = os.open(
                    temporary_name,
                    destination_flags,
                    0o600,
                    dir_fd=destination_parent_fd,
                )
                break
            except FileExistsError:
                continue
        if temporary_fd < 0:
            raise FileExistsError(f"could not allocate install temporary file for {relative}")

        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            _write_all(temporary_fd, chunk)
        os.fchmod(temporary_fd, stat.S_IMODE(opened.st_mode))
        os.fsync(temporary_fd)

        after = os.stat(relative.name, dir_fd=source_parent_fd, follow_symlinks=False)
        if stat.S_ISLNK(after.st_mode) or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino):
            raise UnsafeSourceError(f"source file changed while copying: {relative}")
        _validate_entry_mode(_entry_mode(destination_parent_fd, relative.name), relative, label="destination")
        os.replace(
            temporary_name,
            relative.name,
            src_dir_fd=destination_parent_fd,
            dst_dir_fd=destination_parent_fd,
        )
        temporary_name = ""
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        if temporary_fd >= 0:
            os.close(temporary_fd)
        if temporary_name:
            try:
                os.unlink(temporary_name, dir_fd=destination_parent_fd)
            except FileNotFoundError:
                pass
        os.close(source_parent_fd)
        os.close(destination_parent_fd)


def _prune_at(destination_root_fd: int, removals: list[Path]) -> None:
    for relative in removals:
        parent_fd = _open_relative_directory_fd(
            destination_root_fd,
            relative.parent,
            create=False,
            label="destination",
        )
        try:
            mode = _entry_mode(parent_fd, relative.name)
            if mode is None:
                continue
            if stat.S_ISLNK(mode):
                raise UnsafeDestinationError(f"unsafe destination symlink while pruning: {relative}")
            if stat.S_ISDIR(mode):
                os.rmdir(relative.name, dir_fd=parent_fd)
            else:
                os.unlink(relative.name, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)


def _copy_skill_no_follow(source: Path, destination: Path, *, prune: bool) -> None:
    directories, files = _source_entries(source)
    removals = prune_paths(source, destination) if prune else []
    source_path, source_fd = _open_directory_fd(source, create=False, label="source")
    destination_path, destination_fd = _open_directory_fd(destination, create=True, label="destination")
    try:
        for relative in directories:
            source_directory_fd = _open_relative_directory_fd(
                source_fd,
                relative,
                create=False,
                label="source",
            )
            os.close(source_directory_fd)
            destination_directory_fd = _open_relative_directory_fd(
                destination_fd,
                relative,
                create=True,
                label="destination",
            )
            os.close(destination_directory_fd)
        for relative in files:
            _copy_regular_file_at(source_fd, destination_fd, relative)
        if prune:
            _prune_at(destination_fd, removals)
        if not _directory_identity_matches(source_fd, source_path):
            raise UnsafeSourceError(f"install source root changed while copying: {source_path}")
        if not _directory_identity_matches(destination_fd, destination_path):
            raise UnsafeDestinationError(
                f"destination root or ancestor changed while copying: {destination_path}"
            )
    finally:
        os.close(source_fd)
        os.close(destination_fd)

    ensure_safe_source_tree(source)
    ensure_safe_destination_tree(destination)


def default_destination(codex_home: Path | None = None) -> Path:
    if codex_home is None:
        env_home = os.environ.get("CODEX_HOME")
        codex_home = Path(env_home).expanduser() if env_home else Path.home() / ".codex"
    return codex_home / "skills"


def parse_skill_name(skill_dir: Path) -> str:
    metadata = load_skill_frontmatter(skill_dir / "SKILL.md")
    return metadata["name"].strip()


def discover_skills() -> dict[str, Path]:
    skills: dict[str, Path] = {}
    for skill_dir in sorted(SKILL_ROOT.iterdir()):
        if skill_dir.is_symlink():
            raise UnsafeSourceError(f"unsafe install source symlink: {skill_dir}")
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        ensure_safe_source_tree(skill_dir)
        name = parse_skill_name(skill_dir)
        if name != skill_dir.name:
            raise ValueError(f"skill directory name must match frontmatter: {skill_dir.name!r} != {name!r}")
        skills[name] = skill_dir
    return skills


def selected_skills(
    all_skills: dict[str, Path],
    requested: list[str],
    include_all: bool,
    *,
    no_deps: bool = False,
) -> dict[str, Path]:
    dependencies = load_required_dependencies()
    unknown_graph_names = sorted(set(dependencies) - set(all_skills))
    unknown_dependencies = sorted(
        {dependency for values in dependencies.values() for dependency in values} - set(all_skills)
    )
    if unknown_graph_names or unknown_dependencies:
        details = []
        if unknown_graph_names:
            details.append("unknown Skill entries: " + ", ".join(unknown_graph_names))
        if unknown_dependencies:
            details.append("unknown dependencies: " + ", ".join(unknown_dependencies))
        raise ValueError("invalid Skill dependency graph; " + "; ".join(details))

    if include_all or not requested:
        return dict(all_skills)

    selected: dict[str, Path] = {}
    for name in requested:
        if name not in all_skills:
            choices = ", ".join(sorted(all_skills))
            raise ValueError(f"unknown skill {name!r}; available: {choices}")
        selected[name] = all_skills[name]
    if no_deps:
        return selected
    pending = list(selected)
    while pending:
        name = pending.pop()
        for dependency in dependencies.get(name, ()):
            if dependency not in all_skills:
                raise ValueError(f"Skill {name!r} requires missing Skill {dependency!r}")
            if dependency not in selected:
                selected[dependency] = all_skills[dependency]
                pending.append(dependency)
    return selected


def load_required_dependencies() -> dict[str, tuple[str, ...]]:
    try:
        payload = json.loads(DEPENDENCIES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read Skill dependency graph: {DEPENDENCIES_PATH}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("required"), dict):
        raise ValueError(f"Skill dependency graph must contain an object at required: {DEPENDENCIES_PATH}")
    graph: dict[str, tuple[str, ...]] = {}
    for name, values in payload["required"].items():
        if not isinstance(name, str) or not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            raise ValueError(f"invalid Skill dependency entry for {name!r}")
        graph[name] = tuple(dict.fromkeys(values))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ValueError(f"Skill dependency cycle detected at {name!r}")
        if name in visited:
            return
        visiting.add(name)
        for dependency in graph.get(name, ()):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)
    return graph


def managed_files(root: Path) -> dict[Path, Path]:
    """Return installable files without following ignored/generated artifacts."""

    if not root.exists():
        return {}
    ensure_safe_source_tree(root)
    return {
        path.relative_to(root): path
        for path in root.rglob("*")
        if path.is_file()
        and path.name != PROVENANCE_FILENAME
        and should_install_relative(path.relative_to(root))
    }


def compare_skill(source: Path, destination: Path) -> dict[str, list[str]]:
    """Compare managed files without mutating either tree."""

    source_files = managed_files(source)
    destination_files = managed_files(destination)
    added = sorted(relative.as_posix() for relative in source_files.keys() - destination_files.keys())
    stale = sorted(relative.as_posix() for relative in destination_files.keys() - source_files.keys())
    changed = sorted(
        relative.as_posix()
        for relative in source_files.keys() & destination_files.keys()
        if source_files[relative].read_bytes() != destination_files[relative].read_bytes()
    )
    unchanged = sorted(
        relative.as_posix()
        for relative in source_files.keys() & destination_files.keys()
        if source_files[relative].read_bytes() == destination_files[relative].read_bytes()
    )
    return {"added": added, "changed": changed, "unchanged": unchanged, "stale": stale}


def prune_paths(source: Path, destination: Path) -> list[Path]:
    """Return every destination entry removed by an explicit prune."""

    if not destination.exists():
        return []
    source_entries = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.name != PROVENANCE_FILENAME
        and should_install_relative(path.relative_to(source))
    }
    return sorted(
        (
            path.relative_to(destination)
            for path in destination.rglob("*")
            if path.name != PROVENANCE_FILENAME
            and path.relative_to(destination) not in source_entries
        ),
        key=lambda relative: (len(relative.parts), relative.as_posix()),
        reverse=True,
    )


def copy_skill(source: Path, destination: Path, dry_run: bool, prune: bool = False) -> None:
    ensure_safe_source_tree(source)
    ensure_safe_destination_tree(destination)
    if dry_run:
        diff = compare_skill(source, destination)
        try:
            source_label = source.relative_to(REPO_ROOT)
        except ValueError:
            source_label = source
        print(
            f"DRY-RUN install {source_label} -> {destination} "
            f"added={len(diff['added'])} changed={len(diff['changed'])} "
            f"unchanged={len(diff['unchanged'])} stale={len(diff['stale'])}"
        )
        for kind in ("added", "changed", "stale"):
            for relative in diff[kind]:
                print(f"DRY-RUN {kind} {relative}")
        if prune:
            removals = prune_paths(source, destination)
            print(f"DRY-RUN prune stale files under {destination}: {len(removals)}")
            for relative in reversed(removals):
                print(f"DRY-RUN remove {relative.as_posix()}")
        else:
            print(f"DRY-RUN prune not requested for {destination}")
        return

    if _supports_dir_fd():
        _copy_skill_no_follow(source, destination, prune=prune)
    else:
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=install_ignore_patterns,
            symlinks=True,
        )
        ensure_safe_source_tree(source)
        ensure_safe_destination_tree(destination)

        if prune:
            for relative in prune_paths(source, destination):
                path = destination / relative
                if path.is_dir():
                    path.rmdir()
                else:
                    path.unlink()

    dependencies = load_required_dependencies().get(source.name, ())
    dependency_digests = {
        dependency: content_digest(file_records(SKILL_ROOT / dependency))
        for dependency in dependencies
    }
    write_provenance(
        destination,
        build_provenance(
            source,
            installed_root=destination,
            repository_root=REPO_ROOT,
            skill_name=source.name,
            repository=SKILLS_REPOSITORY,
            dependencies=dependencies,
            dependency_digests=dependency_digests,
        ),
    )
    return


def self_check_skill(skill_dir: Path) -> list[str]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_dir}: missing SKILL.md"]
    try:
        validate_skill_metadata(skill_dir)
    except (OSError, MetadataValidationError) as exc:
        return [str(exc)]
    return []


def _validator_for(skill_dir: Path) -> Path | None:
    for name in ("validate_skill.py", "validate_skill_repo.py"):
        candidate = skill_dir / "scripts" / name
        if candidate.is_file():
            return candidate
    return None


SELF_CHECK_LEVELS = ("metadata", "runtime", "smoke", "full")


def _run_installed_validator(skill_dir: Path) -> list[str]:
    validator = _validator_for(skill_dir)
    if validator is None:
        return []
    with tempfile.TemporaryDirectory(prefix="solvenotes-installed-cwd-") as cwd:
        environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = run_process(
            [sys.executable, str(validator)],
            30,
            f"installed validator {skill_dir.name}",
            cwd=cwd,
            env=environment,
        )
    if result:
        return [f"{skill_dir.name}: installed validator failed with exit code {result}"]
    return []


def _run_installed_smoke(skill_dir: Path, destination_root: Path) -> list[str]:
    """Run a small dependency-aware smoke against the installed maintainer."""

    if skill_dir.name != "solvenotes-vault-maintainer":
        return []

    fixture = (skill_dir / "fixtures" / "solvenotes-mini-vault").resolve()
    if not fixture.is_dir():
        return [f"{skill_dir.name}: missing installed mini-vault fixture: {fixture}"]

    algorithm_root = destination_root / "algorithm-job-notes-for-obsidian"
    cpp_checker = algorithm_root / "scripts" / "check_cpp_examples.py"
    commands = (
        (
            "algorithm-job scanner",
            [skill_dir / "scripts" / "check_algorithm_job_notes.py", "--root", fixture],
        ),
        ("links", [skill_dir / "scripts" / "check_links.py"]),
        ("frontmatter", [skill_dir / "scripts" / "check_frontmatter.py"]),
        ("naturalness", [skill_dir / "scripts" / "check_naturalness.py", "--strict"]),
        (
            "Python fenced blocks",
            [skill_dir / "scripts" / "check_python_examples.py", "--root", fixture],
        ),
        (
            "C++17 runnable blocks",
            [cpp_checker, "--root", fixture, "--timeout", "30"],
        ),
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    # Resolve the complete path before placing it in the child environment.
    # Forward slashes are accepted by Windows path APIs and avoid turning a
    # drive-qualified value into a drive-relative path in a downstream helper.
    environment["SOLVENOTES_VAULT_ROOT"] = fixture.as_posix()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="solvenotes-installed-smoke-") as cwd:
        smoke_cwd = Path(cwd).resolve()
        for label, command in commands:
            def unavailable(item: object) -> bool:
                if not isinstance(item, Path):
                    return False
                expected_directory = item == fixture
                return not (item.is_dir() if expected_directory else item.is_file())

            if any(unavailable(item) for item in command):
                missing = next(str(item) for item in command if unavailable(item))
                issues.append(f"{skill_dir.name}: smoke dependency missing for {label}: {missing}")
                continue
            result = run_process(
                [
                    sys.executable,
                    *(str(item) if isinstance(item, Path) else item for item in command),
                ],
                60,
                f"installed {skill_dir.name} {label} smoke",
                cwd=smoke_cwd,
                env=environment,
            )
            if result:
                issues.append(f"{skill_dir.name}: installed {label} smoke failed with exit code {result}")
    return issues


def _run_installed_full(skill_dir: Path, destination_root: Path) -> list[str]:
    """Extend installed smoke with a clean package built from the runtime fixture."""

    if skill_dir.name != "solvenotes-vault-maintainer":
        return []
    issues = _run_installed_smoke(skill_dir, destination_root)
    if issues:
        return issues
    fixture = (skill_dir / "fixtures" / "solvenotes-mini-vault").resolve()
    package_script = skill_dir / "scripts" / "package_vault.py"
    if not fixture.is_dir() or not package_script.is_file():
        return [f"{skill_dir.name}: installed full smoke is missing its fixture or packager"]
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["SOLVENOTES_VAULT_ROOT"] = fixture.as_posix()
    with tempfile.TemporaryDirectory(prefix="solvenotes-installed-full-") as cwd:
        output = Path(cwd) / "notes.zip"
        result = run_process(
            [
                sys.executable,
                str(package_script),
                "--root",
                str(fixture),
                "--output",
                str(output),
            ],
            120,
            f"installed {skill_dir.name} package smoke",
            cwd=Path(cwd).resolve(),
            env=environment,
        )
        if result:
            return [f"{skill_dir.name}: installed package smoke failed with exit code {result}"]
        try:
            with zipfile.ZipFile(output) as archive:
                if archive.testzip() is not None or not archive.namelist():
                    return [f"{skill_dir.name}: installed package smoke produced an invalid ZIP"]
        except (OSError, zipfile.BadZipFile) as exc:
            return [f"{skill_dir.name}: installed package smoke could not read its ZIP: {exc}"]
    return []


def report_self_check(label: str, issues: list[str], skill_count: int) -> int:
    if issues:
        print(f"{label} failed", file=sys.stderr)
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1

    print(f"{label} ok skills={skill_count}")
    return 0


def self_check_sources(skills: dict[str, Path]) -> int:
    issues: list[str] = []
    for source in skills.values():
        issues.extend(self_check_skill(source))
    return report_self_check("source_self_check", issues, len(skills))


def self_check_selected(
    destination_root: Path,
    skills: dict[str, Path],
    *,
    level: str = "smoke",
) -> int:
    if level not in SELF_CHECK_LEVELS:
        raise ValueError(f"unknown self-check level: {level}")
    issues: list[str] = []
    try:
        ensure_safe_destination_root(destination_root)
    except UnsafeDestinationError as exc:
        issues.append(str(exc))
        return report_self_check("install_self_check", issues, len(skills))

    for name in skills:
        installed_dir = destination_root / name
        try:
            ensure_safe_destination_tree(installed_dir)
        except UnsafeDestinationError as exc:
            issues.append(str(exc))
            continue
        if not installed_dir.exists():
            issues.append(f"{installed_dir}: not installed")
            continue
        issues.extend(self_check_skill(installed_dir))
        try:
            provenance = load_provenance(installed_dir)
        except ValueError as exc:
            issues.append(str(exc))
            provenance = None
        if provenance is None:
            issues.append(f"{installed_dir}: missing {PROVENANCE_FILENAME}")
        else:
            if provenance.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
                issues.append(f"{installed_dir}: unsupported provenance schema")
            if provenance.get("skill") != name:
                issues.append(f"{installed_dir}: provenance skill does not match {name!r}")
            actual_records = file_records(installed_dir)
            actual_digest = content_digest(actual_records)
            if provenance.get("installed_content_digest") != actual_digest:
                issues.append(f"{installed_dir}: content digest mismatch")
            if provenance.get("content_digest") != actual_digest:
                issues.append(f"{installed_dir}: compatibility content digest mismatch")
            if provenance.get("managed_files") != actual_records:
                issues.append(f"{installed_dir}: managed file manifest mismatch")
            for dependency in provenance.get("dependencies", []):
                dependency_dir = destination_root / str(dependency)
                if not dependency_dir.is_dir():
                    issues.append(
                        f"required Skill not installed: {dependency}; "
                        f"install with: python scripts/install_skill.py --skill {name!s}"
                    )
                    continue
                actual_dependency_digest = content_digest(file_records(dependency_dir))
                recorded_dependency_digest = provenance.get("dependency_digests", {}).get(
                    str(dependency)
                )
                if recorded_dependency_digest != actual_dependency_digest:
                    issues.append(
                        f"{installed_dir}: dependency digest mismatch for {dependency}"
                    )
        if level in {"runtime", "smoke", "full"}:
            issues.extend(_run_installed_validator(installed_dir))
        if level == "smoke":
            issues.extend(_run_installed_smoke(installed_dir, destination_root))
        elif level == "full":
            issues.extend(_run_installed_full(installed_dir, destination_root))

    return report_self_check("install_self_check", issues, len(skills))


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Install bundled Codex skills.")
    parser.add_argument("--skill", action="append", default=[], help="Skill name to install. May be repeated.")
    parser.add_argument("--all", action="store_true", help="Install every skill under skill/. This is the default.")
    parser.add_argument(
        "--destination",
        type=Path,
        help="Destination skills directory. Defaults to CODEX_HOME/skills or the user home .codex/skills directory.",
    )
    parser.add_argument("--codex-home", type=Path, help="Codex home used to derive the destination.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument("--self-check", action="store_true", help="Validate the installed Skill after copying (defaults to smoke level).")
    parser.add_argument("--self-check-only", action="store_true", help="Validate selected installed skills without copying.")
    parser.add_argument(
        "--self-check-level",
        choices=SELF_CHECK_LEVELS,
        help="Self-check depth: metadata, runtime, smoke, or full. Implies --self-check.",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Install only explicitly requested Skills; self-check reports missing required dependencies.",
    )
    args = parser.parse_args()

    if args.destination and args.codex_home:
        parser.error("--destination and --codex-home are mutually exclusive")
    if args.self_check_level:
        args.self_check = True

    destination_root = args.destination.expanduser() if args.destination else default_destination(args.codex_home)
    try:
        all_skills = discover_skills()
        skills = selected_skills(all_skills, args.skill, args.all, no_deps=args.no_deps)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.self_check_only:
        return self_check_selected(destination_root, skills, level=args.self_check_level or "smoke")

    try:
        ensure_safe_destination_root(destination_root)
        destinations: list[tuple[str, Path, Path]] = []
        for name, source in skills.items():
            destination = destination_root / name
            ensure_safe_destination_tree(destination)
            if destination.exists():
                raise UnsafeDestinationError(
                    f"destination skill directory already exists: {destination}; "
                    "use scripts/update_installed_skills.py for an explicit update"
                )
            destinations.append((name, source, destination))
        for _name, source, destination in destinations:
            copy_skill(source, destination, dry_run=args.dry_run)
    except (UnsafeDestinationError, UnsafeSourceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.self_check:
        if args.dry_run:
            return self_check_sources(skills)
        return self_check_selected(destination_root, skills, level=args.self_check_level or "smoke")

    print(f"installed_skills {len(skills)} destination={destination_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
