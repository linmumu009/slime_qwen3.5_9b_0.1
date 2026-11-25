#!/usr/bin/env python3
"""Verify the backup without dependencies; optionally restore into a new directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def safe_relative(value: str) -> Path:
    posix = PurePosixPath(value)
    if (
        not value
        or posix.is_absolute()
        or any(part in (".", "..") for part in posix.parts)
        or "\\" in value
        or ":" in value
    ):
        raise ValueError(f"Unsafe backup path: {value!r}")
    return Path(*posix.parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", type=Path, help="New, nonexistent destination directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    checksums = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        path = root / safe_relative(name)
        if name in checksums or not path.is_file() or digest(path) != expected:
            raise ValueError(f"Package checksum mismatch: {name}")
        checksums[name] = expected
    actual_files = {p.name for p in root.iterdir() if p.is_file() and p.name != "SHA256SUMS"}
    if actual_files != set(checksums):
        raise ValueError("Package file list differs from SHA256SUMS")

    manifest = json.loads((root / "backup_manifest.json").read_text(encoding="utf-8"))
    if args.restore and args.restore.exists():
        raise ValueError("Restore destination already exists; choose a new directory")

    # Verify every member before creating the restore directory.
    count = 0
    size = 0
    for archive in manifest["archives"]:
        path = root / safe_relative(archive["file"])
        if path.stat().st_size != archive["bytes"] or checksums[path.name] != archive["sha256"]:
            raise ValueError(f"Archive manifest mismatch: {path.name}")
        if path.stat().st_size != archive["bytes"] or checksums[path.name] != archive["sha256"]:
            raise ValueError(f"Archive manifest mismatch: {path.name}")
        expected = {entry["path"]: entry for entry in archive["members"]}
        if len(expected) != len(archive["members"]):
            raise ValueError(f"Duplicate manifest member: {path.name}")
        seen = set()
        with tarfile.open(path, "r:gz") as tar:
            for member in tar:
                safe_relative(member.name)
                if not member.isfile() or member.name not in expected or member.name in seen:
                    raise ValueError(f"Unexpected archive member: {member.name}")
                entry = expected[member.name]
                handle = tar.extractfile(member)
                if handle is None:
                    raise ValueError(f"Unreadable member: {member.name}")
                with handle:
                    sha = hashlib.file_digest(handle, "sha256").hexdigest()
                if member.size != entry["bytes"] or sha != entry["sha256"]:
                    raise ValueError(f"Member checksum mismatch: {member.name}")
                seen.add(member.name)
                count += 1
                size += member.size
        if seen != set(expected):
            raise ValueError(f"Missing archive members: {path.name}")

    if args.restore:
        destination = args.restore.resolve()
        destination.mkdir(parents=True, exist_ok=False)
        for archive in manifest["archives"]:
            prefix = destination / safe_relative(archive["restore_prefix"])
            with tarfile.open(root / archive["file"], "r:gz") as tar:
                for member in tar:
                    target = prefix / safe_relative(member.name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    handle = tar.extractfile(member)
                    if handle is None:
                        raise ValueError(f"Unreadable member: {member.name}")
                    with handle, target.open("xb") as output:
                        while chunk := handle.read(1024 * 1024):
                            output.write(chunk)
        print(f"Restored to {destination}")
    print(f"Verified {len(checksums)} package files; {count} archive members; {size} original bytes")


if __name__ == "__main__":
    main()
