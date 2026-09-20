from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
import zipfile
from pathlib import Path

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tracked_files() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in _git("ls-files", "--stage").splitlines():
        if not line.strip():
            continue
        metadata, path = line.split("\t", 1)
        mode = metadata.split()[0]
        entries.append((path.replace("\\", "/"), mode))
    return sorted(entries)


def _release_version(repo_root: Path) -> str:
    with (repo_root / "backend" / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def build_release(repo_root: Path, output_path: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    if status:
        raise RuntimeError("Release build requires a clean Git worktree.")

    files: list[dict[str, object]] = []
    payloads: list[tuple[str, str, bytes]] = []
    for path, mode in _tracked_files():
        data = (repo_root / path).read_bytes()
        files.append(
            {
                "path": path,
                "mode": mode,
                "size_bytes": len(data),
                "sha256": _sha256(data),
            }
        )
        payloads.append((path, mode, data))

    manifest: dict[str, object] = {
        "artifact_type": "jolt-source-release",
        "artifact_format_version": "1",
        "git_commit": commit,
        "version": _release_version(repo_root),
        "file_count": len(files),
        "files": files,
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        all_entries = payloads + [("RELEASE_MANIFEST.json", "100644", manifest_bytes)]
        for path, mode, data in sorted(all_entries, key=lambda item: item[0]):
            info = zipfile.ZipInfo(path, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            permissions = 0o755 if mode == "100755" else 0o644
            info.external_attr = permissions << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    manifest["artifact_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    manifest["artifact_size_bytes"] = output_path.stat().st_size
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic JOLT source release ZIP.")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()

    manifest = build_release(args.repo, args.output)
    if args.manifest_output:
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
