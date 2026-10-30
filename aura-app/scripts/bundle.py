"""Build a preview archive from clean source and verified generated output."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from build_provenance import checked_file, verify_provenance, output_files

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PARTS = {'node_modules', '.venv', '__pycache__', 'backups', 'media', 'logs',
                 '.agent-work', 'test-results', 'playwright-report'}
PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx', '.env'}
SECRET_MARKERS = [
    rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    rb'\b(?:sk-ant-api03-|sk-proj-)[A-Za-z0-9_-]{30,}',
    rb'\bsk-[A-Za-z0-9]{40,}',
    rb'\b(?:gh[pousr]_)[A-Za-z0-9_-]{30,}',
    rb'\bgithub_pat_[A-Za-z0-9_-]{30,}',
    rb'\bAKIA[0-9A-Z]{16}\b',
    rb'\bAIza[0-9A-Za-z_-]{35}\b',
    rb'\bnpm_[A-Za-z0-9]{20,}',
    rb'\bxox[baprs]-[A-Za-z0-9-]{20,}',
]


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root).decode().strip()


def validate_source_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe source path')
    if name == 'data/.gitkeep':
        return
    if ('data' in path.parts or PRIVATE_PARTS.intersection(path.parts)
            or path.suffix.lower() in PRIVATE_SUFFIXES
            or path.name.startswith('.env') or path.name == 'mcp.local.json'
            or re.search(r'\.(?:db|sqlite|sqlite3)-(?:wal|shm|journal)$', path.name)
            or name.startswith(('aura-app/release/', 'aura-app/dist/'))):
        raise ValueError(f'Private/runtime file is tracked: {name}')


def checked_bytes(root, name):
    data = checked_file(root, name).read_bytes()
    if data.startswith(b'SQLite format 3\x00') or any(re.search(pattern, data) for pattern in SECRET_MARKERS):
        raise ValueError(f'Private data marker in package input: {name}')
    return data


def source_payload(root=ROOT):
    """Also usable before commit/push, after staging newly created source files."""
    payload = {}
    for name in git(root, 'ls-files', '-z').split('\0'):
        if not name:
            continue
        validate_source_name(name)
        data = checked_bytes(root, name)
        if not name.startswith('.git'):
            payload[name] = data
    return payload


def package(root=ROOT, *, include_native=None):
    if git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Commit reviewed changes before packaging; source tree must be clean')
    source_commit = git(root, 'rev-parse', 'HEAD')
    verify_provenance(root, 'web', 'aura-app/dist')
    payload = source_payload(root)
    for name in output_files(root, 'aura-app/dist'):
        payload[name] = checked_bytes(root, name)
    native = 'aura-app/release/AURA Companion.app'
    include_native = (root / native).exists() if include_native is None else include_native
    native_signing = 'not_included'
    if include_native:
        if platform.system() != 'Darwin':
            raise ValueError('Native output must be verified on macOS')
        verify_provenance(root, 'native', native + '/Contents/Resources')
        subprocess.run(['codesign', '--verify', '--strict', str(root / native)], check=True, capture_output=True)
        signing = subprocess.run(['codesign', '-dv', '--verbose=4', str(root / native)], check=True, capture_output=True).stderr.decode()
        native_signing = 'ad_hoc' if 'Signature=adhoc' in signing else 'signed_identity_not_notarization_verified'
        for name in output_files(root, native):
            payload[name] = checked_bytes(root, name)
    manifest = {
        'format': 'aura-preview-manifest-v1', 'source_commit': source_commit,
        'scope': 'development_preview', 'platform': platform.system(),
        'native_signing': native_signing, 'notarization_verified': False,
        'hardware_acceptance': 'not_established_by_this_build',
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())},
    }
    manifest_data = (json.dumps(manifest, indent=2) + '\n').encode()
    out = root / 'aura-app/release'
    out.mkdir(exist_ok=True)
    if out.is_symlink():
        raise ValueError('Release directory must not be a symlink')
    archive = out / 'AURA-Companion-0.3.0-preview.zip'
    for path in (archive, archive.with_suffix('.zip.sha256'), out / 'release-manifest.json'):
        if path.is_symlink():
            raise ValueError('Release output must not be a symlink')
    # Validate everything before replacing any existing preview.
    with tempfile.TemporaryDirectory(dir=out) as folder:
        temporary = Path(folder) / archive.name
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo('AURA-Companion/' + name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (checked_file(root, name).stat().st_mode & 0xFFFF) << 16
                z.writestr(info, data)
            z.writestr('AURA-Companion/release-manifest.json', manifest_data)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(archive)
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
    (out / 'release-manifest.json').write_bytes(manifest_data)
    return archive


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--check-source']:
            source_payload()
            print('Tracked source privacy checks passed (not a comprehensive secret audit).')
        elif sys.argv[1:]:
            raise ValueError('Unknown packaging option')
        else:
            print(package())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Preview packaging refused: {error}') from None
