"""Verify the exact generated preview archive before publishing it as CI output."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import stat
import subprocess
import sys
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "AURA-Companion-0.3.0-preview.zip"
ARCHIVE_PREFIX = "AURA-Companion/"
MANIFEST_NAME = ARCHIVE_PREFIX + "release-manifest.json"


def verify_preview_archive(root: Path = ROOT, archive: Path | None = None) -> dict[str, object]:
    """Check the archive checksum, provenance, file set, and every manifest hash."""
    root = Path(root).resolve()
    release = root / "aura-app" / "release"
    archive = Path(archive) if archive is not None else release / ARCHIVE_NAME
    if not archive.is_absolute():
        archive = root / archive
    manifest_path = release / "release-manifest.json"
    checksum_path = archive.with_suffix(archive.suffix + ".sha256")
    if any(path.is_symlink() for path in (release, archive, manifest_path, checksum_path)):
        raise ValueError("Preview outputs must not be symlinks")
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        checksum_line = checksum_path.read_text(encoding="ascii").strip().split()
        expected_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        ).strip()
        archive_bytes = archive.read_bytes()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise ValueError("Preview archive metadata is unavailable or malformed") from error

    if len(checksum_line) != 2 or checksum_line[1] != archive.name:
        raise ValueError("Preview archive checksum file has an unexpected format")
    archive_digest = hashlib.sha256(archive_bytes).hexdigest()
    if checksum_line[0] != archive_digest:
        raise ValueError("Preview archive checksum does not match its sidecar")
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "aura-preview-manifest-v1"
        or manifest.get("scope") != "development_preview"
        or manifest.get("source_commit") != expected_commit
        or manifest.get("notarization_verified") is not False
        or manifest.get("hardware_acceptance") != "not_established_by_this_build"
    ):
        raise ValueError("Preview manifest does not match this development build")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Preview manifest has no file inventory")
    for name, digest in files.items():
        if (
            not isinstance(name, str)
            or "\\" in name
            or PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ValueError("Preview manifest contains an unsafe file entry")

    try:
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                raise ValueError("Preview archive contains a damaged member")
            infos = bundle.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ValueError("Preview archive contains duplicate paths")
            for info in infos:
                path = PurePosixPath(info.filename)
                if (
                    not info.filename.startswith(ARCHIVE_PREFIX)
                    or "\\" in info.filename
                    or path.is_absolute()
                    or ".." in path.parts
                ):
                    raise ValueError("Preview archive contains an unsafe path")
                mode = info.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if kind not in (0, stat.S_IFREG):
                    raise ValueError("Preview archive contains a non-regular file")

            expected_names = {ARCHIVE_PREFIX + name for name in files} | {MANIFEST_NAME}
            if set(names) != expected_names:
                raise ValueError("Preview archive file list differs from its manifest")
            if bundle.read(MANIFEST_NAME) != manifest_bytes:
                raise ValueError("Embedded preview manifest differs from release metadata")
            for name, expected_digest in files.items():
                actual_digest = hashlib.sha256(bundle.read(ARCHIVE_PREFIX + name)).hexdigest()
                if actual_digest != expected_digest:
                    raise ValueError(f"Preview file hash mismatch: {name}")
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError, EOFError, zlib.error) as error:
        raise ValueError("Preview archive could not be read safely") from error

    return {
        "archive": archive.name,
        "source_commit": expected_commit,
        "file_count": len(files),
        "size_bytes": len(archive_bytes),
        "sha256": archive_digest,
        "platform": manifest.get("platform"),
        "native_signing": manifest.get("native_signing"),
        "notarization_verified": manifest.get("notarization_verified"),
        "hardware_acceptance": manifest.get("hardware_acceptance"),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(verify_preview_archive(), sort_keys=True))
    except ValueError as error:
        raise SystemExit(f"Preview verification refused: {error}") from None
